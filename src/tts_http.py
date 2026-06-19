"""HTTP TTS 后端 — 调用外部 EasyVoice API 获取 WAV"""
import logging
import threading
import numpy as np
import requests
import soundfile as sf

from config import TTS_URL

_log = logging.getLogger(__name__)


synthesize = None
synthesize_async = None
speak = None
speak_sync = None
wake_ack = None
wake_ack_sync = None
SAMPLE_RATE = 22050


def load():
    """加载 HTTP TTS 后端（无需模型）"""
    global synthesize, speak, speak_sync, wake_ack, wake_ack_sync

    def _synthesize(text: str) -> np.ndarray:
        """调用 HTTP API 合成，返回 float32 numpy 数组"""
        resp = requests.post(
            TTS_URL,
            json={"text": text, "play": False},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        audio, sr = sf.read(data["file"], dtype="float32")
        return audio, sr

    def _synthesize_async(text: str):
        return _synthesize(text)[0]

    def _play(audio: np.ndarray, sr: int):
        import audio_manager
        audio_manager.get().play_sync(audio)

    def _speak(text: str):
        def _run():
            audio, sr = _synthesize(text)
            import audio_manager
            audio_manager.get().play_async(audio)
        threading.Thread(target=_run, daemon=True).start()

    def _speak_sync(text: str):
        audio, sr = _synthesize(text)
        _play(audio, sr)

    def _wake_ack():
        _speak("我在呢")

    def _wake_ack_sync():
        _speak_sync("我在呢")

    synthesize = _synthesize
    synthesize_async = _synthesize_async
    speak = _speak
    speak_sync = _speak_sync
    wake_ack = _wake_ack
    wake_ack_sync = _wake_ack_sync
    _log.info("HTTP TTS backend ready: %s", TTS_URL)
