"""FastAPI Web 管理界面 — 声纹管理 + TTS API"""
import os
import db
import tts_api
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="派萌助手")
app.include_router(tts_api.router)

# ============================================================
# Web 页面
# ============================================================

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
.container { max-width:900px; margin:32px auto; padding:0 24px; }
.toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.toolbar button { background:#0f3460; color:#eee; border:none; padding:8px 18px; border-radius:6px; cursor:pointer; font-size:14px; }
.toolbar button:hover { background:#1a4a8a; }
.stats { color:#888; font-size:14px; }
table { width:100%; border-collapse:collapse; border-radius:8px; overflow:hidden; }
th, td { padding:12px 16px; text-align:left; }
th { background:#0f3460; color:#ccc; font-weight:500; font-size:13px; text-transform:uppercase; letter-spacing:.5px; }
td { background:#16213e; border-bottom:1px solid #1a2a4a; font-size:14px; }
tr:last-child td { border-bottom:none; }
tr:hover td { background:#1a2a4a; }
.name-cell { display:flex; align-items:center; gap:8px; }
.name-cell .display { cursor:pointer; }
.name-cell .display:hover { color:#e94560; }
.name-cell input { background:#0f3460; color:#eee; border:1px solid #e94560; padding:4px 8px; border-radius:4px; font-size:14px; width:120px; outline:none; }
.actions { display:flex; gap:8px; }
.actions button { border:none; padding:5px 14px; border-radius:4px; cursor:pointer; font-size:13px; }
.btn-play { background:#1a5c3a; color:#a0e0c0; }
.btn-play:hover { background:#267a50; }
.btn-edit { background:#0f3460; color:#c0d0f0; }
.btn-edit:hover { background:#1a4a8a; }
.btn-delete { background:#5c1a1a; color:#e0a0a0; }
.btn-delete:hover { background:#7a2626; }
audio { height:24px; width:160px; }
.empty { text-align:center; color:#666; padding:60px 0; }
.empty p { font-size:16px; margin-bottom:8px; }
.empty small { font-size:13px; color:#555; }
.toast { position:fixed; bottom:30px; right:30px; background:#0f3460; color:#eee; padding:12px 24px; border-radius:8px; font-size:14px; opacity:0; transition:opacity .3s; z-index:99; }
.toast.show { opacity:1; }
</style>
</head>
<body>

<header>
  <h1>🎤 派萌助手</h1>
  <span>声纹管理</span>
</header>

<div class="container">
  <div class="toolbar">
    <div class="stats" id="stats">加载中…</div>
    <button onclick="refresh()">🔄 刷新</button>
  </div>
  <table>
    <thead>
      <tr>
        <th>名字</th>
        <th>注册时间</th>
        <th>试听</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="empty" id="empty" style="display:none">
    <p>还没有声纹</p>
    <small>唤醒一次派萌就会自动注册第一条声纹</small>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '/api/voiceprints';

let editingId = null;

async function refresh() {
  try {
    const res = await fetch(API);
    const list = await res.json();
    document.getElementById('stats').textContent = `共 ${list.length} 条声纹`;
    const tbody = document.getElementById('tbody');
    const empty = document.getElementById('empty');

    if (list.length === 0) {
      tbody.innerHTML = '';
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = list.map(v => {
      const displayName = v.name || '未命名';
      const style = v.name ? '' : 'style="color:#888;font-style:italic"';
      return `
      <tr id="row-${v.id}">
        <td>
          <div class="name-cell" id="cell-${v.id}">
            <span class="display" id="display-${v.id}" onclick="startEdit(${v.id}, '${esc(v.name)}')" ${style}>${esc(displayName)}</span>
            <input type="text" id="input-${v.id}" value="${esc(v.name)}" style="display:none" placeholder="输入名字…"
                   onkeydown="if(event.key==='Enter') saveEdit(${v.id})"
                   onblur="saveEdit(${v.id})">
          </div>
        </td>
        <td>${esc(v.created_at || '')}</td>
        <td>
          ${v.audio_path ? `<audio controls src="${API}/${v.id}/audio"></audio>` : '<span style="color:#555">无录音</span>'}
        </td>
        <td>
          <div class="actions">
            <button class="btn-edit" onclick="startEdit(${v.id}, '${esc(v.name)}')">✏️ ${v.name ? '编辑' : '命名'}</button>
            <button class="btn-delete" onclick="deleteVp(${v.id}, '${esc(displayName)}')">🗑 删除</button>
          </div>
        </td>
      </tr>
    `}).join('');
  } catch (e) {
    console.error(e);
    document.getElementById('stats').textContent = '加载失败';
  }
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function startEdit(id, name) {
  if (editingId !== null) saveEdit(editingId);
  editingId = id;
  document.getElementById('display-' + id).style.display = 'none';
  const inp = document.getElementById('input-' + id);
  inp.style.display = 'inline-block';
  inp.value = name;
  inp.focus();
  inp.select();
}

async function saveEdit(id) {
  if (editingId !== id) return;
  editingId = null;
  const name = document.getElementById('input-' + id).value.trim();
  document.getElementById('input-' + id).style.display = 'none';
  document.getElementById('display-' + id).style.display = 'inline';

  if (!name) {
    document.getElementById('display-' + id).textContent = document.getElementById('display-' + id).dataset.old || '';
    return;
  }
  try {
    const res = await fetch(`${API}/${id}?name=${encodeURIComponent(name)}`, { method: 'PUT' });
    if (res.ok) {
      document.getElementById('display-' + id).textContent = name;
      toast('✅ 已重命名为 "' + name + '"');
    }
  } catch (e) { console.error(e); }
}

async function deleteVp(id, name) {
  if (!confirm(`确定删除 "${name}" 的声纹吗？此操作不可恢复。`)) return;
  try {
    const res = await fetch(`${API}/${id}`, { method: 'DELETE' });
    if (res.ok) {
      toast('🗑 已删除 "' + name + '"');
      refresh();
    }
  } catch (e) { console.error(e); }
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

# ============================================================
# API 端点
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.get("/api/voiceprints")
async def list_voiceprints():
    """列出全部声纹"""
    return db.list_all()


@app.put("/api/voiceprints/{id}")
async def rename_voiceprint(id: int, name: str):
    """重命名声纹"""
    vp = db.get(id)
    if not vp:
        raise HTTPException(404, "声纹不存在")
    db.rename(id, name)
    return {"ok": True}


@app.delete("/api/voiceprints/{id}")
async def delete_voiceprint(id: int):
    """删除声纹"""
    vp = db.get(id)
    if not vp:
        raise HTTPException(404, "声纹不存在")
    db.delete(id)
    return {"ok": True}


@app.get("/api/voiceprints/{id}/audio")
async def get_audio(id: int):
    """获取声纹对应的录音文件"""
    vp = db.get(id)
    if not vp or not vp.get("audio_path"):
        raise HTTPException(404, "录音不存在")
    path = vp["audio_path"]
    if not os.path.isfile(path):
        raise HTTPException(404, "录音文件已丢失")
    return FileResponse(path, media_type="audio/wav")
