"""楼下门禁开门工具"""
import logging
import requests
from llm_tools import register
from config import DOOR_OPEN_URL, DOOR_OPEN_TOKEN

_log = logging.getLogger(__name__)


@register(
    memory_value=0, silent=True,
    name="open_door",
    description="打开楼下门禁。调用后会自动打开单元楼的楼下门禁。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def open_door(_args: dict = {}) -> str:
    """打开楼下门禁"""
    if not DOOR_OPEN_URL:
        return "门禁开门未配置（缺少 DOOR_OPEN_URL）"
    if not DOOR_OPEN_TOKEN:
        return "门禁开门未配置（缺少 DOOR_OPEN_TOKEN）"

    headers = {
        "Authorization": f"bearer {DOOR_OPEN_TOKEN}",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.65(0x18004129) "
            "NetType/4G Language/zh_CN"
        ),
        "Referer": "https://servicewechat.com/wx06875950b54784ee/51/page-frame.html",
    }

    try:
        resp = requests.get(DOOR_OPEN_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "00000":
            _log.info("开门成功")
            return "门已打开"
        else:
            _log.error("开门失败: %s", data.get("msg", "未知错误"))
            return f"开门失败: {data.get('msg', '未知错误')}"
    except requests.RequestException as e:
        _log.error("开门请求失败: %s", e)
        return f"开门失败: {e}"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("开门测试...")
    print(open_door())
