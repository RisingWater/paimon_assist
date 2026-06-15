"""网络搜索工具 — 通过 Claude Code CLI 进行联网搜索"""
import os
import subprocess
import logging
from llm_tools import register

_log = logging.getLogger(__name__)

# Windows 上 Claude Code 安装路径
_CLAUDE_BIN = os.path.expandvars(r"%APPDATA%\npm\claude.cmd")
if not os.path.isfile(_CLAUDE_BIN):
    _CLAUDE_BIN = "claude"  # fallback 到 PATH


@register(
    name="web_search",
    description=(
        "使用联网搜索获取最新信息。当用户询问实时信息、新闻、或需要查证的事实，"
        "以及任何你知识截止日期之后发生的事件时使用此工具。"
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
            [_CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "CLAUDE_CODE_SAFE_MODE": "1"},
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            return f"搜索失败：{result.stderr[:300]}"
        return output or "搜索未返回结果"
    except subprocess.TimeoutExpired:
        return "搜索超时，请稍后重试"
    except FileNotFoundError:
        return "搜索失败：找不到 claude CLI，请确认已安装 Claude Code"
    except Exception as e:
        return f"搜索失败：{e}"
