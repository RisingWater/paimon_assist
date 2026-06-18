"""反问用户工具 — 信息不足时向用户提问"""
import logging
from llm_tools import register

_log = logging.getLogger(__name__)


@register(
    name="ask_question_to_user",
    description=(
        "向用户提问以获取关键信息。仅限以下场景使用："
        "1) 用户要求控制设备但没说具体设备名或参数（如'开空调'但未指定温度和房间）；"
        "2) 记忆和上下文都无法确定用户意图，且不询问就无法继续操作；"
        "不要用于闲聊、确认无关细节、或可以自行推断的情况。"
        "每次对话最多调用一次。如果用户无回复则放弃。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要问用户的问题，如'想设置多少度呢？'、'要控制哪台空调？客厅还是主卧？'",
            }
        },
        "required": ["question"],
    },
    memory_value=0,
)
def ask_question_to_user(args: dict) -> str:
    question = args.get("question", "").strip()
    if not question:
        return "未提供问题"

    try:
        # 1. 播放问题
        from vits_tts import tts as _tts
        _tts.speak_sync(question)

        # 2. 录音
        import vad
        filename = vad.record(999)  # counter=999 标记为反问录音

        # 3. STT
        from stt import stt
        text = stt.transcribe(filename)
        if not text.strip():
            return "用户无回复"

        return f"用户回复：{text.strip()}"
    except Exception as e:
        return f"反问失败：{e}"
