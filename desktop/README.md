# ComicStudio AI Desktop

Electron 桌面应用 — 包装现有 React 前端 + Python 后端，提供原生桌面体验。

## 环境要求

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Node.js | 18+ | 构建桌面端 |
| npm | 9+ | 包管理 |
| Python | 3.10+ | 后端（仅 local-python 模式需要） |
| Git | 2.40+ | 拉取代码 |

## 快速开始

### 1. 安装依赖

```bash
cd desktop
npm install
```

如果在中国大陆网络环境下，`.npmrc` 已配置 npmmirror 镜像，可直接安装。

### 2. 生成应用图标（首次必做）

```bash
npm run icons
```

生成以下资源：
- `resources/icons/icon.png` (1024×1024)
- `resources/icons/icon.ico` (Windows)
- `resources/icons/icon.icns` (macOS)
- `resources/icons/tray.png` (托盘图标)
- `resources/icons/trayTemplate.png` (macOS 模板托盘)
- `build/installer-sidebar.bmp` (NSIS 侧栏)

### 3. 开发模式

启动桌面端开发模式（热重载）：

```bash
npm run dev
```

> **注意**：开发模式会从 `http://localhost:5173` 加载前端。请先在 `frontend/` 目录运行 `npm run dev`。

### 4. 类型检查 + 测试

```bash
npm run typecheck   # TypeScript 类型检查
npm test            # 运行单元测试
npm run test:watch  # 监听模式
```

## 配置

### 后端连接模式

通过环境变量 `CS_BACKEND_MODE` 控制：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `remote` (默认) | 连接远程后端（云端部署） | 生产环境、商业化部署 |
| `local-python` | 启动本地 Python 后端子进程 | 开发、离线场景 |
| `disabled` | 不启动任何后端 | 仅前端预览 |

设置示例：
```bash
# Windows PowerShell
$env:CS_BACKEND_MODE = "local-python"
$env:CS_BACKEND_DIR = "../../backend"
$env:CS_PYTHON = "python"
npm run dev

# Linux/macOS
CS_BACKEND_MODE=local-python CS_BACKEND_DIR=../../backend CS_PYTHON=python3 npm run dev
```

### 后端 URL

通过 `VITE_API_BASE_URL` 配置远程后端地址：
```bash
$env:VITE_API_BASE_URL = "https://api.comicstudio.ai"
```

## 打包

### Windows (NSIS 安装包)

```bash
npm run package:win
```

输出到 `release/ComicStudio AI Setup 0.1.0.exe`

### macOS (DMG)

```bash
npm run package:mac
```

输出到 `release/ComicStudio AI-0.1.0.dmg`

> **注意**：macOS 打包需要在 macOS 系统上执行。代码签名需要 Apple Developer 证书。

### Linux (AppImage / deb)

```bash
npm run package:linux
```

输出到 `release/ComicStudio AI-0.1.0.AppImage`

### 仅打包不创建安装程序（调试用）

```bash
npm run package:dir
```

## 自动更新

应用通过 GitHub Releases 自动更新：

1. 在 GitHub 仓库 `comicstudio-ai/comic-studio-releases` 创建 Release
2. 上传打包后的 `latest.yml`（electron-builder 自动生成）和应用安装包
3. 应用启动时会自动检查更新
4. 用户也可通过「帮助 → 检查更新」手动触发

代码签名（Windows）：
```bash
$env:CSC_LINK = "path/to/cert.p12"
$env:CSC_KEY_PASSWORD = "your-password"
npm run package:win
```

## 深度链接

应用注册了 `comicstudio://` 协议，支持从浏览器/邮件直接打开应用并跳转：

| URL | 跳转目标 |
|-----|---------|
| `comicstudio://` | `/dashboard` |
| `comicstudio://projects` | `/projects` |
| `comicstudio://projects/abc` | `/projects/abc` |
| `comicstudio://workflow/run/xyz` | `/projects/xyz` |
| `comicstudio://settings` | `/settings` |

## 项目结构

```
desktop/
├── src/
│   ├── main/          # 主进程（Node.js 环境）
│   ├── preload/       # 预加载脚本（contextBridge）
│   ├── shared/        # 共享类型与常量
│   └── test/          # 单元测试
├── resources/         # 静态资源（图标等）
├── build/             # 打包资源（NSIS 配置等）
├── scripts/           # 工具脚本
├── out/               # 构建产物（gitignore）
└── release/           # 打包产物（gitignore）
```

## 开发者文档

- [Phase 4 实施计划](../docs/superpowers/plans/2026-07-19-phase4-desktop-electron.md)
- [整体架构](../docs/architecture/01-overall-architecture.md)
- [本地部署](../docs/deployment/local-deployment.md)
- [云端部署](../docs/deployment/cloud-deployment.md)
```
