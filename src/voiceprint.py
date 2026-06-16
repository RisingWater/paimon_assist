"""声纹提取与验证 — ModelScope 中文声纹模型"""
import os
import shutil
import numpy as np
from config import VOICEPRINT_MODEL, VOICEPRINT_THRESHOLD
import db

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

    print("Loading voiceprint model...", end=" ", flush=True)
    _pipeline = pipeline(
        task=Tasks.speaker_verification,
        model=VOICEPRINT_MODEL,
    )
    print("Done")


def extract(wav_path: str) -> np.ndarray:
    result = _pipeline([wav_path, wav_path], output_emb=True)
    return np.array(result["embs"][0])


def verify(wav_path: str) -> "tuple[int|None, str]":
    """
    声纹验证（多声纹平均匹配 + 自动注册）。

    Returns:
        (user_id, 信息字符串)
        user_id=None 表示没匹配到任何人（会自动注册新用户）
    """
    emb = extract(wav_path)

    # 库为空 → 创建第一个用户
    if db.count() == 0:
        uid = db.create_user("")
        dest = _move_to_user_dir(wav_path, uid)
        db.enroll(uid, emb, audio_path=dest)
        return uid, "enrolled:"

    # 多声纹平均匹配
    uid, name, avg_sim = db.find_best(emb)

    if uid is not None:
        # 匹配成功 → 追加一条声纹（丰富这个用户的声纹库）
        dest = _move_to_user_dir(wav_path, uid)
        db.enroll(uid, emb, audio_path=dest)
        display = name if name else f"用户#{uid}"
        return uid, f"{display}:{avg_sim:.4f}"

    # 陌生人 → 新建用户 + 首条声纹
    uid = db.create_user("")
    dest = _move_to_user_dir(wav_path, uid)
    db.enroll(uid, emb, audio_path=dest)
    return uid, "enrolled:"
