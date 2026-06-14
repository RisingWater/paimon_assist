"""声纹提取与验证"""
import numpy as np
from config import VOICEPRINT_MODEL, VOICEPRINT_THRESHOLD
import db

_model = None


def _load_model():
    """延迟加载声纹模型"""
    global _model
    if _model is None:
        from pyannote.audio import Model

        print("  Loading voiceprint model...", end=" ", flush=True)
        _model = Model.from_pretrained(VOICEPRINT_MODEL)
        print("Done")
    return _model


def extract(wav_path: str) -> np.ndarray:
    """从音频提取 512 维声纹向量"""
    import torch
    import scipy.io.wavfile as wavfile

    model = _load_model()
    sr, audio = wavfile.read(wav_path)
    # int16 → float32 [-1, 1]
    audio = audio.astype(np.float32) / 32768.0
    # 立体声 → 单声道
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    # (batch=1, channel=1, samples)
    waveform = torch.from_numpy(audio).view(1, 1, -1)
    embedding = model(waveform)
    return embedding[0].detach().cpu().numpy()


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
