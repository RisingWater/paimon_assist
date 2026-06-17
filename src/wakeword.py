"""唤醒词检测"""
from livekit.wakeword import WakeWordModel, WakeWordListener
from config import MODEL_PATH, THRESHOLD, DEBOUNCE


def create_listener() -> WakeWordListener:
    """创建唤醒词监听器（同步加载模型，调用一次即可）"""
    model = WakeWordModel(models=[MODEL_PATH])
    return WakeWordListener(model, threshold=THRESHOLD, debounce=DEBOUNCE)
