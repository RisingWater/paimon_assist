"""楼下门禁开门工具"""
import logging
import requests
from llm_tools import BaseTool, tools
from config import cfg

_log = logging.getLogger(__name__)


class DoorTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="open_door",
            description="打开楼下门禁。调用后会自动打开单元楼的楼下门禁。",
            parameters={"type": "object", "properties": {}, "required": []},
            memory_value=0, silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        if not cfg.DOOR_OPEN_URL:
            return "门禁开门未配置（缺少 cfg.DOOR_OPEN_URL）"
        if not cfg.DOOR_OPEN_TOKEN:
            return "门禁开门未配置（缺少 cfg.DOOR_OPEN_TOKEN）"

        headers = {
            "Authorization": f"bearer {cfg.DOOR_OPEN_TOKEN}",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.65(0x18004129) "
                "NetType/4G Language/zh_CN"
            ),
            "Referer": "https://servicewechat.com/wx06875950b54784ee/51/page-frame.html",
        }
        try:
            resp = requests.get(cfg.DOOR_OPEN_URL, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == "00000":
                _log.info("开门成功")
                return "楼下的门已打开"
            return f"开门失败: {data.get('msg', '未知错误')}"
        except requests.RequestException as e:
            return f"开门失败: {e}"


tools.register(DoorTool())
