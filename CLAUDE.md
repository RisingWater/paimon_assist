# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作提供指引。

## 项目概述

"派萌助手" — 一个实时语音助手，处理链路如下：

1. **唤醒词检测** — ONNX 模型 `models/paimeng.onnx`，通过 `livekit.wakeword` 加载
2. **唤醒应答** — 调用本地 TTS 服务播放"我在"
3. **录音 + VAD** — `silero_vad` 检测静音后自动停止录音
4. **语音转文字（STT）** — FunASR 的 `SenseVoiceSmall` 模型，离线运行
5. **LLM 对话** — 调用 DeepSeek API（`deepseek-chat`）
6. **语音合成（TTS）** — 将 LLM 回复通过 TTS 服务播放

全部代码集中在 `main.py`（约 180 行），无包结构、无测试、无构建系统——就是一个独立脚本。

## 运行方式

```powershell
venv\Scripts\python.exe main.py
```

启动后加载模型（SenseVoiceSmall 和唤醒词 ONNX），然后持续监听唤醒词，按 Ctrl+C 退出。

## 依赖

```
livekit-wakeword[listener]
silero-vad
funasr
modelscope
requests
numpy
```

ONNX Runtime 是唤醒词模型的间接依赖。脚本在启动时 monkey-patch 了 `onnxruntime.InferenceSession.__init__`，强制使用单线程 CPU 推理（防止某些 ONNX 版本在线程池上创建过多线程导致卡死）。

## 关键文件

| 文件 | 用途 |
|------|------|
| `main.py` | 应用主程序 |
| `.env` | 实际配置（含密钥，不入 git） |
| `.env.example` | 配置模板（可提交 git） |
| `models/paimeng.onnx` | 唤醒词检测 ONNX 模型 |
| `models/iic/SenseVoiceSmall/` | SenseVoiceSmall 模型目录（自动下载，已 gitignore） |

## 配置

所有可调参数通过 `.env` 文件管理。`main.py` 启动时通过 `python-dotenv` 加载 `.env`，再用 `os.getenv()` 读取。`.env.example` 是模板文件，列出全部配置项及默认值。`.env` 已加入 `.gitignore`。

关键的配置项（详见 `.env.example`）：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（必填） |
| `TTS_URL` | TTS 服务地址 |
| `THRESHOLD` | 唤醒词置信度阈值 |
| `DISABLE_UPDATE` | 设为 `1` 禁止模型在线更新 |

## 模型下载

SenseVoiceSmall 模型**首次运行时会自动下载**。`.env` 中 `DISABLE_UPDATE=0`（默认），FunASR 会自动从 ModelScope 拉取模型到 `models/iic/SenseVoiceSmall/`。设为 `1` 则跳过在线检查，仅使用本地模型。

`models/iic/` 已加入 `.gitignore`，不会提交到 git。

`models/paimeng.onnx` 是自定义唤醒词模型，需自行训练或获取。

## 注意事项

- TTS 服务是外部依赖，需要单独运行。如果连不上，`speak()` 会静默吞掉异常，不影响主流程。
- ONNX Runtime 的 monkey-patch（`main.py` 开头几行）是必须的，删除可能导致 CPU 线程爆炸。
- 每次对话的录音会保存为 `recording_*.wav` 放在工作目录下，不会自动清理。
