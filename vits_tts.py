"""VITS 本地语音合成 — Paimon 音色

基于 ai-paimon-master 项目的 server.py 实现，
VITS 模型代码来自官方 jaywalnut310/vits（MIT License）。
"""
import asyncio
import json
import os
import threading
import numpy as np

import torch
import pyaudio

from vits import commons
from vits import utils
from vits.models import SynthesizerTrn
from vits.text import text_to_sequence
from vits.text.symbols import symbols  # 178 符号，仅用于 n_vocab

# ============================================================
# 路径配置
# ============================================================
CHECKPOINT = "models/paimon.pth"
CONFIG = "models/paimon_config.json"
PLAY_DEVICE = None


def _load_config(config_path: str) -> dict:
    """读取并返回 VITS 配置（HParams 对象）。

    如果 config 包含 "symbols" 键（自定义符号表），
    则 monkey-patch vits.text 的映射表。
    """
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    # 如果 config 带了自定义 symbols，替换掉 text 模块的默认映射
    if "symbols" in cfg:
        import vits.text as _text_mod

        _text_mod.symbols = cfg["symbols"]
        _text_mod._symbol_to_id = {s: i for i, s in enumerate(cfg["symbols"])}
        _text_mod._id_to_symbol = {i: s for i, s in enumerate(cfg["symbols"])}
        n_sym = len(cfg["symbols"])
    else:
        n_sym = len(symbols)

    hps = utils.get_hparams_from_file(config_path)
    return {"hps": hps, "n_symbols": n_sym}


def _get_text(text: str, hps) -> torch.LongTensor:
    """中文文本 → VITS 输入序列（与训练时完全一致）"""
    text_norm = text_to_sequence(text, hps.data.text_cleaners)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    return torch.LongTensor(text_norm)


# ============================================================
# 模型加载与推理
# ============================================================

_device = torch.device("cpu")
_model: SynthesizerTrn | None = None
_hps = None  # 训练超参


def load():
    """加载 VITS 模型（启动时调用一次）"""
    global _model, _hps

    print("Loading VITS paimon...", end=" ", flush=True)

    info = _load_config(CONFIG)
    hps = info["hps"]
    n_symbols = info["n_symbols"]
    _hps = hps

    _model = SynthesizerTrn(
        n_symbols,
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        **hps.model,
    ).to(_device)
    _model.eval()

    utils.load_checkpoint(CHECKPOINT, _model, None)
    print("Done")


def synthesize(text: str, length_scale: float = 1.0) -> np.ndarray:
    """将文本合成为音频 numpy 数组 (float32, [-1, 1])

    Args:
        text: 输入中文文本
        length_scale: 语速控制（1.0 = 正常，>1 变慢，<1 变快）
    """
    if _model is None:
        load()

    stn_tst = _get_text(text, _hps)
    if stn_tst.numel() == 0:
        return np.zeros(_hps.data.sampling_rate // 2, dtype=np.float32)

    with torch.no_grad():
        x_tst = stn_tst.unsqueeze(0).to(_device)
        x_tst_lengths = torch.LongTensor([stn_tst.size(0)]).to(_device)
        audio = (
            _model.infer(
                x_tst,
                x_tst_lengths,
                noise_scale=0.667,
                noise_scale_w=0.8,
                length_scale=length_scale,
            )[0][0, 0]
            .cpu()
            .float()
            .numpy()
        )
    return np.clip(audio, -1.0, 1.0)


# 导出采样率供缓存模块使用
SAMPLE_RATE = 22050  # biaobei_base.json: data.sampling_rate


async def synthesize_async(text: str, length_scale: float = 1.0) -> np.ndarray:
    """异步版 synthesize，在线程池中运行 CPU 推理，不阻塞事件循环"""
    return await asyncio.to_thread(synthesize, text, length_scale)


def speak(text: str):
    """合成并播放（后台线程，不阻塞）"""

    def _run():
        audio = synthesize(text)
        _play(audio)

    threading.Thread(target=_run, daemon=True).start()


def _play(audio: np.ndarray):
    """通过 PyAudio 播放音频"""
    sr = _hps.data.sampling_rate if _hps else 22050
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paFloat32,
        channels=1,
        rate=sr,
        output=True,
        output_device_index=PLAY_DEVICE,
    )
    stream.write(audio.tobytes())
    stream.stop_stream()
    stream.close()
    pa.terminate()


def wake_ack():
    """唤醒应答：播放"我在" """
    speak("我在呢")


# ============================================================
# 单元测试入口
# ============================================================
if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "你好，我是派萌，今天天气真不错呢！"
    print(f"加载模型 + 合成: 「{text}」")
    load()
    audio = synthesize(text)
    sr = _hps.data.sampling_rate if _hps else 22050
    print(f"合成完成，时长 {len(audio) / sr:.1f}s，开始播放…")
    _play(audio)
    print("播放完毕")
