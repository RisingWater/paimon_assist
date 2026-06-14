"""FastAPI Web 管理界面 — 用户 + 声纹管理（分页 + 下拉选用户）"""
import os
import subprocess
import tempfile
import time
import db
import tts_api
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="派萌助手")
app.include_router(tts_api.router)

# 每页用户数
PAGE_SIZE = 20

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>派萌助手 · 声纹管理</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui, sans-serif; background:#1a1a2e; color:#eee; min-height:100vh; }
header { background:#16213e; padding:16px 32px; display:flex; align-items:center; gap:16px; border-bottom:2px solid #0f3460; }
header h1 { font-size:20px; color:#e94560; }
header span { color:#888; font-size:13px; }
.container { max-width:960px; margin:24px auto; padding:0 20px; }
.toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.toolbar button { background:#0f3460; color:#eee; border:none; padding:7px 16px; border-radius:6px; cursor:pointer; font-size:13px; }
.toolbar button:hover { background:#1a4a8a; }
.stats { color:#888; font-size:13px; }
.pager { display:flex; gap:4px; justify-content:center; margin:16px 0; }
.pager button { background:#0f3460; color:#eee; border:none; padding:4px 12px; border-radius:4px; cursor:pointer; font-size:12px; }
.pager button.active { background:#e94560; }
.pager button:hover { background:#1a4a8a; }
.pager button:disabled { opacity:0.3; cursor:default; }
.user-card { background:#16213e; border-radius:8px; padding:14px 18px; margin-bottom:12px; border-left:3px solid #0f3460; }
.user-header { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.user-header .display { cursor:pointer; font-size:15px; font-weight:600; }
.user-header .display:hover { color:#e94560; }
.user-header input { background:#0f3460; color:#eee; border:1px solid #e94560; padding:4px 8px; border-radius:4px; font-size:13px; width:120px; outline:none; }
.user-header .uid { color:#555; font-size:11px; }
.user-prints { display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }
.vp-item { display:flex; align-items:center; gap:6px; background:#0f3460; padding:4px 10px; border-radius:4px; font-size:12px; }
.vp-item audio { height:20px; width:110px; }
.btn-sm { border:none; padding:3px 10px; border-radius:4px; cursor:pointer; font-size:11px; }
.btn-edit { background:#0f3460; color:#c0d0f0; }
.btn-edit:hover { background:#1a4a8a; }
.btn-del { background:#5c1a1a; color:#e0a0a0; }
.btn-del:hover { background:#7a2626; }
select { background:#0f3460; color:#eee; border:1px solid #1a4a8a; padding:3px 8px; border-radius:4px; font-size:12px; outline:none; }
.empty { text-align:center; color:#666; padding:60px 0; }
.error { text-align:center; color:#e94560; padding:60px 0; }
.toast { position:fixed; bottom:30px; right:30px; background:#0f3460; color:#eee; padding:10px 22px; border-radius:8px; font-size:13px; opacity:0; transition:opacity .3s; z-index:99; }
.toast.show { opacity:1; }
</style>
</head>
<body>

<header>
  <h1>派萌助手</h1>
  <span>用户 & 声纹管理</span>
</header>

<div class="container">
  <div class="toolbar">
    <div class="stats" id="stats">加载中...</div>
    <div style="display:flex;gap:8px">
      <button onclick="showCreateUser()">+ 新建用户</button>
      <button onclick="showAddVoiceprint()">+ 添加声纹</button>
      <button onclick="showDetect()">🔍 声纹检测</button>
      <button onclick="loadPage(currentPage)">刷新</button>
    </div>
  </div>
  <div id="list"></div>
  <div class="pager" id="pager"></div>
  <div class="empty" id="empty" style="display:none">
    <p>还没有用户</p>
    <small>点击 "+ 新建用户" 或唤醒一次派萌自动注册</small>
  </div>

  <!-- 新建用户弹窗 -->
  <div id="dlg-create" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
    <div style="background:#16213e;padding:24px;border-radius:12px;min-width:360px">
      <h3 style="margin-bottom:16px;color:#e94560">新建用户</h3>
      <input id="new-user-name" type="text" placeholder="用户名字（可选）" style="width:100%;background:#0f3460;color:#eee;border:1px solid #1a4a8a;padding:8px 12px;border-radius:6px;font-size:14px;outline:none;margin-bottom:16px">
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button onclick="document.getElementById('dlg-create').style.display='none'" style="background:#333;color:#eee;border:none;padding:8px 20px;border-radius:6px;cursor:pointer">取消</button>
        <button onclick="createUser()" style="background:#e94560;color:#eee;border:none;padding:8px 20px;border-radius:6px;cursor:pointer">创建</button>
      </div>
    </div>
  </div>

  <!-- 添加声纹弹窗 -->
  <div id="dlg-vp" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
    <div style="background:#16213e;padding:24px;border-radius:12px;min-width:380px">
      <h3 style="margin-bottom:16px;color:#e94560">添加声纹</h3>
      <label style="font-size:13px;color:#888">目标用户</label>
      <select id="vp-user" style="width:100%;background:#0f3460;color:#eee;border:1px solid #1a4a8a;padding:8px 12px;border-radius:6px;font-size:14px;outline:none;margin-bottom:16px;margin-top:4px"></select>

      <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px">
        <button id="btn-record" onclick="toggleRecord()" style="background:#e94560;color:#eee;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;min-width:100px">🎤 录音</button>
        <span id="rec-status" style="color:#888;font-size:13px">点击按钮开始录音</span>
      </div>

      <label style="font-size:13px;color:#888">或选择本地 WAV 文件</label>
      <input id="vp-file" type="file" accept=".wav" style="width:100%;background:#0f3460;color:#eee;border:1px solid #1a4a8a;padding:8px 12px;border-radius:6px;font-size:14px;outline:none;margin-bottom:16px;margin-top:4px">
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button onclick="closeVpDlg()" style="background:#333;color:#eee;border:none;padding:8px 20px;border-radius:6px;cursor:pointer">取消</button>
        <button onclick="uploadVoiceprint()" style="background:#e94560;color:#eee;border:none;padding:8px 20px;border-radius:6px;cursor:pointer">上传</button>
      </div>
    </div>
  <!-- 声纹检测弹窗 -->
  <div id="dlg-detect" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
    <div style="background:#16213e;padding:24px;border-radius:12px;min-width:500px;max-height:80vh;overflow-y:auto">
      <h3 style="margin-bottom:16px;color:#e94560">🔍 声纹检测</h3>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:16px">
        <button id="detect-btn" onclick="detectToggleRecord()" style="background:#e94560;color:#eee;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;min-width:100px">🎤 录音</button>
        <span id="detect-status" style="color:#888;font-size:13px">录一段声音，检测是谁</span>
      </div>
      <div id="detect-result" style="font-size:13px"></div>
      <div style="margin-top:16px;text-align:right">
        <button onclick="closeDetect()" style="background:#333;color:#eee;border:none;padding:8px 20px;border-radius:6px;cursor:pointer">关闭</button>
      </div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentPage = 1;
let totalPages = 1;
let allUsers = [];
let editingUid = null;

async function loadPage(page) {
  currentPage = page;
  try {
    const uRes = await fetch("/api/users");
    if (!uRes.ok) throw new Error("API error: " + uRes.status);
    allUsers = await uRes.json();
  } catch (e) {
    document.getElementById("stats").textContent = "加载失败: " + e.message;
    document.getElementById("list").innerHTML = '<div class="error">API 连接失败，请检查服务是否正常</div>';
    return;
  }

  totalPages = Math.max(1, Math.ceil(allUsers.length / 20));
  if (page > totalPages) page = totalPages;
  if (page < 1) page = 1;
  currentPage = page;

  document.getElementById("stats").textContent = allUsers.length + " 个用户 (第 " + page + "/" + totalPages + " 页)";

  if (allUsers.length === 0) {
    document.getElementById("list").innerHTML = "";
    document.getElementById("pager").innerHTML = "";
    document.getElementById("empty").style.display = "block";
    return;
  }
  document.getElementById("empty").style.display = "none";

  const start = (page - 1) * 20;
  const pageUsers = allUsers.slice(start, start + 20);

  let html = "";
  for (const u of pageUsers) {
    // 获取该用户的声纹列表
    let vps = [];
    try {
      const vRes = await fetch("/api/users/" + u.id + "/voiceprints");
      vps = vRes.ok ? await vRes.json() : [];
    } catch (e) {}

    const displayName = u.name || "用户#" + u.id;
    const style = u.name ? "" : "color:#888;font-style:italic";
    html += '<div class="user-card">';
    html += '<div class="user-header">';
    html += '<span class="display" style="' + style + '" id="display-' + u.id + '" onclick="startEdit(' + u.id + ',\'' + esc(u.name) + '\')">' + esc(displayName) + '</span>';
    html += '<input type="text" id="input-' + u.id + '" value="' + esc(u.name) + '" style="display:none" placeholder="输入名字..." onkeydown="if(event.key===&#39;Enter&#39;)saveEdit(' + u.id + ')" onblur="saveEdit(' + u.id + ')">';
    html += '<span class="uid">#' + u.id + '</span>';
    html += '<span style="flex:1"></span>';
    html += '<button class="btn-sm btn-del" onclick="deleteUser(' + u.id + ',\'' + esc(displayName) + '\')">删除用户</button>';
    html += '</div>';
    html += '<div class="user-prints">';
    html += '<span style="color:#666;font-size:11px">声纹 (' + vps.length + '):</span>';
    // 下拉框：把声纹移动到其他用户
    html += '<select onchange="moveVp(this.value)" data-vp=""><option value="">移动声纹到...</option>';
    for (const t of allUsers) {
      if (t.id !== u.id) {
        html += '<option value="' + t.id + '">' + esc(t.name || "用户#" + t.id) + '</option>';
      }
    }
    html += '</select>';
    for (const vp of vps) {
      html += '<div class="vp-item">';
      html += '<span>#' + vp.id + '</span>';
      if (vp.audio_path) {
        html += '<audio controls src="/api/voiceprints/' + vp.id + '/audio"></audio>';
      }
      html += '<button class="btn-sm btn-del" onclick="deleteVp(' + vp.id + ')">x</button>';
      html += '</div>';
    }
    html += '</div></div>';
  }
  document.getElementById("list").innerHTML = html;

  // 分页按钮
  let pHtml = "";
  pHtml += '<button onclick="loadPage(' + (page-1) + ')" ' + (page<=1?'disabled':'') + '>上一页</button>';
  for (let p = 1; p <= totalPages; p++) {
    pHtml += '<button onclick="loadPage(' + p + ')" ' + (p===page?'class="active"':'') + '>' + p + '</button>';
  }
  pHtml += '<button onclick="loadPage(' + (page+1) + ')" ' + (page>=totalPages?'disabled':'') + '>下一页</button>';
  document.getElementById("pager").innerHTML = pHtml;
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

function startEdit(uid, name) {
  if (editingUid !== null) saveEdit(editingUid);
  editingUid = uid;
  document.getElementById("display-" + uid).style.display = "none";
  const inp = document.getElementById("input-" + uid);
  inp.style.display = "inline-block";
  inp.value = name;
  inp.focus(); inp.select();
}

async function saveEdit(uid) {
  if (editingUid !== uid) return;
  editingUid = null;
  const name = document.getElementById("input-" + uid).value.trim();
  document.getElementById("input-" + uid).style.display = "none";
  document.getElementById("display-" + uid).style.display = "inline";
  if (!name) return;
  try {
    const res = await fetch("/api/users/" + uid + "?name=" + encodeURIComponent(name), { method: "PUT" });
    if (res.ok) {
      document.getElementById("display-" + uid).textContent = name;
      document.getElementById("display-" + uid).style.color = "";
      document.getElementById("display-" + uid).style.fontStyle = "";
      toast("已命名: " + name);
      loadPage(currentPage);
    }
  } catch (e) { toast("保存失败: " + e); }
}

async function deleteUser(uid, name) {
  if (!confirm("确定删除 \"" + name + "\" 及其所有声纹？")) return;
  try {
    await fetch("/api/users/" + uid, { method: "DELETE" });
    toast("已删除 " + name);
    loadPage(currentPage);
  } catch (e) { toast("删除失败"); }
}

async function deleteVp(vpId) {
  if (!confirm("删除这条声纹？")) return;
  try {
    await fetch("/api/voiceprints/" + vpId, { method: "DELETE" });
    toast("已删除声纹");
    loadPage(currentPage);
  } catch (e) { toast("删除失败"); }
}

async function moveVp(targetUid) {
  // TODO: 声纹移动接口（暂未实现）
}

function showCreateUser() {
  document.getElementById("new-user-name").value = "";
  document.getElementById("dlg-create").style.display = "flex";
}

async function createUser() {
  const name = document.getElementById("new-user-name").value.trim();
  try {
    const res = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name })
    });
    if (res.ok) {
      document.getElementById("dlg-create").style.display = "none";
      toast("用户已创建");
      loadPage(currentPage);
    } else {
      toast("创建失败: " + (await res.text()));
    }
  } catch (e) { toast("创建失败: " + e); }
}

// ---- 浏览器录音 ----
let mediaRecorder = null;
let audioChunks = [];
let recordedBlob = null;

async function toggleRecord() {
  const btn = document.getElementById("btn-record");
  const status = document.getElementById("rec-status");

  if (mediaRecorder && mediaRecorder.state === "recording") {
    // 停止录音
    mediaRecorder.stop();
    btn.textContent = "🎤 录音";
    btn.style.background = "#e94560";
    status.textContent = "录音完成，点击上传提交";
  } else {
    // 开始录音
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunks = [];
      recordedBlob = null;

      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = () => {
        recordedBlob = new Blob(audioChunks, { type: "audio/webm" });
        stream.getTracks().forEach(t => t.stop());
      };

      mediaRecorder.start();
      btn.textContent = "⏹ 停止";
      btn.style.background = "#c0392b";
      status.textContent = "正在录音...对着麦克风说话";
    } catch (e) {
      toast("无法访问麦克风: " + e.message);
    }
  }
}

function closeVpDlg() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
  document.getElementById("dlg-vp").style.display = "none";
  document.getElementById("btn-record").textContent = "🎤 录音";
  document.getElementById("btn-record").style.background = "#e94560";
  document.getElementById("rec-status").textContent = "点击按钮开始录音";
  recordedBlob = null;
}

function showAddVoiceprint() {
  let opts = "";
  for (const u of allUsers) {
    const dn = u.name || "用户#" + u.id;
    opts += '<option value="' + u.id + '">' + esc(dn) + '</option>';
  }
  if (!opts) { toast("请先创建用户"); return; }
  document.getElementById("vp-user").innerHTML = opts;
  document.getElementById("vp-file").value = "";
  recordedBlob = null;
  document.getElementById("rec-status").textContent = "点击按钮开始录音";
  document.getElementById("dlg-vp").style.display = "flex";
}

async function uploadVoiceprint() {
  const uid = document.getElementById("vp-user").value;
  const fileInput = document.getElementById("vp-file");
  const fd = new FormData();

  if (recordedBlob) {
    // 使用录音
    fd.append("file", recordedBlob, "recording.webm");
  } else if (fileInput.files[0]) {
    // 使用本地文件
    fd.append("file", fileInput.files[0]);
  } else {
    toast("请先录音或选择文件"); return;
  }

  try {
    const res = await fetch("/api/users/" + uid + "/voiceprints", { method: "POST", body: fd });
    if (res.ok) {
      closeVpDlg();
      toast("声纹已添加");
      loadPage(currentPage);
    } else {
      toast("上传失败: " + (await res.text()));
    }
  } catch (e) { toast("上传失败: " + e); }
}

// ---- 声纹检测 ----
let detectRecorder = null;
let detectChunks = [];
let detectBlob = null;

async function detectToggleRecord() {
  const btn = document.getElementById("detect-btn");
  const status = document.getElementById("detect-status");

  if (detectRecorder && detectRecorder.state === "recording") {
    detectRecorder.stop();
    btn.textContent = "🎤 录音";
    btn.style.background = "#e94560";
    status.textContent = "正在分析...";
  } else {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      detectRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      detectChunks = [];
      detectBlob = null;
      document.getElementById("detect-result").innerHTML = "";

      detectRecorder.ondataavailable = e => detectChunks.push(e.data);
      detectRecorder.onstop = async () => {
        detectBlob = new Blob(detectChunks, { type: "audio/webm" });
        stream.getTracks().forEach(t => t.stop());
        await runDetection();
      };

      detectRecorder.start();
      btn.textContent = "⏹ 停止";
      btn.style.background = "#c0392b";
      status.textContent = "正在录音...";
    } catch (e) {
      toast("无法访问麦克风: " + e.message);
    }
  }
}

async function runDetection() {
  if (!detectBlob) return;
  const fd = new FormData();
  fd.append("file", detectBlob, "detect.webm");

  try {
    const res = await fetch("/api/voiceprints/detect", { method: "POST", body: fd });
    if (!res.ok) { toast("检测失败"); return; }
    const data = await res.json();

    document.getElementById("detect-status").textContent =
      data.best_uid ? ("识别结果: " + (data.best_name || "用户#" + data.best_uid) + " (sim=" + data.best_avg.toFixed(4) + ")") : "未匹配到任何人";

    let html = "";
    for (const ug of data.users) {
      const dn = ug.name || "用户#" + ug.user_id;
      html += '<div style="background:#0f3460;padding:10px 14px;border-radius:6px;margin-bottom:8px">';
      html += '<strong>' + esc(dn) + '</strong> (avg=' + ug.avg_sim.toFixed(4) + ')';
      html += '<div style="margin-top:4px">';
      for (const vp of ug.voiceprints) {
        const c = vp.sim > 0.5 ? "#a0e0a0" : "#888";
        html += '<span style="color:' + c + ';margin-right:12px;font-size:11px">#' + vp.id + ': ' + vp.sim.toFixed(4) + '</span>';
      }
      html += '</div></div>';
    }
    document.getElementById("detect-result").innerHTML = html;
  } catch (e) { toast("检测失败: " + e); }
}

function showDetect() {
  detectBlob = null;
  document.getElementById("detect-result").innerHTML = "";
  document.getElementById("detect-status").textContent = "录一段声音，检测是谁";
  document.getElementById("detect-btn").textContent = "🎤 录音";
  document.getElementById("detect-btn").style.background = "#e94560";
  document.getElementById("dlg-detect").style.display = "flex";
}

function closeDetect() {
  if (detectRecorder && detectRecorder.state === "recording") detectRecorder.stop();
  document.getElementById("dlg-detect").style.display = "none";
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2000);
}

loadPage(1);
</script>

</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


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

    # webm → wav 转换（浏览器录音格式）
    if file.filename and file.filename.endswith(".webm") or file.content_type == "audio/webm":
        tmp_webm = tempfile.mktemp(suffix=".webm")
        with open(tmp_webm, "wb") as f:
            f.write(content)
        path = f"recording_upload_{ts}_{user_id}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_webm, "-ar", "16000", "-ac", "1", "-f", "wav", path],
            capture_output=True,
        )
        os.unlink(tmp_webm)
    else:
        path = f"recording_upload_{ts}_{user_id}.wav"
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
    db.enroll(user_id, emb, audio_path=path)
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
