"""TTS 缓存 — MD5 hash → DB + WAV 文件，避免重复合成"""
import hashlib
from pathlib import Path
from typing import Optional

import db


class TTSCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[Path]:
        """命中返回缓存路径，否则 None"""
        h = self._hash(text)
        row = db.cache_get(h)
        if row and Path(row["audio_path"]).is_file():
            return Path(row["audio_path"])
        return None

    def save(self, text: str, audio: "np.ndarray", sample_rate: int, backend: str = "vits") -> Path:
        """合成后写入缓存，返回缓存路径"""
        import soundfile as sf

        h = self._hash(text)
        path = self.cache_dir / f"{h}.wav"
        sf.write(str(path), audio, sample_rate)
        db.cache_set(h, text, str(path), backend)
        return path
