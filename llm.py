"""LLM 对话 — DeepSeek API，按 user_id 管理独立对话历史"""
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_URL, DEEPSEEK_MODEL

_SYSTEM = {
    "role": "system",
    "content": (
        "你是派萌，一个可爱的AI助手。你的回答会通过语音播放给用户听。"
        "每条用户消息前会标注说话人的名字，你可以根据名字来称呼对方。"
        "规则："
        "1. 不要使用任何emoji、颜文字、特殊符号 "
        "2. 不要使用markdown格式 "
        "3. 用中文回答，语气活泼可爱 "
        "4. 回复尽量简短在1-2句话内 "
        "5. 使用口语化的表达方式。"
    ),
}

# user_id → conversation history
_histories: dict[int, list[dict]] = {}


def _get_history(user_id: int) -> list[dict]:
    if user_id not in _histories:
        _histories[user_id] = [_SYSTEM]
    return _histories[user_id]


def chat(user_text: str, user_id: int = 0, speaker: str = "") -> str:
    """发送消息到 DeepSeek，返回回复文本。

    Args:
        user_text: 用户说的话
        user_id: 声纹匹配到的用户 ID（0 = 陌生人/未识别）
        speaker: 用户的名字
    """
    history = _get_history(user_id)

    content = f"[说话人: {speaker}] {user_text}" if speaker else user_text
    history.append({"role": "user", "content": content})

    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": history,
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            history.append({"role": "assistant", "content": reply})
            return reply
        return f"API error: {resp.status_code}"
    except Exception as e:
        return f"Request failed: {e}"
