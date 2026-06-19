"""长期记忆工具 — 读写 memory.md"""
import logging
import os
import re
import time
import threading
from llm_tools import register

_log = logging.getLogger(__name__)
_MEMORY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory", "memory.md"))

# 记忆摘要（200字以内），贴到 system prompt 尾部供 LLM 快速参考
memory_summary = ""
_summary_dirty = False


def _rebuild_summary_simple():
    """简单截断摘要，写回 memory.md 头部"""
    global memory_summary
    try:
        if not os.path.exists(_MEMORY_FILE):
            memory_summary = ""
            return
        with open(_MEMORY_FILE, encoding="utf-8") as f:
            content = f.read()
        lines = [l.strip() for l in content.split("\n") if l.strip().startswith("- ")]
        summary = "。".join(l[2:] for l in lines)
        if len(summary) > 200:
            summary = summary[:197] + "…"

        # 写回文件：摘要行 + 空行 + 原内容（跳过旧摘要行和空行开头的）
        new = [f"> 摘要：{summary}", ""]
        for l in content.split("\n"):
            if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
                continue
            new.append(l)
        with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(new).strip() + "\n")
        memory_summary = summary
    except Exception:
        memory_summary = ""


def rebuild_summary_async():
    """后台线程：调 LLM 重新生成 memory 摘要"""
    global _summary_dirty, memory_summary
    _summary_dirty = False

    try:
        if not os.path.exists(_MEMORY_FILE):
            memory_summary = ""
            return
        with open(_MEMORY_FILE, encoding="utf-8") as f:
            content = f.read().strip()
        lines = [l for l in content.split("\n") if l.strip().startswith("- ")]
        if not lines:
            return


        prompt = (
            "请将以下事实压缩为一段200字以内的摘要，保留所有人名、地名、关键关系：\n"
            + "\n".join(lines)
        )
        resp = requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "你是摘要助手。输出200字以内的中文摘要，只输出摘要本身。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 100,
                "temperature": 0.3,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            if len(summary) > 200:
                summary = summary[:197] + "…"
            memory_summary = summary
        else:
            _log.warning("LLM 摘要生成失败: %d", resp.status_code)
            _rebuild_summary_simple()
    except Exception as e:
        _log.warning("LLM 摘要异常: %s", e)
        _rebuild_summary_simple()


# 启动时简单构建摘要
_rebuild_summary_simple()


@register(memory_value=0,
    name="read_memory",
    description=(
        "读取长期+中期记忆，获取已知的用户偏好、身份、房间归属等信息。"
        "当 question_about 指定具体用户时会同时读取该用户的中期记忆。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "question_about": {
                "type": "string",
                "description": "问题涉及的用户名，如'王旭'，用于读取该用户的中期记忆。不填只返回长期记忆。",
            }
        },
        "required": [],
    },
)
def read_memory(args: dict = {}) -> str:
    parts = []
    try:
        if not os.path.exists(_MEMORY_FILE):
            parts.append("（暂无长期记忆）")
        else:
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                parts.append(f.read().strip())
    except Exception as e:
        parts.append(f"读取长期记忆失败：{e}")

    # 如果有对应用户，查中期记忆
    name = (args or {}).get("question_about", "")
    if name:
        users = _db.list_users()
        for u in users:
            if u["name"] == name:
                mid = _read_midterm_raw(u["id"])
                if mid:
                    parts.append(f"\n[{name}的近期动态]\n{mid}")
                break

    return "\n".join(parts) if parts else "（暂无记忆）"


@register(memory_value=10,
    name="save_memory",
    description=(
        "向长期记忆文件追加一条新信息。当了解到用户的新偏好、身份、房间设备归属等时使用。"
        "每条记忆一行，格式为 '- 事实描述'。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "要记录的事实，如'王旭的房间是主卧'、'乔宝的通话器名称是乔宝空调'",
            }
        },
        "required": ["fact"],
    },
)
def save_memory(args: dict) -> str:
    fact = args.get("fact", "").strip()
    if not fact:
        return "未提供要记录的内容"

    # 去重
    try:
        if os.path.exists(_MEMORY_FILE):
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                existing = f.read()
            if fact in existing:
                return f"已存在：{fact}"
    except Exception:
        pass

    try:
        with open(_MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"- {fact}\n")
        threading.Thread(target=rebuild_summary_async, daemon=True).start()
        return f"已记住：{fact}"
    except Exception as e:
        return f"保存记忆失败：{e}"


# ============================================================
# 中期记忆：按用户分文件 + 摘要
# ============================================================

_MIDTERM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory"))

# user_id → 摘要缓存
_midterm_cache: dict[int, str] = {}


def _midterm_file(user_id: int) -> str:
    os.makedirs(_MIDTERM_DIR, exist_ok=True)
    return os.path.join(_MIDTERM_DIR, f"{user_id}.md")


def _read_midterm_raw(user_id: int) -> str:
    path = _midterm_file(user_id)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def get_midterm_summary(user_id: int) -> str:
    """获取用户的中期记忆摘要（200字以内）"""
    if user_id in _midterm_cache:
        return _midterm_cache[user_id]
    content = _read_midterm_raw(user_id)
    if not content:
        return ""
    # 从文件中提取摘要行（以 "> 摘要：" 开头）
    for line in content.split("\n"):
        if line.startswith("> 摘要："):
            summary = line[4:].strip()
            _midterm_cache[user_id] = summary
            return summary
    return ""


def append_to_midterm(user_id: int, fact: str):
    """向中期记忆追加一条事实，并后台重建摘要"""
    path = _midterm_file(user_id)
    # 去重
    existing = _read_midterm_raw(user_id)
    if fact in existing:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")
    _rebuild_midterm_simple(user_id)
    _midterm_mtimes[user_id] = os.path.getmtime(path)


def _rebuild_midterm_simple(user_id: int):
    """简单截断摘要（自动提取时用，不调 LLM），写回文件"""
    content = _read_midterm_raw(user_id)
    facts = [l.strip()[2:] for l in content.split("\n") if l.strip().startswith("- ")]
    if not facts:
        _midterm_cache[user_id] = ""
        return
    summary = "。".join(facts[-10:])
    if len(summary) > 200:
        summary = summary[:197] + "…"

    # 写回文件头部
    path = _midterm_file(user_id)
    new = [f"> 摘要：{summary}", ""]
    for l in content.split("\n"):
        if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
            continue
        new.append(l)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new).strip() + "\n")
    _midterm_cache[user_id] = summary


def rebuild_midterm_llm(user_id: int):
    """用 LLM 重建中期记忆摘要，写回文件头部"""
    global _midterm_cache
    path = _midterm_file(user_id)
    content = _read_midterm_raw(user_id)
    facts = [l.strip()[2:] for l in content.split("\n") if l.strip().startswith("- ")]
    if not facts:
        _midterm_cache[user_id] = ""
        return

    try:
        prompt = "请将以下事实压缩为一段200字以内的摘要，保留所有人名、地名、关键信息：\n" + "\n".join(facts)
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "你是摘要助手。输出200字以内的中文摘要，只输出摘要本身。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 100, "temperature": 0.3,
            },
            timeout=15,
        )
        summary = ""
        if resp.status_code == 200:
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            if len(summary) > 200:
                summary = summary[:197] + "…"
    except Exception:
        summary = ""

    if not summary:
        _rebuild_midterm_simple(user_id)
        return

    # 写回文件头部
    new = [f"> 摘要：{summary}", ""]
    for l in content.split("\n"):
        if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
            continue
        new.append(l)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new).strip() + "\n")
    _midterm_cache[user_id] = summary


# 中期记忆定期检查线程
_midterm_mtimes: dict[int, float] = {}
_midterm_check_running = False


def _midterm_periodic_check():
    """每 5 分钟检查：扫描 memory/ 目录，对变化的中期记忆文件用 LLM 重建摘要"""
    global _midterm_check_running, _midterm_mtimes
    while True:
        time.sleep(300)
        try:
            if not os.path.isdir(_MIDTERM_DIR):
                continue
            for fname in os.listdir(_MIDTERM_DIR):
                m = _re.match(r"^(\d+)\.md$", fname)
                if not m:
                    continue
                user_id = int(m.group(1))
                path = os.path.join(_MIDTERM_DIR, fname)
                mtime = os.path.getmtime(path)
                if mtime > _midterm_mtimes.get(user_id, 0):
                    _midterm_mtimes[user_id] = mtime
                    rebuild_midterm_llm(user_id)
        except Exception:
            pass


def _start_midterm_checker():
    global _midterm_check_running
    if _midterm_check_running:
        return
    _midterm_check_running = True
    threading.Thread(target=_midterm_periodic_check, daemon=True).start()


_start_midterm_checker()
