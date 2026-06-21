# 派萌助手

实时语音对话助手 — 唤醒词检测 → 声纹验证 → 语音识别 → DeepSeek + Tool Calling → VITS 语音合成。

## 工作流程

```
"派萌" 唤醒
  → "我在呢"(VITS TTS, 同步播放)
  → 录音(VAD, 静音自动停止)
  → 声纹验证(eres2netv2, 多声纹平均匹配)
  → STT(SenseVoiceSmall)
  → DeepSeek 对话(按用户隔离历史, 支持 Tool Calling)
  → VITS TTS 播报(同步播放, 播完恢复唤醒检测)
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
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 4. 编译前端（可选，跳过则使用 fallback 页面）
cd frontend && bun install && bun run build && cd ..

# 5. 放置唤醒词模型
#    将 paimeng.onnx 放到 models/ 目录

# 6. 运行
python src/main.py                 # 完整模式
python src/main.py --web-only      # 仅 Web 管理界面
```

首次运行会自动下载 SenseVoiceSmall（STT）和 eres2netv2（声纹）模型。

Web 管理界面：`http://localhost:8160`

## Docker 部署

```bash
# 1. 构建镜像
cd docker
docker build -t paimon-assist -f Dockerfile ..

# 2. 启动容器
bash run_docker.sh
```

`run_docker.sh` 会自动创建 venv、安装依赖、启动 PulseAudio 音频服务、运行主程序。
项目根目录整体挂载到容器 `/workdir`，修改源码、`run.sh`、`.env` 后重启容器即可，无需重新构建。

Claude Code CLI 配置：将 `settings.json` 放到 `.claude/` 目录，容器启动时自动拷贝到 `~/.claude/`。

## 模块说明

| 模块 | 职责 |
|------|------|
| `src/main.py` | 入口，ONNX 补丁，主循环，`--web-only` |
| `src/config.py` | 加载 `.env`，导出全部配置 |
| `src/wakeword.py` | 唤醒词检测（paimeng.onnx） |
| `src/tts/` | TTS 模块（VITS/HTTP 工厂 + 缓存 + API + 音频管理） |
| `src/settings.py` | 统一配置读写（settings/settings.json） |
| `src/vad.py` | VAD 录音（委托给 AudioManager） |
| `src/voiceprint.py` | 声纹提取与匹配（eres2netv2） |
| `src/db.py` | SQLite：用户表 + 声纹表 + 聊天历史 |
| `src/stt.py` | 语音转文字（SenseVoiceSmall） |
| `src/llm.py` | DeepSeek 对话 + Tool Calling，按用户隔离历史 |
| `src/llm_tools/memory.py` | 长期+中期记忆：读写、摘要、自动提取 |
| `src/llm_tools/` | 工具注册中心 + 天气/定位/搜索/空调/电视/记忆/提醒/音量/门禁 |
| `src/log_manager.py` | 日志管理（磁盘持久化 20MB + 内存缓冲） |
| `src/reminder_thread.py` | 定时提醒后台线程（每分钟检查） |
| `src/server.py` | FastAPI REST API + serve 前端 |
| `src/tts_api.py` | TTS Web API + 缓存 |
| `src/tts_cache.py` | MD5 WAV 缓存 |
| `src/vits/` | VITS 模型代码（jaywalnut310/vits，MIT） |
| `frontend/` | React + Vite + antd 前端（9 个 tab） |

## LLM Tool Calling

DeepSeek 自动调用工具获取实时信息：

| 工具 | 功能 |
|------|------|
| `get_weather` | 查询指定城市今天/明天天气（wttr.in） |
| `get_yuqiao_location` | 查询乔宝通话器当前位置和地址 |
| `get_yuqiao_power` | 查询乔宝通话器剩余电量 |
| `list_ac` / `control_ac` | 查看/控制家中空调（开关/温度/模式） |
| `get_tv_state` / `control_tv` | 查看/控制小米电视（关=进入音响模式） |
| `read_memory` / `save_memory` | 长期记忆读写（用户身份、房间归属等） |
| `add_reminder` / `list_reminders` / `delete_reminder` | 定时提醒（一次性/每天/每月/农历） |
| `get_volume` / `set_volume` | 查询/设置音量百分比 |
| `ask_question_to_user` | 信息不足时反问用户（TTS提问+录音+STT） |
| `web_search` | 通过 Claude Code CLI 联网搜索最新信息 |
| `open_door` | 打开楼下门禁 |

工具静默：每个工具通过 `@register(silent=True/False)` 声明是否播 TTS 提示语，Web 配置页可覆盖。
Final 工具（`control_ac`/`control_tv`/`set_volume`/`open_door`/`add_reminder`/`delete_reminder`）：返回值直接作为最终 TTS 播出，跳过 LLM 二次加工，省 token 更快响应。

## 配置（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `THRESHOLD` | 唤醒词灵敏度 | 0.25 |
| `VOICEPRINT_THRESHOLD` | 声纹相似度阈值 | 0.5 |
| `VAD_SILENCE_MS` | 静音判定（ms） | 800 |
| `MAX_RECORD_SECONDS` | 最大录音时长 | 10 |
| `TTS_CACHE_DIR` | TTS 缓存目录 | models/tts_cache |
| `DEFAULT_CITY` | 天气默认城市 | 福州 |
| `CLAUDE_BIN` | Claude Code CLI 路径 | %APPDATA%\npm\claude.cmd |
| `QB_LOCATION_URL` | QB 定位平台地址 | — |
| `QB_LOCATION_USERNAME` | QB 定位登录名 | — |
| `QB_LOCATION_PASSWORD` | QB 定位密码 | — |
| `HOMEASSIANT_URL` | Home Assistant 地址 | — |
| `HOMEASSIANT_TOKEN` | Home Assistant 令牌 | — |
| `DOOR_OPEN_URL` | 门禁开门接口地址 | — |
| `DOOR_OPEN_TOKEN` | 门禁开门 JWT token | — |

## Web 管理界面

`http://localhost:8160` — 九个栏目 + 系统配置弹窗，支持移动端自适应：

- **用户管理** — 创建、重命名、删除用户
- **声纹管理** — 浏览器录音 / 上传 WAV + 试听 + 拖拽移动 + 声纹检测
- **聊天历史** — 按用户查看/编辑/删除 LLM 对话 + 直接提问测试
- **定时提醒** — 添加/删除提醒（一次性/每天/每月/农历）
- **记忆管理** — 编辑长期记忆和各个用户的中期记忆
- **TTS 缓存** — 查看/搜索/试听/删除缓存记录
- **备份恢复** — 创建/上传/下载/恢复备份 ZIP
- **系统日志** — 实时查看/筛选/搜索/导出日志（磁盘持久化 20MB）
- **唤醒词收集** — 正例/负例分表、试听、移动、删除（用于模型重训练）
- 右上角齿轮 → **系统配置**（TTS 后端 + 工具静默 + 唤醒词开关/定时）

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
│   ├── wakeword.py         # 唤醒词 + 音频收集
│   ├── log_manager.py      # 日志管理（磁盘 20MB）
│   ├── vits_tts.py         # VITS 合成
│   ├── vad.py              # VAD 录音
│   ├── voiceprint.py       # 声纹
│   ├── db.py               # 数据库
│   ├── stt.py              # 语音转文字
│   ├── llm.py              # LLM 对话 + Tool Calling
│   ├── tts_api.py          # TTS API
│   ├── tts_cache.py        # TTS 缓存
│   ├── llm_tools/          # 工具：天气/定位/搜索/空调/电视/记忆/提醒/音量/门禁
│   ├── reminder_thread.py  # 定时提醒后台线程（每分钟检查）
│   └── vits/               # VITS 模型代码
├── frontend/               # React + Vite + antd 前端
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       ├── components/     # 9 个 Tab 组件
│       └── dialogs/        # CreateUser, AddVoiceprint, Detect
├── models/                 # 模型文件
│   ├── paimeng.onnx        # 唤醒词模型
│   ├── paimon.pth          # VITS 权重（417MB）
│   ├── paimon_config.json  # VITS 配置
│   └── tts_cache/          # TTS 缓存（自动生成）
├── recordings/             # 用户录音（按 user_id 分目录）
├── logs/                   # 运行日志（磁盘持久化，最多 20MB）
├── wakeword/               # 唤醒词训练数据（positive/negative）
├── memory/                 # 长期记忆 + 中期记忆文件
├── docker/                 # Docker 部署
├── requirements.txt
└── .env.example
```
