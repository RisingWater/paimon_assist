"""语音转文字（STT）— FunASR SenseVoiceSmall"""
import re
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from config import DISABLE_UPDATE

_model = None

# SenseVoice 特殊标签，表示无有效语音
_NOSPEECH_TAGS = re.compile(r"<\|nospeech\|>")
_TAG_PATTERN = re.compile(r"<\|[^|]+\|>")


def load():
    """加载 STT 模型（启动时调用一次）"""
    global _model
    print("Loading SenseVoiceSmall...", end=" ", flush=True)
    _model = AutoModel(
        model="models/iic/SenseVoiceSmall",
        device="cpu",
        disable_update=DISABLE_UPDATE,
    )
    print("Done")


def transcribe(wav_path: str) -> str:
    """识别音频文件，返回纯文本；无有效语音时返回空字符串"""
    result = _model.generate(
        input=wav_path,
        language="auto",      # 自动检测语种
        use_itn=True,          # 逆文本正则化（加标点、数字转写）
        batch_size_s=60,
    )
    if not result:
        return ""

    raw = result[0].get("text", "")
    # 无语音 → 直接返回空
    if _NOSPEECH_TAGS.search(raw):
        return ""

    # 用 FunASR 官方后处理清洗
    text = rich_transcription_postprocess(raw)
    # 兜底：去除残留标签
    text = _TAG_PATTERN.sub("", text).strip()
    return text
