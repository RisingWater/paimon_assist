"""Home Assistant 小米电视控制工具

电视的开关对应：开=退出音响模式，关=进入音响模式
HA 中通过 media_player 或 button 实体控制
"""
import logging
import requests
from llm_tools import register
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN

_log = logging.getLogger(__name__)

_HEADERS = {
    "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
    "Content-Type": "application/json",
}


def _call_service(domain: str, service: str, entity_id: str, data: dict | None = None):
    url = f"{HOME_ASSISTANT_URL}/api/services/{domain}/{service}"
    body = {"entity_id": entity_id}
    if data:
        body.update(data)
    resp = requests.post(url, json=body, headers=_HEADERS, timeout=10)
    resp.raise_for_status()


def _find_tv() -> str | None:
    """查找电视实体"""
    resp = requests.get(
        f"{HOME_ASSISTANT_URL}/api/states",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        name = s["attributes"].get("friendly_name", "")
        # 匹配电视相关实体
        if ("电视" in name or "tv" in eid.lower() or "xiaomi" in eid.lower()) and s["state"] != "unavailable":
            return eid
    return None


@register(
    name="control_tv",
    description=(
        "控制小米电视。开=退出音响模式，关=进入音响模式。"
        "根据用户说'打开电视'或'关闭电视'来调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "on=开机（退出音响模式），off=关机（进入音响模式）",
            }
        },
        "required": ["action"],
    },
)
def control_tv(args: dict) -> str:
    action = args["action"]
    try:
        entity_id = _find_tv()
        if not entity_id:
            return "没有找到小米电视"

        if action == "on":
            # 退出音响模式 = 打开电视
            _call_service("media_player", "turn_on", entity_id)
            return f"已打开电视（退出音响模式）"
        else:
            # 进入音响模式 = 关闭电视
            _call_service("media_player", "turn_off", entity_id)
            return f"已关闭电视（进入音响模式）"
    except Exception as e:
        return f"电视控制失败：{e}"
