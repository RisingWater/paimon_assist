"""QB 设备位置查询工具"""
import logging
import requests
from llm_tools import register
from config import (
    QB_LOCATION_URL,
    QB_LOCATION_AUTHORITY,
    QB_LOCATION_USERNAME,
    QB_LOCATION_PASSWORD,
)

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
    """创建带必要 headers 的 session"""
    s = requests.Session()
    s.headers.update(_BASE_HEADERS)
    s.headers.update({
        "authority": QB_LOCATION_AUTHORITY,
        "origin": QB_LOCATION_URL,
        "referer": f"{QB_LOCATION_URL}/login",
    })
    return s


def _login(session: requests.Session) -> bool:
    """登录 QB 定位平台，成功后将 token 写入 session headers"""
    resp = session.post(
        f"{QB_LOCATION_URL}/api/sys/loginout/login",
        json={"loginName": QB_LOCATION_USERNAME, "password": QB_LOCATION_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 1000:
        _log.error("登录失败 code=%s msg=%s", data.get("code"), data.get("msg", ""))
        return False
    token = data["data"]["token"]
    session.headers.update({"token": token})
    return True


def _get_devices(session: requests.Session) -> list[dict]:
    """获取设备列表"""
    resp = session.get(
        f"{QB_LOCATION_URL}/api/device/locationManager/getOfficeDeviceTreeData",
        params={"size": 100, "current": 1, "stateType": "", "imei": "", "officeId": "", "excludeLbs": 0},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 1000:
        return []
    return data["data"].get("records", [])


def _get_address(session: requests.Session, device: dict) -> str | None:
    """根据设备信息获取详细地址"""
    # 获取 modelId
    detail = session.post(
        f"{QB_LOCATION_URL}/api/device/locationManager/getCurrPointInfoAll",
        json={"deviceIdList": [device["id"]], "excludeLbs": 1},
        timeout=10,
    )
    detail_data = detail.json()
    _log.info("getCurrPointInfoAll: code=%s", detail_data.get("code"))
    if detail_data.get("code") != 1000 or not detail_data.get("data"):
        _log.error("getCurrPointInfoAll 失败: %s", detail_data.get("msg", ""))
        return None
    model_id = detail_data["data"][0].get("modelId")

    # 根据坐标+型号查地址
    addr = session.post(
        f"{QB_LOCATION_URL}/api/device/locationManager/batchAddress",
        json={
            "pointList": [{
                "lat": device["latitude"],
                "lon": device["longitude"],
                "infoType": device.get("infoType", 3),
                "modelId": model_id,
            }]
        },
        timeout=10,
    )
    addr_data = addr.json()
    _log.info("batchAddress: code=%s data=%s", addr_data.get("code"), addr_data.get("data"))
    if addr_data.get("code") != 1000 or not addr_data.get("data"):
        _log.error("batchAddress 失败: %s", addr_data.get("msg", ""))
        return None
    return addr_data["data"][0]


@register(memory_value=8,
    name="get_yuqiao_location",
    description="查询煜乔的当前位置。返回设备名称、电量和详细地址。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def get_yuqiao_location(_args: dict = {}) -> str:
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


def _get_yuqiao_device() -> dict | None:
    """登录并获取煜乔的设备信息（共享逻辑）"""
    s = _new_session()
    if not _login(s):
        s.close()
        _log.error("登录失败")
        return None

    devices = _get_devices(s)
    s.close()
    if not devices:
        _log.error("未找到设备")
        return None
    all_names = [d.get("name", "?") for d in devices]
    _log.info("QB devices: %s", all_names)
    yuqiao = [d for d in devices if "乔宝" in d.get("name", "")]
    return yuqiao[0] if yuqiao else None


@register(memory_value=5,
    name="get_yuqiao_power",
    description="查询煜乔的通话器剩余电量，返回电量百分比。",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def get_yuqiao_power(_args: dict = {}) -> str:
    try:
        d = _get_yuqiao_device()
        if not d:
            return "未找到煜乔的设备"
        name = d["name"]
        power = d.get("power", "?")
        return f"{name} 当前电量 {power}%"
    except Exception as e:
        return f"查询电量失败: {e}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("=== 煜乔位置 ===")
    print(get_yuqiao_location())
    print("\n=== 煜乔电量 ===")
    print(get_yuqiao_power())
