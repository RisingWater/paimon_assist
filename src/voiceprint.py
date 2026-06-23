"""声纹提取与验证 — ModelScope 中文声纹模型"""
import logging
import os
import shutil
import numpy as np
from config import VOICEPRINT_MODEL, VOICEPRINT_THRESHOLD
import db
import memory_monitor

_log = logging.getLogger(__name__)
_pipeline = None
RECORDINGS_DIR = "recordings"


def _move_to_user_dir(wav_path: str, user_id: int) -> str:
    """将录音文件移动到 recordigns/{user_id}/ 下"""
    user_dir = os.path.join(RECORDINGS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    fname = os.path.basename(wav_path)
    dest = os.path.join(user_dir, fname)
    if os.path.abspath(wav_path) != os.path.abspath(dest):
        shutil.move(wav_path, dest)
    return dest


def load():
    global _pipeline
    if _pipeline is not None:
        return
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks

    _log.info("Loading voiceprint model...")
    _pipeline = pipeline(
        task=Tasks.speaker_verification,
        model=VOICEPRINT_MODEL,
    )
    # 注册到内存监控
    try:
        if hasattr(_pipeline, "model"):
            memory_monitor.register_model("ERes2NetV2 (声纹)", _pipeline.model,
                                          "声纹提取与验证，192维",
                                          category="模型")
        else:
            memory_monitor.register_component("ERes2NetV2 (声纹)", "ModelScope Pipeline",
                                              size_bytes=0, category="模型")
    except Exception:
        pass
    _log.info("Voiceprint model loaded")


def extract(wav_path: str) -> np.ndarray:
    result = _pipeline([wav_path, wav_path], output_emb=True)
    return np.array(result["embs"][0])


def verify(wav_path: str) -> "tuple[int|None, str, str, int]":
    """
    声纹验证（多声纹平均匹配 + 自动注册）。

    Returns:
        (user_id, 信息字符串, 移动后的文件路径, 刚添加的声纹 ID)
    """
    emb = extract(wav_path)

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
