"""PS5 游戏控制工具 — 一键开关 PS5 + 联动小米电视"""
import sys
import os
import logging
import time
import requests

# 支持直接运行 python llm_tools/ps5_game.py 时能找到项目模块
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_tools import BaseTool, tools
from config import cfg

_log = logging.getLogger(__name__)

_HEADERS = {"Authorization": f"Bearer {cfg.HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}
_MITV_PREFIX = "xiaomi_cn_mitv"


def _call_service(domain: str, service: str, entity_id: str, data: dict | None = None):
    """调用 Home Assistant 服务"""
    url = f"{cfg.HOME_ASSISTANT_URL}/api/services/{domain}/{service}"
    body = {"entity_id": entity_id}
    if data:
        body.update(data)
    resp = requests.post(url, json=body, headers=_HEADERS, timeout=10)
    resp.raise_for_status()


def _press_button(entity_id: str):
    """按下 HA 中的 button 实体"""
    _call_service("button", "press", entity_id)


def _find_tv_button(keyword: str) -> str | None:
    """搜索小米电视按钮实体，按 keyword 模糊匹配"""
    resp = requests.get(f"{cfg.HOME_ASSISTANT_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith(f"button.{_MITV_PREFIX}") and keyword in eid:
            return eid
    return None


def _is_audio_mode() -> bool | None:
    """查询小米电视是否处于音响模式（屏幕关闭）"""
    resp = requests.get(f"{cfg.HOME_ASSISTANT_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith("switch.") and _MITV_PREFIX in eid and "is_on" in eid:
            return s["state"] == "on"
    return None


def _find_tv_media_player() -> str | None:
    """搜索小米电视 media_player 实体"""
    resp = requests.get(f"{cfg.HOME_ASSISTANT_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if eid.startswith(f"media_player.{_MITV_PREFIX}"):
            return eid
    return None


def _find_ps5_entity() -> str | None:
    """搜索 PS5 MQTT 设备实体"""
    resp = requests.get(f"{cfg.HOME_ASSISTANT_URL}/api/states", headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    for s in resp.json():
        eid = s["entity_id"]
        if "ps5" in eid.lower() or "playstation" in eid.lower():
            return eid
    return None


class ControlPs5Tool(BaseTool):
    def __init__(self):
        super().__init__(
            name="control_ps5",
            description=(
                "控制 PS5 游戏机开关。"
                "开=退出电视音响模式→打开PS5→等3秒→切HDMI 1。"
                "关=关闭PS5→电视进入音响模式。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "power": {
                        "type": "boolean",
                        "description": "true=开启PS5打游戏，false=关闭PS5不玩了",
                    },
                },
                "required": ["power"],
            },
            memory_value=0, silent=True, final=True,
        )

    def execute(self, args: dict) -> str:
        power = args["power"]
        try:
            if power:
                # === ON 流程 ===

                # Step 1: 如果电视在音响模式，先退出（打开屏幕）
                am = _is_audio_mode()
                if am is None:
                    return "无法获取电视状态，请稍后再试"
                if am:
                    eid = _find_tv_button("turn_mode_off")
                    if not eid:
                        return "没有找到电视退出音响模式的按钮"
                    _press_button(eid)
                    _log.info("电视已退出音响模式")
                    time.sleep(1)  # 等屏幕亮起来

                # Step 2: 打开 PS5
                ps5_entity = _find_ps5_entity()
                if not ps5_entity:
                    return "未找到 PS5 设备，请检查 Home Assistant 中的 MQTT 设备配置"
                domain = ps5_entity.split(".")[0]
                _call_service(domain, "turn_on", ps5_entity)
                _log.info(f"PS5 已开启 ({ps5_entity})")

                # Step 3: 等 3 秒，切电视信源到 HDMI 1
                time.sleep(3)
                tv = _find_tv_media_player()
                if tv:
                    _call_service("media_player", "select_source", tv, {"source": "HDMI 1"})
                    _log.info(f"电视信源已切换到 HDMI 1 ({tv})")
                    return "PS5 已开启，电视已切换到 HDMI 1，开始享受游戏吧！"
                else:
                    return "PS5 已开启，但未找到电视 media_player，请手动切换到 HDMI 1"

            else:
                # === OFF 流程 ===

                # Step 1: 关闭 PS5
                ps5_entity = _find_ps5_entity()
                if ps5_entity:
                    domain = ps5_entity.split(".")[0]
                    _call_service(domain, "turn_off", ps5_entity)
                    _log.info(f"PS5 已关闭 ({ps5_entity})")
                else:
                    _log.warning("未找到 PS5 设备，跳过关闭步骤")

                # Step 2: 电视进入音响模式
                eid = _find_tv_button("turn_mode_on")
                if eid:
                    _press_button(eid)
                    return "PS5 已关闭，电视已进入音响模式"
                else:
                    return "PS5 已关闭，但未找到电视音响模式按钮，请手动操作"

        except requests.RequestException as e:
            return f"PS5 控制失败（网络错误）：{e}"
        except Exception as e:
            return f"PS5 控制失败：{e}"


tools.register(ControlPs5Tool())


# ============================================================
# main — 独立测试
# ============================================================
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("用法: python ps5_game.py [on|off]")
        print("  on  — 开启 PS5（退出音响模式→开PS5→等3秒→切HDMI）")
        print("  off — 关闭 PS5（关PS5→电视进音响模式）")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "on":
        result = tools.execute("control_ps5", {"power": True})
    elif action == "off":
        result = tools.execute("control_ps5", {"power": False})
    else:
        print(f"未知参数: {action}，请用 on 或 off")
        sys.exit(1)

    print(f"结果: {result}")
