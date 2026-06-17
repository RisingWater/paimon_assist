"""定时提醒后台线程 — 每 5 分钟检查一次到期提醒，通知 LLM"""
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

    for r in due:
        _log.info("Reminder triggered: #%d %s", r["id"], r["content"])
        try:
            uid = db._ensure_reminder_user()
            reply = llm.chat(
                f"[定时提醒] {r['content']}。请用自然语言提醒我。",
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
        time.sleep(300)
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
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    _log.info("Reminder thread started (every 5min)")
