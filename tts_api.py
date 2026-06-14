"""TTS Web API — VITS 合成 + 缓存，参考 audio_services 接口风格"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from tts_cache import TTSCache
from config import TTS_CACHE_DIR
import vits_tts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    length_scale: float = Field(default=1.0, gt=0)


class TTSResponse(BaseModel):
    cached: bool
    file: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Cache init
# ---------------------------------------------------------------------------
_cache = TTSCache(Path(TTS_CACHE_DIR))

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("/speak", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """文字转语音，返回 WAV 音频文件"""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    # 1. 查缓存
    cached = _cache.get(text)
    if cached is not None:
        logger.info(f"TTS cache hit: {text[:30]}...")
        import soundfile as sf
        info = sf.info(str(cached))
        return TTSResponse(cached=True, file=str(cached), duration_ms=int(info.duration * 1000))

    # 2. VITS 合成
    logger.info(f"TTS synthesize: {text[:30]}...")
    try:
        audio = await vits_tts.synthesize_async(text, length_scale=req.length_scale)
    except Exception as e:
        logger.error(f"VITS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {e}")

    # 3. 写缓存
    sr = vits_tts.SAMPLE_RATE if hasattr(vits_tts, "SAMPLE_RATE") else 22050
    path = _cache.save(text, audio, sr)

    return TTSResponse(
        cached=False,
        file=str(path),
        duration_ms=int(len(audio) / sr * 1000),
    )


@router.get("/speak/{text:path}")
async def text_to_speech_get(text: str, length_scale: float = 1.0):
    """GET 方式 TTS（方便调试）"""
    req = TTSRequest(text=text, length_scale=length_scale)
    result = await text_to_speech(req)
    return FileResponse(result.file, media_type="audio/wav")
