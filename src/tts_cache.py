"""TTS 缓存 — MD5(text|backend) → DB + WAV 文件"""
import hashlib
from pathlib import Path
from typing import Optional

import db


class TTSCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(text: str, backend: str) -> str:
        return hashlib.md5(f"{text}|{backend}".encode("utf-8")).hexdigest()

    def get(self, text: str, backend: str = "vits") -> Optional[Path]:
        """命中返回缓存路径，否则 None"""
        h = self._hash(text, backend)
        row = db.cache_get(h)
        if row and Path(row["audio_path"]).is_file():
            return Path(row["audio_path"])
        return None

    def save(self, text: str, audio: "np.ndarray", sample_rate: int, backend: str = "vits") -> Path:
        """合成后写入缓存，返回缓存路径"""
        import soundfile as sf

        h = self._hash(text, backend)
        path = self.cache_dir / f"{h}.wav"
        sf.write(str(path), audio, sample_rate)
        db.cache_set(h, text, str(path), backend)
        return path
