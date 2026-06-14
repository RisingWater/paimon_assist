# 派萌助手

实时语音对话助手，支持唤醒词检测、语音识别、LLM 对话和语音合成。

## 工作流程

```
唤醒词 → "我在"(TTS) → 录音(VAD) → 语音转文字(SenseVoiceSmall) → DeepSeek对话 → TTS 播报
```

## 环境要求

- Python 3.10+
- Windows / Linux / macOS
- 麦克风
- 可访问 DeepSeek API 的网络
- 本地 TTS 服务（默认地址 `192.168.1.180:6018`）

## 快速开始

```powershell
# 1. 创建虚拟环境
python -m venv venv

# 2. 安装依赖
venv\Scripts\pip install -r requirements.txt

# 3. 创建配置文件并填入你的 API Key
copy .env.example .env
notepad .env

# 4. 将唤醒词模型放到 models/paimeng.onnx（需自行训练或获取）

# 5. 运行（首次运行会自动下载 SenseVoiceSmall 模型）
venv\Scripts\python main.py
```

## 模型说明

| 模型 | 用途 | 路径 | 来源 |
|------|------|------|------|
| paimeng.onnx | 唤醒词检测 | `models/paimeng.onnx` | 自定义训练 |
| SenseVoiceSmall | 语音转文字 | `models/iic/SenseVoiceSmall/` | [ModelScope](https://www.modelscope.cn/iic/SenseVoiceSmall) |

**SenseVoiceSmall 首次运行时会自动从 ModelScope 下载**，无需手动获取。如果想离线使用，可提前下载好放到 `models/iic/SenseVoiceSmall/`，然后在 `.env` 中设置 `DISABLE_UPDATE=1`。

## 配置说明

所有配置通过 `.env` 文件管理，首次使用请复制模板并编辑：

```powershell
copy .env.example .env
```

主要配置项（完整列表见 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（必填） | — |
| `TTS_URL` | TTS 服务地址 | `http://192.168.1.180:6018/api/tts/speak` |
| `THRESHOLD` | 唤醒词灵敏度（越低越灵敏） | 0.25 |
| `DISABLE_UPDATE` | 设为 `1` 禁用模型在线更新 | 0 |
| `VAD_SILENCE_MS` | 说话后等多少毫秒结束录音 | 800 |
| `MAX_RECORD_SECONDS` | 单次录音最长秒数 | 10 |

## 项目结构

```
paimon_assist/
├── main.py               # 主程序
├── requirements.txt      # 依赖列表
├── .env.example          # 配置模板（可提交 git）
├── .env                  # 实际配置（含密钥，不入 git）
├── models/
│   ├── paimeng.onnx      # 唤醒词模型
│   └── iic/
│       └── SenseVoiceSmall/  # STT 模型（自动下载）
└── recordings_*.wav      # 录音文件（自动生成，可删除）
```
