"""派萌助手 — 实时唤醒 + STT + DeepSeek 对话"""
import os
from dotenv import load_dotenv

load_dotenv()

import onnxruntime as ort
_orig_init = ort.InferenceSession.__init__
def _patched_init(self, path, sess_options=None, providers=None, **kw):
    if sess_options is None:
        sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 1
    sess_options.inter_op_num_threads = 1
    if providers is None:
        providers = ["CPUExecutionProvider"]
    _orig_init(self, path, sess_options=sess_options, providers=providers, **kw)
ort.InferenceSession.__init__ = _patched_init

import asyncio
import threading
import time
import wave
import requests
import numpy as np
from livekit.wakeword import WakeWordModel, WakeWordListener
from silero_vad import load_silero_vad, get_speech_timestamps

# ============================================================
# 配置（默认值在 .env.example，实际值在 .env）
# ============================================================
MODEL_PATH = os.getenv("MODEL_PATH", "models/paimeng.onnx")
THRESHOLD = float(os.getenv("THRESHOLD", "0.25"))
DEBOUNCE = float(os.getenv("DEBOUNCE", "1.0"))
TTS_URL = os.getenv("TTS_URL", "http://192.168.1.180:6018/api/tts/speak")
TTS_TEXT = "我在"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DISABLE_UPDATE = os.getenv("DISABLE_UPDATE", "0") == "1"

_chat_history: list[dict] = [
    {"role": "system", "content": (
        "你是派萌，一个可爱的AI助手。你的回答会通过语音播放给用户听，所以："
        "1. 不要使用任何emoji、颜文字、特殊符号 "
        "2. 不要使用markdown格式 "
        "3. 用中文回答，语气活泼可爱 "
        "4. 回复尽量简短在1-2句话内 "
        "5. 使用口语化的表达方式。"
    )}
]

SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "800"))
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "10"))


# ============================================================
# 组件
# ============================================================

def speak(text: str):
    def _call():
        try:
            requests.post(TTS_URL, json={"text": text}, timeout=10)
        except Exception:
            pass
    threading.Thread(target=_call, daemon=True).start()


def chat_with_deepseek(user_text: str) -> str:
    _chat_history.append({"role": "user", "content": user_text})
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": _chat_history,
                "max_tokens": 200,
                "temperature": 0.7,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            _chat_history.append({"role": "assistant", "content": reply})
            return reply
        return f"API error: {resp.status_code}"
    except Exception as e:
        return f"Request failed: {e}"


def record_and_transcribe(counter: int, stt_model) -> str:
    import pyaudio

    vad_model = load_silero_vad()
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, frames_per_buffer=512,
    )

    frames: list[bytes] = []
    max_frames = int(SAMPLE_RATE * MAX_RECORD_SECONDS / 512)

    print("  Recording...", end=" ", flush=True)

    for _ in range(max_frames):
        data = stream.read(512, exception_on_overflow=False)
        frames.append(data)

        if len(frames) % 64 == 0:
            audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
            speech_ts = get_speech_timestamps(audio, vad_model, sampling_rate=SAMPLE_RATE)

            if len(speech_ts) > 0:
                last_end = speech_ts[-1]["end"] / SAMPLE_RATE
                silence_dur = len(audio) / SAMPLE_RATE - last_end
                if silence_dur >= VAD_SILENCE_MS / 1000:
                    cutoff = int(last_end * SAMPLE_RATE * 2)
                    all_audio = b"".join(frames)
                    frames = [all_audio[:min(cutoff, len(all_audio))]]
                    break

    stream.stop_stream()
    stream.close()
    pa.terminate()

    all_audio = b"".join(frames)
    duration = len(all_audio) / (2 * SAMPLE_RATE)

    filename = f"recording_{time.strftime('%Y%m%d_%H%M%S')}_{counter}.wav"
    wf = wave.open(filename, "wb")
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(all_audio)
    wf.close()

    print(f"({duration:.1f}s)")

    print("  STT...", end=" ", flush=True)
    result = stt_model.generate(input=filename)
    text = result[0].get("text", "") if result else ""
    print(f"-> '{text}'")

    if text.strip():
        print("  DeepSeek...", end=" ", flush=True)
        reply = chat_with_deepseek(text)
        print(f"-> '{reply}'")
        speak(reply)

    print(f"  Saved: {filename}\n")
    return text


async def main():
    from funasr import AutoModel
    print("Loading SenseVoiceSmall...", end=" ", flush=True)
    stt_model = AutoModel(model="models/iic/SenseVoiceSmall", device="cpu", disable_update=DISABLE_UPDATE)
    print("Done")

    model = WakeWordModel(models=[MODEL_PATH])

    print(f"Model: {MODEL_PATH}  Threshold: {THRESHOLD}")
    print(f"VAD: {VAD_SILENCE_MS}ms silence  Max: {MAX_RECORD_SECONDS}s")
    print("Listening... Ctrl+C to stop.\n")

    counter = 0
    async with WakeWordListener(model, threshold=THRESHOLD, debounce=DEBOUNCE) as listener:
        while True:
            detection = await listener.wait_for_detection()
            print(f">>> WAKE! score={detection.confidence:.4f}")
            speak(TTS_TEXT)
            await asyncio.sleep(1.5)

            await asyncio.to_thread(record_and_transcribe, counter, stt_model)
            counter += 1


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
