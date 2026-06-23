"""HTTP TTS 后端 — 调用外部 EasyVoice API"""
import logging
import threading
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from tts import audio_manager

from config import TTS_URL, TTS_CACHE_DIR
from tts.cache import TTSCache

_log = logging.getLogger(__name__)


class HttpTTS:
    def __init__(self):
        self.cache = TTSCache(Path(TTS_CACHE_DIR))

    def load(self):
        import memory_monitor
        memory_monitor.register_component("HTTP TTS (EasyVoice)", "远程语音合成，无本地模型",
                                          size_bytes=0, category="TTS")
        _log.info("HTTP TTS ready: %s", TTS_URL)

    def synthesize(self, text: str, length_scale: float = 1.0) -> tuple[np.ndarray, int]:
        cached = self.cache.get(text, "http")
        if cached is not None:
            return sf.read(str(cached), dtype="float32")

        payload = {
            "data": [{"text": text, "voice": "zh-CN-XiaoxiaoNeural", "rate": "0%", "pitch": "0Hz", "volume": "0%"}]
        }
        resp = requests.post(TTS_URL, json=payload, timeout=30)
        resp.raise_for_status()

        # MP3 → WAV 转换（PyAudio 需要 PCM）
        import tempfile, subprocess, os
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(resp.content)
            mp3_path = tmp.name
        wav_path = mp3_path + ".wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-f", "wav", wav_path],
            capture_output=True,
        )
        audio, sr = sf.read(wav_path, dtype="float32")
        os.unlink(mp3_path)
        os.unlink(wav_path)

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
