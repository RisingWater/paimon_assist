"""声纹提取与验证 — ModelScope 中文声纹模型"""
import logging
import os
import shutil
import numpy as np
from config import cfg
import db
from memory_monitor import MemoryTracked

_log = logging.getLogger(__name__)
RECORDINGS_DIR = "recordings"


def _move_to_user_dir(wav_path: str, user_id: int) -> str:
    user_dir = os.path.join(RECORDINGS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    fname = os.path.basename(wav_path)
    dest = os.path.join(user_dir, fname)
    if os.path.abspath(wav_path) != os.path.abspath(dest):
        shutil.move(wav_path, dest)
    return dest


class VoiceprintEngine(MemoryTracked):
    """声纹提取与验证引擎（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    @classmethod
    def instance(cls):
        return cls()

    def _init(self):
        super().__init__("ERes2NetV2 (声纹)", "声纹提取与验证，192维", category="模型")
        self._pipeline = None

    def _mem_size(self) -> int:
        if self._pipeline and hasattr(self._pipeline, "model"):
            return MemoryTracked._model_size(self._pipeline.model)
        return 0

    def load(self):
        if self._pipeline is not None:
            return
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks

        _log.info("Loading voiceprint model...")
        self._pipeline = pipeline(
            task=Tasks.speaker_verification,
            model=cfg.VOICEPRINT_MODEL,
        )
        _log.info("Voiceprint model loaded")

    def extract(self, wav_path: str) -> np.ndarray:
        result = self._pipeline([wav_path, wav_path], output_emb=True)
        return np.array(result["embs"][0])

    def verify(self, wav_path: str) -> "tuple[int|None, str, str, int]":
        emb = self.extract(wav_path)

        if db.count() == 0:
            uid = db.create_user("")
            dest = _move_to_user_dir(wav_path, uid)
            vp_id = db.enroll(uid, emb, audio_path=dest)
            return uid, "enrolled:", dest, vp_id

        uid, name, avg_sim = db.find_best(emb)

        if uid is not None:
            dest = _move_to_user_dir(wav_path, uid)
            vp_id = db.enroll(uid, emb, audio_path=dest)
            display = name if name else f"用户#{uid}"
            return uid, f"{display}:{avg_sim:.4f}", dest, vp_id

        uid = db.create_user("")
        dest = _move_to_user_dir(wav_path, uid)
        vp_id = db.enroll(uid, emb, audio_path=dest)
        return uid, "enrolled:", dest, vp_id


# 全局单例
vp_engine = VoiceprintEngine()
