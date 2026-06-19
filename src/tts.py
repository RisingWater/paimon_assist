"""TTS 播报 — 根据 settings.json 自动分发到 VITS 或 HTTP"""
import logging
from vits_tts import tts as _vits, speak as _vs, wake_ack as _va, wake_ack_sync as _vas, load as _vl
from tts_http import speak as _hs, wake_ack as _ha, wake_ack_sync as _has, load as _hl

_log = logging.getLogger(__name__)


def _backend():
    import settings
    return settings.get("tts_backend")


def load():
    _vl()
    _hl()
    _log.info("Both TTS backends loaded")


def speak(text: str):
    _hs(text) if _backend() == "http" else _vs(text)


def wake_ack():
    _ha() if _backend() == "http" else _va()


def wake_ack_sync():
    _has() if _backend() == "http" else _vas()


def speak_sync(text: str):
    if _backend() == "http":
        _hs(text)
    else:
        _vits.speak_sync(text)
