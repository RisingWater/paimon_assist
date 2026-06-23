"""统一配置读写 — Settings 单例管理 settings/settings.json"""
import json
import logging
import os

_log = logging.getLogger(__name__)

_FILE = os.path.join(os.path.dirname(__file__), "..", "settings", "settings.json")
_DEFAULTS = {
    "tts_backend": "vits",
    "silent_tools": [],
    "wakeword_enabled": True,
    "wakeword_schedule_enabled": False,
    "wakeword_start": "06:00",
    "wakeword_end": "24:00",
}


class Settings:
    """应用设置单例，读写 settings.json"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _load(self):
        self._config = dict(_DEFAULTS)
        if os.path.isfile(_FILE):
            try:
                with open(_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                self._config.update(data)
            except Exception:
                pass

    def _save(self):
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key: str):
        return self._config.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value):
        self._config[key] = value
        self._save()

    def get_silent_tools(self) -> set[str]:
        return set(self.get("silent_tools"))

    def set_silent_tools(self, tools: set[str]):
        self.set("silent_tools", sorted(tools))


# 全局单例
settings = Settings()
