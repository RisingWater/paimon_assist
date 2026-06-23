"""内存监控 — MemoryTracked 基类 + MemoryMonitor 单例管理器

用法:
  1. 继承 MemoryTracked，super().__init__() 自动注册到监控
  2. 子类可重写 _mem_size() 返回自身内存占用
  3. MemoryMonitor.instance().get_report() 获取完整报告
  4. MemoryMonitor.instance().gc_now() 手动触发 GC
"""

import gc
import logging
import os
import sys
import threading
import time
from typing import Optional

_log = logging.getLogger(__name__)


# ============================================================
# MemoryMonitor — 单例管理器
# ============================================================

class MemoryMonitor:
    """内存监控单例，管理所有 MemoryTracked 实例的追踪"""

    _instance: Optional["MemoryMonitor"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls) -> "MemoryMonitor":
        return cls()

    def _init(self):
        self._tracked: dict[str, "MemoryTracked"] = {}
        self._tracelock = threading.Lock()
        self._tracemalloc_started = False
        self._last_snapshot: dict | None = None
        self._last_snapshot_time = 0.0
        self._snapshot_cache_sec = 2

    # ---- tracemalloc ----

    def _ensure_tracemalloc(self):
        if self._tracemalloc_started:
            return
        try:
            import tracemalloc
            tracemalloc.start(25)
            self._tracemalloc_started = True
            _log.info("tracemalloc started")
        except Exception:
            pass

    # ---- 注册 ----

    def register(self, obj: "MemoryTracked"):
        """注册一个 MemoryTracked 实例"""
        with self._tracelock:
            name = obj._mem_name or obj.__class__.__name__
            # 同名覆盖（如模型 reload）
            self._tracked[name] = obj

    def unregister(self, name: str):
        with self._tracelock:
            self._tracked.pop(name, None)

    # ---- 报告 ----

    def get_report(self) -> dict:
        """生成完整内存报告"""
        now = time.time()
        if self._last_snapshot and (now - self._last_snapshot_time) < self._snapshot_cache_sec:
            return self._last_snapshot

        self._ensure_tracemalloc()

        # 进程 RSS
        total_rss = 0
        try:
            import psutil
            total_rss = psutil.Process(os.getpid()).memory_info().rss
        except ImportError:
            pass

        # 已注册的 MemoryTracked 实例
        tracked = []
        with self._tracelock:
            for name, obj in self._tracked.items():
                size = obj._mem_size()
                tracked.append({
                    "name": name,
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 1),
                    "category": obj._mem_category,
                    "description": obj._mem_description,
                })

        # tracemalloc 快照
        tm_items = self._tracemalloc_stats()

        # 汇总饼图（TOP 15）
        all_items = []
        for t in tracked:
            all_items.append({"name": t["name"], "size_mb": t["size_mb"], "category": t["category"]})
        for t in tm_items:
            all_items.append({"name": t["name"], "size_mb": t["size_mb"], "category": t["category"]})
        all_items.sort(key=lambda x: -x["size_mb"])
        accounted_mb = sum(i["size_mb"] for i in all_items)
        other_mb = max(0, round(total_rss / (1024 * 1024), 1) - accounted_mb)
        if other_mb > 0.5:
            all_items.append({"name": "未分类（系统开销+碎片）", "size_mb": round(other_mb, 1), "category": "系统"})

        # GC 统计
        gc_stats = {"counts": gc.get_count(), "threshold": gc.get_threshold(), "details": []}
        try:
            for i, s in enumerate(gc.get_stats()):
                gc_stats["details"].append({"gen": i, **s})
        except Exception:
            pass

        report = {
            "total_rss": total_rss,
            "total_rss_mb": round(total_rss / (1024 * 1024), 1),
            "tracked": tracked,
            "tracemalloc": tm_items,
            "summary": all_items[:15],
            "gc_stats": gc_stats,
            "timestamp": now,
        }
        self._last_snapshot = report
        self._last_snapshot_time = now
        return report

    def gc_now(self) -> dict:
        """手动触发 GC，返回回收统计"""
        before = 0
        try:
            import psutil
            before = psutil.Process(os.getpid()).memory_info().rss
        except ImportError:
            pass

        collected = gc.collect()

        after = 0
        try:
            import psutil
            after = psutil.Process(os.getpid()).memory_info().rss
        except ImportError:
            pass

        return {
            "collected": collected,
            "before_mb": round(before / (1024 * 1024), 1),
            "after_mb": round(after / (1024 * 1024), 1),
            "freed_mb": round((before - after) / (1024 * 1024), 1),
        }

    # ---- tracemalloc 内部分析 ----

    _TRACEMALLOC_PATTERNS = [
        ("vits", "VITS 推理"),
        ("funasr", "FunASR STT"),
        ("modelscope", "ModelScope 声纹"),
        ("onnxruntime", "ONNX Runtime"),
        ("silero_vad", "Silero VAD"),
        ("livekit", "LiveKit WakeWord"),
        ("torch", "PyTorch 引擎"),
        ("llm_tools/web_search", "Tool: 网络搜索"),
        ("llm_tools/memory", "Tool: 记忆读写"),
        ("llm_tools/weather", "Tool: 天气查询"),
        ("llm_tools/location", "Tool: 设备定位"),
        ("llm_tools/home_assistant", "Tool: 空调控制"),
        ("llm_tools/home_tv", "Tool: 电视控制"),
        ("llm_tools/reminder", "Tool: 定时提醒"),
        ("llm_tools/volume", "Tool: 音量控制"),
        ("llm_tools/ask_user", "Tool: 反问用户"),
        ("llm_tools/door", "Tool: 门禁开门"),
        ("llm_tools", "LLM 工具"),
        ("llm", "LLM 对话"),
        ("audio_manager", "音频管理"),
        ("server", "Web Server"),
        ("db", "数据库"),
        ("tts", "TTS 缓存/播放"),
        ("vad", "VAD 录音"),
        ("wakeword", "唤醒词"),
        ("voiceprint", "声纹验证"),
        ("stt", "STT 识别"),
        ("memory_monitor", "内存监控自身"),
        ("memory", "记忆系统"),
        ("reminder", "定时提醒"),
        ("log_manager", "日志缓冲"),
        ("uvicorn", "Uvicorn"),
        ("fastapi", "FastAPI"),
        ("numpy", "NumPy"),
        ("pyaudio", "PyAudio"),
        ("<unknown>", "未知/其他"),
    ]

    def _tracemalloc_stats(self) -> list[dict]:
        if not self._tracemalloc_started:
            return []
        try:
            import tracemalloc
        except ImportError:
            return []

        snap = tracemalloc.take_snapshot()
        stats = snap.statistics("traceback")
        module_sizes: dict[str, int] = {}
        for s in stats:
            mod = self._classify_traceback(s.traceback)
            module_sizes[mod] = module_sizes.get(mod, 0) + s.size

        return [
            {"name": mod, "size_bytes": size, "size_mb": round(size / (1024 * 1024), 1), "category": "Python 分配"}
            for mod, size in sorted(module_sizes.items(), key=lambda x: -x[1])
        ]

    def _classify_traceback(self, tb) -> str:
        for frame in tb:
            fname = frame.filename
            for pattern, label in self._TRACEMALLOC_PATTERNS:
                if pattern in fname.lower():
                    return label
        return "其他 Python"


# ============================================================
# MemoryTracked — 基类
# ============================================================

class MemoryTracked:
    """继承此基类自动注册到 MemoryMonitor，获得内存追踪能力。

    子类在 __init__ 中调用 super().__init__(name=..., category=...)。
    可重写 _mem_size() 返回自身内存字节数。
    """

    def __init__(self, name: str = "", description: str = "", category: str = "组件"):
        self._mem_name = name or self.__class__.__name__
        self._mem_description = description
        self._mem_category = category
        MemoryMonitor.instance().register(self)

    def _mem_size(self) -> int:
        """子类重写以返回自身内存占用。默认用 sys.getsizeof"""
        try:
            return sys.getsizeof(self)
        except Exception:
            return 0

    @staticmethod
    def _model_size(model) -> int:
        """测量 PyTorch 模型参数内存"""
        try:
            import torch
            if isinstance(model, torch.nn.Module):
                return sum(p.numel() * p.element_size() for p in model.parameters())
        except ImportError:
            pass
        return 0

    @staticmethod
    def _file_size(path: str) -> int:
        """文件大小"""
        try:
            return os.path.getsize(path) if os.path.isfile(path) else 0
        except Exception:
            return 0


# ============================================================
# 工具函数 — 用于注册非 MemoryTracked 子类的外部资源
# ============================================================

def register_model(name: str, model_or_path, description: str = "", category: str = "模型"):
    """手动注册模型（如第三方库的 ONNX 模型，无法继承 MemoryTracked 时使用）"""
    class _ModelRef(MemoryTracked):
        def __init__(self):
            super().__init__(name=name, description=description, category=category)
            self._ref = model_or_path

        def _mem_size(self):
            if hasattr(self._ref, "parameters"):
                return MemoryTracked._model_size(self._ref)
            if isinstance(self._ref, str) and os.path.isfile(self._ref):
                return MemoryTracked._file_size(self._ref)
            return 0

    _ModelRef()


def register_component(name: str, description: str = "", size_bytes: int = 0, category: str = "组件"):
    """手动注册非模型组件（缓存、缓冲等）"""
    class _Comp(MemoryTracked):
        def __init__(self):
            super().__init__(name=name, description=description, category=category)
            self._size = size_bytes

        def _mem_size(self):
            return self._size

    _Comp()


def update_component(name: str, size_bytes: int):
    """更新组件大小"""
    tracked = MemoryMonitor.instance()._tracked.get(name)
    if tracked and hasattr(tracked, "_size"):
        tracked._size = size_bytes
