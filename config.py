"""配置 — 从 .env 加载全部可调参数"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- 唤醒词 ---
MODEL_PATH = os.getenv("MODEL_PATH", "models/paimeng.onnx")
THRESHOLD = float(os.getenv("THRESHOLD", "0.25"))
DEBOUNCE = float(os.getenv("DEBOUNCE", "1.0"))

# --- TTS ---
TTS_URL = os.getenv("TTS_URL", "http://192.168.1.180:6018/api/tts/speak")
TTS_TEXT = os.getenv("TTS_TEXT", "我在")

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# --- FunASR ---
DISABLE_UPDATE = os.getenv("DISABLE_UPDATE", "0") == "1"

# --- 录音 / VAD ---
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
VAD_SILENCE_MS = int(os.getenv("VAD_SILENCE_MS", "800"))
MAX_RECORD_SECONDS = int(os.getenv("MAX_RECORD_SECONDS", "10"))

# --- 声纹验证 ---
VOICEPRINT_THRESHOLD = float(os.getenv("VOICEPRINT_THRESHOLD", "0.75"))
VOICEPRINT_DB = os.getenv("VOICEPRINT_DB", "models/voiceprints.db")
VOICEPRINT_MODEL = os.getenv("VOICEPRINT_MODEL", "pyannote/wespeaker-voxceleb-resnet34-LM")
