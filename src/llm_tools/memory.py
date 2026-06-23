"""长期记忆工具 — 读写 memory.md

包含:
  - MemoryManager(MemoryTracked): 记忆系统单例，管理长期/中期记忆
  - ReadMemoryTool(BaseTool) / SaveMemoryTool(BaseTool): LLM 工具
"""
import logging
import os
import re
import time
import threading
import requests

from llm_tools import BaseTool, tools
from memory_monitor import MemoryTracked

_log = logging.getLogger(__name__)

_MEMORY_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory", "memory.md"))
_MIDTERM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "memory"))


# ============================================================
# MemoryManager — 记忆系统单例
# ============================================================

class MemoryManager(MemoryTracked):
    """长期 + 中期记忆管理器。单例，被 ReadMemoryTool / SaveMemoryTool 调用。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        super().__init__("记忆系统", "长期摘要 + 中期缓存 + 定期检查", category="Tool")
        self.memory_summary = ""
        self._summary_dirty = False
        self._midterm_cache: dict[int, str] = {}
        self._midterm_mtimes: dict[int, float] = {}
        self._midterm_check_running = False

        # 启动时构建摘要
        self._rebuild_summary_simple()

        # 启动中期记忆定期检查
        self._start_midterm_checker()

    # ---- 长期记忆 ----

    def _rebuild_summary_simple(self):
        try:
            if not os.path.exists(_MEMORY_FILE):
                self.memory_summary = ""
                return
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                content = f.read()
            lines = [l.strip() for l in content.split("\n") if l.strip().startswith("- ")]
            summary = "。".join(l[2:] for l in lines)
            if len(summary) > 200:
                summary = summary[:197] + "…"

            new = [f"> 摘要：{summary}", ""]
            for l in content.split("\n"):
                if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
                    continue
                new.append(l)
            with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(new).strip() + "\n")
            self.memory_summary = summary
        except Exception:
            self.memory_summary = ""

    def rebuild_summary_async(self):
        """后台线程用 LLM 重建长期记忆摘要"""
        self._summary_dirty = False
        try:
            if not os.path.exists(_MEMORY_FILE):
                self.memory_summary = ""
                return
            with open(_MEMORY_FILE, encoding="utf-8") as f:
                content = f.read().strip()
            lines = [l for l in content.split("\n") if l.strip().startswith("- ")]
            if not lines:
                return

            from config import cfg
            prompt = "请将以下事实压缩为一段200字以内的摘要，保留所有人名、地名、关键关系：\n" + "\n".join(lines)
            resp = requests.post(
                cfg.DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": cfg.DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是摘要助手。输出200字以内的中文摘要，只输出摘要本身。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 100, "temperature": 0.3,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                summary = resp.json()["choices"][0]["message"]["content"].strip()
                if len(summary) > 200:
                    summary = summary[:197] + "…"
                self.memory_summary = summary
            else:
                _log.warning("LLM 摘要生成失败: %d", resp.status_code)
                self._rebuild_summary_simple()
        except Exception as e:
            _log.warning("LLM 摘要异常: %s", e)
            self._rebuild_summary_simple()

    def read_raw(self) -> str:
        if not os.path.exists(_MEMORY_FILE):
            return "（暂无长期记忆）"
        with open(_MEMORY_FILE, encoding="utf-8") as f:
            return f.read().strip()

    def save_fact(self, fact: str) -> str:
        fact = fact.strip()
        if not fact:
            return "未提供要记录的内容"
        try:
            if os.path.exists(_MEMORY_FILE):
                with open(_MEMORY_FILE, encoding="utf-8") as f:
                    if fact in f.read():
                        return f"已存在：{fact}"
        except Exception:
            pass
        try:
            with open(_MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"- {fact}\n")
            threading.Thread(target=self.rebuild_summary_async, daemon=True).start()
            return f"已记住：{fact}"
        except Exception as e:
            return f"保存记忆失败：{e}"

    # ---- 中期记忆 ----

    def _midterm_file(self, user_id: int) -> str:
        os.makedirs(_MIDTERM_DIR, exist_ok=True)
        return os.path.join(_MIDTERM_DIR, f"{user_id}.md")

    def _read_midterm_raw(self, user_id: int) -> str:
        path = self._midterm_file(user_id)
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read().strip()

    def get_midterm_summary(self, user_id: int) -> str:
        if user_id in self._midterm_cache:
            return self._midterm_cache[user_id]
        content = self._read_midterm_raw(user_id)
        if not content:
            return ""
        for line in content.split("\n"):
            if line.startswith("> 摘要："):
                summary = line[4:].strip()
                self._midterm_cache[user_id] = summary
                return summary
        return ""

    def append_to_midterm(self, user_id: int, fact: str):
        path = self._midterm_file(user_id)
        existing = self._read_midterm_raw(user_id)
        if fact in existing:
            return
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"- {fact}\n")
        self._rebuild_midterm_simple(user_id)
        self._midterm_mtimes[user_id] = os.path.getmtime(path)

    def _rebuild_midterm_simple(self, user_id: int):
        content = self._read_midterm_raw(user_id)
        facts = [l.strip()[2:] for l in content.split("\n") if l.strip().startswith("- ")]
        if not facts:
            self._midterm_cache[user_id] = ""
            return
        summary = "。".join(facts[-10:])
        if len(summary) > 200:
            summary = summary[:197] + "…"

        path = self._midterm_file(user_id)
        new = [f"> 摘要：{summary}", ""]
        for l in content.split("\n"):
            if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
                continue
            new.append(l)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(new).strip() + "\n")
        self._midterm_cache[user_id] = summary

    def rebuild_midterm_llm(self, user_id: int):
        path = self._midterm_file(user_id)
        content = self._read_midterm_raw(user_id)
        facts = [l.strip()[2:] for l in content.split("\n") if l.strip().startswith("- ")]
        if not facts:
            self._midterm_cache[user_id] = ""
            return
        try:
            from config import cfg
            prompt = "请将以下事实压缩为一段200字以内的摘要，保留所有人名、地名、关键信息：\n" + "\n".join(facts)
            resp = requests.post(
                cfg.DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {cfg.DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": cfg.DEEPSEEK_MODEL,
                    "messages": [{"role": "system", "content": "你是摘要助手。输出200字以内的中文摘要，只输出摘要本身。"},
                                 {"role": "user", "content": prompt}],
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
            self._rebuild_midterm_simple(user_id)
            return

        new = [f"> 摘要：{summary}", ""]
        for l in content.split("\n"):
            if l.startswith("> 摘要") or (not new[-1] and l.strip() == ""):
                continue
            new.append(l)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(new).strip() + "\n")
        self._midterm_cache[user_id] = summary

    # ---- 定期检查 ----

    def _midterm_periodic_check(self):
        while True:
            time.sleep(300)
            try:
                if not os.path.isdir(_MIDTERM_DIR):
                    continue
                for fname in os.listdir(_MIDTERM_DIR):
                    m = re.match(r"^(\d+)\.md$", fname)
                    if not m:
                        continue
                    user_id = int(m.group(1))
                    path = os.path.join(_MIDTERM_DIR, fname)
                    mtime = os.path.getmtime(path)
                    if mtime > self._midterm_mtimes.get(user_id, 0):
                        self._midterm_mtimes[user_id] = mtime
                        self.rebuild_midterm_llm(user_id)
            except Exception:
                pass

    def _start_midterm_checker(self):
        if self._midterm_check_running:
            return
        self._midterm_check_running = True
        threading.Thread(target=self._midterm_periodic_check, daemon=True).start()


# 全局单例
_mgr = MemoryManager()

# 向后兼容别名（llm.py / server.py 用这些函数）
# 注意：memory_summary 是字符串，llm.py 应直接用 _mgr.memory_summary 获取最新值
get_midterm_summary = _mgr.get_midterm_summary
append_to_midterm = _mgr.append_to_midterm
rebuild_summary_async = _mgr.rebuild_summary_async
rebuild_midterm_llm = _mgr.rebuild_midterm_llm
_midterm_file = _mgr._midterm_file  # server.py 用的路径函数
# _MEMORY_FILE 和 _MIDTERM_DIR 是模块级常量，server.py 直接引用


# ============================================================
# Tools
# ============================================================

class ReadMemoryTool(BaseTool):
    def __init__(self):
        super().__init__(
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
            memory_value=0, silent=True,
        )

    def execute(self, args: dict) -> str:
        parts = []
        try:
            parts.append(_mgr.read_raw())
        except Exception as e:
            parts.append(f"读取长期记忆失败：{e}")

        name = (args or {}).get("question_about", "")
        if name:
            import db as _db
            users = _db.list_users()
            for u in users:
                if u["name"] == name:
                    mid = _mgr._read_midterm_raw(u["id"])
                    if mid:
                        parts.append(f"\n[{name}的近期动态]\n{mid}")
                    break
        return "\n".join(parts) if parts else "（暂无记忆）"


class SaveMemoryTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="save_memory",
            description=(
                "向长期记忆文件追加一条新信息。当了解到用户的新偏好、身份、房间设备归属等时使用。"
                "每条记忆一行，格式为 '- 事实描述'。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "要记录的事实，如'王旭的房间是主卧'"},
                },
                "required": ["fact"],
            },
            memory_value=10, silent=True,
        )

    def execute(self, args: dict) -> str:
        return _mgr.save_fact(args.get("fact", ""))


tools.register(ReadMemoryTool())
tools.register(SaveMemoryTool())
