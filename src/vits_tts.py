"""VITS 本地语音合成 — Paimon 音色

基于 ai-paimon-master 项目的 server.py 实现，
VITS 模型代码来自官方 jaywalnut310/vits（MIT License）。
"""
import asyncio
import json
import logging
import queue
import re
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import pyaudio

_log = logging.getLogger(__name__)

from vits import commons
from vits import utils
from vits.models import SynthesizerTrn
from vits.text import text_to_sequence
from vits.text.symbols import symbols

from tts_cache import TTSCache
import audio_manager


def _load_config(config_path: str) -> dict:
    """读取并返回 VITS 配置（HParams 对象）。

    如果 config 包含 "symbols" 键（自定义符号表），
    则 monkey-patch vits.text 的映射表。
    """
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

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
# VitsTTS
# ============================================================

class VitsTTS:
    """VITS 语音合成引擎（Paimon 音色，22050Hz）"""

    def __init__(self, checkpoint: str, config: str, cache_dir: Path, play_device: int | None = None):
        self.checkpoint = checkpoint
        self.config = config
        self.play_device = play_device
        self.sample_rate = 22050  # biaobei_base.json: data.sampling_rate

        self._device = torch.device("cpu")
        self._model: SynthesizerTrn | None = None
        self._hps = None
        self._cache = TTSCache(cache_dir)

    # ---- 加载 ----

    def load(self):
        """加载 VITS 模型（启动时调用一次）"""
        _log.info("Loading VITS paimon...")

        info = _load_config(self.config)
        hps = info["hps"]
        n_symbols = info["n_symbols"]
        self._hps = hps

        self._model = SynthesizerTrn(
            n_symbols,
            hps.data.filter_length // 2 + 1,
            hps.train.segment_size // hps.data.hop_length,
            **hps.model,
        ).to(self._device)
        self._model.eval()

        utils.load_checkpoint(self.checkpoint, self._model, None)
        _log.info("VITS paimon loaded")

    # ---- 合成 ----

    def synthesize(self, text: str, length_scale: float = 1.0) -> np.ndarray:
        """将文本合成为音频 numpy 数组 (float32, [-1, 1])

        自动走缓存：相同文本只合成一次，后续直接读 WAV。
        """
        cached = self._cache.get(text)
        if cached is not None:
            audio, _sr = sf.read(str(cached), dtype="float32")
            return audio

        if self._model is None:
            self.load()

        stn_tst = _get_text(text, self._hps)
        if stn_tst.numel() == 0:
            return np.zeros(self._hps.data.sampling_rate // 2, dtype=np.float32)

        with torch.no_grad():
            x_tst = stn_tst.unsqueeze(0).to(self._device)
            x_tst_lengths = torch.LongTensor([stn_tst.size(0)]).to(self._device)
            audio = (
                self._model.infer(
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
        audio = np.clip(audio, -1.0, 1.0)

        self._cache.save(text, audio, self.sample_rate)
        return audio

    async def synthesize_async(self, text: str, length_scale: float = 1.0) -> np.ndarray:
        """异步版 synthesize，在线程池中运行 CPU 推理，不阻塞事件循环"""
        return await asyncio.to_thread(self.synthesize, text, length_scale)

    # ---- 播放 ----

    def speak(self, text: str):
        """合成并播放（异步，入队即返回）"""
        def _run():
            audio = self.synthesize(text)
            audio_manager.init()
            audio_manager.get().play_async(audio)
        threading.Thread(target=_run, daemon=True).start()

    def speak_sync(self, text: str):
        """合成并播放（阻塞直到播放完成）

        长文本按句拆分，TTS 合成一句就入队播放，后台继续合下一句。
        首句延迟大幅降低。
        """
        sentences = re.split(r"(?<=[。！？；\n])", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return

        # 合并短句（< 5 字并到下一句）
        merged = []
        i = 0
        while i < len(sentences):
            chunk = sentences[i]
            while len(chunk) < 5 and i + 1 < len(sentences):
                i += 1
                chunk += sentences[i]
            merged.append(chunk)
            i += 1

        if len(merged) == 1:
            self._play(self.synthesize(merged[0]))
            return

        audio_queue = queue.Queue()
        synth_done = threading.Event()
        sr = self._hps.data.sampling_rate if self._hps else self.sample_rate

        # 第一句提前合成入队，消除首句延迟
        _log.info("[TTS 1/%d start] %s", len(merged), merged[0])
        audio_queue.put(self.synthesize(merged[0]).tobytes())

        def _producer():
            for i, s in enumerate(merged[1:], 1):
                _log.info("[TTS %d/%d start] %s", i + 1, len(merged), s)
                audio_queue.put(self.synthesize(s).tobytes())
            synth_done.set()

        threading.Thread(target=_producer, daemon=True).start()

        current_chunk = audio_queue.get()
        offset = 0

        def _callback(in_data, frame_count, time_info, status):
            nonlocal current_chunk, offset
            needed = frame_count * 4
            buf = bytearray()

            while len(buf) < needed:
                if current_chunk is None:
                    if synth_done.is_set() and audio_queue.empty():
                        break
                    try:
                        current_chunk = audio_queue.get_nowait()
                        offset = 0
                    except queue.Empty:
                        break

                remaining = len(current_chunk) - offset
                take = min(remaining, needed - len(buf))
                buf.extend(current_chunk[offset:offset + take])
                offset += take
                if offset >= len(current_chunk):
                    current_chunk = None

            if len(buf) == 0 and synth_done.is_set():
                return (b"\x00" * needed, pyaudio.paComplete)
            elif len(buf) < needed:
                buf.extend(b"\x00" * (needed - len(buf)))
                return (bytes(buf), pyaudio.paContinue)
            else:
                return (bytes(buf), pyaudio.paContinue)

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paFloat32, channels=1, rate=sr,
            output=True, output_device_index=self.play_device,
            stream_callback=_callback,
        )
        stream.start_stream()
        while stream.is_active():
            import time as _time
            _time.sleep(0.05)
        stream.stop_stream()
        stream.close()
        pa.terminate()

    def _play(self, audio: np.ndarray):
        """通过音频管理器播放（同步：阻塞到播完）"""
        audio_manager.init()
        audio_manager.get().play_sync(audio)

    def wake_ack(self):
        """唤醒应答（非阻塞）"""
        self.speak("我在呢")

    def wake_ack_sync(self):
        """唤醒应答（阻塞直到播放完成）"""
        self.speak_sync("我在呢")


# ============================================================
# 模块级单例（向后兼容）
# ============================================================

_tts = VitsTTS(
    checkpoint="models/paimon.pth",
    config="models/paimon_config.json",
    cache_dir=Path("models/tts_cache"),
)

SAMPLE_RATE = _tts.sample_rate
load = _tts.load
synthesize = _tts.synthesize
synthesize_async = _tts.synthesize_async
speak = _tts.speak
wake_ack = _tts.wake_ack
tts = _tts  # 也可作为 tts.load() / tts.speak() 使用

# ============================================================
# 单元测试入口
# ============================================================
if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "你好，我是派萌，今天天气真不错呢！"
    print(f"加载模型 + 合成: 「{text}」")
    _tts.load()
    audio = _tts.synthesize(text)
    sr = _tts._hps.data.sampling_rate if _tts._hps else SAMPLE_RATE
    print(f"合成完成，时长 {len(audio) / sr:.1f}s，开始播放…")
    _tts._play(audio)
    print("播放完毕")
