"""音频管理器 — 统一播放/录音，其他模块不直接操作 pyaudio

播放:
  - play_async(audio): 入队即返回
  - play_sync(audio):  入队，阻塞到自己的音频播完
录音:
  - record(timeout_sec) → np.ndarray, sample_rate
"""
import logging
import queue
import threading
import numpy as np
import pyaudio

_log = logging.getLogger(__name__)

RECORD_SAMPLE_RATE = 16000  # VAD/STT 用 16kHz


class AudioManager:
    def __init__(self, play_sample_rate: int = 22050, play_device: int | None = None):
        self.play_sample_rate = play_sample_rate
        self.play_device = play_device
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._done_events: dict[int, threading.Event] = {}
        self._id_counter = 0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    # ---- 播放 ----

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

    # ---- 录音 ----

    def record(self, timeout_sec: int, silence_ms: int = 800) -> np.ndarray:
        """录音，静音自动停止，返回 (audio, sample_rate)"""
        from silero_vad import load_silero_vad, get_speech_timestamps

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16, channels=1,
            rate=RECORD_SAMPLE_RATE, input=True,
            frames_per_buffer=512,
        )

        frames = []
        max_frames = int(RECORD_SAMPLE_RATE * timeout_sec / 512)
        vad_model = load_silero_vad()

        for _ in range(max_frames):
            data = stream.read(512, exception_on_overflow=False)
            frames.append(data)

            if len(frames) % (RECORD_SAMPLE_RATE // 512) == 0:  # 每秒检查一次
                audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
                speech_ts = get_speech_timestamps(audio, vad_model, sampling_rate=RECORD_SAMPLE_RATE)
                if len(speech_ts) > 0:
                    last_end = speech_ts[-1]["end"] / RECORD_SAMPLE_RATE
                    silence_dur = len(audio) / RECORD_SAMPLE_RATE - last_end
                    if silence_dur >= silence_ms / 1000:
                        cutoff = int(last_end * RECORD_SAMPLE_RATE * 2)
                        all_audio = b"".join(frames)
                        frames = [all_audio[: min(cutoff, len(all_audio))]]
                        break

        stream.stop_stream()
        stream.close()
        pa.terminate()

        all_audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        return all_audio

    def stop(self):
        self._running = False
        self._queue.put(None)

    def _play_loop(self):
        import time as _time
        pa = pyaudio.PyAudio()
        stream = None

        while self._running:
            try:
                item = self._queue.get(timeout=2)
            except queue.Empty:
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
                    rate=self.play_sample_rate, output=True,
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


_manager: AudioManager | None = None


def init(sample_rate: int = 22050, play_device: int | None = None):
    global _manager
    if _manager is None:
        _manager = AudioManager(sample_rate, play_device)


def get() -> AudioManager:
    if _manager is None:
        init()
    return _manager

