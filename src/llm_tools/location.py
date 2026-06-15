"""QB 设备位置查询工具"""
import requests
from llm_tools import register
from config import (
    QB_LOCATION_URL,
    QB_LOCATION_AUTHORITY,
    QB_LOCATION_USERNAME,
    QB_LOCATION_PASSWORD,
)


def _login(session: requests.Session) -> bool:
    """登录 QB 定位平台，成功后将 token 写入 session headers"""
    resp = session.post(
        f"{QB_LOCATION_URL}/api/sys/loginout/login",
        json={"loginName": QB_LOCATION_USERNAME, "password": QB_LOCATION_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 1000:
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
    if detail_data.get("code") != 1000 or not detail_data.get("data"):
        return None
    model_id = detail_data["data"][0].get("modelId")

    # 根据坐标+型号查地址
    addr = session.post(
        f"{QB_LOCATION_URL}/api/device/locationManager/batchAddress",
        json={
            "pointList": [{
                "lat": device["latitude"],
                "lon": device["longitude"],
                "infoType": device["infoType"],
                "modelId": model_id,
            }]
        },
        timeout=10,
    )
    addr_data = addr.json()
    if addr_data.get("code") != 1000 or not addr_data.get("data"):
        return None
    return addr_data["data"][0]


@register(
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

        s = requests.Session()
        s.headers.update({
            "authority": QB_LOCATION_AUTHORITY,
            "accept": "application/json",
            "content-type": "application/json",
            "origin": QB_LOCATION_URL,
            "referer": f"{QB_LOCATION_URL}/login",
            "user-agent": "Mozilla/5.0",
        })
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
    s = requests.Session()
    s.headers.update({
        "authority": QB_LOCATION_AUTHORITY,
        "accept": "application/json",
        "content-type": "application/json",
        "origin": QB_LOCATION_URL,
        "referer": f"{QB_LOCATION_URL}/login",
        "user-agent": "Mozilla/5.0",
    })
    if not _login(s):
        s.close()
        return None
    devices = _get_devices(s)
    s.close()
    if not devices:
        return None
    yuqiao = [d for d in devices if "煜乔" in d.get("name", "")]
    return yuqiao[0] if yuqiao else None


@register(
    name="get_yuqiao_power",
    description="查询煜乔通话器的剩余电量。返回电量百分比。",
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
