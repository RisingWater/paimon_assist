"""TTS 播报 — 根据 TTS_BACKEND 自动分发到 VITS 或 HTTP"""
import logging

_log = logging.getLogger(__name__)

_tts = None
_speak_fn = None
_wake_ack_fn = None
_wake_ack_sync_fn = None
_loaded = False


def _ensure_loaded():
    global _loaded, _tts, _speak_fn, _wake_ack_fn, _wake_ack_sync_fn
    if _loaded:
        return
    _loaded = True
    from vits_tts import tts as _vt, synthesize, speak as vs, wake_ack as va, wake_ack_sync as vas, load as vl
    vl()
    _tts = _vt
    _speak_fn = vs
    _wake_ack_fn = va
    _wake_ack_sync_fn = vas
    _log.info("TTS backend: vits loaded")


def _resolve():
    """动态读取当前 TTS 后端"""
    import settings
    return settings.get("tts_backend")


def speak(text: str):
    if _resolve() == "http":
        from tts_http import speak as s; s(text); return
    _ensure_loaded()
    _speak_fn(text)


def wake_ack():
    if _resolve() == "http":
        from tts_http import wake_ack as w; w(); return
    _ensure_loaded()
    _wake_ack_fn()


def wake_ack_sync():
    if _resolve() == "http":
        from tts_http import wake_ack_sync as w; w(); return
    _ensure_loaded()
    _wake_ack_sync_fn()


def speak_sync(text: str):
    if _resolve() == "http":
        from tts_http import speak_sync as s; s(text); return
    _ensure_loaded()
    # vits_tts 没有暴露 speak_sync，走 tts 对象
    from vits_tts import tts
    tts.speak_sync(text)


def load():
    if _resolve() == "http":
        from tts_http import load as l; l()
    else:
        _ensure_loaded()
