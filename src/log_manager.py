"""日志管理 — 磁盘持久化（20MB）+ 内存缓冲，供 Web UI 查看和导出"""
import logging
import logging.handlers
import os
import sys
import threading
import time
from collections import deque
from typing import Optional

# ---- 磁盘日志 ----
_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "paimon.log")
_MAX_BYTES = 5 * 1024 * 1024      # 单个文件 5MB
_BACKUP_COUNT = 3                  # 保留 3 个备份 → 总共 20MB

# ---- 内存缓冲（供 Web 快速查询，不设硬上限，靠总条数大约 20000 控制） ----
_MAX_MEMORY_ENTRIES = 20000
_buffer: deque = deque(maxlen=_MAX_MEMORY_ENTRIES)
_lock = threading.Lock()
_counter = 0


def _format_time(ts: float) -> str:
    """带毫秒的时间戳"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"


def _ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)


class MemoryHandler(logging.Handler):
    """将日志记录同时写入内存环形缓冲区"""

    def emit(self, record: logging.LogRecord):
        global _counter
        try:
            with _lock:
                _counter += 1
                _buffer.append({
                    "id": _counter,
                    "time": _format_time(record.created),
                    "level": record.levelname,
                    "name": record.name,
                    "message": self.format(record),
                })
        except Exception:
            self.handleError(record)


def _create_file_handler() -> logging.Handler:
    """创建 RotatingFileHandler：单文件 5MB × 4 = 20MB 上限"""
    _ensure_log_dir()
    handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
        delay=False,  # 立即创建文件，确保目录已存在
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    return handler


def setup():
    """安装内存 + 磁盘日志处理器到根 logger，并接管 sys.excepthook"""
    # 磁盘持久化
    logging.root.addHandler(_create_file_handler())

    # 内存缓冲（Web UI 查询用）
    mem_handler = MemoryHandler()
    mem_handler.setLevel(logging.DEBUG)
    mem_handler.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.root.addHandler(mem_handler)

    # 捕获未处理的异常写入日志
    _orig_excepthook = sys.excepthook

    def _log_excepthook(exc_type, exc_value, exc_tb):
        import traceback
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger("unhandled").error("Unhandled exception:\n%s", tb_text.rstrip())
        _orig_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _log_excepthook

    # 也捕获线程中的未处理异常
    if hasattr(threading, "excepthook"):
        _orig_threadhook = threading.excepthook

        def _log_threadhook(args):
            import traceback
            tb_text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
            logging.getLogger("unhandled").error("Thread exception:\n%s", tb_text.rstrip())
            if _orig_threadhook:
                _orig_threadhook(args)

        threading.excepthook = _log_threadhook


def get_logs(
    level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询内存中最近的日志，支持按级别过滤、关键词搜索、分页"""
    with _lock:
        entries = list(_buffer)

    if level:
        level = level.upper()
        entries = [e for e in entries if e["level"] == level]

    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in e["message"].lower()]

    total = len(entries)

    # 分页（从最新往前）
    entries.reverse()
    page = entries[offset:offset + limit]

    return {"total": total, "logs": page}


def export_text() -> str:
    """导出全部日志 — 直接读取磁盘文件（完整保留，最多 20MB）"""
    files = [_LOG_FILE]
    for i in range(1, _BACKUP_COUNT + 1):
        f = f"{_LOG_FILE}.{i}"
        if os.path.isfile(f):
            files.append(f)

    # 按修改时间排序（旧的在前）
    files.sort(key=lambda f: os.path.getmtime(f))

    lines = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                lines.append(fh.read().rstrip())
        except Exception:
            pass

    return "\n".join(lines)


def clear():
    """清空内存缓冲 + 清空磁盘日志文件"""
    global _counter
    with _lock:
        _buffer.clear()
        _counter = 0

    # 清空日志文件（包括备份）
    for path in [_LOG_FILE] + [f"{_LOG_FILE}.{i}" for i in range(1, _BACKUP_COUNT + 1)]:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass
