"""语音转文字（STT）— FunASR SenseVoiceSmall"""
import re
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from config import DISABLE_UPDATE


class STT:
    """FunASR SenseVoiceSmall 语音转文字引擎"""

    def __init__(self, model_path: str = "models/iic/SenseVoiceSmall"):
        self.model_path = model_path
        self._model = None

    def load(self):
        """加载 STT 模型（启动时调用一次）"""
        print("Loading SenseVoiceSmall...", end=" ", flush=True)
        self._model = AutoModel(
            model=self.model_path,
            device="cpu",
            disable_update=DISABLE_UPDATE,
        )
        print("Done")

    def transcribe(self, wav_path: str) -> str:
        """识别音频文件，返回纯文本；无有效语音时返回空字符串"""
        if self._model is None:
            self.load()

        result = self._model.generate(
            input=wav_path,
            language="auto",
            use_itn=True,
            batch_size_s=60,
        )
        if not result:
            return ""

        raw = result[0].get("text", "")
        if _NOSPEECH_TAGS.search(raw):
            return ""

        text = rich_transcription_postprocess(raw)
        text = _TAG_PATTERN.sub("", text).strip()
        return text


# SenseVoice 特殊标签
_NOSPEECH_TAGS = re.compile(r"<\|nospeech\|>")
_TAG_PATTERN = re.compile(r"<\|[^|]+\|>")


# 模块级单例（向后兼容）
stt = STT()
load = stt.load
transcribe = stt.transcribe
