"""数据库 — 用户表 + 声纹表（一个用户可绑定多条声纹）"""
import os
import sqlite3
import numpy as np
from config import VOICEPRINT_DB


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(VOICEPRINT_DB), exist_ok=True)
    conn = sqlite3.connect(VOICEPRINT_DB, check_same_thread=False)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL DEFAULT '',
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voiceprints (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            vector     BLOB    NOT NULL,
            audio_path TEXT    DEFAULT '',
            type       TEXT    NOT NULL DEFAULT 'auto',
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # 迁移：为旧表增加 type 列
    try:
        conn.execute("ALTER TABLE voiceprints ADD COLUMN type TEXT NOT NULL DEFAULT 'auto'")
    except:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL DEFAULT '',
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            content    TEXT    NOT NULL,
            rtype      TEXT    NOT NULL DEFAULT 'once',
            datetime   TEXT    NOT NULL,
            lunar      INTEGER NOT NULL DEFAULT 0,
            done       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tts_cache (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            hash       TEXT    NOT NULL UNIQUE,
            text       TEXT    NOT NULL,
            audio_path TEXT    NOT NULL,
            backend    TEXT    NOT NULL DEFAULT 'vits',
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    return conn


def _ensure_reminder_user() -> int:
    """确保存在一个"定时任务"系统用户，返回其 user_id"""
    conn = _connect()
    row = conn.execute("SELECT id FROM users WHERE name='定时任务'").fetchone()
    if row:
        conn.close()
        return row[0]
    cur = conn.execute("INSERT INTO users (name) VALUES ('定时任务')")
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


# ============================================================
# 用户操作
# ============================================================

def create_user(name: str = "") -> int:
    """创建新用户，返回 user_id"""
    conn = _connect()
    cur = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def rename_user(user_id: int, name: str):
    conn = _connect()
    conn.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
    conn.commit()
    conn.close()


def list_users() -> "list[dict]":
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def get_user(user_id: int) -> "dict|None":
    conn = _connect()
    row = conn.execute("SELECT id, name, created_at FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "created_at": row[2]}
    return None


def delete_user(user_id: int):
    conn = _connect()
    conn.execute("DELETE FROM voiceprints WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


# ============================================================
# 声纹操作
# ============================================================

def enroll(user_id: int, emb: np.ndarray, audio_path: str = "", vp_type: str = "auto") -> int:
    """为指定用户添加一条声纹，返回声纹 ID。vp_type: 'auto'/'manual'

    自动声纹上限 100 条，超出时删除最早的。
    """
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO voiceprints (user_id, vector, audio_path, type) VALUES (?, ?, ?, ?)",
        (user_id, emb.astype(np.float32).tobytes(), audio_path, vp_type),
    )
    vp_id = cur.lastrowid
    conn.commit()

    # 自动声纹上限 100，超出删最早的
    if vp_type == "auto":
        total = conn.execute(
            "SELECT COUNT(*) FROM voiceprints WHERE user_id=? AND type='auto'",
            (user_id,),
        ).fetchone()[0]
        excess = total - 100
        if excess > 0:
            rows = conn.execute(
                "SELECT id, audio_path FROM voiceprints WHERE user_id=? AND type='auto' "
                "ORDER BY id ASC LIMIT ?",
                (user_id, excess),
            ).fetchall()
            for vp_id, audio_path in rows:
                if audio_path:
                    import os as _os
                    try:
                        if _os.path.isfile(audio_path):
                            _os.remove(audio_path)
                    except Exception:
                        pass
                conn.execute("DELETE FROM voiceprints WHERE id=?", (vp_id,))
            conn.commit()

    conn.close()
    return vp_id


def count() -> int:
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) FROM voiceprints").fetchone()[0]
    conn.close()
    return n


def find_best(emb: np.ndarray) -> "tuple[int|None, str, float]":
    """
    声纹匹配算法：

    1. 计算当前声纹与库中每一条声纹的余弦相似度
    2. 筛选 sim > 0.5 的声纹
    3. 统计命中的 user_id：
       - 0 个 user_id → 陌生人
       - 1 个 user_id → 就是这个人
       - 多个 user_id → 对每个 user 取平均 sim，最高者胜出

    Returns:
        (user_id, name, best_similarity)
        陌生人返回 (None, "", 0.0)
    """
    THRESHOLD = 0.5

    conn = _connect()
    rows = conn.execute(
        "SELECT v.user_id, v.vector, u.name FROM voiceprints v JOIN users u ON v.user_id=u.id"
    ).fetchall()
    conn.close()

    if not rows:
        return None, "", 0.0

    # 1. 计算每条声纹的相似度
    hits: list[tuple[int, str, float]] = []  # (user_id, name, sim)
    for uid, vec_blob, name in rows:
        stored = np.frombuffer(vec_blob, dtype=np.float32)
        sim = float(np.dot(emb, stored) / (np.linalg.norm(emb) * np.linalg.norm(stored)))
        if sim > THRESHOLD:
            hits.append((uid, name, sim))

    # 2. 统计命中的 user_id
    hit_uids = set(uid for uid, _, _ in hits)

    if len(hit_uids) == 0:
        # 陌生人
        return None, "", 0.0

    if len(hit_uids) == 1:
        # 只有一个 user → 就是这个人
        uid = next(iter(hit_uids))
        avg = sum(s for u, _, s in hits if u == uid) / sum(1 for u, _, s in hits if u == uid)
        name = hits[0][1]
        return uid, name, avg

    # 3. 多个 user_id → 取平均分最高的
    best_uid, best_name, best_avg = None, "", 0.0
    for uid in hit_uids:
        user_hits = [(n, s) for u, n, s in hits if u == uid]
        avg = sum(s for _, s in user_hits) / len(user_hits)
        if avg > best_avg:
            best_avg = avg
            best_uid = uid
            best_name = user_hits[0][0]

    return best_uid, best_name, best_avg


def list_voiceprints(user_id: int | None = None) -> "list[dict]":
    conn = _connect()
    if user_id is not None:
        rows = conn.execute(
            "SELECT v.id, v.user_id, u.name, v.audio_path, v.type, v.created_at "
            "FROM voiceprints v JOIN users u ON v.user_id=u.id "
            "WHERE v.user_id=? ORDER BY CASE v.type WHEN 'manual' THEN 0 ELSE 1 END, v.id",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT v.id, v.user_id, u.name, v.audio_path, v.type, v.created_at "
            "FROM voiceprints v JOIN users u ON v.user_id=u.id "
            "ORDER BY CASE v.type WHEN 'manual' THEN 0 ELSE 1 END, v.id"
        ).fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "name": r[2], "audio_path": r[3], "type": r[4], "created_at": r[5]}
        for r in rows
    ]


def get_voiceprint(vp_id: int) -> "dict|None":
    conn = _connect()
    row = conn.execute(
        "SELECT v.id, v.user_id, u.name, v.audio_path, v.type, v.created_at "
        "FROM voiceprints v JOIN users u ON v.user_id=u.id "
        "WHERE v.id=?",
        (vp_id,),
    ).fetchone()
    conn.close()
    if row:
        return {"id": row[0], "user_id": row[1], "name": row[2], "audio_path": row[3], "type": row[4], "created_at": row[5]}
    return None


def delete_voiceprint(vp_id: int):
    conn = _connect()
    conn.execute("DELETE FROM voiceprints WHERE id=?", (vp_id,))
    conn.commit()
    conn.close()


def move_voiceprint(vp_id: int, target_user_id: int):
    """将声纹移动到另一个用户，同时移动 WAV 文件"""
    conn = _connect()
    vp = conn.execute("SELECT audio_path FROM voiceprints WHERE id=?", (vp_id,)).fetchone()
    conn.execute("UPDATE voiceprints SET user_id=? WHERE id=?", (target_user_id, vp_id))
    conn.commit()
    conn.close()
    # 移动录音文件
    if vp and vp[0]:
        import os as _os
        import shutil as _shutil
        old_path = vp[0]
        if _os.path.isfile(old_path):
            dest_dir = _os.path.join("recordings", str(target_user_id))
            _os.makedirs(dest_dir, exist_ok=True)
            dest = _os.path.join(dest_dir, _os.path.basename(old_path))
            _shutil.move(old_path, dest)
            # 更新 DB 中的路径
            conn = _connect()
            conn.execute("UPDATE voiceprints SET audio_path=? WHERE id=?", (dest, vp_id))
            conn.commit()
            conn.close()


# ============================================================
# 聊天历史操作
# ============================================================

def load_history(user_id: int) -> "list[dict]":
    """加载用户的聊天历史，返回 [{"role": ..., "content": ...}, ...]"""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM chat_history WHERE user_id=? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]


def append_message(user_id: int, role: str, content: str):
    """向用户聊天历史追加一条消息"""
    conn = _connect()
    conn.execute(
        "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content),
    )
    conn.commit()
    conn.close()


def update_message(msg_id: int, content: str):
    """编辑一条聊天记录的内容"""
    conn = _connect()
    conn.execute(
        "UPDATE chat_history SET content=? WHERE id=?",
        (content, msg_id),
    )
    conn.commit()
    conn.close()


def delete_message(msg_id: int):
    """删除一条聊天记录"""
    conn = _connect()
    conn.execute("DELETE FROM chat_history WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()


def clear_history(user_id: int):
    """清空用户的全部聊天历史"""
    conn = _connect()
    conn.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ============================================================
# 定时提醒操作
# ============================================================

def add_reminder(user_id: int, content: str, rtype: str, dt: str, lunar: bool = False) -> int:
    """添加提醒。rtype: once/daily/monthly, dt: '2026-06-18 21:00'/'21:00'/'15 21:00'"""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO reminders (user_id, content, rtype, datetime, lunar) VALUES (?, ?, ?, ?, ?)",
        (user_id, content, rtype, dt, 1 if lunar else 0),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def list_reminders(user_id: int | None = None, include_done: bool = False) -> list[dict]:
    """列出提醒"""
    conn = _connect()
    if user_id is not None:
        rows = conn.execute(
            "SELECT id, user_id, content, rtype, datetime, lunar, done, created_at "
            "FROM reminders WHERE user_id=? " + ("" if include_done else "AND done=0 ") +
            "ORDER BY datetime, id",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, content, rtype, datetime, lunar, done, created_at "
            "FROM reminders " + ("" if include_done else "WHERE done=0 ") +
            "ORDER BY datetime, id"
        ).fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "content": r[2], "rtype": r[3],
         "datetime": r[4], "lunar": bool(r[5]), "done": bool(r[6]), "created_at": r[7]}
        for r in rows
    ]


def delete_reminder(rid: int):
    conn = _connect()
    conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
    conn.commit()
    conn.close()


def mark_reminder_done(rid: int):
    conn = _connect()
    conn.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
    conn.commit()
    conn.close()


def get_due_reminders() -> list[dict]:
    """获取到期的提醒（供后台线程调用）"""
    import lunardate as _ld
    from datetime import datetime as _dt

    now = _dt.now()
    today_solar = now.day
    today_lunar = _ld.LunarDate.fromSolarDate(now.year, now.month, now.day).day
    now_str = now.strftime("%H:%M")
    today_str = now.strftime("%Y-%m-%d")

    all_reminders = list_reminders(include_done=False)
    due = []

    for r in all_reminders:
        dt = r["datetime"]
        if r["rtype"] == "once" and dt <= _dt.now().strftime("%Y-%m-%d %H:%M"):
            due.append(r)
        elif r["rtype"] == "daily" and dt == now_str:
            due.append(r)
        elif r["rtype"] == "monthly":
            parts = dt.split()
            if len(parts) == 2:
                day = int(parts[0])
                tm = parts[1]
                day_match = today_lunar if r["lunar"] else today_solar
                if day == day_match and tm == now_str:
                    due.append(r)

    return due

# ============================================================
# TTS 缓存操作
# ============================================================

def cache_get(text_hash: str) -> dict | None:
    conn = _connect()
    row = conn.execute(
        "SELECT audio_path, backend FROM tts_cache WHERE hash=?", (text_hash,)
    ).fetchone()
    conn.close()
    if row:
        return {"audio_path": row[0], "backend": row[1]}
    return None


def cache_set(text_hash: str, text: str, audio_path: str, backend: str):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO tts_cache (hash, text, audio_path, backend) VALUES (?, ?, ?, ?)",
        (text_hash, text, audio_path, backend),
    )
    conn.commit()
    conn.close()


def cache_list(search: str = "", limit: int = 100) -> list[dict]:
    conn = _connect()
    if search:
        rows = conn.execute(
            "SELECT id, text, audio_path, backend, created_at FROM tts_cache "
            "WHERE text LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"%{search}%", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, text, audio_path, backend, created_at FROM tts_cache "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {"id": r[0], "text": r[1], "audio_path": r[2], "backend": r[3], "created_at": r[4]}
        for r in rows
    ]


def cache_delete(cache_id: int):
    import os as _os2
    conn = _connect()
    row = conn.execute("SELECT audio_path FROM tts_cache WHERE id=?", (cache_id,)).fetchone()
    if row:
        try:
            if _os2.path.isfile(row[0]):
                _os2.remove(row[0])
        except Exception:
            pass
    conn.execute("DELETE FROM tts_cache WHERE id=?", (cache_id,))
    conn.commit()
    conn.close()


def cache_clear():
    import os as _os2
    conn = _connect()
    rows = conn.execute("SELECT audio_path FROM tts_cache").fetchall()
    for (path,) in rows:
        try:
            if _os2.path.isfile(path):
                _os2.remove(path)
        except Exception:
            pass
    conn.execute("DELETE FROM tts_cache")
    conn.commit()
    conn.close()


def cache_count() -> int:
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) FROM tts_cache").fetchone()[0]
    conn.close()
    return n
