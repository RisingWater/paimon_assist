"""PulseAudio 音量控制工具"""
import subprocess
import re
import logging
from llm_tools import register

_log = logging.getLogger(__name__)

_CN_DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def _cn(n: int) -> str:
    if n < 10:
        return _CN_DIGITS[n]
    if n == 10:
        return "十"
    if n < 20:
        return f"十{_CN_DIGITS[n - 10]}"
    if n < 100:
        tens = _CN_DIGITS[n // 10]
        ones = _CN_DIGITS[n % 10]
        return f"{tens}十{ones}" if n % 10 else f"{tens}十"
    hundreds = _CN_DIGITS[n // 100]
    rest = n % 100
    if rest == 0:
        return f"{hundreds}百"
    return f"{hundreds}百{_cn(rest)}"

_SINK = "@DEFAULT_SINK@"


def _get_volume() -> int:
    """获取当前音量百分比"""
    r = subprocess.run(
        ["pactl", "get-sink-volume", _SINK],
        capture_output=True, text=True,
    )
    m = re.search(r"(\d+)%", r.stdout)
    return int(m.group(1)) if m else 50


@register(memory_value=0, silent=True,
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


@register(memory_value=0, silent=True, final=True,
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
        return f"音量已经设置为百分之{_cn(vol)}"
    except Exception as e:
        return f"设置音量失败：{e}"
