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

# ---- 日志 ----
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

# ---- 标准库 & 业务模块 ----
import asyncio
import threading
import time
from datetime import datetime
from config import THRESHOLD, VOICEPRINT_THRESHOLD
import wakeword as ww
from vits_tts import tts
import vad
import voiceprint
from stt import stt
import llm
import reminder_thread


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
    voiceprint.load()
    tts.load()
    reminder_thread.start()

    print(f"Threshold: {THRESHOLD}")
    print(f"Voiceprint threshold: {VOICEPRINT_THRESHOLD}")
    print("Listening... Ctrl+C to stop.\n")

    counter = 0
    async with ww.create_listener() as listener:
        while True:
            detection = await listener.wait_for_detection()
            now = datetime.now().strftime("%H:%M:%S")
            print(f"{now} >>> WAKE! score={detection.confidence:.4f}")

            t0 = time.time()
            # 同步播放"我在呢"，播完立即开始录音
            await asyncio.to_thread(tts.wake_ack_sync)

            # 1. 录音
            filename = await asyncio.to_thread(vad.record, counter)

            # 2. 声纹验证
            user_id, info, audio_path = await asyncio.to_thread(voiceprint.verify, filename)
            if info.startswith("enrolled:"):
                speaker = ""
                print(f"  Voiceprint: ENROLLED (user_id={user_id})")
            else:
                speaker = info.rsplit(":", 1)[0]
                sim = info.split(":")[-1]
                print(f"  Voiceprint: {speaker} user_id={user_id} sim={sim}")

            # 3. STT（用验证返回的新路径，文件已被移到 records/{user_id}/）
            t1 = time.time()
            print("  STT...", end=" ", flush=True)
            text = await asyncio.to_thread(stt.transcribe, audio_path)
            print(f"-> '{text}' ({time.time()-t1:.1f}s)")

            # 4. LLM + 同步播放回复
            if text.strip():
                t2 = time.time()
                print(f"  DeepSeek...", end=" ", flush=True)
                reply = await asyncio.to_thread(llm.chat, text, user_id or 0, speaker)
                dt = time.time() - t2
                print(f"-> '{reply}' ({dt:.1f}s)")

                t3 = time.time()
                await asyncio.to_thread(tts.speak_sync, reply)
                if time.time() - t3 > 0.5:
                    print(f"  TTS: {time.time()-t3:.1f}s")
            # 没说话 → 直接回到唤醒词检测

            print(f"  Saved: {audio_path}  [total={time.time()-t0:.1f}s]\n")
            counter += 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="派萌助手")
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="只启动 Web 管理界面，不加载唤醒词/STT/LLM",
    )
    args = parser.parse_args()

    if args.web_only:
        import uvicorn
        from server import app

        print("Web-only mode: http://localhost:8160")
        reminder_thread.start()
        uvicorn.run(app, host="0.0.0.0", port=8160, log_level="info")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nStopped.")
