# 桌面端打包指南（Phase 5）

> 本文档说明如何将 Python 后端打包为独立可执行文件，并集成到 Electron 桌面应用中，实现真正的离线运行。

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────┐
│ Electron App (comicstudio-setup.exe)                │
│                                                      │
│  ┌──────────────────┐  ┌─────────────────────────┐ │
│  │  React Frontend  │  │  Packaged Python Backend │ │
│  │  (renderer)      │  │  (comicstudio-backend)   │ │
│  │                  │←→│                          │ │
│  │  - React Flow    │  │  - FastAPI + uvicorn    │ │
│  │  - Ant Design    │  │  - SQLite (aiosqlite)   │ │
│  │  - Zustand       │  │  - All AI engines        │ │
│  └──────────────────┘  └─────────────────────────┘ │
│                                                      │
│  extraResources: ../backend/dist/comicstudio-backend │
└─────────────────────────────────────────────────────┘
```

**关键组件：**
- **PyInstaller 6.21+**：将 Python 后端打包为单目录可执行文件
- **SQLite/aiosqlite**：桌面模式下的数据库 fallback（无需 PostgreSQL）
- **BackendProcess**：Electron 主进程管理后端子进程
- **extraResources**：electron-builder 将后端打包到 Electron 应用中

---

## 二、前置要求

### 2.1 开发环境

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.14+ | 后端运行时（PyInstaller 6.21+ 要求 Python ≥3.9） |
| Node.js | 18+ | 前端 + Electron 构建 |
| PyInstaller | 6.21+ | Python 打包工具 |
| electron-builder | 24+ | Electron 打包工具 |
| FFmpeg | 任意 | 系统 PATH 中（视频合成功能需要） |

### 2.2 已完成阶段

- Phase 1: 全栈基础骨架
- Phase 2: AI 引擎层（9 个引擎，零成本策略）
- Phase 3: 工作流引擎（节点编排 + 5 个内置模板）
- Phase 4: Electron 桌面应用（70 测试）
- Phase 5: Python 后端打包（本阶段，新增 67 后端测试 + 5 桌面测试）

---

## 三、构建 Python 后端可执行文件

### 3.1 安装打包依赖

```bash
cd backend
# 安装到 .deps 目录（项目惯例）
python -m pip install --target .deps pyinstaller==6.21.0 aiosqlite==0.19.0
```

### 3.2 验证 spec 文件完整性

```bash
cd backend
python packaging/verify_spec.py
```

预期输出：
```
[PASS] Spec file exists
[PASS] Spec parses as Python
[PASS] entry.py referenced
[PASS] All hooks exist
[PASS] App modules listed
[PASS] Excludes are safe
```

### 3.3 执行打包

```bash
cd backend
# 清理旧产物并重新构建
python packaging/build.py --clean

# 或不清理直接构建
python packaging/build.py
```

构建产物位于 `backend/dist/comicstudio-backend/`：
- Windows: `comicstudio-backend.exe`（约 16 MB）
- Linux/macOS: `comicstudio-backend`

构建时间：首次约 5-15 分钟（取决于依赖数量和磁盘速度）。

### 3.4 验证可执行文件

```bash
# 启动后端（桌面模式）
./dist/comicstudio-backend/comicstudio-backend.exe --port 8765

# 另开终端测试
curl http://127.0.0.1:8765/health
# 预期: {"code":0,"message":"success","data":{"status":"ok","version":"0.1.0"}}
```

### 3.5 运行端到端测试

```bash
cd backend
# 设置 PYTHONPATH（运行测试需要）
$env:PYTHONPATH = "$PWD\.deps;$PWD"
python -m pytest tests/test_e2e_packaged.py -v
```

预期：10 个测试全部通过（health/root/openapi/sqlite_db/uploads/jwt_secret/version/logs/size/no_python_dependency）。

---

## 四、构建 Electron 桌面应用

### 4.1 确保后端已打包

确认 `backend/dist/comicstudio-backend/` 目录存在且包含可执行文件。

### 4.2 构建 Electron 应用

```bash
cd desktop
npm run build       # 构建 main/preload/renderer
npm run package:win # Windows 打包（或 package:mac / package:linux）
```

> **GPU/CPU 变体构建（生产/CI 使用，推荐）**：按目标分别产出安装包：
> ```bash
> node scripts/build-variant.js --target nsis-gpu       # Win GPU (捆绑 torch ~2.5GB)
> node scripts/build-variant.js --target nsis-cpu       # Win CPU (ONNX ~600MB)
> node scripts/build-variant.js --target appimage-gpu   # Linux GPU
> node scripts/build-variant.js --target appimage-cpu   # Linux CPU
> # 等价 npm 快捷：npm run build:win-gpu / build:win-cpu / build:linux-gpu / build:linux-cpu
> ```

产物位于 `desktop/release/`：
- Windows GPU: `release/YNEX-Story-Studio-Setup-<version>-GPU.exe` (NSIS)
- Windows CPU: `release/YNEX-Story-Studio-Setup-<version>-CPU.exe` (NSIS)

`electron-builder.yml` 中的 `extraResources` 配置会自动将后端打包到 Electron 应用的 `resources/comicstudio-backend/` 目录。

### 4.3 安装并测试

运行安装包，启动应用。应用会：
1. Electron 主进程的 `BackendProcess` 检测 packaged exe 是否存在
2. 若存在，spawn packaged exe 并设置 `CS_DESKTOP_MODE=1`、`CS_DATA_DIR=<userData>`
3. 后端首次启动时 `bootstrap_desktop()` 创建数据目录、SQLite 数据库、JWT 密钥
4. 前端连接到 `http://127.0.0.1:8000`
5. 用户即可离线使用所有功能（无需安装 Python、无需 PostgreSQL）

---

## 五、运行时数据目录

桌面模式下，所有用户数据存储在 Electron 的 `userData` 目录（通过 `app.getPath('userData')` 获取）：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%/comic-studio-desktop/` |
| macOS | `~/Library/Application Support/comic-studio-desktop/` |
| Linux | `~/.config/comic-studio-desktop/` |

目录结构：
```
comic-studio-desktop/
├── comicstudio.db         # SQLite 数据库（自动创建所有表）
├── .jwt_secret            # JWT 密钥（首次自动生成，64 字符）
├── version.txt            # 版本信息（诊断用）
├── logs/
│   └── app.log            # 应用日志
└── uploads/
    ├── images/
    │   └── 20260719/      # 按日期组织
    └── audio/
        └── 20260719/
```

---

## 六、配置覆盖

### 6.1 使用外部 PostgreSQL

默认桌面模式使用 SQLite。如需连接外部 PostgreSQL（多设备同步、更大容量等），设置环境变量：

```bash
# Windows (PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/db"
$env:CS_DESKTOP_MODE = "1"
comicstudio-backend.exe

# Linux/macOS
DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" CS_DESKTOP_MODE=1 ./comicstudio-backend
```

### 6.2 自定义数据目录

```bash
# 默认: ~/comicstudio-data 或 Electron userData
# 自定义:
CS_DATA_DIR=/path/to/data comicstudio-backend.exe
```

### 6.3 端口配置

```bash
comicstudio-backend.exe --port 9000 --host 0.0.0.0
```

---

## 七、调试

### 7.1 查看后端日志

后端日志输出到两个位置：
1. **stderr**（Electron 主进程控制台，可通过 DevTools 主进程查看）
2. **`<data_dir>/logs/app.log`**（持久化日志）

### 7.2 常见问题

#### Q1: 后端启动失败

检查 Electron 主进程日志（`console.log`）。常见原因：
- 可执行文件路径错误 → 检查 `getPackagedBackendPath()` 三段式解析
- 端口被占用 → 修改 `LOCAL_BACKEND_CONFIG.port` 或通过 `--port` 参数覆盖
- 数据目录权限不足 → 检查 `CS_DATA_DIR` 路径可写性

#### Q2: PyInstaller 打包时缺少模块

错误：`ModuleNotFoundError: No module named 'xxx'`

解决：在 `packaging/comicstudio_backend.spec` 的 `hiddenimports` 列表中添加该模块，然后重新打包：
```bash
python packaging/build.py --clean
```

#### Q3: 原生模块加载失败

错误：`ImportError: DLL load failed while importing _xxx`

解决：检查 `packaging/hooks/` 目录中对应的 hook 文件是否正确使用 `collect_dynamic_libs`。当前已包含 6 个 hook：
- `hook-asyncpg.py`（asyncpg Cython 扩展）
- `hook-bcrypt.py`（bcrypt _bcrypt.pyd）
- `hook-loguru.py`（loguru 动态 sinks）
- `hook-pydantic_core.py`（pydantic-core Rust 扩展）
- `hook-alembic.py`（alembic Mako 模板）
- `hook-ffmpeg_python.py`（ffmpeg-python _run.py 模板）

#### Q4: SQLite 性能问题

SQLite 适用于单用户桌面场景。如性能不足：
1. 连接外部 PostgreSQL（见 6.1）
2. 或在 `app/core/database.py` 调整 SQLite pragma（如 `journal_mode=WAL`）

#### Q5: 打包体积过大

当前打包包含所有 AI 引擎依赖（约 16 MB）。如需减小体积：
1. 在 spec 的 `excludes` 中排除不用的模块（如 `torch`、`transformers` 已排除）
2. 使用 UPX 压缩（`upx=True`，需安装 UPX）
3. 拆分为多个可选包（高级，按需加载）

---

## 八、CI/CD 集成（参考）

```yaml
# .github/workflows/build-desktop.yml
name: Build Desktop App
on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install backend deps
        run: |
          cd backend
          pip install --target .deps -r requirements.txt

      - name: Build backend executable
        run: |
          cd backend
          python packaging/build.py --clean

      - name: Install frontend deps
        run: cd frontend && npm ci

      - name: Build frontend
        run: cd frontend && npm run build

      - name: Install desktop deps
        run: cd desktop && npm ci

      - name: Build desktop installer (GPU/CPU variant)
        run: cd desktop && node scripts/build-variant.js --target nsis-gpu
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/upload-artifact@v4
        with:
          name: comicstudio-setup
          path: desktop/release/*.exe
```

---

## 九、测试覆盖

Phase 5 新增测试汇总：

| 测试文件 | 测试数 | 覆盖内容 |
|---------|--------|---------|
| `test_desktop_config.py` | 12 | 桌面模式检测、数据目录、SQLite URL、JWT 密钥、runtime 模式 |
| `test_database_fallback.py` | 8 | SQLite 引擎创建、URL 选择、init_db、session、pool 配置 |
| `test_paths.py` | 8 | uploads 目录、子目录、日期路径、resource dir、log file |
| `test_bootstrap.py` | 10 | 目录创建、DB 初始化、幂等性、JWT 密钥、版本文件、数据持久化 |
| `test_verify_spec.py` | 6 | spec 文件存在、解析、entry 引用、hooks 存在、模块列表、excludes 安全 |
| `test_runtime.py` | 8 | frozen 检测、bundle dir、executable dir、data dir、setup_desktop_env |
| `test_build_script.py` | 5 | build.py 存在、解析、PyInstaller 引用、spec 引用、--help |
| `test_e2e_packaged.py` | 10 | health/root/openapi/sqlite/uploads/jwt/version/logs/size/no_python_dep |
| desktop `integration.test.ts` | +5 | PACKAGED_BACKEND_CONFIG、getPackagedBackendPath、env override、import、extraResources |
| **总计** | **72 新测试** | backend 249 + desktop 75 = **324 总测试** |

---

*本文档最后更新：2026-07-19*
