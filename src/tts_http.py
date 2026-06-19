"""HTTP TTS 后端 — 调用外部 EasyVoice API"""
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


class HttpTTS:
    def __init__(self):
        self.cache = TTSCache(Path(TTS_CACHE_DIR))

    def load(self):
        _log.info("HTTP TTS ready: %s", TTS_URL)

    def synthesize(self, text: str, length_scale: float = 1.0) -> tuple[np.ndarray, int]:
        cached = self.cache.get(text, "http")
        if cached is not None:
            return sf.read(str(cached), dtype="float32")
        resp = requests.post(TTS_URL, json={"text": text, "play": False}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        audio, sr = sf.read(data["file"], dtype="float32")
        self.cache.save(text, audio, sr, "http")
        return audio, sr

    def speak(self, text: str):
        def _run():
            audio, sr = self.synthesize(text)
            audio_manager.get().play_async(audio, sr)
        threading.Thread(target=_run, daemon=True).start()

    def speak_sync(self, text: str):
        audio, sr = self.synthesize(text)
        audio_manager.get().play_sync(audio, sr)

    def wake_ack(self):
        self.speak("我在呢")

    def wake_ack_sync(self):
        self.speak_sync("我在呢")
