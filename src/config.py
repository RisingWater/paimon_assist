"""配置 — Config 单例从 .env 加载全部可调参数

用法:
    from config import config
    api_key = config.DEEPSEEK_API_KEY

向后兼容（from config import THRESHOLD）通过模块级变量保持。
"""
import os
from dotenv import load_dotenv


class Config:
    """应用配置单例，从 .env 加载"""

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
        load_dotenv()

        # 唤醒词
        self.MODEL_PATH = os.getenv("MODEL_PATH", "models/paimeng.onnx")
        self.THRESHOLD = float(os.getenv("THRESHOLD", "0.25"))
        self.DEBOUNCE = float(os.getenv("DEBOUNCE", "1.0"))

        # TTS
        self.TTS_URL = os.getenv("TTS_URL", "http://192.168.1.180:6019/api/v1/tts/generateJson")
        self.TTS_TEXT = os.getenv("TTS_TEXT", "我在呢")
        self.TTS_CACHE_DIR = os.getenv("TTS_CACHE_DIR", "models/tts_cache")

        # DeepSeek
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
        self.DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions")
        self.DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # 天气
        self.DEFAULT_CITY = os.getenv("DEFAULT_CITY", "福州")

        # Home Assistant
        self.HOME_ASSISTANT_URL = os.getenv("HOMEASSIANT_URL", "")
        self.HOME_ASSISTANT_TOKEN = os.getenv("HOMEASSIANT_TOKEN", "")

        # Claude Code CLI
        self.CLAUDE_BIN = os.path.expandvars(os.getenv("CLAUDE_BIN", r"%APPDATA%\npm\claude.cmd"))

        # QB 设备定位
        self.QB_LOCATION_URL = os.getenv("QB_LOCATION_URL", "")
        self.QB_LOCATION_AUTHORITY = os.getenv("QB_LOCATION_AUTHORITY", "")
        self.QB_LOCATION_USERNAME = os.getenv("QB_LOCATION_USERNAME", "")
        self.QB_LOCATION_PASSWORD = os.getenv("QB_LOCATION_PASSWORD", "")

        # 门禁
        self.DOOR_OPEN_URL = os.getenv("DOOR_OPEN_URL", "")
        self.DOOR_OPEN_TOKEN = os.getenv("DOOR_OPEN_TOKEN", "")

        # FunASR
        self.DISABLE_UPDATE = os.getenv("DISABLE_UPDATE", "0") == "1"

        # 录音 / VAD
        self.SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
        self.VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "800"))
        self.MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "10"))

        # 声纹验证
        self.VOICEPRINT_THRESHOLD = float(os.getenv("VOICEPRINT_THRESHOLD", "0.5"))
        self.VOICEPRINT_DB = os.getenv("VOICEPRINT_DB", "db/paimon.db")
        self.VOICEPRINT_MODEL = os.getenv("VOICEPRINT_MODEL", "iic/speech_eres2netv2_sv_zh-cn_16k-common")


# 全局单例
config = Config()

# 向后兼容 — from config import XXX
MODEL_PATH = config.MODEL_PATH
THRESHOLD = config.THRESHOLD
DEBOUNCE = config.DEBOUNCE
TTS_URL = config.TTS_URL
TTS_TEXT = config.TTS_TEXT
TTS_CACHE_DIR = config.TTS_CACHE_DIR
DEEPSEEK_API_KEY = config.DEEPSEEK_API_KEY
DEEPSEEK_URL = config.DEEPSEEK_URL
DEEPSEEK_MODEL = config.DEEPSEEK_MODEL
DEFAULT_CITY = config.DEFAULT_CITY
HOME_ASSISTANT_URL = config.HOME_ASSISTANT_URL
HOME_ASSISTANT_TOKEN = config.HOME_ASSISTANT_TOKEN
CLAUDE_BIN = config.CLAUDE_BIN
QB_LOCATION_URL = config.QB_LOCATION_URL
QB_LOCATION_AUTHORITY = config.QB_LOCATION_AUTHORITY
QB_LOCATION_USERNAME = config.QB_LOCATION_USERNAME
QB_LOCATION_PASSWORD = config.QB_LOCATION_PASSWORD
DOOR_OPEN_URL = config.DOOR_OPEN_URL
DOOR_OPEN_TOKEN = config.DOOR_OPEN_TOKEN
DISABLE_UPDATE = config.DISABLE_UPDATE
SAMPLE_RATE = config.SAMPLE_RATE
VAD_SILENCE_MS = config.VAD_SILENCE_MS
MAX_RECORD_SECONDS = config.MAX_RECORD_SECONDS
VOICEPRINT_THRESHOLD = config.VOICEPRINT_THRESHOLD
VOICEPRINT_DB = config.VOICEPRINT_DB
VOICEPRINT_MODEL = config.VOICEPRINT_MODEL
