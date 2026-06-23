"""LLM Tool Calling — BaseTool(MemoryTracked) 基类 + ToolRegistry 单例

每个工具继承 BaseTool，定义 schema + execute(args) → str。
模块加载时自动实例化并注册到 ToolRegistry。
"""
import logging
from memory_monitor import MemoryTracked

_log = logging.getLogger(__name__)


# ============================================================
# BaseTool — 工具基类，继承 MemoryTracked 自动获得内存追踪
# ============================================================

class BaseTool(MemoryTracked):
    """LLM 工具基类。子类需实现 execute(args) → str。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        memory_value: int = 0,
        silent: bool = False,
        final: bool = False,
    ):
        super().__init__(name=name, description=description, category="Tool")
        self.memory_value = memory_value
        self.silent = silent
        self.final = final
        self._schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    @property
    def schema(self) -> dict:
        return self._schema

    def execute(self, args: dict) -> str:
        raise NotImplementedError(f"{self._mem_name}.execute() not implemented")


# ============================================================
# ToolRegistry — 工具注册中心单例
# ============================================================

class ToolRegistry(MemoryTracked):
    """工具注册中心单例，管理所有 BaseTool 的注册/查找/执行"""

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
        super().__init__("Tool 注册表", "所有 LLM 工具的注册中心", category="Tool")
        self._tools: dict[str, BaseTool] = {}

    # ---- 注册 ----

    def register(self, tool: BaseTool):
        self._tools[tool.schema["function"]["name"]] = tool

    # ---- 查询 ----

    def get_schemas(self) -> list[dict]:
        return [t.schema for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"未知工具: {name}"
        try:
            return tool.execute(arguments)
        except Exception as e:
            return f"工具调用失败: {e}"

    def get_memory_value(self, name: str) -> int:
        tool = self._tools.get(name)
        return tool.memory_value if tool else 0

    def get_default_silent_tools(self) -> set[str]:
        return {name for name, t in self._tools.items() if t.silent}

    def is_final(self, name: str) -> bool:
        tool = self._tools.get(name)
        return tool.final if tool else False

    def __len__(self):
        return len(self._tools)


# ============================================================
# 全局单例
# ============================================================

tools = ToolRegistry()

# 向后兼容别名（旧代码 from llm_tools import register / get_schemas / execute ...）
register = tools.register
get_schemas = tools.get_schemas
execute = tools.execute
get_memory_value = tools.get_memory_value
get_default_silent_tools = tools.get_default_silent_tools
is_final = tools.is_final


# ============================================================
# 导入所有工具模块（触发注册）
# ============================================================

import llm_tools.weather             # noqa: E402,F401
import llm_tools.location            # noqa: E402,F401
import llm_tools.web_search          # noqa: E402,F401
import llm_tools.home_assistant_ac   # noqa: E402,F401
import llm_tools.memory              # noqa: E402,F401
import llm_tools.home_tv             # noqa: E402,F401
import llm_tools.reminder            # noqa: E402,F401
import llm_tools.volume              # noqa: E402,F401
import llm_tools.ask_user            # noqa: E402,F401
import llm_tools.door                # noqa: E402,F401
