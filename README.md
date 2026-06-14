# 派萌助手

实时语音对话助手 — 唤醒词检测 → 声纹验证 → 语音识别 → DeepSeek 对话 → VITS 语音合成。

## 工作流程

```
"派萌"唤醒 → "我在呢"(VITS TTS)
  → 录音(VAD, 静音自动停止)
  → 声纹验证(eres2netv2, 多声纹平均匹配)
  → STT(SenseVoiceSmall)
  → DeepSeek 对话(按用户独立历史)
  → VITS TTS 播报(Paimon 音色)
```

## 环境要求

- Python 3.10+
- 麦克风
- DeepSeek API Key
- 约 1.5GB 磁盘（模型自动下载）
- 约 2GB 内存（CPU 推理）

## 快速开始

```powershell
# 1. 创建虚拟环境
python -m venv venv

# 2. 安装依赖
venv\Scripts\pip install -r requirements.txt

# 3. 配置
copy .env.example .env
notepad .env          # 填入 DEEPSEEK_API_KEY

# 4. 放置唤醒词模型
#    将 paimeng.onnx 放到 models/ 目录

# 5. 放置 VITS 模型（可选，也可以只用 web TTS）
#    将 paimon.pth 放到 models/ 目录

# 6. 运行
venv\Scripts\python main.py                 # 完整模式
venv\Scripts\python main.py --web-only      # 仅 Web 管理界面
```

首次运行会自动下载 SenseVoiceSmall（STT）和 eres2netv2（声纹）模型。

Web 管理界面：`http://localhost:8160`

## 模块说明

| 模块 | 职责 |
|------|------|
| `main.py` | 入口，ONNX 补丁，主循环，`--web-only` 参数 |
| `config.py` | 加载 `.env`，导出全部配置 |
| `wakeword.py` | 唤醒词检测（paimeng.onnx） |
| `tts.py` | TTS 后端分发（vits / web） |
| `vits_tts.py` | VITS 本地语音合成，Paimon 音色，22050Hz |
| `vad.py` | VAD 录音，silero-vad，静音自动停止 |
| `voiceprint.py` | 声纹提取与多声纹匹配（eres2netv2） |
| `db.py` | SQLite 用户表 + 声纹表 |
| `stt.py` | 语音转文字（SenseVoiceSmall） |
| `llm.py` | DeepSeek 对话，按用户隔离历史 |
| `server.py` | FastAPI Web 管理界面（内嵌 HTML + REST API） |
| `tts_api.py` | TTS Web API + 缓存 |
| `tts_cache.py` | MD5 WAV 缓存 |
| `vits/` | VITS 模型代码（jaywalnut310/vits，MIT License） |

## 配置（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `TTS_BACKEND` | "vits"（本地）或 "web"（远程） | vits |
| `TTS_URL` | Web TTS 地址 | `http://192.168.1.180:6018/api/tts/speak` |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹余弦相似度阈值 | 0.5 |
| `VAD_SILENCE_MS` | 静音判定（ms） | 800 |
| `MAX_RECORD_SECONDS` | 最大录音时长 | 10 |
| `TTS_CACHE_DIR` | TTS 缓存目录 | models/tts_cache |

## Web 管理界面

`http://localhost:8160`

- 用户管理：创建、重命名、删除用户
- 声纹管理：浏览器录音 / 上传 WAV，试听，删除
- 声纹检测：录音后显示与所有库中声纹的详细相似度
- TTS API：`POST /api/tts/speak` + 缓存

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
├── main.py                # 入口
├── server.py              # Web 管理界面
├── config.py              # 配置
├── wakeword.py            # 唤醒词
├── tts.py                 # TTS 分发
├── vits_tts.py            # VITS 合成
├── vad.py                 # VAD 录音
├── voiceprint.py          # 声纹
├── db.py                  # 数据库
├── stt.py                 # 语音转文字
├── llm.py                 # DeepSeek 对话
├── tts_api.py             # TTS Web API
├── tts_cache.py           # TTS 缓存
├── web_tts.py             # HTTP TTS 后端
├── vits/                  # VITS 模型代码
├── requirements.txt       # 依赖
├── .env.example           # 配置模板
├── models/
│   ├── paimeng.onnx       # 唤醒词模型
│   ├── paimon.pth         # VITS 权重（417MB）
│   ├── paimon_config.json # VITS 配置
│   ├── tts_cache/         # TTS 缓存（自动生成）
│   └── iic/               # STT 模型（自动下载）
└── recording_*.wav        # 录音（自动生成）
```
