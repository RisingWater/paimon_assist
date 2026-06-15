# 派萌助手

实时语音对话助手 — 唤醒词检测 → 声纹验证 → 语音识别 → DeepSeek 对话 → VITS 语音合成。

## 工作流程

```
"派萌"唤醒 → "我在呢"(VITS TTS)
  → 录音(VAD, 静音自动停止)
  → 声纹验证(eres2netv2, 多声纹平均匹配)
  → STT(SenseVoiceSmall)
  → DeepSeek 对话(按用户独立历史，持久化到 SQLite)
  → VITS TTS 播报(Paimon 音色)
```

## 环境要求

- Python 3.10+
- 麦克风 + 扬声器
- DeepSeek API Key
- 约 2GB 磁盘（模型文件）
- 约 2GB 内存（CPU 推理）

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 4. 放置唤醒词模型
#    将 paimeng.onnx 放到 models/ 目录

# 5. 运行
python src/main.py                 # 完整模式（唤醒词 + STT + LLM + TTS）
python src/main.py --web-only      # 仅 Web 管理界面（不加载模型）
```

首次运行会自动下载 SenseVoiceSmall（STT）和 eres2netv2（声纹）模型。

## 前端（Web 管理界面）

```bash
cd frontend
bun install
bun run dev          # 开发模式 :5173（proxy API 到 :8160）
bun run build        # 构建产物到 frontend/dist/
```

生产环境：`python src/main.py --web-only` 在 `:8160` 同时 serve API 和前端静态文件。

## Docker 部署

```bash
docker compose -f docker/docker-compose.yml up -d
```

容器内 PulseAudio 自动启动，加载 ALSA 扬声器 + 麦克风，通过 `/var/run/pulse` 可与其他容器共享音频。

## 配置（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹余弦相似度阈值 | 0.5 |
| `VAD_SILENCE_MS` | 静音判定（ms） | 800 |
| `MAX_RECORD_SECONDS` | 最大录音时长 | 10 |
| `TTS_CACHE_DIR` | TTS 缓存目录 | models/tts_cache |

## 模块说明

| 模块 | 职责 |
|------|------|
| `src/main.py` | 入口，ONNX 补丁，主循环，`--web-only` |
| `src/config.py` | 加载 `.env`，导出全部配置 |
| `src/wakeword.py` | 唤醒词检测（paimeng.onnx） |
| `src/vits_tts.py` | VITS 语音合成（Paimon 音色，22050Hz） |
| `src/vad.py` | VAD 录音（silero-vad，静音自动停止） |
| `src/voiceprint.py` | 声纹提取与匹配（eres2netv2） |
| `src/db.py` | SQLite：用户表 + 声纹表 + 聊天历史 |
| `src/stt.py` | 语音转文字（SenseVoiceSmall） |
| `src/llm.py` | DeepSeek 对话，按用户隔离历史，持久化 |
| `src/server.py` | FastAPI REST API + serve 前端 |
| `src/tts_api.py` | TTS Web API |
| `src/tts_cache.py` | MD5 WAV 缓存 |
| `src/vits/` | VITS 模型代码（jaywalnut310/vits，MIT） |
| `frontend/` | React + Vite + antd 前端 |
| `docker/` | Dockerfile + docker-compose + run.sh |

## Web 管理界面

`http://localhost:8160` — 三个栏目：

- **用户管理** — 创建、重命名、删除用户
- **声纹管理** — 浏览器录音 / 上传 WAV，试听，删除，声纹检测
- **聊天历史** — 查看、编辑、删除、清空每个用户的 LLM 对话记录

## 声纹匹配逻辑

1. 提取 192 维 embedding（eres2netv2）
2. 与库中每条声纹计算余弦相似度
3. 筛选 sim > 0.5 的命中项
4. 0 个 user → 陌生人，自动注册
5. 1 个 user → 确定身份，追加声纹
6. 多个 user → 取平均分最高者

## 项目结构

```
paimon_assist/
├── src/                    # Python 后端
│   ├── main.py             # 入口
│   ├── server.py           # FastAPI + REST API
│   ├── config.py           # 配置加载
│   ├── wakeword.py         # 唤醒词
│   ├── vits_tts.py         # VITS 合成
│   ├── vad.py              # VAD 录音
│   ├── voiceprint.py       # 声纹
│   ├── db.py               # 数据库
│   ├── stt.py              # 语音转文字
│   ├── llm.py              # LLM 对话
│   ├── tts_api.py          # TTS API
│   ├── tts_cache.py        # TTS 缓存
│   └── vits/               # VITS 模型代码
├── frontend/               # React + Vite + antd 前端
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── components/     # UserTab, VoiceprintTab, ChatTab
│       └── dialogs/        # CreateUser, AddVoiceprint, Detect
├── docker/                 # Docker 部署
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── run.sh
├── models/                 # 模型文件
│   ├── paimeng.onnx        # 唤醒词模型
│   ├── paimon.pth          # VITS 权重（417MB，LFS）
│   ├── paimon_config.json  # VITS 配置
│   ├── tts_cache/          # TTS 缓存（自动生成）
│   └── iic/                # STT 模型（自动下载）
├── requirements.txt
├── .env.example
└── .gitattributes          # Git LFS 配置
```
