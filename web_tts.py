"""TTS 播报 — 通过 HTTP 调用本地 TTS 服务"""
import threading
import requests
from config import TTS_URL, TTS_TEXT


def speak(text: str):
    """异步发送 TTS 请求（fire-and-forget）"""

    def _call():
        try:
            requests.post(TTS_URL, json={"text": text}, timeout=10)
        except Exception:
            pass

    threading.Thread(target=_call, daemon=True).start()


def wake_ack():
    """唤醒应答：播放"我在" """
    speak(TTS_TEXT)
