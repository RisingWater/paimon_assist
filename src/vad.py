"""VAD 录音 — 检测到静音后自动停止，委托给 AudioManager"""
import logging
import os
import time
import wave
from tts import audio_manager
from config import config

_log = logging.getLogger(__name__)
RECORDINGS_DIR = "recordings"


def record(counter: int) -> str:
    """
    录音直到检测到静音，保存为 WAV 文件。
    返回文件名。
    """
    _log.info("Recording...")
    audio = audio_manager.get().record(config.MAX_RECORD_SECONDS, config.VAD_SILENCE_MS)

    all_audio = (audio * 32768.0).astype("<i2")
    duration = len(all_audio) / audio_manager.RECORD_SAMPLE_RATE
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    filename = f"{RECORDINGS_DIR}/recording_{time.strftime('%Y%m%d_%H%M%S')}_{counter}.wav"

    wf = wave.open(filename, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(audio_manager.RECORD_SAMPLE_RATE)
    wf.writeframes(all_audio.tobytes())
    wf.close()

    _log.info("Recorded %.1fs", duration)
    return filename
