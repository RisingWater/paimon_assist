"""唤醒词检测 + 音频收集"""
import logging
import os
import threading
import time
import wave

import numpy as np
from livekit.wakeword import WakeWordModel, WakeWordListener

from config import MODEL_PATH, THRESHOLD, DEBOUNCE

_log = logging.getLogger(__name__)

_TMP_DIR = "wakeword/.tmp"
SAMPLE_RATE = 16000

_last_audio_path: str | None = None
_lock = threading.Lock()


def _on_detection(name: str, score: float, timestamp: float, audio: np.ndarray, sr: int):
    """唤醒词检测回调 — 保存 2 秒音频到临时目录"""
    global _last_audio_path
    os.makedirs(_TMP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_TMP_DIR, f"{ts}_{score:.4f}.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    with _lock:
        _last_audio_path = path
    _log.info("Wake audio saved: %s", path)


def create_listener() -> WakeWordListener:
    """创建唤醒词监听器，带音频收集回调"""
    model = WakeWordModel(models=[MODEL_PATH])
    import memory_monitor
    memory_monitor.register_model("Paimon WakeWord (ONNX)", MODEL_PATH,
                                  "唤醒词检测，16kHz ONNX",
                                  category="模型")
    return WakeWordListener(
        model, threshold=THRESHOLD, debounce=DEBOUNCE,
        on_detection_callback=_on_detection,
    )


def get_last_audio_path() -> str | None:
    with _lock:
        return _last_audio_path


def classify_audio(category: str) -> str | None:
    """将最近一次唤醒音频移动到 positive/negative 目录"""
    global _last_audio_path
    with _lock:
        src = _last_audio_path
        _last_audio_path = None
    if not src or not os.path.isfile(src):
        return None
    dst_dir = f"wakeword/{category}"
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    try:
        os.rename(src, dst)
        _log.info("Wake audio classified as %s: %s", category, dst)
        return dst
    except OSError:
        return None
