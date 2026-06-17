"""PulseAudio 音量控制工具"""
import subprocess
import re
import logging
from llm_tools import register

_log = logging.getLogger(__name__)

_SINK = "@DEFAULT_SINK@"


def _get_volume() -> int:
    """获取当前音量百分比"""
    r = subprocess.run(
        ["pactl", "get-sink-volume", _SINK],
        capture_output=True, text=True,
    )
    m = re.search(r"(\d+)%", r.stdout)
    return int(m.group(1)) if m else 50


@register(
    name="get_volume",
    description="获取当前扬声器音量百分比。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_volume(_args: dict = {}) -> str:
    try:
        vol = _get_volume()
        return f"当前音量 {vol}%"
    except Exception as e:
        return f"获取音量失败：{e}"


@register(
    name="set_volume",
    description="设置扬声器音量。参数为百分比数字，如 50 表示 50%。",
    parameters={
        "type": "object",
        "properties": {
            "volume": {
                "type": "integer",
                "description": "音量百分比，0-200，如 50",
            }
        },
        "required": ["volume"],
    },
)
def set_volume(args: dict) -> str:
    vol = max(0, min(200, int(args["volume"])))
    try:
        subprocess.run(
            ["pactl", "set-sink-volume", _SINK, f"{vol}%"],
            capture_output=True, check=True,
        )
        return f"音量已设为 {vol}%"
    except Exception as e:
        return f"设置音量失败：{e}"
