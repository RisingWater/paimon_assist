"""LLM 对话 — DeepSeek API，按 user_id 管理独立对话历史，持久化到 SQLite，支持 Tool Calling"""
import json
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL, DEFAULT_CITY
import db
import llm_tools

_DEFAULT_RULES = (
    "你是派萌，一个可爱的AI助手。你的回答会通过语音播放给用户听。"
    "每条用户消息前会标注说话人的名字，你可以根据名字来称呼对方。"
    "规则："
    "1. 不要使用任何emoji、颜文字、特殊符号 "
    "2. 不要使用markdown格式 "
    "3. 用中文回答，语气活泼可爱 "
    "4. 回复尽量简短在1-2句话内 "
    "5. 使用口语化的表达方式 "
    "6. 数字用中文写（二十五而不是25），语音模型无法念阿拉伯数字 "
    "7. 如果用户询问天气但没有指定城市，默认查询"
    f" {DEFAULT_CITY} 的天气。使用 get_weather 工具，date 参数用 today 或 tomorrow。"
    "8. 如果用户询问煜乔的位置、在哪里、定位，使用 get_yuqiao_location 工具；"
    "如果询问煜乔的通话器电量、还剩多少电，使用 get_yuqiao_power 工具。"
)

_SYSTEM = {"role": "system", "content": _DEFAULT_RULES}


def _get_history(user_id: int) -> list[dict]:
    """从 DB 加载对话历史，始终使用最新的 system prompt"""
    rows = db.load_history(user_id)
    if not rows:
        db.append_message(user_id, "system", _SYSTEM["content"])
        return [_SYSTEM]
    # 跳过 DB 中旧的 system prompt，始终用当前版本
    return [_SYSTEM] + [
        {"role": r["role"], "content": r["content"]}
        for r in rows
        if r["role"] != "system"
    ]


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
        data = _call_api(history, tools)
        choice = data["choices"][0]
        msg = choice["message"]

        # 处理 tool calls
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            if user_id:
                db.append_message(user_id, "assistant", json.dumps(msg, ensure_ascii=False))
            history.append(msg)

            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                result = llm_tools.execute(fn_name, fn_args)
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
                history.append(tool_msg)
                if user_id:
                    db.append_message(user_id, "tool", json.dumps(tool_msg, ensure_ascii=False))

            # 让模型基于 tool 结果生成最终回复
            data = _call_api(history, tools)
            choice = data["choices"][0]
            msg = choice["message"]

        reply = msg.get("content", "")
        if reply:
            history.append({"role": "assistant", "content": reply})
            if user_id:
                db.append_message(user_id, "assistant", reply)
        return reply or "（无回复）"
    except Exception as e:
        import traceback
        return f"Request failed: {e}\n{traceback.format_exc()}"
