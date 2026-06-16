"""FastAPI Web 管理界面 — 用户 + 声纹管理（分页 + 下拉选用户）"""
import os
import subprocess
import tempfile
import time
import db
import tts_api
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="派萌助手")
app.include_router(tts_api.router)

PAGE_SIZE = 20

# ---- SPA 静态文件 ----
import os as _os
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIST = "frontend/dist"
if _os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=f"{_FRONTEND_DIST}/assets"), name="assets")

_INDEX_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>派萌助手 · 声纹管理</title>
<script type="module" crossorigin src="/assets/index-B6mKfYOL.js"></script>
<link rel="stylesheet" crossorigin href="/assets/index-Bl5hNFR3.css">
</head>
<body>
<div id="root"></div>
</body>
</html>"""
# 生产环境自动替换为 Vite 构建的 index.html
import os as _os2
_dist_index = "frontend/dist/index.html"
if _os2.path.exists(_dist_index):
    with open(_dist_index, encoding="utf-8") as _f:
        _INDEX_HTML = _f.read()


@app.get("/")
async def index():
    from fastapi.responses import HTMLResponse
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
    import voiceprint
    try:
        voiceprint.load()
        emb = voiceprint.extract(path)
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
    import voiceprint

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
        voiceprint.load()
        emb = voiceprint.extract(tmp_path)
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
    import llm
    reply = llm.chat(req.text.strip(), req.user_id, req.speaker)
    return {"reply": reply}


# ---- SPA fallback（必须放在所有路由之后） ----
@app.get("/{path:path}")
async def spa_fallback(path: str):
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_INDEX_HTML)
