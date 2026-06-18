"""音频管理器 — 统一队列播放，支持同步/异步

- play_async(audio): 入队即返回（tool content 用）
- play_sync(audio):  入队，阻塞到自己的音频播完（wake_ack / 最终回复用）
- 有音频时保持 stream 打开，队列空后 2 秒关 stream
"""
import logging
import queue
import threading
import numpy as np
import pyaudio

_log = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, sample_rate: int = 22050, play_device: int | None = None):
        self.sample_rate = sample_rate
        self.play_device = play_device
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._done_events: dict[int, threading.Event] = {}  # id → event
        self._id_counter = 0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def play_async(self, audio: np.ndarray):
        """入队即返回"""
        self._queue.put(audio.tobytes())

    def play_sync(self, audio: np.ndarray):
        """入队，阻塞到该音频被播放完毕"""
        with self._lock:
            self._id_counter += 1
            chunk_id = self._id_counter
            event = threading.Event()
            self._done_events[chunk_id] = event
        self._queue.put((chunk_id, audio.tobytes()))
        event.wait()

    def stop(self):
        self._running = False
        self._queue.put(None)

    def _run(self):
        """后台线程：打开 stream，从队列取数据写入，队列空后关闭 stream"""
        import time as _time

        pa = pyaudio.PyAudio()
        stream = None

        while self._running:
            try:
                item = self._queue.get(timeout=2)
            except queue.Empty:
                # 2 秒空闲 → 关闭 stream
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
                    stream = None
                continue

            if item is None:
                break

            if stream is None:
                stream = pa.open(
                    format=pyaudio.paFloat32, channels=1,
                    rate=self.sample_rate, output=True,
                    output_device_index=self.play_device,
                )

            if isinstance(item, tuple):
                chunk_id, data = item
                stream.write(data)
                with self._lock:
                    if chunk_id in self._done_events:
                        self._done_events.pop(chunk_id).set()
            else:
                data = item
                stream.write(data)

        if stream is not None:
            stream.stop_stream()
            stream.close()
        pa.terminate()


# 全局单例
_manager: AudioManager | None = None


def init(sample_rate: int = 22050, play_device: int | None = None):
    global _manager
    if _manager is None:
        _manager = AudioManager(sample_rate, play_device)


def get() -> AudioManager:
    if _manager is None:
        init()
    return _manager
