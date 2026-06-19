"""TTS 工厂 — 根据 settings.json 分发到 VITS 或 HTTP"""
import logging
from pathlib import Path

from vits_tts import VitsTTS
from tts_http import HttpTTS

_log = logging.getLogger(__name__)

_vits = VitsTTS(
    checkpoint="models/paimon.pth",
    config="models/paimon_config.json",
    cache_dir=Path("models/tts_cache"),
)
_http = HttpTTS()


def _backend():
    import settings
    return settings.get("tts_backend")


def _get():
    return _http if _backend() == "http" else _vits


def load():
    _vits.load()
    _http.load()


def speak(text: str):
    _get().speak(text)


def wake_ack():
    _get().wake_ack()


def wake_ack_sync():
    _get().wake_ack_sync()


def speak_sync(text: str):
    _get().speak_sync(text)
