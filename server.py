"""FastAPI Web 管理界面 — 用户 + 声纹管理"""
import os
import db
import tts_api
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="派萌助手")
app.include_router(tts_api.router)

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>派萌助手 · 声纹管理</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui, sans-serif; background:#1a1a2e; color:#eee; min-height:100vh; }
header { background:#16213e; padding:20px 40px; display:flex; align-items:center; gap:16px; border-bottom:2px solid #0f3460; }
header h1 { font-size:22px; color:#e94560; }
header span { color:#888; font-size:14px; }
.container { max-width:960px; margin:32px auto; padding:0 24px; }
.toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.toolbar button { background:#0f3460; color:#eee; border:none; padding:8px 18px; border-radius:6px; cursor:pointer; font-size:14px; }
.toolbar button:hover { background:#1a4a8a; }
.stats { color:#888; font-size:14px; }
.user-card { background:#16213e; border-radius:8px; padding:16px 20px; margin-bottom:16px; border-left:3px solid #0f3460; }
.user-card:hover { border-left-color:#e94560; }
.user-header { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.user-header .display { cursor:pointer; font-size:16px; font-weight:600; }
.user-header .display:hover { color:#e94560; }
.user-header input { background:#0f3460; color:#eee; border:1px solid #e94560; padding:4px 8px; border-radius:4px; font-size:14px; width:120px; outline:none; }
.user-header .uid { color:#666; font-size:12px; }
.user-prints { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
.vp-item { display:flex; align-items:center; gap:8px; background:#0f3460; padding:6px 12px; border-radius:6px; font-size:13px; }
.vp-item audio { height:22px; width:120px; }
.btn-edit { border:none; padding:4px 12px; border-radius:4px; cursor:pointer; font-size:12px; background:#0f3460; color:#c0d0f0; }
.btn-edit:hover { background:#1a4a8a; }
.btn-delete { border:none; padding:4px 12px; border-radius:4px; cursor:pointer; font-size:12px; background:#5c1a1a; color:#e0a0a0; }
.btn-delete:hover { background:#7a2626; }
.empty { text-align:center; color:#666; padding:60px 0; }
.toast { position:fixed; bottom:30px; right:30px; background:#0f3460; color:#eee; padding:12px 24px; border-radius:8px; font-size:14px; opacity:0; transition:opacity .3s; z-index:99; }
.toast.show { opacity:1; }
</style>
</head>
<body>

<header>
  <h1>🎤 派萌助手</h1>
  <span>用户 & 声纹管理</span>
</header>

<div class="container">
  <div class="toolbar">
    <div class="stats" id="stats">加载中…</div>
    <button onclick="refresh()">🔄 刷新</button>
  </div>
  <div id="list"></div>
  <div class="empty" id="empty" style="display:none">
    <p>还没有用户</p>
    <small>唤醒一次派萌就会自动注册第一个用户</small>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let editingUid = null;

async function refresh() {
  const uRes = await fetch('/api/users');
  const users = await uRes.json();
  document.getElementById('stats').textContent = users.length + ' 个用户';

  if (users.length === 0) {
    document.getElementById('list').innerHTML = '';
    document.getElementById('empty').style.display = 'block';
    return;
  }
  document.getElementById('empty').style.display = 'none';

  let html = '';
  for (const u of users) {
    const vRes = await fetch('/api/users/' + u.id + '/voiceprints');
    const vps = await vRes.json();
    const displayName = u.name || '用户#' + u.id;
    const style = u.name ? '' : 'style="color:#888;font-style:italic"';
    html += '<div class="user-card">';
    html += '<div class="user-header">';
    html += '<span class="display" ' + style + ' id="display-' + u.id + '" onclick="startEdit(' + u.id + ',\'' + esc(u.name) + '\')">' + esc(displayName) + '</span>';
    html += '<input type="text" id="input-' + u.id + '" value="' + esc(u.name) + '" style="display:none" placeholder="输入名字…" onkeydown="if(event.key===\'Enter\') saveEdit(' + u.id + ')" onblur="saveEdit(' + u.id + ')">';
    html += '<span class="uid">#' + u.id + '</span>';
    html += '<span style="flex:1"></span>';
    html += '<button class="btn-delete" onclick="deleteUser(' + u.id + ',\'' + esc(displayName) + '\')">删除用户</button>';
    html += '</div>';
    html += '<div class="user-prints">';
    html += '<span style="color:#666;font-size:12px">声纹 (' + vps.length + '):</span>';
    for (const vp of vps) {
      html += '<div class="vp-item">';
      html += '<span>#' + vp.id + '</span>';
      if (vp.audio_path) {
        html += '<audio controls src="/api/voiceprints/' + vp.id + '/audio"></audio>';
      }
      html += '<button class="btn-delete" onclick="deleteVp(' + vp.id + ')">✕</button>';
      html += '</div>';
    }
    html += '</div></div>';
  }
  document.getElementById('list').innerHTML = html;
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function startEdit(uid, name) {
  if (editingUid !== null) saveEdit(editingUid);
  editingUid = uid;
  document.getElementById('display-' + uid).style.display = 'none';
  const inp = document.getElementById('input-' + uid);
  inp.style.display = 'inline-block';
  inp.value = name;
  inp.focus();
  inp.select();
}

async function saveEdit(uid) {
  if (editingUid !== uid) return;
  editingUid = null;
  const name = document.getElementById('input-' + uid).value.trim();
  document.getElementById('input-' + uid).style.display = 'none';
  document.getElementById('display-' + uid).style.display = 'inline';
  if (!name) return;
  await fetch('/api/users/' + uid + '?name=' + encodeURIComponent(name), { method: 'PUT' });
  document.getElementById('display-' + uid).textContent = name;
  document.getElementById('display-' + uid).style.color = '';
  document.getElementById('display-' + uid).style.fontStyle = '';
  toast('已命名: ' + name);
}

async function deleteUser(uid, name) {
  if (!confirm('确定删除 "' + name + '" 及其所有声纹？')) return;
  await fetch('/api/users/' + uid, { method: 'DELETE' });
  toast('已删除 ' + name);
  refresh();
}

async function deleteVp(vpId) {
  if (!confirm('删除这条声纹？')) return;
  await fetch('/api/voiceprints/' + vpId, { method: 'DELETE' });
  toast('已删除声纹');
  refresh();
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2000);
}

refresh();
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
