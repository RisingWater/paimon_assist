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
            created_at TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    return conn


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
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


# ============================================================
# 声纹操作
# ============================================================

def enroll(user_id: int, emb: np.ndarray, audio_path: str = ""):
    """为指定用户添加一条声纹"""
    conn = _connect()
    conn.execute(
        "INSERT INTO voiceprints (user_id, vector, audio_path) VALUES (?, ?, ?)",
        (user_id, emb.astype(np.float32).tobytes(), audio_path),
    )
    conn.commit()
    conn.close()


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
            "SELECT v.id, v.user_id, u.name, v.audio_path, v.created_at "
            "FROM voiceprints v JOIN users u ON v.user_id=u.id "
            "WHERE v.user_id=? ORDER BY v.id",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT v.id, v.user_id, u.name, v.audio_path, v.created_at "
            "FROM voiceprints v JOIN users u ON v.user_id=u.id "
            "ORDER BY v.id"
        ).fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "name": r[2], "audio_path": r[3], "created_at": r[4]}
        for r in rows
    ]


def get_voiceprint(vp_id: int) -> "dict|None":
    conn = _connect()
    row = conn.execute(
        "SELECT v.id, v.user_id, u.name, v.audio_path, v.created_at "
        "FROM voiceprints v JOIN users u ON v.user_id=u.id "
        "WHERE v.id=?",
        (vp_id,),
    ).fetchone()
    conn.close()
    if row:
        return {"id": row[0], "user_id": row[1], "name": row[2], "audio_path": row[3], "created_at": row[4]}
    return None


def delete_voiceprint(vp_id: int):
    conn = _connect()
    conn.execute("DELETE FROM voiceprints WHERE id=?", (vp_id,))
    conn.commit()
    conn.close()
