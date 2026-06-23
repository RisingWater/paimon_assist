"""反问用户工具 — 信息不足时向用户提问"""
import logging
from llm_tools import BaseTool, tools
import tts
import vad
from stt import stt

_log = logging.getLogger(__name__)


class AskUserTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="ask_question_to_user",
            description=(
                "向用户提问以获取关键信息。仅限以下场景使用："
                "1) 用户要求控制设备但没说具体设备名或参数；"
                "2) 记忆和上下文都无法确定用户意图，且不询问就无法继续操作；"
                "不要用于闲聊、确认无关细节、或可以自行推断的情况。"
                "每次对话最多调用一次。如果用户无回复则放弃。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要问用户的问题，如'想设置多少度呢？'"},
                },
                "required": ["question"],
            },
            memory_value=0,
        )

    def execute(self, args: dict) -> str:
        question = args.get("question", "").strip()
        if not question:
            return "未提供问题"
        try:
            tts.speak_sync(question)
            filename = vad.record(999)
            text = stt.transcribe(filename)
            if not text.strip():
                return "用户无回复"
            return f"用户回复：{text.strip()}"
        except Exception as e:
            return f"反问失败：{e}"


tools.register(AskUserTool())
