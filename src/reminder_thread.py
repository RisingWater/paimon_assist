"""定时提醒后台线程 — 每分钟检查一次到期提醒，通知 LLM"""
import asyncio
import logging
import time
import threading

_log = logging.getLogger(__name__)


def _check_and_notify():
    """检查到期提醒，触发 LLM 通知"""
    import db
    import llm

    due = db.get_due_reminders()
    if not due:
        return

    uid = db._ensure_reminder_user()
    for r in due:
        _log.info("Reminder triggered: #%d %s", r["id"], r["content"])
        try:
            reply = llm.chat(
                f"[定时任务] 现在到了执行以下任务的时间：{r['content']}。请执行这个任务，如果需要用到工具就直接调用，完成后告知结果。",
                user_id=uid,
                speaker="定时任务",
            )
            _log.info("Reminder LLM reply: %s", reply[:100] if reply else "(empty)")
            if reply and "失败" not in reply:
                try:
                    from vits_tts import tts as _tts
                    _tts.speak_sync(reply)
                except Exception:
                    pass
            if r["rtype"] == "once":
                db.mark_reminder_done(r["id"])
        except Exception as e:
            _log.error("Reminder #%d failed: %s", r["id"], e)


def _loop():
    """后台循环：每 5 分钟检查一次"""
    while True:
        time.sleep(60)
        try:
            _check_and_notify()
        except Exception as e:
            _log.error("Reminder loop error: %s", e)


_thread: threading.Thread | None = None


def start():
    """启动提醒后台线程"""
    global _thread
    if _thread is not None:
        return
    import db
    db._ensure_reminder_user()
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    _log.info("Reminder thread started (every 1min)")
