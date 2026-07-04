# Y·NEX AI 管家

> 让你的电脑成为真正的私人智能助手。零成本，模块化，可无限扩展。

## 功能一览

| 分类 | 功能 |
|------|------|
| **自然对话** | 语音唤醒 / 语音识别 / 语音合成 / 本地 LLM 兜底 |
| **智能家居** | Home Assistant / ESP32 传感器 / 自动化规则 / 场景控制 |
| **PC 自动化** | 窗口管理 / 键鼠模拟 / 剪贴板监听 / 截图 |
| **远程控制** | HTTP API / Telegram Bot / 手机 Termux / iOS 快捷指令 |
| **环境感知** | 摄像头人脸/姿态检测 / 运动检测 / 传感器联动 |
| **自托管服务** | Paperless 文档搜索 / Immich 相册 / n8n 工作流 |
| **记忆系统** | SQLite 对话历史 / ChromaDB 向量知识库 / 用户画像 |
| **语音增强** | 噪声抑制 / AGC / VAD / 远场麦克风支持 |
| **唤醒词** | openWakeWord 离线唤醒 / 中文唤醒词训练支持 |

---

## 快速开始

### 1. 安装（一键）

```bash
git clone <项目地址>
cd Y·NEX版Y·NEX项目
python setup.py
```

按提示配置：
- DeepSeek API Key（必需）
- Home Assistant（可选，有智能家居才填）
- Telegram Bot Token（可选，全球通用遥控）

### 2. 启动

```bash
# 文本对话（麦克风不可用时）
python main.py --text

# 测试模式（无需 API Key）
python main.py --text --mock-llm

# 轻量模式（笔记本省电）
python main.py --text --light

# 后台托盘模式（Ctrl+Shift+J 唤醒）
python main.py --text --tray
```

### 3. 系统自检

```bash
python setup.py --check
```

---

## 用户分级与权限

| 角色 | 说明 |
|------|------|
| **owner** | 管理员，全部功能 + 用户管理 |
| **family** | 家人，全部工具使用 |
| **guest** | 访客，仅对话和查看 |

API Key 管理：登录后访问 `/keys` 接口，或 Bot 发 `/addkey 名称 owner|family|guest`。

---

## 远程访问（全球通用）

### 方案一：Cloudflare Tunnel（推荐）

```bash
# 树莓派/小主机上
cloudflared tunnel create Y·NEX
cloudflared tunnel route dns Y·NEX your-subdomain.trycloudflare.com
cloudflared tunnel run --token <your-token>
```

优势：免费、不暴露端口、自动 HTTPS。

### 方案二：Tailscale

两边都装 Tailscale，组成虚拟局域网，直接访问 `http://100.x.x.x:7788`。

### 方案三：手机遥控

- **Android**：Termux 装 `termux_client.py`，后台守护 + 通知回传
- **iOS**：快捷指令 → HTTP POST `/chat` 接口

---

## 硬件升级路线

| 阶段 | 设备 | 成本 | 效果 |
|------|------|------|------|
| 当前 | 笔记本电脑 | 0 | 完整功能 |
| 升级1 | ReSpeaker 2-Mics | ~100元 | 远场语音唤醒，3-5米可唤醒 |
| 升级2 | ReSpeaker 4-Mic | ~200元 | 波束成形，指向性拾取 |
| 升级3 | ESP32 传感器套装 | ~300元 | 人体存在/门窗/温湿度，全屋感知 |
| 升级4 | 树莓派5 + SSD | ~800元 | 真正 24/7 低功耗运行 |
| 升级5 | 珊瑚 USB 加速棒 | ~500元 | 本地 LLM 推理 10 倍加速 |

---

## 目录结构

```
Y·NEX版Y·NEX项目/
├── main.py              # 主入口
├── setup.py             # 一键安装配置脚本
├── brain.py             # AI 大脑（LLM 调用 + 工具编排）
├── speech.py            # 语音（ASR + TTS）
├── skills.py            # 43 个技能函数
├── config.py            # 配置管理
├── memory.py            # SQLite 短期记忆
├── knowledge_base.py    # ChromaDB 长期知识库
├── auth.py              # 认证与权限体系
├── api_server.py        # HTTP API 服务器
├── telegram_bot.py      # Telegram 通用遥控
├── mqtt_bus.py          # MQTT 消息总线
├── device_hub.py        # 统一设备抽象层
├── pc_control.py        # PC 控制（窗口/键鼠/截图）
├── home_assistant.py     # 智能家居控制
├── esp_sensors.py       # ESP32 传感器接入
├── automation_engine.py  # 自动化规则引擎
├── clipboard_listener.py # 剪贴板智能处理
├── remote_voice.py      # 远程语音 UDP 通道
├── vision.py            # 摄像头视觉感知
├── far_field_mic.py     # 远场麦克风 + 语音增强
├── wake_word_zh.py      # 中文唤醒词
├── selfhost.py          # 自托管服务（Paperless/Immich/n8n）
├── deploy.py            # systemd 部署脚本
├── system_tray.py       # 系统托盘 + 全局热键
├── termux_client.py     # Android Termux 客户端
├── esp32_firmware/      # ESP32 传感器固件示例
└── requirements.txt     # Python 依赖
```

---

## 依赖说明

| 依赖 | 必需 | 说明 |
|------|------|------|
| `deepseek-api` / `ollama` | ✅ | LLM 大脑 |
| `requests` | ✅ | HTTP 调用 |
| `loguru` | ✅ | 日志 |
| `python-dotenv` | ✅ | 配置管理 |
| `SpeechRecognition` | ⚠️ | 语音识别 |
| `edge-tts` | ⚠️ | 语音合成 |
| `pygame` | ⚠️ | 音频播放 |
| `opencv-python` | ○ | 摄像头视觉 |
| `mediapipe` | ○ | 人脸/姿态识别 |
| `psutil` | ○ | 系统监控 |
| `chromadb` | ○ | 向量知识库 |
| `playwright` | ○ | 浏览器自动化 |
| `pyautogui` | ○ | PC 自动化 |

✅ 必需 | ⚠️ 推荐 | ○ 可选

---

## 常见问题

**Q: 语音识别不准**
A: 优先使用 `faster-whisper` 本地模型，或在 `.env` 设置 `WHISPER_MODEL=medium` 下载更大模型。

**Q: Telegram Bot 无法连接**
A: 确认 Token 正确，且 Bot 已通过 `@BotFather` 激活。

**Q: 摄像头不工作**
A: 检查是否被其他程序占用，关闭微信/QQ 等视频软件后重试。

**Q: 内存占用高**
A: 使用 `--light` 模式，或在 `main.py` 中关闭视觉守护和剪贴板监听。

**Q: DeepSeek API 费用**
A: DeepSeek 价格极低（约 $0.1/1M tokens），日常对话每月不到 1 元。

---

## 贡献

模块化设计，新增技能只需：
1. 在 `skills.py` 写函数
2. 在 `brain.py` TOOLS 列表加定义
3. 自动注册，无需其他配置
