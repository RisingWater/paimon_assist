"""QB 设备位置查询工具"""
import logging
import requests
from llm_tools import BaseTool, tools
from config import cfg

_log = logging.getLogger(__name__)

_BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "client_type": "pc",
    "content-type": "application/json",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_BASE_HEADERS)
    s.headers.update({
        "authority": cfg.QB_LOCATION_AUTHORITY,
        "origin": cfg.QB_LOCATION_URL,
        "referer": f"{cfg.QB_LOCATION_URL}/login",
    })
    return s


def _login(session: requests.Session) -> bool:
    resp = session.post(
        f"{cfg.QB_LOCATION_URL}/api/sys/loginout/login",
        json={"loginName": cfg.QB_LOCATION_USERNAME, "password": QB_LOCATION_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 1000:
        _log.error("登录失败 code=%s msg=%s", data.get("code"), data.get("msg", ""))
        return False
    session.headers.update({"token": data["data"]["token"]})
    return True


def _get_devices(session: requests.Session) -> list[dict]:
    resp = session.get(
        f"{cfg.QB_LOCATION_URL}/api/device/locationManager/getOfficeDeviceTreeData",
        params={"size": 100, "current": 1, "stateType": "", "imei": "", "officeId": "", "excludeLbs": 0},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 1000:
        return []
    return data["data"].get("records", [])


def _get_address(session: requests.Session, device: dict) -> str | None:
    detail = session.post(
        f"{cfg.QB_LOCATION_URL}/api/device/locationManager/getCurrPointInfoAll",
        json={"deviceIdList": [device["id"]], "excludeLbs": 1},
        timeout=10,
    )
    detail_data = detail.json()
    if detail_data.get("code") != 1000 or not detail_data.get("data"):
        return None
    model_id = detail_data["data"][0].get("modelId")

    addr = session.post(
        f"{cfg.QB_LOCATION_URL}/api/device/locationManager/batchAddress",
        json={"pointList": [{
            "lat": device["latitude"], "lon": device["longitude"],
            "infoType": device.get("infoType", 3), "modelId": model_id,
        }]},
        timeout=10,
    )
    addr_data = addr.json()
    if addr_data.get("code") != 1000 or not addr_data.get("data"):
        return None
    return addr_data["data"][0]


def _get_yuqiao_device() -> dict | None:
    s = _new_session()
    if not _login(s):
        s.close()
        return None
    devices = _get_devices(s)
    s.close()
    if not devices:
        return None
    all_names = [d.get("name", "?") for d in devices]
    _log.info("QB devices: %s", all_names)
    yuqiao = [d for d in devices if "乔宝" in d.get("name", "")]
    return yuqiao[0] if yuqiao else None


class YuqiaoLocationTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_location",
            description="查询煜乔的当前位置。返回设备名称、电量和详细地址。",
            parameters={"type": "object", "properties": {}, "required": []},
            memory_value=8,
        )

    def execute(self, args: dict) -> str:
        try:
            d = _get_yuqiao_device()
            if not d:
                return "未找到煜乔的设备"
            s = _new_session()
            if not _login(s):
                s.close()
                return "查询位置失败：登录失败"
            name = d["name"]
            power = d.get("power", "?")
            addr = _get_address(s, d)
            s.close()
            if addr:
                return f"{name}（电量 {power}%）— {addr}"
            return f"{name}（电量 {power}%）— 地址获取失败"
        except Exception as e:
            return f"查询位置失败: {e}"


class YuqiaoPowerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="get_yuqiao_power",
            description="查询煜乔的通话器剩余电量，返回电量百分比。",
            parameters={"type": "object", "properties": {}, "required": []},
            memory_value=5,
        )

    def execute(self, args: dict) -> str:
        try:
            d = _get_yuqiao_device()
            if not d:
                return "未找到煜乔的设备"
            return f"{d['name']} 当前电量 {d.get('power', '?')}%"
        except Exception as e:
            return f"查询电量失败: {e}"


tools.register(YuqiaoLocationTool())
tools.register(YuqiaoPowerTool())
