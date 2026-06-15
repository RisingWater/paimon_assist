"""配置 — 从 .env 加载全部可调参数"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- 唤醒词 ---
MODEL_PATH = os.getenv("MODEL_PATH", "models/paimeng.onnx")
THRESHOLD = float(os.getenv("THRESHOLD", "0.25"))
DEBOUNCE = float(os.getenv("DEBOUNCE", "1.0"))

# --- TTS ---
TTS_TEXT = os.getenv("TTS_TEXT", "我在呢")
TTS_CACHE_DIR = os.getenv("TTS_CACHE_DIR", "models/tts_cache")

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# --- 天气 ---
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "福州")

# --- QB 设备定位 ---
QB_LOCATION_URL = os.getenv("QB_LOCATION_URL", "")
QB_LOCATION_AUTHORITY = os.getenv("QB_LOCATION_AUTHORITY", "")
QB_LOCATION_USERNAME = os.getenv("QB_LOCATION_USERNAME", "")
QB_LOCATION_PASSWORD = os.getenv("QB_LOCATION_PASSWORD", "")

# --- FunASR ---
DISABLE_UPDATE = os.getenv("DISABLE_UPDATE", "0") == "1"

# --- 录音 / VAD ---
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "800"))
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "10"))

# --- 声纹验证 ---
VOICEPRINT_THRESHOLD = float(os.getenv("VOICEPRINT_THRESHOLD", "0.5"))
VOICEPRINT_DB = os.getenv("VOICEPRINT_DB", "models/voiceprints.db")
VOICEPRINT_MODEL = os.getenv(
    "VOICEPRINT_MODEL", "iic/speech_eres2netv2_sv_zh-cn_16k-common"
)
