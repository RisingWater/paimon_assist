"""TTS 缓存 — MD5 文本 → WAV 文件，避免重复合成"""
import hashlib
from pathlib import Path
from typing import Optional


class TTSCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[Path]:
        """命中返回缓存路径，否则 None"""
        path = self.cache_dir / f"{self._hash(text)}.wav"
        return path if path.exists() else None

    def save(self, text: str, audio: "np.ndarray", sample_rate: int) -> Path:
        """合成后写入缓存，返回缓存路径"""
        import soundfile as sf

        path = self.cache_dir / f"{self._hash(text)}.wav"
        sf.write(str(path), audio, sample_rate)
        return path
