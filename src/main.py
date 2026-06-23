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
    # 启用图优化以减少内存碎片，禁用不必要的日志
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    sess_options.enable_mem_pattern = False  # 减少内存模式缓存
    sess_options.enable_cpu_mem_arena = False  # 减少内存竞技场开销
    if providers is None:
        providers = ["CPUExecutionProvider"]
    _orig_init(self, path, sess_options=sess_options, providers=providers, **kw)


ort.InferenceSession.__init__ = _patched_init

# ---- 日志 ----
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

# ---- 日志内存缓冲（Web UI 查看用） ----
from log_manager import log_mgr
log_mgr.setup()

# ---- 内存监控（5 帧 tracemalloc，开销可忽略） ----
from memory_monitor import MemoryMonitor
MemoryMonitor.instance()._ensure_tracemalloc()

# ---- 标准库 & 业务模块 ----
import asyncio
import gc
import threading
import time
from datetime import datetime
from config import cfg
from settings import settings

_log = logging.getLogger("main")
import wakeword as ww
import tts
import vad
from voiceprint import vp_engine
from stt import stt
from llm import llm
from tts import audio_manager
import reminder_thread


def _start_webserver():
    """在后台线程启动 FastAPI 管理界面"""
    import uvicorn
    from server import app
    port = 8160
    _log.info("Web UI: http://localhost:%d", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


async def main():
    threading.Thread(target=_start_webserver, daemon=True).start()

    stt.load()
    vp_engine.load()
    tts.load()
    audio_manager.init()
    reminder_thread.start()

    _log.info("Threshold=%.2f Voiceprint=%.2f", cfg.THRESHOLD, cfg.VOICEPRINT_THRESHOLD)
    _log.info("Listening... Ctrl+C to stop")

    counter = 0
    async with ww.create_listener() as listener:
        while True:
            detection = await listener.wait_for_detection()
            _log.info("WAKE! score=%.4f", detection.confidence)

            # 总开关
            if not settings.get("wakeword_enabled"):
                _log.info("Wakeword disabled, skipped")
                continue
            # 定时开关 + 时间段
            if settings.get("wakeword_schedule_enabled"):
                now = datetime.now().strftime("%H:%M")
                start = settings.get("wakeword_start") or "06:00"
                end = settings.get("wakeword_end") or "24:00"
                in_range = (start <= now <= end) if start <= end else (now >= start or now <= end)
                if not in_range:
                    _log.info("Wakeword outside allowed time (%s-%s), skipped", start, end)
                    continue

            t0 = time.time()
            # 同步播放"我在呢"，播完立即开始录音
            await asyncio.to_thread(tts.wake_ack_sync)

            # 1. 录音
            filename = await asyncio.to_thread(vad.record, counter)

            # 2. 声纹验证
            user_id, info, audio_path, vp_id = await asyncio.to_thread(vp_engine.verify, filename)
            if info.startswith("enrolled:"):
                speaker = ""
                _log.info("Voiceprint: ENROLLED (user_id=%d)", user_id)
            else:
                speaker = info.rsplit(":", 1)[0]
                sim = info.split(":")[-1]
                _log.info("Voiceprint: %s user_id=%d sim=%s", speaker, user_id, sim)

            # 3. STT（用验证返回的新路径，文件已被移到 records/{user_id}/）
            t1 = time.time()
            _log.info("STT...")
            text = await asyncio.to_thread(stt.transcribe, audio_path)
            _log.info("STT: '%s' (%.1fs)", text, time.time()-t1)

            # 过滤太短的输入（≤2 个字不送 LLM）
            if text.strip() and len(text.strip()) < 3:
                _log.info("STT too short, skipped")
                ww.classify_audio("negative")
                text = ""

            # 4. LLM + 同步播放回复
            if text.strip():
                t2 = time.time()
                _log.info("DeepSeek...")
                reply = await asyncio.to_thread(llm.chat, text, user_id or 0, speaker)
                dt = time.time() - t2
                _log.info("LLM: '%s' (%.1fs)", reply, dt)

                if reply == "__SKIP__":
                    _log.info("LLM skip (noise/misrecognition)")
                    ww.classify_audio("negative")
                    import os as _os
                    try:
                        if _os.path.isfile(audio_path):
                            _os.remove(audio_path)
                    except Exception:
                        pass
                    import db
                    if vp_id:
                        db.delete_voiceprint(vp_id)
                elif reply:
                    ww.classify_audio("positive")
                    t3 = time.time()
                    await asyncio.to_thread(tts.speak_sync, reply)
                    if time.time() - t3 > 0.5:
                        _log.info("TTS playback: %.1fs", time.time()-t3)
            else:
                ww.classify_audio("negative")

            _log.info("Saved: %s [total=%.1fs]", audio_path, time.time()-t0)
            counter += 1

            # 每轮对话后强制 GC，回收 ONNX/Torch 中间张量
            gc.collect()


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

        _log.info("Web-only mode: http://localhost:8160")
        reminder_thread.start()
        uvicorn.run(app, host="0.0.0.0", port=8160, log_level="info")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            _log.info("Stopped")
