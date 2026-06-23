"""内存监控 — 追踪各模块内存占用，供 Web UI 展示

使用 tracemalloc 追踪 Python 层分配，psutil 获取进程级 RSS。
模型通过 register_model() 注册，自动测量参数/权重内存。

模块内存分类规则：
  - 优先匹配显式注册的模型（VITS、SenseVoice、声纹等）
  - 剩余归入 tracemalloc 文件路径分组
"""

import gc
import logging
import os
import threading
import time

_log = logging.getLogger(__name__)

# ---- 状态 ----
_started = False
_lock = threading.Lock()

# 显式注册的模型：name -> {description, model_obj, size_bytes, category}
_models: dict[str, dict] = {}

# 其他组件（非模型）：name -> {description, size_bytes}
_components: dict[str, dict] = {}

# 上一次快照（用于增量）
_last_snapshot_time = 0.0
_last_snapshot: dict | None = None
SNAPSHOT_CACHE_SEC = 2  # 缓存 2 秒，避免高频刷新时重复计算


def start():
    """启动 tracemalloc（只调一次）"""
    global _started
    if _started:
        return
    import tracemalloc
    tracemalloc.start(25)  # 保留 25 帧，足够定位到模块
    _started = True
    _log.info("Memory monitor started (tracemalloc)")


def register_model(name: str, model_or_path, description: str = "", category: str = "模型"):
    """注册一个 PyTorch 模型，自动计算参数内存

    Args:
        name: 显示名称，如 "VITS Paimon"
        model_or_path: torch.nn.Module 或模型文件路径
        description: 补充说明
        category: 分组（模型/ONNX/其他）
    """
    size = _measure_model(model_or_path)
    with _lock:
        _models[name] = {
            "description": description,
            "size_bytes": size,
            "category": category,
        }
    _log.info("Memory monitor: %s = %.1f MB", name, size / (1024 * 1024))


def register_component(name: str, description: str = "", size_bytes: int = 0, category: str = "组件"):
    """注册非模型组件，如缓存、日志缓冲等"""
    with _lock:
        _components[name] = {
            "description": description,
            "size_bytes": size_bytes,
            "category": category,
        }


def update_component(name: str, size_bytes: int):
    """更新组件大小（如 TTS 缓存在变化）"""
    with _lock:
        if name in _components:
            _components[name]["size_bytes"] = size_bytes


def _measure_model(model_or_path) -> int:
    """测量 PyTorch 模型或 ONNX 会话的内存占用"""
    try:
        import torch
        if isinstance(model_or_path, torch.nn.Module):
            total = 0
            for p in model_or_path.parameters():
                total += p.numel() * p.element_size()
            return total
    except ImportError:
        pass

    # ONNX 会话：无法直接测量，估算
    if hasattr(model_or_path, "_model_path"):
        path = model_or_path._model_path
        if os.path.isfile(path):
            return os.path.getsize(path)
    if isinstance(model_or_path, str) and os.path.isfile(model_or_path):
        return os.path.getsize(model_or_path)

    return 0


def _get_tracemalloc_stats() -> list[dict]:
    """获取 tracemalloc 按模块分组的统计"""
    if not _started:
        return []
    try:
        import tracemalloc
    except ImportError:
        return []

    snap = tracemalloc.take_snapshot()
    stats = snap.statistics("traceback")
    # 聚合到模块名
    module_sizes: dict[str, int] = {}
    for s in stats:
        mod = _classify_traceback(s.traceback)
        module_sizes[mod] = module_sizes.get(mod, 0) + s.size

    result = []
    for mod, size in sorted(module_sizes.items(), key=lambda x: -x[1]):
        result.append({"name": mod, "size_bytes": size, "category": "Python 分配"})
    return result


def _classify_traceback(tb) -> str:
    """将 tracemalloc traceback 分类到模块名"""
    # 已知模式
    patterns = [
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
    for frame in tb:
        fname = frame.filename
        for pattern, label in patterns:
            if pattern in fname.lower():
                return label
    return "其他 Python"


def get_report() -> dict:
    """生成完整内存报告

    Returns:
        {
            "total_rss": int,          # 进程总 RSS（字节）
            "total_rss_mb": float,
            "models": [{name, size_bytes, size_mb, category, description}],
            "components": [{...}],
            "tracemalloc": [{name, size_bytes, size_mb, category}],
            "summary": [{name, size_mb, percent}],  # 汇总饼图数据
            "gc_stats": {...},
            "timestamp": float,
        }
    """
    global _last_snapshot, _last_snapshot_time
    now = time.time()
    if _last_snapshot and (now - _last_snapshot_time) < SNAPSHOT_CACHE_SEC:
        return _last_snapshot

    # 进程 RSS
    total_rss = 0
    try:
        import psutil
        total_rss = psutil.Process(os.getpid()).memory_info().rss
    except ImportError:
        pass

    # 模型
    models = []
    with _lock:
        for name, info in _models.items():
            models.append({
                "name": name,
                "size_bytes": info["size_bytes"],
                "size_mb": round(info["size_bytes"] / (1024 * 1024), 1),
                "category": info["category"],
                "description": info.get("description", ""),
            })

        # 组件
        components = []
        for name, info in _components.items():
            components.append({
                "name": name,
                "size_bytes": info["size_bytes"],
                "size_mb": round(info["size_bytes"] / (1024 * 1024), 1),
                "category": info["category"],
                "description": info.get("description", ""),
            })

    # tracemalloc
    tm_stats = _get_tracemalloc_stats()
    tm_items = []
    for s in tm_stats:
        tm_items.append({
            "name": s["name"],
            "size_bytes": s["size_bytes"],
            "size_mb": round(s["size_bytes"] / (1024 * 1024), 1),
            "category": s["category"],
        })

    # 汇总饼图数据（取 TOP 15）
    all_items = []
    for m in models:
        all_items.append({"name": m["name"], "size_mb": m["size_mb"], "category": m["category"]})
    for c in components:
        all_items.append({"name": c["name"], "size_mb": c["size_mb"], "category": c["category"]})
    for t in tm_items:
        all_items.append({"name": t["name"], "size_mb": t["size_mb"], "category": t["category"]})

    all_items.sort(key=lambda x: -x["size_mb"])
    accounted_mb = sum(i["size_mb"] for i in all_items)
    other_mb = max(0, round(total_rss / (1024 * 1024), 1) - accounted_mb)
    if other_mb > 0.5:
        all_items.append({"name": "未分类（系统开销+碎片）", "size_mb": round(other_mb, 1), "category": "系统"})

    summary = all_items[:15]

    # GC 统计
    gc_stats = {
        "counts": gc.get_count(),
        "threshold": gc.get_threshold(),
    }
    try:
        raw_stats = gc.get_stats()
        gc_stats["details"] = [{"gen": i, **s} for i, s in enumerate(raw_stats)]
    except Exception:
        gc_stats["details"] = []

    report = {
        "total_rss": total_rss,
        "total_rss_mb": round(total_rss / (1024 * 1024), 1),
        "models": models,
        "components": components,
        "tracemalloc": tm_items,
        "summary": summary,
        "gc_stats": gc_stats,
        "timestamp": now,
    }
    _last_snapshot = report
    _last_snapshot_time = now
    return report


def gc_now() -> dict:
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
