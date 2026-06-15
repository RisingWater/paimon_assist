"""网络搜索工具 — 通过 Claude Code CLI 进行联网搜索"""
import os
import subprocess
import logging
from llm_tools import register
from config import CLAUDE_BIN

_log = logging.getLogger(__name__)


@register(
    name="web_search",
    description=(
        "仅用于查询最新时效性信息：新闻、实时数据、近期事件。"
        "常识、历史、科学、编程等知识类问题不要调用此工具。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题，用中文。例如：'今天福州的天气'、'2026年世界杯最新消息'",
            }
        },
        "required": ["query"],
    },
)
def web_search(args: dict) -> str:
    query = args["query"].strip()
    if not query:
        return "搜索失败：查询内容为空"

    prompt = f"请搜索网络获取以下信息，并给出简洁的总结：{query}"

    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env={**os.environ, "CLAUDE_CODE_SAFE_MODE": "1"},
        )
        output = (result.stdout or "").strip()
        if not output and result.stderr:
            return f"搜索失败：{(result.stderr or '')[:300]}"
        return output or "搜索未返回结果"
    except subprocess.TimeoutExpired:
        return "搜索超时，请稍后重试"
    except FileNotFoundError:
        return "搜索失败：找不到 claude CLI，请确认已安装 Claude Code"
    except Exception as e:
        return f"搜索失败：{e}"
