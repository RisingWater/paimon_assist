"""TTS Web API — 合成 + 缓存 + 播放"""
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import TTS_CACHE_DIR
import tts as _tts_mod
import audio_manager

logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    length_scale: float = Field(default=1.0, gt=0)
    play: bool = Field(default=True, description="是否播放音频")


class TTSResponse(BaseModel):
    cached: bool
    file: str
    duration_ms: int


router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.post("/speak", response_model=TTSResponse)
async def text_to_speech(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    # 直接用 VITS 对象合成（保证 format/rate 一致）
    import soundfile as sf
    from pathlib import Path
    from tts_cache import TTSCache
    cache = TTSCache(Path(TTS_CACHE_DIR))

    backend = "vits"
    cached_hit = cache.get(text, backend)
    if cached_hit is not None:
        logger.info(f"TTS cache hit: {text[:30]}...")
        info = sf.info(str(cached_hit))
        if req.play:
            audio, sr = sf.read(str(cached_hit), dtype="float32")
            audio_manager.get().play_async(audio, sr)
        return TTSResponse(cached=True, file=str(cached_hit), duration_ms=int(info.duration * 1000))

    logger.info(f"TTS synthesize: {text[:30]}...")
    try:
        audio = await asyncio.to_thread(_tts_mod._vits.synthesize, text, req.length_scale)
    except Exception as e:
        logger.error(f"VITS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {e}")

    path = cache.get(text, backend)
    duration_ms = int(len(audio) / _tts_mod._vits.sample_rate * 1000)

    if req.play:
        audio_manager.get().play_async(audio, _tts_mod._vits.sample_rate)

    return TTSResponse(cached=False, file=str(path), duration_ms=duration_ms)


@router.get("/speak/{text:path}")
async def text_to_speech_get(text: str, length_scale: float = 1.0):
    req = TTSRequest(text=text, length_scale=length_scale)
    result = await text_to_speech(req)
    return FileResponse(result.file, media_type="audio/wav")
