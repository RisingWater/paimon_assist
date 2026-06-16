"""VAD 录音 — 检测到静音后自动停止"""
import os
import time
import wave
import pyaudio
import numpy as np
from silero_vad import load_silero_vad, get_speech_timestamps
from config import SAMPLE_RATE, VAD_SILENCE_MS, MAX_RECORD_SECONDS

RECORDINGS_DIR = "recordings"


def record(counter: int) -> str:
    """
    录音直到检测到静音，保存为 WAV 文件。
    返回文件名。
    """
    vad_model = load_silero_vad()
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=512,
    )

    frames: list[bytes] = []
    max_frames = int(SAMPLE_RATE * MAX_RECORD_SECONDS / 512)

    print("  Recording...", end=" ", flush=True)

    for i in range(max_frames):
        data = stream.read(512, exception_on_overflow=False)
        frames.append(data)

        # 每 16 帧 (~0.5s) 检查一次 VAD，比之前的 64 帧 (~2s) 灵敏很多
        if i > 0 and i % 16 == 0:
            audio = (
                np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32)
                / 32768.0
            )
            speech_ts = get_speech_timestamps(
                audio,
                vad_model,
                sampling_rate=SAMPLE_RATE,
                threshold=0.7,               # 更高 = 更严格，背景噪音不容易被当成语音
                min_speech_duration_ms=250,  # 最短语音时长（恢复默认）
                min_silence_duration_ms=200, # 静音至少持续 200ms 才算断句
            )

            if len(speech_ts) > 0:
                last_end = speech_ts[-1]["end"] / SAMPLE_RATE
                silence_dur = len(audio) / SAMPLE_RATE - last_end
                if silence_dur >= VAD_SILENCE_MS / 1000:
                    cutoff = int(last_end * SAMPLE_RATE * 2)
                    all_audio = b"".join(frames)
                    frames = [all_audio[: min(cutoff, len(all_audio))]]
                    break

    stream.stop_stream()
    stream.close()
    pa.terminate()

    all_audio = b"".join(frames)
    duration = len(all_audio) / (2 * SAMPLE_RATE)
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    filename = f"{RECORDINGS_DIR}/recording_{time.strftime('%Y%m%d_%H%M%S')}_{counter}.wav"

    wf = wave.open(filename, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(all_audio)
    wf.close()

    print(f"({duration:.1f}s)")
    return filename
