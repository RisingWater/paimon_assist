"""LLM 对话 — DeepSeek API，按 user_id 管理独立对话历史，持久化到 SQLite，支持 Tool Calling"""
import json
import logging
import os
from datetime import datetime, timedelta
import requests
import threading
from config import DEEPSEEK_API_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL, DEFAULT_CITY
import db
import llm_tools
import llm_tools.memory as _mem_mod
from llm_tools import get_memory_value
from vits_tts import tts as _tts_module
import settings

_log = logging.getLogger(__name__)

def _load_silent_tools() -> set[str]:
    return settings.get_silent_tools()

_DEFAULT_RULES_PREFIX = (
    "你是派萌，一个可爱的AI助手。你的回答会通过语音播放给用户听。"
    "每条用户消息前会标注说话人的名字，你可以根据名字来称呼对方。"
    "规则："
    "1. 不要使用任何emoji、颜文字、特殊符号 "
    "2. 不要使用markdown格式 "
    "3. 用中文回答，语气活泼可爱 "
    "4. 回复尽量简短在1-2句话内 "
    "5. 使用口语化的表达方式 "
    "5.1 如果用户说的话明显不是在对你说（无意义噪音、背景闲聊、STT误识别），"
    "回复 __SKIP__ 即可，不要过度解读。"
    "6. 数字用中文写（二十五而不是25），语音模型无法念阿拉伯数字 "
    "7. 如果用户询问天气但没有指定城市，默认查询"
    f" {DEFAULT_CITY} 的天气。使用 get_weather 工具，date 参数用 today 或 tomorrow。"
    "8. 如果用户询问煜乔的位置、在哪里、定位，使用 get_yuqiao_location 工具；"
    "如果询问煜乔的通话器电量、还剩多少电，使用 get_yuqiao_power 工具。"
    "9. web_search 仅用于查询最新消息、实时数据、新闻事件等超出你知识范围的内容。"
    "常识、历史、科学等已知知识不要搜索。调用前先自然地告诉用户你要查一下。"
    "10. 控制空调前必须先调 list_ac 获取最新状态和空调名称，"
    "再根据名称匹配调 control_ac。不要用历史记录里的名字。"
    "模式支持 cool/heat/auto/dry/fan_only，设温度默认制冷。"
    "11. 控制电视前先调 get_tv_state 查状态，再调 control_tv（开=退出音响模式，关=进入音响模式）。"
    "12. 回答涉及用户身份、偏好、房间归属时，先调 read_memory 查记忆。"
    "了解到新信息（如'王旭住主卧'）后调 save_memory 记录。"
    "13. 用户要求定时提醒/定时任务时，用 add_reminder 添加。"
    "查看/删除提醒用 list_reminders/delete_reminder。"
    "14. 调节音量用 get_volume/set_volume，参数是百分比数字，最大可以到200%。"
    "15. 当设备名或参数不明确、记忆也无法确定时，"
    "或者一定需要收集额外信息才能回答问题，用 ask_question_to_user 询问用户。"
    "每次对话最多用一次，能自行推断就不要问。"
)

def _build_system() -> dict:
    """构建带当前时间和记忆摘要的 system prompt"""
    now = datetime.now().strftime("现在是%Y年%m月%d日 %A %H:%M。")
    content = now + _DEFAULT_RULES_PREFIX
    # 附加长期记忆摘要（动态读取，避免 import 缓存旧值）
    if _mem_mod.memory_summary:
        content += f"\n[长期记忆] {_mem_mod.memory_summary}"
    return {"role": "system", "content": content}


def _get_history(user_id: int) -> list[dict]:
    """从 DB 加载 5 分钟内的对话历史，超出部分交给中期记忆"""
    system = _build_system()
    rows = db.load_history(user_id)
    if not rows:
        db.append_message(user_id, "system", system["content"])
        return [system]

    # 只取最近 5 分钟的消息
    cutoff = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    rows = [r for r in rows if r.get("created_at", "") >= cutoff]

    messages = [system]

    # 附加中期记忆摘要（动态读取，避免 import 缓存旧值）
    mid = _mem_mod.get_midterm_summary(user_id)
    if mid:
        messages.append({"role": "system", "content": f"[近期回顾] {mid}"})

    for r in rows:
        if r["role"] == "system":
            continue
        content = r["content"]
        if content.startswith("{") and content.endswith("}"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "role" in parsed:
                    messages.append(parsed)
                    continue
            except (json.JSONDecodeError, TypeError):
                pass
        messages.append({"role": r["role"], "content": content})
    return messages


def _log_to_midterm(user_id: int, tool_calls_during_chat: list[str], user_text: str, reply: str):
    """规则：如果本轮对话沾了 memory_value=0 的 tool，整轮不进中期记忆"""
    if user_id <= 0:
        return
    for name in tool_calls_during_chat:
        if get_memory_value(name) == 0:
            return  # 有低价值 tool → 整轮丢弃

    # 纯聊天或高价值 tool → 记入中期记忆
    ts = datetime.now().strftime("%m-%d %H:%M")
    _mem_mod.append_to_midterm(user_id, f"[{ts}] 问：{user_text} | 答：{reply[:200]}")


def _call_api(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """调用 DeepSeek API，返回完整响应 JSON"""
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "max_tokens": 200,
        "temperature": 0.7,
    }
    if tools:
        body["tools"] = tools

    resp = requests.post(
        DEEPSEEK_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=15,
    )
    if resp.status_code != 200:
        _log.error("DeepSeek API %d: %s", resp.status_code, resp.text[:500])
        raise RuntimeError(f"API error: {resp.status_code}")
    return resp.json()


def chat(user_text: str, user_id: int = 0, speaker: str = "") -> str:
    """发送消息到 DeepSeek，返回回复文本。支持自动 tool calling。

    Args:
        user_text: 用户说的话
        user_id: 声纹匹配到的用户 ID（0 = 陌生人/未识别）
        speaker: 用户的名字
    """
    history = _get_history(user_id)

    content = f"[说话人: {speaker}] {user_text}" if speaker else user_text
    history.append({"role": "user", "content": content})
    if user_id:
        db.append_message(user_id, "user", content)

    try:
        tools = llm_tools.get_schemas()
        tool_prefix = ""

        # 记录本轮涉及的所有 tool 名称（用于判断记忆价值）
        all_tool_names: list[str] = []

        # 多轮 tool call 循环：列表→控制这样的连续调用
        for _round in range(5):  # 最多 5 轮，防止死循环
            data = _call_api(history, tools)
            choice = data["choices"][0]
            msg = choice["message"]
            _log.info("LLM finish_reason=%s content=%s tool_calls=%s",
                choice.get("finish_reason", "?"),
                (msg.get("content") or "")[:50],
                [tc["function"]["name"] for tc in (msg.get("tool_calls") or [])],
            )

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                # 没有 tool call，回复就是最终内容
                break

            # 保存友好提示语（第一轮的 content）
            content = (msg.get("content") or "").strip()
            if content and not tool_prefix:
                tool_prefix = content

            if user_id:
                db.append_message(user_id, "assistant", json.dumps(msg, ensure_ascii=False))
            if tool_prefix:
                # 从配置文件加载静默工具列表
                silent_tools = _load_silent_tools()
                should_play = all(
                    tc["function"]["name"] not in silent_tools
                    for tc in tool_calls
                )
                if should_play:
                    try:
                        _tts_module.speak(tool_prefix)
                    except Exception:
                        pass
                tool_prefix = ""  # 只处理一次
            history.append(msg)

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                all_tool_names.append(fn_name)
                fn_args = json.loads(tc["function"]["arguments"])
                _log.info("Tool call: %s(%s)", fn_name, fn_args)
                result = llm_tools.execute(fn_name, fn_args)
                _log.info("Tool result: %s", result[:200] if result else "(empty)")
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
                history.append(tool_msg)
                if user_id:
                    db.append_message(user_id, "tool", json.dumps(tool_msg, ensure_ascii=False))

        reply = msg.get("content", "")
        if reply:
            history.append({"role": "assistant", "content": reply})
            if user_id:
                db.append_message(user_id, "assistant", reply)

        # 简单规则记入中期记忆
        if user_id:
            _log_to_midterm(user_id, all_tool_names, user_text, reply or "")

        return reply or "（无回复）"
    except Exception as e:
        _log.error("LLM chat error: %s", e)
        return ""
