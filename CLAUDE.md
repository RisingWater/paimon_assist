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
| `src/wakeword.py` | 唤醒词检测 + 音频收集（训练数据） | `create_listener()`, `classify_audio()` |
| `src/log_manager.py` | 日志管理（磁盘 20MB + 内存缓冲 + 异常捕获） | `setup()`, `get_logs()`, `export_text()`, `clear()` |
| `src/tts/` | TTS 模块 — VITS/HTTP 工厂 + 缓存 + API + 音频管理 | `import tts` |
| `src/tts/vits_tts.py` | VitsTTS（Paimon 22050Hz） | `synthesize() → (audio, sr)` |
| `src/tts/tts_http.py` | HttpTTS（EasyVoice API） | `synthesize() → (audio, sr)` |
| `src/tts/__init__.py` | TTS 工厂分发 | `speak()`, `wake_ack()`, `load()` |
| `src/tts/audio_manager.py` | 统一音频管理（播放 + 录音） | `play_async()`, `play_sync()`, `record()` |
| `src/settings.py` | 统一配置读写（settings/settings.json） | `get(key)`, `set(key, value)` |
| `src/vad.py` | VAD 录音，委托给 AudioManager | `record(counter) -> filename` |
| `src/voiceprint.py` | 声纹提取 + 多声纹平均匹配 | `verify(wav_path) -> (user_id, info)` |
| `src/db.py` | 用户表 + 声纹表 + 聊天历史（SQLite） | `create_user()`, `enroll()`, `find_best()`, `load_history()` |
| `src/stt.py` | 语音转文字（SenseVoiceSmall） | `load()`, `transcribe(wav_path) -> str` |
| `src/llm.py` | DeepSeek 对话 + Tool Calling，按 user_id 隔离历史 | `chat(text, user_id, speaker) -> str` |
| `src/llm_tools/` | LLM 工具注册中心 + 各工具模块 | `register()`, `get_schemas()`, `execute()` |
| `src/llm_tools/weather.py` | 天气查询（wttr.in），中文描述 | `get_weather` tool |
| `src/llm_tools/location.py` | QB 设备定位查询 | `get_yuqiao_location`, `get_yuqiao_power` |
| `src/llm_tools/web_search.py` | Claude Code CLI 联网搜索 | `web_search` tool |
| `src/llm_tools/home_assistant_ac.py` | Home Assistant 空调控制 | `list_ac`, `control_ac` |
| `src/llm_tools/home_tv.py` | Home Assistant 小米电视控制 | `get_tv_state`, `control_tv` |
| `src/llm_tools/memory.py` | 长期记忆读写（memory.md） | `read_memory`, `save_memory` |
| `src/llm_tools/reminder.py` | 定时提醒（一次性/每天/每月/农历） | `add_reminder`, `list_reminders`, `delete_reminder` |
| `src/llm_tools/volume.py` | PulseAudio 音量控制 | `get_volume`, `set_volume` |
| `src/llm_tools/ask_user.py` | 反问用户收集信息 | `ask_question_to_user` |
| `src/llm_tools/door.py` | 楼下门禁开门 | `open_door` |
| `src/reminder_thread.py` | 定时提醒后台线程（每分钟检查） | `start()` |
| `src/server.py` | FastAPI REST API + serve 前端 | REST API + SPA fallback |
| `src/tts/api.py` | FastAPI TTS 路由（/api/tts/speak） | 内嵌 cache |
| `src/tts/cache.py` | MD5 WAV 缓存，DB 存储 | `TTSCache` |
| `src/vits/` | VITS 模型代码（jaywalnut310/vits，MIT） | 推理用 |
| `frontend/` | React + Vite + antd 前端（9 tabs） | bun run dev / bun run build |

## 运行方式

```powershell
# 完整模式（唤醒词 + STT + LLM + TTS）
python src/main.py

# 仅 Web 管理界面（不加载模型）
python src/main.py --web-only
```

Web 界面 `localhost:8160` — 九个栏目 + 系统配置弹窗：
- **用户管理** — 创建、重命名、删除用户
- **声纹管理** — 浏览器录音 / 上传 WAV + 试听 + 拖拽移动 + 声纹检测
- **聊天历史** — 按用户查看/编辑/删除 LLM 对话，内置直接提问框
- **定时提醒** — 添加/查看/删除提醒
- **记忆管理** — 编辑长期+中期记忆
- **TTS 缓存** — 查看/搜索/试听/删除缓存
- **备份恢复** — 创建/上传/下载/恢复备份 ZIP
- **系统日志** — 实时查看/筛选/搜索/导出（磁盘持久化 20MB）
- **唤醒词收集** — 正例/负例分表、试听、移动、删除（用于模型重训练）
- 右上角齿轮 → 系统配置（TTS 后端 + 工具静默）

## 数据库

```
users (id, name, created_at)
voiceprints (id, user_id, vector BLOB, audio_path, type, created_at)
  → type: 'manual'（Web 上传，固定），'auto'（对话采集，上限 100）
  → audio_path 指向 recordings/{user_id}/ 下的 WAV 文件
chat_history (id, user_id, role, content, created_at)
  → LLM 对话按 user_id 独立存储
  → tool_calls 消息存为完整 JSON
reminders (id, user_id, content, rtype, datetime, lunar, done, created_at)
  → rtype: once/daily/monthly, lunar: 0=公历 1=农历
memory/
  memory.md            ← 长期记忆文件（不提交 git）
  {user_id}.md         ← 中期记忆文件（不提交 git）
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
| `list_ac` | 列出家中所有空调的状态和温度 |
| `control_ac` | 控制空调开关/温度/模式（默认制冷） |
| `get_tv_state` | 查询小米电视当前状态（音响模式/打开） |
| `control_tv` | 控制小米电视开关（关=进入音响模式） |
| `read_memory` | 读取长期记忆（用户身份、偏好、房间归属） |
| `save_memory` | 向长期记忆追加新信息 |
| `add_reminder` | 添加定时提醒（一次性/每天/每月/农历） |
| `list_reminders` | 列出所有未完成提醒 |
| `delete_reminder` | 删除指定提醒 |
| `get_volume` | 查询当前扬声器音量百分比 |
| `set_volume` | 设置扬声器音量（0-200%） |
| `ask_question_to_user` | 信息不足时反问用户（TTS提问+录音+STT） |
| `web_search` | 通过 Claude Code CLI 联网搜索最新信息 |
| `open_door` | 打开楼下门禁 |

每个工具标注 `memory_value`（0-10）：0=无记忆价值（开关/查询），5-8=中高价值（定位/搜索），10=极高（save_memory）。
每个工具通过 `@register(silent=True/False)` 声明是否播 TTS 提示语。Web 配置页可覆盖。

新增工具：在 `src/llm_tools/` 下创建模块 → 用 `@register(memory_value=N, silent=True/False)` 装饰 → 在 `__init__.py` 导入。

## 记忆系统

- **长期记忆**：`memory/memory.md`，通过 `save_memory`/`read_memory` 工具读写，200 字摘要贴到 system prompt
- **中期记忆**：`memory/{user_id}.md`，在聊天后自动提取。规则：如果本轮对话涉及 memory_value=0 的 tool（如开关空调），整轮丢弃；纯聊天或高价值 tool 记入
- **对话上下文**：只保留最近 5 分钟的 chat_history，超出部分交给中期记忆

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
| `TTS_BACKEND` | TTS 后端: "vits" 或 "http" | vits |
| `TTS_URL` | HTTP TTS 服务地址 | `http://192.168.1.180:6018/api/tts/speak` |
| `DEFAULT_CITY` | 天气未指定城市时的默认城市 | 福州 |
| `CLAUDE_BIN` | Claude Code CLI 路径 | %APPDATA%\npm\claude.cmd |
| `QB_LOCATION_URL` | QB 定位平台地址 | — |
| `QB_LOCATION_AUTHORITY` | QB 定位 authority header | — |
| `QB_LOCATION_USERNAME` | QB 定位登录名 | — |
| `QB_LOCATION_PASSWORD` | QB 定位密码 | — |
| `HOMEASSIANT_URL` | Home Assistant 地址 | — |
| `HOMEASSIANT_TOKEN` | Home Assistant 长期令牌 | — |
| `DEFAULT_CITY` | 天气默认城市 | 福州 |
| `CLAUDE_BIN` | Claude Code CLI 路径 | %APPDATA%\npm\claude.cmd |
| `DOOR_OPEN_URL` | 门禁开门接口地址 | — |
| `DOOR_OPEN_TOKEN` | 门禁开门 JWT token | — |
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
- `memory.md` 包含个人信息，不提交 git
- TTS 缓存目录 `models/tts_cache/` 不提交 git
- 录音目录 `recordings/` 不提交 git
- 声纹数据库 `models/voiceprints.db` 不提交 git
- VITS 模型权重 `models/paimon.pth` 不提交 git
- TTS 播放时暂停唤醒词检测，播完自动恢复
- tool call 多轮循环最多 5 轮
- 静默工具由 `@register(silent=True)` 声明，与 settings.json 合并生效
- 日志磁盘持久化 `logs/paimon.log`（5MB×4=20MB），Web 可查看/导出
- 唤醒词音频自动收集到 `wakeword/positive/` 和 `wakeword/negative/`
