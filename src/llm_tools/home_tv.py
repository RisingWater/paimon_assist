"""Home Assistant 小米电视控制工具

电视开关对应 button 实体：
  开（退出音响模式）= button.xxx_turn_mode_off
  关（进入音响模式）= button.xxx_turn_mode_on
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
_MITV_PREFIX = "xiaomi_cn_mitv"


def _press_button(entity_id: str):
    url = f"{HOME_ASSISTANT_URL}/api/services/button/press"
    resp = requests.post(
        url,
        json={"entity_id": entity_id},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()


def _find_tv_button(keyword: str) -> str | None:
    """查找包含关键词的电视 button 实体"""
    resp = requests.get(
        f"{HOME_ASSISTANT_URL}/api/states",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith(f"button.{_MITV_PREFIX}") and keyword in eid:
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
        if action == "on":
            eid = _find_tv_button("turn_mode_off")
            if not eid:
                return "没有找到电视开关（退出音响模式按钮）"
            _press_button(eid)
            return "已打开电视（退出音响模式）"
        else:
            eid = _find_tv_button("turn_mode_on")
            if not eid:
                return "没有找到电视开关（进入音响模式按钮）"
            _press_button(eid)
            return "已关闭电视（进入音响模式）"
    except Exception as e:
        return f"电视控制失败：{e}"


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m llm_tools.home_tv on|off|show")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "show":
        resp = requests.get(
            f"{HOME_ASSISTANT_URL}/api/states",
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        for s in resp.json():
            eid = s["entity_id"]
            if _MITV_PREFIX in eid:
                name = s["attributes"].get("friendly_name", "")
                print(f"{eid}  [{s['state']}]  {name}")
    else:
        print(control_tv({"action": cmd}))
