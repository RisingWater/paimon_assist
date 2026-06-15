"""LLM Tool 注册中心 — 按需加载工具模块，提供 OpenAI 兼容的 function schema"""

from typing import Any, Callable

# tool_name → {schema, handler}
_registry: dict[str, dict] = {}


def register(
    name: str,
    description: str,
    parameters: dict,
):
    """装饰器：注册一个 tool。被装饰函数签名为 (arguments: dict) -> str"""

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
        }
        return fn

    return decorator


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
import llm_tools.weather    # noqa: E402,F401
import llm_tools.location   # noqa: E402,F401
import llm_tools.web_search # noqa: E402,F401
