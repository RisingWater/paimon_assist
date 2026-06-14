"""TTS 播报 — 根据 TTS_BACKEND 自动分发到 VITS 或 Web TTS"""
from config import TTS_BACKEND

if TTS_BACKEND == "web":
    from web_tts import speak, wake_ack

    def load():
        pass  # Web TTS 无需加载模型
else:
    from vits_tts import speak, wake_ack, load
