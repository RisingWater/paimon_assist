"""LLM Tool 注册中心 — 按需加载工具模块，提供 OpenAI 兼容的 function schema"""

from typing import Any, Callable

# tool_name → {schema, handler, memory_value, silent}
_registry: dict[str, dict] = {}


def register(
    name: str,
    description: str,
    parameters: dict,
    memory_value: int = 0,
    silent: bool = False,
    final: bool = False,
):
    """装饰器：注册一个 tool。

    Args:
        memory_value: 0=无记忆价值(开关/查询), 1-3=低(提醒CRUD),
                      4-6=中(天气/定位), 7-10=高(搜索/记忆)
        silent: True=调用时不播 TTS 提示语（开关/查询类工具）
        final: True=工具返回值直接作为最终回复播出，不再让 LLM 二次加工。
               失败（含"失败"/"错误"字样）时仍会交给 LLM 友好解释。
    """

    def decorator(fn: Callable[[dict], str]):
        _registry[name] = {
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
            "handler": fn,
            "memory_value": memory_value,
            "silent": silent,
            "final": final,
        }
        return fn

    return decorator


def get_memory_value(name: str) -> int:
    """返回工具的长期记忆价值（0-10）"""
    t = _registry.get(name)
    return t["memory_value"] if t else 0


def get_default_silent_tools() -> set[str]:
    """返回所有 silent=True 的工具名（工具自身声明）"""
    return {name for name, t in _registry.items() if t.get("silent")}


def is_final(name: str) -> bool:
    """工具是否标记为 final（返回值直接作为最终回复）"""
    t = _registry.get(name)
    return t.get("final", False) if t else False


def get_schemas() -> list[dict]:
    """返回 OpenAI 兼容的 tools 列表，可直接传入 API 请求"""
    return [t["schema"] for t in _registry.values()]


def execute(name: str, arguments: dict) -> str:
    """执行指定 tool，返回结果字符串"""
    tool = _registry.get(name)
    if not tool:
        return f"未知工具: {name}"
    try:
        return tool["handler"](arguments)
    except Exception as e:
        return f"工具调用失败: {e}"


# 导入所有工具模块（触发注册）
import llm_tools.weather        # noqa: E402,F401
import llm_tools.location       # noqa: E402,F401
import llm_tools.web_search     # noqa: E402,F401
import llm_tools.home_assistant_ac # noqa: E402,F401
import llm_tools.memory           # noqa: E402,F401
import llm_tools.home_tv          # noqa: E402,F401
import llm_tools.reminder         # noqa: E402,F401
import llm_tools.volume           # noqa: E402,F401
import llm_tools.ask_user         # noqa: E402,F401
import llm_tools.door             # noqa: E402,F401
