"""HTTP TTS 后端 — 调用外部 EasyVoice API 获取 WAV"""
import logging
import threading
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
import audio_manager

from config import TTS_URL, TTS_CACHE_DIR
from tts_cache import TTSCache

_log = logging.getLogger(__name__)

_cache = TTSCache(Path(TTS_CACHE_DIR))


def _synthesize(text: str) -> tuple[np.ndarray, int]:
    """调用 HTTP API 合成（带缓存），返回 (audio, sr)"""
    cached = _cache.get(text, "http")
    if cached is not None:
        audio, sr = sf.read(str(cached), dtype="float32")
        return audio, sr

    resp = requests.post(
        TTS_URL,
        json={"text": text, "play": False},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    audio, sr = sf.read(data["file"], dtype="float32")
    _cache.save(text, audio, sr, "http")
    return audio, sr


def speak(text: str):
    def _run():
        audio, sr = _synthesize(text)
        audio_manager.get().play_async(audio, sr)
    threading.Thread(target=_run, daemon=True).start()


def speak_sync(text: str):
    audio, sr = _synthesize(text)
    audio_manager.get().play_sync(audio, sr)


def wake_ack():
    speak("我在呢")


def wake_ack_sync():
    speak_sync("我在呢")


def load():
    _log.info("HTTP TTS backend ready: %s", TTS_URL)
