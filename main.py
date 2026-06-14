"""派萌助手 — 实时唤醒 + 声纹验证 + STT + LLM + TTS

入口文件，负责：ONNX patch、主循环编排。
具体逻辑分散在各模块中。
"""
# ---- ONNX Runtime 补丁（必须在任何 onnxruntime 使用前执行） ----
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

# ---- 标准库 & 业务模块 ----
import asyncio
import threading
from config import THRESHOLD, VOICEPRINT_THRESHOLD
import wakeword as ww
import tts
import vad
import voiceprint
import stt
import llm


def _start_webserver():
    """在后台线程启动 FastAPI 管理界面"""
    import uvicorn
    from server import app
    port = 8160
    print(f"\n🌐 声纹管理界面: http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


async def main():
    threading.Thread(target=_start_webserver, daemon=True).start()

    stt.load()

    print(f"Threshold: {THRESHOLD}")
    print(f"Voiceprint threshold: {VOICEPRINT_THRESHOLD}")
    print("Listening... Ctrl+C to stop.\n")

    counter = 0
    async with ww.create_listener() as listener:
        while True:
            detection = await listener.wait_for_detection()
            print(f">>> WAKE! score={detection.confidence:.4f}")

            tts.wake_ack()
            await asyncio.sleep(1.5)

            # 1. 录音
            filename = await asyncio.to_thread(vad.record, counter)

            # 2. 声纹验证
            ok, info = await asyncio.to_thread(voiceprint.verify, filename)
            # 从 info 中提取说话人名字（空字符串 = 未命名）
            if info.startswith("enrolled:"):
                speaker = info.split(":", 1)[1]
                if speaker:
                    print(f"  Voiceprint: ENROLLED as '{speaker}'")
                else:
                    print(f"  Voiceprint: ENROLLED (unnamed)")
            else:
                speaker = info.rsplit(":", 1)[0]  # "张三:0.92" → "张三"
                print(f"  Voiceprint: {speaker} sim={info.split(':')[-1]}")

            # 3. STT
            print("  STT...", end=" ", flush=True)
            text = await asyncio.to_thread(stt.transcribe, filename)
            print(f"-> '{text}'")

            # 4. LLM（仅当声纹已命名时才告诉 LLM 说话人）
            if text.strip():
                print(f"  DeepSeek...", end=" ", flush=True)
                reply = await asyncio.to_thread(llm.chat, text, speaker if speaker else "")
                print(f"-> '{reply}'")
                tts.speak(reply)

            print(f"  Saved: {filename}\n")
            counter += 1


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
