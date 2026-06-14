# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作提供指引。

## 项目概述

"派萌助手" — 实时语音助手，处理链路：

```
唤醒词 → "我在"(TTS) → 录音(VAD) → 声纹验证 → STT → DeepSeek → TTS 播报
```

## 模块结构

| 文件 | 职责 | 对外接口 |
|------|------|----------|
| `main.py` | 入口 + ONNX patch + 主循环编排 | — |
| `config.py` | 加载 `.env`，导出全部配置常量 | 模块级变量 |
| `wakeword.py` | 唤醒词检测 | `create_listener() -> WakeWordListener` |
| `tts.py` | TTS 播报 | `speak(text)`, `wake_ack()` |
| `vad.py` | VAD 录音 | `record(counter) -> filename` |
| `voiceprint.py` | 声纹提取 + 验证 | `verify(wav_path) -> (bool, str)` |
| `db.py` | 声纹 SQLite 操作 | `enroll()`, `find_best()`, `count()` |
| `stt.py` | 语音转文字 | `load()`, `transcribe(wav_path) -> str` |
| `llm.py` | DeepSeek 对话 | `chat(user_text) -> str` |
| `server.py` | FastAPI Web 管理界面 | 内嵌 HTML + REST API |

## 运行方式

```powershell
venv\Scripts\python.exe main.py
```

启动后自动在 `http://localhost:8160` 开启声纹管理 Web 界面，可以试听录音、编辑名字、删除声纹。

## 依赖

```
livekit-wakeword[listener]
silero-vad
funasr
modelscope
pyannote.audio
requests
numpy
python-dotenv
```

ONNX Runtime 由 livekit-wakeword 间接引入。`main.py` 在顶部 monkey-patch 了 `onnxruntime.InferenceSession.__init__`，强制单线程 CPU 推理，防止线程池爆炸。

## 配置

所有参数通过 `.env` 管理（模板见 `.env.example`）。`config.py` 用 `python-dotenv` 加载并导出为模块级常量，其他模块按需 import。

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek 密钥（必填） | — |
| `TTS_URL` | TTS 服务地址 | `http://192.168.1.180:6018/api/tts/speak` |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹余弦相似度阈值 | 0.75 |
| `DEFAULT_SPEAKER_NAME` | 首次自动注册的默认名字 | 主人 |
| `DISABLE_UPDATE` | 设为 `1` 禁止模型在线更新 | 0 |

## 模型下载

| 模型 | 来源 | 自动下载 |
|------|------|----------|
| paimeng.onnx | 自定义训练/获取 | 否 |
| SenseVoiceSmall | ModelScope | 是（首次） |
| wespeaker-voxceleb-resnet34-LM | HuggingFace | 是（首次调用声纹时） |

## 注意事项

- TTS 服务是外部依赖，需单独运行。连不上时 `tts.speak()` 静默吞错。
- 录音文件 `recording_*.wav` 不会自动清理。
- `models/voiceprints.db` 是声纹数据库，删除即清空全部注册。
- `models/iic/`、`models/voiceprints.db`、`.env` 已在 `.gitignore`。
