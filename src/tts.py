"""TTS 播报 — 根据 settings.json 自动分发到 VITS 或 HTTP"""
import logging

_log = logging.getLogger(__name__)

_vits_loaded = False
_http_loaded = False


def _resolve():
    import settings
    return settings.get("tts_backend")


def _ensure_vits():
    global _vits_loaded
    if _vits_loaded:
        return
    from vits_tts import load as vl
    vl()
    _vits_loaded = True
    _log.info("TTS backend: vits loaded")


def _ensure_http():
    global _http_loaded
    if _http_loaded:
        return
    from tts_http import load as hl
    hl()
    _http_loaded = True
    _log.info("TTS backend: http loaded")


def speak(text: str):
    if _resolve() == "http":
        _ensure_http()
        from tts_http import speak as s; s(text)
    else:
        _ensure_vits()
        from vits_tts import speak as s; s(text)


def wake_ack():
    if _resolve() == "http":
        _ensure_http()
        from tts_http import wake_ack as w; w()
    else:
        _ensure_vits()
        from vits_tts import wake_ack as w; w()


def wake_ack_sync():
    if _resolve() == "http":
        _ensure_http()
        from tts_http import wake_ack_sync as w; w()
    else:
        _ensure_vits()
        from vits_tts import wake_ack_sync as w; w()


def speak_sync(text: str):
    if _resolve() == "http":
        _ensure_http()
        from tts_http import speak_sync as s; s(text)
    else:
        _ensure_vits()
        from vits_tts import tts
        tts.speak_sync(text)


def load():
    if _resolve() == "http":
        _ensure_http()
    else:
        _ensure_vits()
