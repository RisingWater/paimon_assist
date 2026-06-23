"""FastAPI Web 管理界面 — 用户 + 声纹管理（分页 + 下拉选用户）"""
import os
import subprocess
import tempfile
import time
import db
from tts import api as tts_api
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="派萌助手")
app.include_router(tts_api.router)

PAGE_SIZE = 20

# ---- SPA 静态文件 ----
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIST = "frontend/dist"
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=f"{_FRONTEND_DIST}/assets"), name="spa-assets")

_INDEX_HTML = ""
_dist_index = "frontend/dist/index.html"
if os.path.isfile(_dist_index):
    with open(_dist_index, encoding="utf-8") as _f:
        _INDEX_HTML = _f.read()


@app.get("/")
async def index():
    from fastapi.responses import HTMLResponse
    if not _INDEX_HTML:
        raise HTTPException(503, "前端未构建，请运行: cd frontend && bun run build")
    return HTMLResponse(_INDEX_HTML)


# ---- 用户 API ----

@app.get("/api/users")
async def api_list_users():
    return db.list_users()


class CreateUserBody(BaseModel):
    name: str = ""


@app.post("/api/users")
async def api_create_user(body: CreateUserBody):
    uid = db.create_user(body.name)
    return {"id": uid, "name": body.name, "ok": True}


@app.put("/api/users/{user_id}")
async def api_rename_user(user_id: int, name: str):
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    db.rename_user(user_id, name)
    return {"ok": True}


@app.delete("/api/users/{user_id}")
async def api_delete_user(user_id: int):
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u["name"] == "定时任务":
        raise HTTPException(403, "系统用户不可删除")
    db.delete_user(user_id)
    return {"ok": True}


@app.get("/api/users/{user_id}/voiceprints")
async def api_list_user_voiceprints(user_id: int):
    return db.list_voiceprints(user_id)


@app.post("/api/users/{user_id}/voiceprints")
async def api_add_voiceprint(user_id: int, file: UploadFile = File(...)):
    """上传音频文件（WAV/webm），提取声纹并绑定到用户"""
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(404, "用户不存在")

    content = await file.read()
    ts = time.strftime("%Y%m%d_%H%M%S")
    user_dir = f"recordings/{user_id}"
    os.makedirs(user_dir, exist_ok=True)
    path = f"{user_dir}/upload_{ts}.wav"

    # webm → wav 转换（浏览器录音格式）
    if file.filename and file.filename.endswith(".webm") or file.content_type == "audio/webm":
        tmp_webm = tempfile.mktemp(suffix=".webm")
        with open(tmp_webm, "wb") as f:
            f.write(content)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_webm, "-ar", "16000", "-ac", "1", "-f", "wav", path],
            capture_output=True,
        )
        os.unlink(tmp_webm)
    else:
        with open(path, "wb") as f:
            f.write(content)

    # 提取声纹
    from voiceprint import vp_engine
    try:
        vp_engine.load()
        emb = vp_engine.extract(path)
    except Exception as e:
        raise HTTPException(500, f"声纹提取失败: {e}")

    # 保存
    db.enroll(user_id, emb, audio_path=path, vp_type="manual")
    return {"ok": True, "user_id": user_id, "audio_path": path}


# ---- 声纹检测 ----

@app.post("/api/voiceprints/detect")
async def api_detect_voiceprint(file: UploadFile = File(...)):
    """上传音频，返回与库中所有声纹的详细相似度"""
    import numpy as np
    from voiceprint import vp_engine

    content = await file.read()
    ts = time.strftime("%Y%m%d_%H%M%S")
    tmp_path = f"recording_detect_{ts}.wav"

    # webm → wav
    if file.filename and (file.filename.endswith(".webm") or file.content_type == "audio/webm"):
        tmp_webm = tempfile.mktemp(suffix=".webm")
        with open(tmp_webm, "wb") as f:
            f.write(content)
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_webm, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_path],
            capture_output=True,
        )
        os.unlink(tmp_webm)
    else:
        with open(tmp_path, "wb") as f:
            f.write(content)

    try:
        vp_engine.load()
        emb = vp_engine.extract(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # 与每条声纹做余弦相似度
    import db
    rows = []
    conn = db._connect()
    for uid, vec_blob, name in conn.execute(
        "SELECT v.user_id, v.vector, u.name FROM voiceprints v JOIN users u ON v.user_id=u.id"
    ).fetchall():
        stored = np.frombuffer(vec_blob, dtype=np.float32)
        sim = float(np.dot(emb, stored) / (np.linalg.norm(emb) * np.linalg.norm(stored)))
        rows.append({"user_id": uid, "name": name, "vp_id": uid, "sim": sim, "vector_blob": vec_blob})
    conn.close()

    # 重新查完整的声纹 ID
    conn = db._connect()
    all_vps = conn.execute(
        "SELECT v.id, v.user_id, v.vector, u.name FROM voiceprints v JOIN users u ON v.user_id=u.id"
    ).fetchall()
    conn.close()

    details = []
    for vp_id, uid, vec_blob, name in all_vps:
        stored = np.frombuffer(vec_blob, dtype=np.float32)
        sim = float(np.dot(emb, stored) / (np.linalg.norm(emb) * np.linalg.norm(stored)))
        details.append({"vp_id": vp_id, "user_id": uid, "name": name, "sim": sim})

    # 按用户分组
    users_map = {}
    for d in details:
        uid = d["user_id"]
        if uid not in users_map:
            users_map[uid] = {"user_id": uid, "name": d["name"], "voiceprints": [], "avg_sim": 0}
        users_map[uid]["voiceprints"].append({"id": d["vp_id"], "sim": d["sim"]})

    for uid, ug in users_map.items():
        sims = [v["sim"] for v in ug["voiceprints"]]
        ug["avg_sim"] = sum(sims) / len(sims) if sims else 0

    users_list = sorted(users_map.values(), key=lambda u: u["avg_sim"], reverse=True)

    # 按 db.find_best 逻辑判断匹配
    best_uid, best_name, best_avg = db.find_best(emb)

    return {
        "best_uid": best_uid,
        "best_name": best_name,
        "best_avg": best_avg,
        "users": users_list,
    }


# ---- 声纹 API ----

@app.put("/api/voiceprints/{vp_id}/move")
async def api_move_voiceprint(vp_id: int, target_user_id: int):
    """将声纹移动到另一个用户"""
    vp = db.get_voiceprint(vp_id)
    if not vp:
        raise HTTPException(404, "声纹不存在")
    if not db.get_user(target_user_id):
        raise HTTPException(404, "目标用户不存在")
    db.move_voiceprint(vp_id, target_user_id)
    return {"ok": True}


@app.delete("/api/voiceprints/{vp_id}")
async def api_delete_voiceprint(vp_id: int):
    vp = db.get_voiceprint(vp_id)
    if not vp:
        raise HTTPException(404, "声纹不存在")
    db.delete_voiceprint(vp_id)
    return {"ok": True}


@app.get("/api/voiceprints/{vp_id}/audio")
async def api_get_audio(vp_id: int):
    vp = db.get_voiceprint(vp_id)
    if not vp or not vp.get("audio_path"):
        raise HTTPException(404, "录音不存在")
    path = vp["audio_path"]
    if not os.path.isfile(path):
        raise HTTPException(404, "录音文件已丢失")
    return FileResponse(path, media_type="audio/wav")


# ---- 聊天历史 API ----

@app.get("/api/users/{user_id}/history")
async def api_get_history(user_id: int):
    return db.load_history(user_id)


class UpdateMessageBody(BaseModel):
    content: str


@app.put("/api/history/{msg_id}")
async def api_update_message(msg_id: int, body: UpdateMessageBody):
    db.update_message(msg_id, body.content)
    return {"ok": True}


@app.delete("/api/history/{msg_id}")
async def api_delete_message(msg_id: int):
    db.delete_message(msg_id)
    return {"ok": True}


@app.delete("/api/users/{user_id}/history")
async def api_clear_history(user_id: int):
    db.clear_history(user_id)
    return {"ok": True}


# ---- 快速对话（绕过唤醒/STT，直接测试 LLM + tool call） ----

class ChatRequest(BaseModel):
    text: str
    user_id: int = 0
    speaker: str = ""


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    from llm import llm
    reply = llm.chat(req.text.strip(), req.user_id, req.speaker)
    return {"reply": reply}


# ---- 定时提醒 ----

@app.get("/api/reminders")
async def api_list_reminders():
    return db.list_reminders(include_done=True)


@app.post("/api/reminders")
async def api_add_reminder(req: dict):
    rid = db.add_reminder(
        req.get("user_id", db._ensure_reminder_user()),
        req["content"], req["rtype"], req["datetime"],
        req.get("lunar", False),
    )
    return {"id": rid, "ok": True}


@app.put("/api/reminders/{rid}")
async def api_update_reminder(rid: int, req: dict):
    # 简单实现：删除旧 + 添加新
    db.delete_reminder(rid)
    new_id = db.add_reminder(
        req.get("user_id", db._ensure_reminder_user()),
        req["content"], req["rtype"], req["datetime"],
        req.get("lunar", False),
    )
    return {"id": new_id, "ok": True}


@app.delete("/api/reminders/{rid}")
async def api_delete_reminder(rid: int):
    db.delete_reminder(rid)
    return {"ok": True}


# ---- 内存监控 API（必须在 /api/memory/{name} 之前，否则 "report" 被 {name} 吃掉） ----

@app.get("/api/memory_track/report")
async def api_memory_report():
    """获取各模块内存占用报告"""
    import traceback
    try:
        report = MemoryMonitor.instance().get_report()
        if not isinstance(report.get("summary"), list):
            report["summary"] = []
        return report
    except Exception:
        traceback.print_exc()
        return {
            "total_rss": 0, "total_rss_mb": 0,
            "tracked": [], "tracemalloc": [], "summary": [],
            "gc_stats": {"counts": [0, 0, 0], "threshold": [700, 10, 10], "details": []},
            "timestamp": 0,
            "error": traceback.format_exc(),
        }


@app.post("/api/memory_track/gc")
async def api_memory_gc():
    """手动触发垃圾回收"""
    return MemoryMonitor.instance().gc_now()


# ---- 记忆编辑 ----

@app.get("/api/memory/{name}")
async def api_read_memory(name: str):
    """读取记忆文件。name='long' 读长期记忆，数字=user_id 读中期记忆"""
    import llm_tools.memory as _mem
    try:
        if name == "long":
            path = _mem._MEMORY_FILE
        elif name.isdigit():
            path = _mem._midterm_file(int(name))
        else:
            raise HTTPException(400, "无效的记忆名称")
        if not os.path.isfile(path):
            return {"content": ""}
        with open(path, encoding="utf-8") as f:
            return {"content": f.read()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/api/memory/{name}")
async def api_save_memory(name: str, req: dict):
    """保存记忆文件，自动重建摘要"""
    import llm_tools.memory as _mem
    content = req.get("content", "")
    try:
        if name == "long":
            path = _mem._MEMORY_FILE
        elif name.isdigit():
            path = _mem._midterm_file(int(name))
        else:
            raise HTTPException(400, "无效的记忆名称")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        # Web 编辑后立即用 LLM 重建摘要
        if name == "long":
            _mem.rebuild_summary_async()  # 阻塞，等 LLM 完
        else:
            uid = int(name)
            _mem.rebuild_midterm_llm(uid)  # 阻塞，等 LLM 完
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ---- 工具配置 ----

# ---- 系统配置 ----

from settings import settings as app_settings

_tts_backend = app_settings.get("tts_backend")


@app.get("/api/tool-config")
async def api_get_tool_config():
    from llm_tools import tools as tool_registry
    default_silent = tool_registry.get_default_silent_tools()
    tool_list = []
    for s in tool_registry.get_schemas():
        name = s["function"]["name"]
        tool_list.append({
            "name": name,
            "description": s["function"]["description"],
            "silent_default": name in default_silent,
        })
    return {"tools": tool_list, "silent": list(app_settings.get_silent_tools())}


@app.put("/api/tool-config")
async def api_save_tool_config(req: dict):
    app_settings.set_silent_tools(set(req.get("silent", [])))
    return {"ok": True}


@app.get("/api/system-config")
async def api_get_system_config():
    return {
        "tts_backend": app_settings.get("tts_backend"),
        "wakeword_enabled": app_settings.get("wakeword_enabled"),
        "wakeword_schedule_enabled": app_settings.get("wakeword_schedule_enabled"),
        "wakeword_start": app_settings.get("wakeword_start"),
        "wakeword_end": app_settings.get("wakeword_end"),
    }


@app.put("/api/system-config")
async def api_save_system_config(req: dict):
    global _tts_backend
    backend = req.get("tts_backend", "vits")
    app_settings.set_config("tts_backend", backend)
    _tts_backend = backend

    if "wakeword_enabled" in req:
        app_settings.set_config("wakeword_enabled", bool(req["wakeword_enabled"]))
    if "wakeword_schedule_enabled" in req:
        app_settings.set_config("wakeword_schedule_enabled", bool(req["wakeword_schedule_enabled"]))
    if "wakeword_start" in req:
        app_settings.set_config("wakeword_start", req["wakeword_start"])
    if "wakeword_end" in req:
        app_settings.set_config("wakeword_end", req["wakeword_end"])

    return {"ok": True, "tts_backend": backend}


# ---- TTS 缓存管理 ----

@app.get("/api/tts-cache")
async def api_cache_list(search: str = "", limit: int = 100):
    return db.cache_list(search, limit)


@app.get("/__cache_audio/{cache_id}")
async def api_cache_audio(cache_id: int):
    from fastapi.responses import FileResponse
    items = db.cache_list(limit=1000)
    for it in items:
        if it["id"] == cache_id and os.path.isfile(it["audio_path"]):
            return FileResponse(it["audio_path"], media_type="audio/wav")
    raise HTTPException(404, "缓存文件不存在")


@app.delete("/api/tts-cache/{cache_id}")
async def api_cache_delete(cache_id: int):
    db.cache_delete(cache_id)
    return {"ok": True}


@app.delete("/api/tts-cache")
async def api_cache_clear():
    db.cache_clear()
    return {"ok": True}
# ---- 备份/恢复 ----

_BACKUP_DIR = "backups"

def _create_zip() -> bytes:
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ["db/paimon.db", ".env", "settings/settings.json"]:
            if os.path.isfile(path): zf.write(path)
        for d in ["memory", "recordings", "models/tts_cache", "settings"]:
            if os.path.isdir(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        zf.write(os.path.join(root, f))
    buf.seek(0)
    return buf.read()


@app.post("/api/backup")
async def api_create_backup():
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"paimon_{ts}.zip"
    with open(os.path.join(_BACKUP_DIR, filename), "wb") as f:
        f.write(_create_zip())
    return {"ok": True, "filename": filename}


@app.get("/api/backups")
async def api_list_backups():
    if not os.path.isdir(_BACKUP_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(_BACKUP_DIR) if f.endswith(".zip")],
        reverse=True,
    )
    return [{"filename": f, "size": os.path.getsize(os.path.join(_BACKUP_DIR, f))} for f in files]


@app.get("/api/backups/{filename}")
async def api_download_backup(filename: str):
    path = os.path.join(_BACKUP_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "备份不存在")
    return FileResponse(path, media_type="application/zip",
        filename=filename)


@app.post("/api/backups/upload")
async def api_upload_backup(file: UploadFile = File(...)):
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    fname = file.filename or f"upload_{int(time.time())}.zip"
    with open(os.path.join(_BACKUP_DIR, fname), "wb") as f:
        f.write(await file.read())
    return {"ok": True, "filename": fname}


@app.post("/api/backups/{filename}/restore")
async def api_restore_backup(filename: str):
    import zipfile, io
    path = os.path.join(_BACKUP_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "备份不存在")
    with zipfile.ZipFile(path) as zf:
        zf.extractall(".")
    return {"ok": True, "message": f"已从 {filename} 恢复，重启生效"}


# ---- 日志查看 ----

from fastapi.responses import PlainTextResponse
from log_manager import log_mgr
from memory_monitor import MemoryMonitor


@app.get("/api/logs")
async def api_get_logs(
    level: str = "",
    search: str = "",
    limit: int = 200,
    offset: int = 0,
):
    """查询内存日志，支持级别过滤、关键词搜索、分页"""
    return log_mgr.get_logs(
        level=level or None,
        search=search or None,
        limit=min(limit, 1000),
        offset=offset,
    )


@app.get("/api/logs/export")
async def api_export_logs():
    """导出全部日志为纯文本文件"""
    text = log_mgr.export_text()
    ts = time.strftime("%Y%m%d_%H%M%S")
    return PlainTextResponse(
        text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=paimon_logs_{ts}.txt"},
    )


@app.delete("/api/logs")
async def api_clear_logs():
    """清空内存日志"""
    log_mgr.clear()
    return {"ok": True}


# ---- 唤醒词音频管理 ----

_WW_DIR = "wakeword"


@app.get("/api/wakeword/list")
async def api_wakeword_list(category: str = "positive"):
    """列出唤醒词音频文件"""
    if category not in ("positive", "negative"):
        raise HTTPException(400, "category 必须是 positive 或 negative")
    d = os.path.join(_WW_DIR, category)
    if not os.path.isdir(d):
        return []
    files = []
    for fn in sorted(os.listdir(d), reverse=True):
        if fn.endswith(".wav"):
            fp = os.path.join(d, fn)
            files.append({"filename": fn, "size": os.path.getsize(fp), "mtime": os.path.getmtime(fp)})
    return files


@app.get("/api/wakeword/audio/{category}/{filename}")
async def api_wakeword_audio(category: str, filename: str):
    """播放唤醒词音频"""
    if category not in ("positive", "negative"):
        raise HTTPException(400)
    path = os.path.join(_WW_DIR, category, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(path, media_type="audio/wav")


class WakewordMoveBody(BaseModel):
    filename: str
    from_category: str
    to_category: str


@app.put("/api/wakeword/move")
async def api_wakeword_move(body: WakewordMoveBody):
    """在 positive/negative 之间移动"""
    src = os.path.join(_WW_DIR, body.from_category, body.filename)
    dst = os.path.join(_WW_DIR, body.to_category, body.filename)
    if not os.path.isfile(src):
        raise HTTPException(404, "源文件不存在")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)
    return {"ok": True}


@app.delete("/api/wakeword/{category}/{filename}")
async def api_wakeword_delete(category: str, filename: str):
    """删除唤醒词音频"""
    path = os.path.join(_WW_DIR, category, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "文件不存在")
    os.remove(path)
    return {"ok": True}


@app.get("/{path:path}")
async def spa_fallback(path: str):
    # API 和静态资源不走 fallback
    if path.startswith("api/") or path.startswith("assets/"):
        raise HTTPException(404)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_INDEX_HTML)
