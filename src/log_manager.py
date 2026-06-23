"""日志管理 — LogManager 单例：磁盘持久化（20MB）+ 内存缓冲，供 Web UI 查看和导出"""
import logging
import logging.handlers
import os
import sys
import threading
import time
from collections import deque
from typing import Optional

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "paimon.log")
_MAX_BYTES = 5 * 1024 * 1024      # 单个文件 5MB
_BACKUP_COUNT = 3                  # 保留 3 个备份 → 总共 20MB
_MAX_MEMORY_ENTRIES = 20000


def _format_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) + f".{int(ts * 1000) % 1000:03d}"


def _ensure_log_dir():
    os.makedirs(_LOG_DIR, exist_ok=True)


class _MemoryHandler(logging.Handler):
    """将日志记录写入 LogManager 的内存环形缓冲区"""

    def __init__(self, mgr: "LogManager"):
        super().__init__()
        self._mgr = mgr

    def emit(self, record: logging.LogRecord):
        try:
            self._mgr._append_record(record)
        except Exception:
            self.handleError(record)


class LogManager:
    """日志管理单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        self._buffer: deque = deque(maxlen=_MAX_MEMORY_ENTRIES)
        self._lock = threading.Lock()
        self._counter = 0

    # ---- 初始化 ----

    def setup(self):
        """安装内存 + 磁盘日志处理器到根 logger，并接管 sys.excepthook"""
        # 磁盘持久化
        _ensure_log_dir()
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT,
            encoding="utf-8", delay=False,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logging.root.addHandler(file_handler)

        # 内存缓冲
        mem_handler = _MemoryHandler(self)
        mem_handler.setLevel(logging.DEBUG)
        mem_handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s",
            datefmt="%H:%M:%S",
        ))
        logging.root.addHandler(mem_handler)

        # 注册到内存监控
        import memory_monitor
        memory_monitor.register_component("日志缓冲", f"内存环形缓冲，最多 {_MAX_MEMORY_ENTRIES} 条",
                                          size_bytes=0, category="系统")

        # 捕获未处理的异常
        _orig_excepthook = sys.excepthook
        def _log_excepthook(exc_type, exc_value, exc_tb):
            import traceback
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.getLogger("unhandled").error("Unhandled exception:\n%s", tb_text.rstrip())
            _orig_excepthook(exc_type, exc_value, exc_tb)
        sys.excepthook = _log_excepthook

        if hasattr(threading, "excepthook"):
            _orig_threadhook = threading.excepthook
            def _log_threadhook(args):
                import traceback
                tb_text = "".join(traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback))
                logging.getLogger("unhandled").error("Thread exception:\n%s", tb_text.rstrip())
                if _orig_threadhook:
                    _orig_threadhook(args)
            threading.excepthook = _log_threadhook

    # ---- 内部 ----

    def _append_record(self, record: logging.LogRecord):
        with self._lock:
            self._counter += 1
            self._buffer.append({
                "id": self._counter,
                "time": _format_time(record.created),
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
            })

    # ---- 查询 ----

    def get_logs(
        self, level: Optional[str] = None, search: Optional[str] = None,
        limit: int = 200, offset: int = 0,
    ) -> dict:
        with self._lock:
            entries = list(self._buffer)
            try:
                import sys as _sys
                buf_size = _sys.getsizeof(self._buffer) + sum(_sys.getsizeof(e) for e in entries)
                import memory_monitor
                memory_monitor.update_component("日志缓冲", buf_size)
            except Exception:
                pass

        if level:
            level = level.upper()
            entries = [e for e in entries if e["level"] == level]
        if search:
            search_lower = search.lower()
            entries = [e for e in entries if search_lower in e["message"].lower()]

        total = len(entries)
        entries.reverse()
        page = entries[offset:offset + limit]
        return {"total": total, "logs": page}

    def export_text(self) -> str:
        files = [_LOG_FILE]
        for i in range(1, _BACKUP_COUNT + 1):
            f = f"{_LOG_FILE}.{i}"
            if os.path.isfile(f):
                files.append(f)
        files.sort(key=lambda f: os.path.getmtime(f))
        lines = []
        for path in files:
            try:
                with open(path, encoding="utf-8") as fh:
                    lines.append(fh.read().rstrip())
            except Exception:
                pass
        return "\n".join(lines)

    def clear(self):
        with self._lock:
            self._buffer.clear()
            self._counter = 0
        for path in [_LOG_FILE] + [f"{_LOG_FILE}.{i}" for i in range(1, _BACKUP_COUNT + 1)]:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass


# 全局单例
log_mgr = LogManager()
