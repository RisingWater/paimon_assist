"""TTS Web API — VITS 合成 + 缓存，参考 audio_services 接口风格

所有音频生成都经过 vits_tts.synthesize()，内部已集成缓存，
相同文本自动命中，不会重复推理。
"""
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
# Cache（仅用于查路径；实际存取在 vits_tts.synthesize() 内部）
# ---------------------------------------------------------------------------
_cache = TTSCache(Path(TTS_CACHE_DIR))

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("/speak", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    """文字转语音，返回 WAV 音频文件（自动缓存）"""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    # 先查缓存（用于返回 cached 标识）
    cached_hit = _cache.get(text)
    if cached_hit is not None:
        logger.info(f"TTS cache hit: {text[:30]}...")
        import soundfile as sf
        info = sf.info(str(cached_hit))
        return TTSResponse(cached=True, file=str(cached_hit), duration_ms=int(info.duration * 1000))

    # 调用 VITS（内部也会查缓存 + 写缓存）
    logger.info(f"TTS synthesize: {text[:30]}...")
    try:
        audio = await vits_tts.tts.synthesize_async(text, length_scale=req.length_scale)
    except Exception as e:
        logger.error(f"VITS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {e}")

    # synthesize 内部已写缓存，直接拿路径
    path = _cache.get(text)
    duration_ms = int(len(audio) / vits_tts.tts.sample_rate * 1000)

    return TTSResponse(cached=False, file=str(path), duration_ms=duration_ms)


@router.get("/speak/{text:path}")
async def text_to_speech_get(text: str, length_scale: float = 1.0):
    """GET 方式 TTS（方便调试）"""
    req = TTSRequest(text=text, length_scale=length_scale)
    result = await text_to_speech(req)
    return FileResponse(result.file, media_type="audio/wav")
