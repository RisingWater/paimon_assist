"""Home Assistant 空调控制工具"""
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
    """调用 HA service"""
    url = f"{HOME_ASSISTANT_URL}/api/services/{domain}/{service}"
    body = {"entity_id": entity_id}
    if data:
        body.update(data)
    resp = requests.post(url, json=body, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _list_climate_entities() -> list[dict]:
    """列出所有空调实体"""
    resp = requests.get(
        f"{HOME_ASSISTANT_URL}/api/states",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return [
        {
            "entity_id": s["entity_id"],
            "name": s["attributes"].get("friendly_name", s["entity_id"]),
            "state": s["state"],
            "temperature": s["attributes"].get("temperature"),
            "hvac_modes": s["attributes"].get("hvac_modes", []),
            "min_temp": s["attributes"].get("min_temp"),
            "max_temp": s["attributes"].get("max_temp"),
        }
        for s in resp.json()
        if s["entity_id"].startswith("climate.") and s["state"] != "unavailable"
    ]


def _find_entity(name: str) -> str | None:
    """按名称模糊匹配空调实体"""
    acs = _list_climate_entities()
    for ac in acs:
        if name in ac["name"] or name in ac["entity_id"]:
            return ac["entity_id"]
    if acs:
        return acs[0]["entity_id"]  # 没匹配到就用第一个
    return None


def _fmt_ac(ac: dict) -> str:
    mode_cn = {"off": "关闭", "cool": "制冷", "heat": "制热", "auto": "自动", "fan_only": "送风", "dry": "除湿"}
    mode = mode_cn.get(ac["state"], ac["state"])
    s = f"{ac['name']}：{mode}"
    if ac.get("temperature"):
        s += f"，{ac['temperature']}°C"
    return s


# ============================================================
# Tools
# ============================================================


@register(
    name="list_ac",
    description="列出家中所有空调的名称、当前状态（开关/模式）和设定温度。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_ac(_args: dict = {}) -> str:
    try:
        acs = _list_climate_entities()
        if not acs:
            return "没有找到空调设备"
        return "\n".join(_fmt_ac(a) for a in acs)
    except Exception as e:
        return f"查询空调失败：{e}"


@register(
    name="control_ac",
    description=(
        "控制指定的空调。支持开关、设置温度、切换模式。"
        "可通过空调名称模糊匹配，如未指定则控制第一台。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "空调名称或位置，如'客厅'、'主卧'。留空则控制全部或第一台。",
            },
            "action": {
                "type": "string",
                "enum": ["on", "off", "set_temp", "set_mode"],
                "description": "操作：on=开机, off=关机, set_temp=设置温度, set_mode=切换模式",
            },
            "value": {
                "type": "string",
                "description": "参数值：set_temp 时填温度数字如 26，set_mode 时填 cool/heat/auto/dry/fan_only",
            },
        },
        "required": ["action"],
    },
)
def control_ac(args: dict) -> str:
    action = args.get("action", "")
    name = args.get("name", "")
    value = args.get("value", "")

    try:
        entity_id = _find_entity(name) if name else None
        if not entity_id:
            if name:
                return f"未找到名称包含'{name}'的空调"
            acs = _list_climate_entities()
            if not acs:
                return "没有找到空调设备"
            entity_id = acs[0]["entity_id"]

        if action == "on":
            _call_service("climate", "turn_on", entity_id)
            return f"已开启 {entity_id}"

        elif action == "off":
            _call_service("climate", "turn_off", entity_id)
            return f"已关闭 {entity_id}"

        elif action == "set_temp":
            if not value:
                return "请指定温度，如 26"
            temp = float(value)
            _call_service("climate", "set_temperature", entity_id, {"temperature": temp})
            return f"已设置 {entity_id} 温度为 {temp}°C"

        elif action == "set_mode":
            if not value:
                return "请指定模式：cool(制冷)/heat(制热)/auto(自动)/dry(除湿)/fan_only(送风)"
            valid = {"cool", "heat", "auto", "dry", "fan_only"}
            value = value.lower()
            if value not in valid:
                return f"无效模式，可选：{', '.join(sorted(valid))}"
            _call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": value})
            mode_cn = {"cool": "制冷", "heat": "制热", "auto": "自动", "dry": "除湿", "fan_only": "送风"}
            return f"已设置 {entity_id} 模式为 {mode_cn.get(value, value)}"

        return f"未知操作: {action}"

    except Exception as e:
        return f"空调控制失败：{e}"
