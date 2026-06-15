# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作提供指引。

## 项目概述

"派萌助手" — 实时语音助手，处理链路：

```
唤醒词 → "我在呢"(TTS, 同步) → 录音(VAD) → 声纹验证 → STT → DeepSeek(+Tool Calling) → TTS 播报(同步)
```

TTS 播放期间暂停唤醒词检测，播完自动恢复。

## 模块结构

| 文件 | 职责 | 对外接口 |
|------|------|----------|
| `src/main.py` | 入口 + ONNX patch + 主循环 + `--web-only` | — |
| `src/config.py` | 加载 `.env`，导出全部配置常量 | 模块级变量 |
| `src/wakeword.py` | 唤醒词检测 | `create_listener()` |
| `src/vits_tts.py` | VITS 本地合成（Paimon 音色，22050Hz），内置缓存 | `synthesize(text)`, `speak(text)`, `wake_ack()`, `speak_sync(text)` |
| `src/vad.py` | VAD 录音，silero-vad，静音自动停止 | `record(counter) -> filename` |
| `src/voiceprint.py` | 声纹提取 + 多声纹平均匹配 | `verify(wav_path) -> (user_id, info)` |
| `src/db.py` | 用户表 + 声纹表 + 聊天历史（SQLite） | `create_user()`, `enroll()`, `find_best()`, `load_history()` |
| `src/stt.py` | 语音转文字（SenseVoiceSmall） | `load()`, `transcribe(wav_path) -> str` |
| `src/llm.py` | DeepSeek 对话 + Tool Calling，按 user_id 隔离历史 | `chat(text, user_id, speaker) -> str` |
| `src/llm_tools/` | LLM 工具注册中心 + 各工具模块 | `register()`, `get_schemas()`, `execute()` |
| `src/llm_tools/weather.py` | 天气查询（wttr.in），中文描述 | `get_weather` tool |
| `src/llm_tools/location.py` | QB 设备定位查询 | `get_yuqiao_location`, `get_yuqiao_power` |
| `src/llm_tools/web_search.py` | Claude Code CLI 联网搜索 | `web_search` tool |
| `src/server.py` | FastAPI REST API + serve 前端 | REST API + SPA fallback |
| `src/tts_api.py` | FastAPI TTS 路由（/api/tts/speak） | 内嵌 cache |
| `src/tts_cache.py` | MD5 WAV 缓存，避免重复合成 | `TTSCache` |
| `src/vits/` | VITS 模型代码（jaywalnut310/vits，MIT） | 推理用 |
| `frontend/` | React + Vite + antd 前端（3 tabs） | bun run dev / bun run build |

## 运行方式

```powershell
# 完整模式（唤醒词 + STT + LLM + TTS）
python src/main.py

# 仅 Web 管理界面（不加载模型）
python src/main.py --web-only
```

Web 界面 `localhost:8160` — 三个栏目：
- **用户管理** — 创建、重命名、删除用户
- **声纹管理** — 浏览器录音 / 上传 WAV + 试听 + 声纹检测（逐条相似度）
- **聊天历史** — 按用户查看/编辑/删除 LLM 对话，内置直接提问框（绕过唤醒/STT）

## 数据库

```
users (id, name, created_at)
voiceprints (id, user_id, vector BLOB, audio_path, created_at)
chat_history (id, user_id, role, content, created_at)
  → 一个 user 可绑定多条声纹
  → LLM 对话按 user_id 独立存储
```

## 声纹匹配算法

1. 提取当前音频的 192 维 embedding（eres2netv2）
2. 与库中每条声纹计算余弦相似度
3. 筛选 sim > 0.5 的命中项
4. 0 个 user_id → 陌生人（自动创建新 user）
5. 1 个 user_id → 确定身份（追加声纹）
6. 多个 user_id → 取每个 user 的平均分，最高者胜

## LLM Tool Calling

DeepSeek 支持自动调用工具，当前注册的工具：

| Tool | 用途 |
|------|------|
| `get_weather` | 查询指定城市今天/明天天气 |
| `get_yuqiao_location` | 查询乔宝通话器的当前位置和地址 |
| `get_yuqiao_power` | 查询乔宝通话器剩余电量 |
| `web_search` | 通过 Claude Code CLI 联网搜索最新信息 |

新增工具：在 `src/llm_tools/` 下创建模块 → 用 `@register()` 装饰 → 在 `__init__.py` 导入。

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
| `DEFAULT_CITY` | 天气未指定城市时的默认城市 | 福州 |
| `CLAUDE_BIN` | Claude Code CLI 路径 | %APPDATA%\npm\claude.cmd |
| `QB_LOCATION_URL` | QB 定位平台地址 | — |
| `QB_LOCATION_AUTHORITY` | QB 定位 authority header | — |
| `QB_LOCATION_USERNAME` | QB 定位登录名 | — |
| `QB_LOCATION_PASSWORD` | QB 定位密码 | — |
| `DISABLE_UPDATE` | 设为 1 禁止模型在线更新 | 0 |

## 模型文件

| 模型 | 路径 | 说明 |
|------|------|------|
| paimeng.onnx | models/ | 唤醒词模型 |
| paimon.pth | models/ | VITS Paimon 语音合成（417MB，不提交 git） |
| paimon_config.json | models/ | VITS 训练配置 |
| SenseVoiceSmall | 自动下载到缓存 | STT 模型（iic/SenseVoiceSmall） |
| eres2netv2 | ~/.cache/modelscope/ | 声纹模型（首次自动下载） |

## 注意事项

- `.env` 包含 API 密钥，不提交 git
- TTS 缓存目录 `models/tts_cache/` 不提交 git
- 录音文件 `recording_*.wav` 不提交 git
- 声纹数据库 `models/voiceprints.db` 不提交 git
- VITS 模型权重 `models/paimon.pth` 不提交 git
