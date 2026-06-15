# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作提供指引。

## 项目概述

"派萌助手" — 实时语音助手，处理链路：

```
唤醒词 → "我在呢"(TTS) → 录音(VAD) → 声纹验证 → STT → DeepSeek → TTS 播报
```

## 模块结构

| 文件 | 职责 | 对外接口 |
|------|------|----------|
| `src/main.py` | 入口 + ONNX patch + 主循环编排 + `--web-only` | — |
| `src/config.py` | 加载 `.env`，导出全部配置常量 | 模块级变量 |
| `src/wakeword.py` | 唤醒词检测 | `create_listener()` |
| `src/vits_tts.py` | VITS 本地合成（Paimon 音色，22050Hz） | `synthesize(text)`, `speak(text)`, `wake_ack()` |
| `src/vad.py` | VAD 录音，静音自动停止 | `record(counter) -> filename` |
| `src/voiceprint.py` | 声纹提取 + 多声纹平均匹配 | `verify(wav_path) -> (user_id, info)` |
| `src/db.py` | 用户表 + 声纹表（SQLite） | `create_user()`, `enroll()`, `find_best()` |
| `src/stt.py` | 语音转文字（SenseVoiceSmall） | `load()`, `transcribe(wav_path) -> str` |
| `src/llm.py` | DeepSeek 对话，按 user_id 隔离历史 | `chat(text, user_id, speaker) -> str` |
| `src/server.py` | FastAPI REST API + serve 前端静态文件 | REST API + SPA fallback |
| `src/tts_api.py` | FastAPI TTS 路由（/api/tts/speak） | 内嵌 cache |
| `src/tts_cache.py` | MD5 WAV 缓存，避免重复合成 | `TTSCache` |
| `src/vits/` | VITS 模型代码（jaywalnut310/vits，MIT） | 推理用 |
| `frontend/` | React + Vite + antd 前端 | bun run dev / bun run build |
| `docker/` | Dockerfile + docker-compose + run.sh | 容器化部署 |

## 运行方式

```powershell
# 完整模式（唤醒词 + STT + LLM + TTS）
python src/main.py

# 仅 Web 管理界面（不加载模型）
python src/main.py --web-only
```

Web 界面：
- Dev: `cd frontend && bun run dev` → `localhost:5173`（proxy API 到 8160）
- Prod: `python src/main.py --web-only` → `localhost:8160`（serve 构建好的静态文件）
- 构建: `cd frontend && bun run build`（产物在 frontend/dist/）

## 数据库

```
users (id, name, created_at)
voiceprints (id, user_id, vector BLOB, audio_path, created_at)
  → 一个 user 可绑定多条声纹
```

## 声纹匹配算法

1. 提取当前音频的 192 维 embedding（eres2netv2）
2. 与库中每条声纹计算余弦相似度
3. 筛选 sim > 0.5 的声纹
4. 0 个 user_id → 陌生人（自动创建新 user）
5. 1 个 user_id → 确定身份（追加声纹）
6. 多个 user_id → 取每个 user 的平均分，最高者胜

## 依赖

```
torch, pyaudio, pypinyin, unidecode, phonemizer, soundfile, scipy
livekit-wakeword[listener], silero-vad, funasr, modelscope, addict
fastapi, uvicorn, python-multipart, requests
numpy, python-dotenv
```

## 关键配置（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek 密钥（必填） | — |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹相似度阈值 | 0.5 |
| `VAD_SILENCE_MS` | VAD 静音判定时间 | 800 |
| `MAX_RECORD_SECONDS` | 最长录音时间 | 10 |
| `TTS_CACHE_DIR` | TTS 缓存目录 | models/tts_cache |
| `DISABLE_UPDATE` | 设为 1 禁止模型在线更新 | 0 |

## 模型文件

| 模型 | 路径 | 说明 |
|------|------|------|
| paimeng.onnx | models/ | 唤醒词模型 |
| paimon.pth | models/ | VITS Paimon 语音合成（417MB，不提交 git） |
| paimon_config.json | models/ | VITS 训练配置（biaobei_base.json） |
| SenseVoiceSmall | models/iic/ | STT 模型（首次自动下载） |
| eres2netv2 | ~/.cache/modelscope/ | 声纹模型（首次自动下载） |

## 注意事项

- TTS 缓存目录 `models/tts_cache/` 不提交 git
- 录音文件 `recording_*.wav` 不提交 git
- 声纹数据库 `models/voiceprints.db` 不提交 git
- VITS 模型权重 `models/paimon.pth` 不提交 git
- `models/iic/` 不提交 git
