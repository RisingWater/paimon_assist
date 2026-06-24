"""LLM 对话 — DeepSeek API，按 user_id 管理独立对话历史，支持 Tool Calling"""
import gc
import json
import logging
import os
from datetime import datetime, timedelta
import requests
import threading
from config import cfg
import db
from llm_tools import tools
import llm_tools.memory as _mem_mod
import tts as _tts_mod
from settings import settings
from memory_monitor import MemoryTracked

_log = logging.getLogger(__name__)

_DEFAULT_RULES_PREFIX = (
    "你是派萌，一个可爱的AI助手。你的回答会通过语音播放给用户听。"
    "每条用户消息前会标注说话人的名字，你可以根据名字来称呼对方。"
    "规则："
    "0. 【最高优先级】判断用户输入是否值得回复。必须严格执行：\n"
    "   以下情况直接回复 __SKIP__（只回复这三个词，不要多说）：\n"
    "   - 单个字、语气词（嗯、啊、哦、哈、唉）\n"
    "   - 闲聊寒暄、自言自语、不是对你说的对话\n"
    "   - 语法不通、乱码、语音识别错误导致的无意义文本\n"
    "   - 模糊的碎片（比如只说'那个…'、'就是…'）\n"
    "   - 非指令性的陈述句（比如'今天好热'、'我饿了'）\n"
    "   ⚠️ 宁可错杀不可放过。拿不准的时候直接 __SKIP__，不要追问"
    "1. 不要使用任何emoji、颜文字、特殊符号 "
    "2. 不要使用markdown格式 "
    "3. 用中文回答，语气活泼可爱 "
    "4. 回复尽量简短在1-2句话内 "
    "5. 使用口语化的表达方式 "
    "6. 数字用中文写（二十五而不是25），语音模型无法念阿拉伯数字 "
    "7. 如果用户询问天气但没有指定城市，默认查询"
    f" {cfg.DEFAULT_CITY} 的天气。使用 get_weather 工具，date 参数用 today 或 tomorrow。"
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
    "15. 用户要打游戏、开PS5时，调 control_ps5 power=true。"
    "不想玩了、关PS5时，调 control_ps5 power=false。"
    "16. 当设备名或参数不明确、记忆也无法确定时，"
    "或者一定需要收集额外信息才能回答问题，用 ask_question_to_user 询问用户。"
    "每次对话最多用一次，能自行推断就不要问。"
)


class LLM(MemoryTracked):
    """DeepSeek LLM 对话引擎（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        super().__init__("LLM 对话引擎", "DeepSeek API + Tool Calling，按 user_id 隔离历史", category="LLM")

    # ---- 公开接口 ----

    def chat(self, user_text: str, user_id: int = 0, speaker: str = "") -> str:
        """发送消息到 DeepSeek，返回回复文本。支持自动 tool calling。"""
        history = self._get_history(user_id)

        content = f"[说话人: {speaker}] {user_text}" if speaker else user_text
        history.append({"role": "user", "content": content})
        if user_id:
            db.append_message(user_id, "user", content)

        try:
            tool_schemas = tools.get_schemas()
            tool_prefix = ""
            all_tool_names: list[str] = []

            for _round in range(5):
                data = self._call_api(history, tool_schemas)
                choice = data["choices"][0]
                msg = choice["message"]
                _log.info("LLM finish_reason=%s content=%s tool_calls=%s",
                    choice.get("finish_reason", "?"),
                    (msg.get("content") or "")[:50],
                    [tc["function"]["name"] for tc in (msg.get("tool_calls") or [])],
                )

                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    break

                content = (msg.get("content") or "").strip()
                if content and not tool_prefix:
                    tool_prefix = content

                if user_id:
                    db.append_message(user_id, "assistant", json.dumps(msg, ensure_ascii=False))
                if tool_prefix:
                    silent_tools = self._load_silent_tools()
                    should_play = all(
                        tc["function"]["name"] not in silent_tools for tc in tool_calls
                    )
                    if should_play:
                        try:
                            _tts_mod.speak(tool_prefix)
                        except Exception:
                            pass
                    tool_prefix = ""
                history.append(msg)

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    all_tool_names.append(fn_name)
                    fn_args = json.loads(tc["function"]["arguments"])
                    _log.info("Tool call: %s(%s)", fn_name, fn_args)
                    result = tools.execute(fn_name, fn_args)
                    _log.info("Tool result: %s", result[:200] if result else "(empty)")

                    if tools.is_final(fn_name):
                        is_error = "失败" in result or "错误" in result
                        if not is_error:
                            if user_id:
                                db.append_message(user_id, "assistant", result)
                            history.append({"role": "assistant", "content": result})
                            return result

                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                    history.append(tool_msg)
                    if user_id:
                        db.append_message(user_id, "tool", json.dumps(tool_msg, ensure_ascii=False))

            reply = msg.get("content", "")
            if reply == "__SKIP__":
                if user_id:
                    rows = db.load_history(user_id)
                    if rows:
                        db.delete_message(rows[-1]["id"])
                return "__SKIP__"
            if reply:
                history.append({"role": "assistant", "content": reply})
                if user_id:
                    db.append_message(user_id, "assistant", reply)

            if user_id:
                self._log_to_midterm(user_id, all_tool_names, user_text, reply or "")

            gc.collect()
            return reply or "（无回复）"
        except Exception as e:
            _log.error("LLM chat error: %s", e)
            return ""

    # ---- 内部 ----

    @staticmethod
    def _load_silent_tools() -> set[str]:
        return tools.get_default_silent_tools() | settings.get_silent_tools()

    @staticmethod
    def _build_system() -> dict:
        now = datetime.now().strftime("现在是%Y年%m月%d日 %A %H:%M。")
        content = now + _DEFAULT_RULES_PREFIX
        if _mem_mod._mgr.memory_summary:
            content += f"\n[长期记忆] {_mem_mod._mgr.memory_summary}"
        return {"role": "system", "content": content}

    @staticmethod
    def _get_history(user_id: int) -> list[dict]:
        system = LLM._build_system()
        rows = db.load_history(user_id)
        if not rows:
            db.append_message(user_id, "system", system["content"])
            return [system]

        cutoff = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        rows = [r for r in rows if r.get("created_at", "") >= cutoff]

        messages = [system]
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

    @staticmethod
    def _log_to_midterm(user_id: int, tool_calls_during_chat: list[str], user_text: str, reply: str):
        if user_id <= 0:
            return
        for name in tool_calls_during_chat:
            if tools.get_memory_value(name) == 0:
                return
        ts = datetime.now().strftime("%m-%d %H:%M")
        _mem_mod.append_to_midterm(user_id, f"[{ts}] 问：{user_text} | 答：{reply[:200]}")

    @staticmethod
    def _call_api(messages: list[dict], tools: list[dict] | None = None) -> dict:
        body = {
            "model": cfg.DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.7,
        }
        if tools:
            body["tools"] = tools

        resp = requests.post(
            cfg.DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )
        if resp.status_code != 200:
            _log.error("DeepSeek API %d: %s", resp.status_code, resp.text[:500])
            raise RuntimeError(f"API error: {resp.status_code}")
        return resp.json()


# 全局单例
llm = LLM()
