# 派萌助手

实时语音对话助手，支持唤醒词检测、声纹验证、语音识别、LLM 对话和语音合成。

## 工作流程

```
唤醒词 → "我在"(TTS) → 录音(VAD) → 声纹验证(首次自动注册) → 语音转文字(SenseVoiceSmall) → DeepSeek对话 → TTS 播报
```

## 环境要求

- Python 3.10+
- 麦克风
- 可访问 DeepSeek API 的网络
- 本地 TTS 服务（默认 `192.168.1.180:6018`）

## 快速开始

```powershell
# 1. 创建虚拟环境
python -m venv venv

# 2. 安装依赖
venv\Scripts\pip install -r requirements.txt

# 3. 配置
copy .env.example .env
notepad .env          # 填入 DEEPSEEK_API_KEY

# 4. 放置唤醒词模型到 models/paimeng.onnx

# 5. 运行
venv\Scripts\python main.py
```

## 模块说明

| 模块 | 职责 |
|------|------|
| `main.py` | 入口，ONNX 补丁，主循环编排 |
| `config.py` | 加载 `.env`，导出全部配置 |
| `wakeword.py` | 唤醒词检测 |
| `tts.py` | TTS 语音播报 |
| `vad.py` | VAD 录音，静音自动停止 |
| `voiceprint.py` | 声纹提取与验证 |
| `db.py` | 声纹数据库（SQLite） |
| `stt.py` | 语音转文字 |
| `llm.py` | DeepSeek 对话 |
| `server.py` | Web 管理界面（FastAPI） |

## 配置说明

复制 `.env.example` 为 `.env` 后编辑，主要项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（必填） | — |
| `TTS_URL` | TTS 服务地址 | `http://192.168.1.180:6018/api/tts/speak` |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹相似度阈值 | 0.75 |
| `DEFAULT_SPEAKER_NAME` | 首次自动注册的名字 | 主人 |
| `DISABLE_UPDATE` | 设为 `1` 禁止模型在线更新 | 0 |

## 项目结构

```
paimon_assist/
├── main.py               # 入口 + 后台启动 Web 服务
├── server.py              # FastAPI 管理界面
├── config.py              # 配置
├── wakeword.py            # 唤醒词
├── tts.py                 # TTS 播报
├── vad.py                 # VAD 录音
├── voiceprint.py          # 声纹
├── db.py                  # 声纹数据库
├── stt.py                 # 语音转文字
├── llm.py                 # DeepSeek 对话
├── requirements.txt       # 依赖
├── .env.example           # 配置模板
├── models/
│   ├── paimeng.onnx       # 唤醒词模型
│   ├── voiceprints.db     # 声纹库（自动生成）
│   └── iic/SenseVoiceSmall/  # STT 模型（自动下载）
└── recording_*.wav        # 录音（自动生成）
```
