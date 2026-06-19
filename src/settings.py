"""统一配置读写 — settings/settings.json"""
import json
import logging
import os

_log = logging.getLogger(__name__)

_FILE = os.path.join(os.path.dirname(__file__), "..", "settings", "settings.json")
_DEFAULTS = {
    "tts_backend": "vits",
    "silent_tools": [
        "read_memory", "save_memory", "list_ac", "get_tv_state",
        "list_reminders", "get_volume", "set_volume",
    ],
}


def _load() -> dict:
    if os.path.isfile(_FILE):
        try:
            with open(_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # 合并默认值，保证所有 key 存在
            cfg = dict(_DEFAULTS)
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return dict(_DEFAULTS)


def _save(cfg: dict):
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# 模块加载时读取
config = _load()


def get(key: str):
    return config.get(key, _DEFAULTS.get(key))


def set(key: str, value):
    config[key] = value
    _save(config)


def get_silent_tools() -> set[str]:
    return set(get("silent_tools"))


def set_silent_tools(tools: set[str]):
    set("silent_tools", sorted(tools))
