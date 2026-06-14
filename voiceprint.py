"""声纹提取与验证 — ModelScope 中文声纹模型"""
import numpy as np
from config import VOICEPRINT_MODEL, VOICEPRINT_THRESHOLD
import db

_pipeline = None


def load():
    """预加载声纹模型（启动时调用一次）"""
    global _pipeline
    if _pipeline is not None:
        return
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks

    print("Loading voiceprint model...", end=" ", flush=True)
    _pipeline = pipeline(
        task=Tasks.speaker_verification,
        model=VOICEPRINT_MODEL,
    )
    print("Done")


def extract(wav_path: str) -> np.ndarray:
    """从音频提取声纹向量"""
    # pipeline 需要一对音频来提取 embedding
    result = _pipeline([wav_path, wav_path], output_emb=True)
    return np.array(result["embs"][0])


def verify(wav_path: str) -> "tuple[bool, str]":
    """
    声纹验证（持续注册模式）。
    - 数据库为空 → 注册，名字留空
    - 最匹配声纹 >= 阈值 → 识别为该用户
    - 最匹配声纹 < 阈值 → 自动注册，名字留空
    始终返回 (True, 信息字符串)。名字为空表示尚未命名。
    """
    emb = extract(wav_path)

    # 首次运行
    if db.count() == 0:
        db.enroll("", emb, audio_path=wav_path)
        return True, "enrolled:"

    name, sim = db.find_best(emb)
    if name and sim >= VOICEPRINT_THRESHOLD:
        return True, f"{name}:{sim:.4f}"

    # 未匹配 → 自动注册，名字留空
    db.enroll("", emb, audio_path=wav_path)
    return True, "enrolled:"
