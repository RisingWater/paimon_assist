"""唤醒词检测"""
import livekit.wakeword.inference.listener as _listener_mod
from livekit.wakeword import WakeWordModel, WakeWordListener
from config import MODEL_PATH, THRESHOLD, DEBOUNCE

# 调整检测帧率（默认 80ms/帧，调大降低 CPU）
FRAME_MS = 200  # 每帧毫秒数
_listener_mod.FRAME_SAMPLES = int(16000 * (FRAME_MS / 1000))    # 3200 samples
_listener_mod.CHUNK_FRAMES = max(1, int(2000 / FRAME_MS))       # 10 frames = 2s window


def create_listener() -> WakeWordListener:
    """创建唤醒词监听器（同步加载模型，调用一次即可）"""
    model = WakeWordModel(models=[MODEL_PATH])
    return WakeWordListener(model, threshold=THRESHOLD, debounce=DEBOUNCE)
