"""楼下门禁开门工具"""
import logging
import requests
from llm_tools import register
from config import DOOR_OPEN_URL, DOOR_OPEN_TOKEN

_log = logging.getLogger(__name__)


@register(
    name="open_door",
    description="打开楼下门禁。调用后会自动打开单元楼的楼下门禁。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    memory_value=0,
)
def open_door(_args: dict = {}) -> str:
    """打开楼下门禁"""
    if not DOOR_OPEN_URL:
        return "门禁开门未配置（缺少 DOOR_OPEN_URL）"
    if not DOOR_OPEN_TOKEN:
        return "门禁开门未配置（缺少 DOOR_OPEN_TOKEN）"

    headers = {
        "Authorization": f"Bearer {DOOR_OPEN_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }

    try:
        resp = requests.get(DOOR_OPEN_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        _log.info("开门请求成功 status=%s body=%s", resp.status_code, resp.text[:200])
        return "门已打开"
    except requests.RequestException as e:
        _log.error("开门请求失败: %s", e)
        return f"开门失败: {e}"
