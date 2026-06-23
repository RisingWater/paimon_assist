"""TTS 工厂 — 根据 settings.json 分发到 VITS 或 HTTP"""
import logging
from pathlib import Path

from tts.vits_tts import VitsTTS
from tts.tts_http import HttpTTS

_log = logging.getLogger(__name__)

_vits = VitsTTS(
    checkpoint="models/paimon.pth",
    config="models/paimon_config.json",
    cache_dir=Path("models/tts_cache"),
)
_http = HttpTTS()


def _backend():
    from settings import settings
    return settings.get("tts_backend")


def _get():
    return _http if _backend() == "http" else _vits


def load():
    """加载全部 TTS 后端，支持运行时动态切换"""
    _vits.load()
    _http.load()
    # 注册 TTS 缓存（磁盘 WAV 缓存，启动时扫描大小）
    import memory_monitor
    import db as _db
    try:
        count = _db.cache_count()
        import os as _os
        total = 0
        cache_dir = _vits._cache.cache_dir
        if _os.path.isdir(cache_dir):
            for f in _os.listdir(cache_dir):
                try:
                    total += _os.path.getsize(_os.path.join(cache_dir, f))
                except Exception:
                    pass
        memory_monitor.register_component("TTS 缓存", f"{count} 条缓存，磁盘 {total/1024/1024:.1f}MB",
                                          size_bytes=total, category="TTS")
    except Exception:
        pass


def speak(text: str):
    _get().speak(text)


def wake_ack():
    _get().wake_ack()


def wake_ack_sync():
    _get().wake_ack_sync()


def speak_sync(text: str):
    _get().speak_sync(text)
