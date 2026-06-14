"""声纹数据库（SQLite）"""
import os
import sqlite3
import numpy as np
from config import VOICEPRINT_DB


def _connect() -> sqlite3.Connection:
    """获取数据库连接，自动建表/迁移"""
    os.makedirs(os.path.dirname(VOICEPRINT_DB), exist_ok=True)
    conn = sqlite3.connect(VOICEPRINT_DB, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voiceprints (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            vector     BLOB    NOT NULL,
            audio_path TEXT    DEFAULT '',
            created_at TEXT    DEFAULT (datetime('now','localtime'))
        )
    """)
    # 兼容旧表：尝试添加 audio_path 列
    try:
        conn.execute("ALTER TABLE voiceprints ADD COLUMN audio_path TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    return conn


def enroll(name: str, emb: np.ndarray, audio_path: str = ""):
    """保存一条声纹"""
    conn = _connect()
    conn.execute(
        "INSERT INTO voiceprints (name, vector, audio_path) VALUES (?, ?, ?)",
        (name, emb.astype(np.float32).tobytes(), audio_path),
    )
    conn.commit()
    conn.close()


def find_best(emb: np.ndarray) -> "tuple[str|None, float]":
    """
    遍历所有声纹，返回 (名字, 最高余弦相似度)。
    库为空时返回 (None, 0.0)。
    """
    conn = _connect()
    rows = conn.execute("SELECT name, vector FROM voiceprints").fetchall()
    conn.close()

    best_name, best_sim = None, 0.0
    for name, vec_blob in rows:
        stored = np.frombuffer(vec_blob, dtype=np.float32)
        sim = float(
            np.dot(emb, stored) / (np.linalg.norm(emb) * np.linalg.norm(stored))
        )
        if sim > best_sim:
            best_sim = sim
            best_name = name
    return best_name, best_sim


def count() -> int:
    """返回已注册声纹数量"""
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) FROM voiceprints").fetchone()[0]
    conn.close()
    return n


def list_all() -> "list[dict]":
    """返回全部声纹（不含向量）"""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, created_at, audio_path FROM voiceprints ORDER BY id"
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "created_at": r[2],
            "audio_path": r[3],
        }
        for r in rows
    ]


def get(id: int) -> "dict|None":
    """获取单条声纹信息（不含向量）"""
    conn = _connect()
    row = conn.execute(
        "SELECT id, name, created_at, audio_path FROM voiceprints WHERE id=?",
        (id,),
    ).fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "created_at": row[2], "audio_path": row[3]}
    return None


def rename(id: int, name: str):
    """重命名声纹"""
    conn = _connect()
    conn.execute("UPDATE voiceprints SET name=? WHERE id=?", (name, id))
    conn.commit()
    conn.close()


def delete(id: int):
    """删除声纹"""
    conn = _connect()
    conn.execute("DELETE FROM voiceprints WHERE id=?", (id,))
    conn.commit()
    conn.close()
