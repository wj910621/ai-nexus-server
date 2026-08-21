# 全栈基础骨架实施计划 (Full-Stack Foundation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建可运行的全栈骨架：FastAPI 后端（用户认证 + 项目/角色/剧本/分镜/音频/渲染/工作流 CRUD）+ React 前端（登录 + 仪表盘 + 项目编辑器 + React Flow 工作流）+ Docker 开发环境，为后续 AI 引擎层和商业化模块奠定基础。

**Architecture:**
- **后端**：FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 15 + Redis 7 + Alembic + JWT 认证
- **前端**：React 18 + TypeScript 5 + Vite 5 + React Flow 12 + TanStack Query 5 + Zustand 4 + Ant Design 5 + Tailwind CSS 3
- **基础设施**：Docker Compose 编排 PostgreSQL / Redis / MinIO；后端/前端本地运行开发模式
- **目录约定**：`backend/` (Python) + `frontend/` (React) + `docker/` (编排) + `ai-models/` (模型权重占位)

**Tech Stack:** Python 3.11, FastAPI 0.104+, SQLAlchemy 2.0+, asyncpg, Alembic, pydantic-settings, python-jose, passlib, Redis 7, MinIO; Node.js 18+, React 18, TypeScript 5, Vite 5, React Flow 12, TanStack Query 5, Zustand 4, Ant Design 5, Tailwind CSS 3, Axios, React Router 6

---

## 文件结构总览

### 后端文件结构 (`backend/`)
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # Pydantic Settings 配置
│   │   ├── database.py            # 异步数据库引擎+会话
│   │   ├── security.py            # JWT + 密码哈希
│   │   ├── response.py            # 统一响应类
│   │   └── deps.py                # 依赖注入 (get_db, get_current_user)
│   ├── models/
│   │   ├── __init__.py            # 导出所有模型
│   │   ├── base.py                # Base + Mixins
│   │   ├── user.py                # User
│   │   ├── project.py             # Project
│   │   ├── character.py           # Character
│   │   ├── script.py              # Script + Scene + Dialogue
│   │   ├── storyboard.py          # StoryboardFrame
│   │   ├── audio.py               # VoiceProfile + AudioTrack
│   │   ├── render.py              # RenderTask
│   │   ├── workflow.py            # Workflow + WorkflowExecution
│   │   └── billing.py             # Subscription + CreditTransaction
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py              # ApiResponse, PaginatedResponse
│   │   ├── user.py                # UserCreate, UserLogin, UserResponse
│   │   ├── project.py
│   │   ├── character.py
│   │   ├── script.py
│   │   ├── storyboard.py
│   │   ├── audio.py
│   │   ├── render.py
│   │   └── workflow.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base_service.py        # BaseService 抽象类
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── character_service.py
│   │   ├── script_service.py
│   │   ├── storyboard_service.py
│   │   ├── audio_service.py
│   │   ├── render_service.py
│   │   └── workflow_service.py
│   └── api/
│       ├── __init__.py
│       ├── router.py              # 路由聚合
│       ├── auth.py                # 注册/登录/刷新token
│       ├── users.py
│       ├── projects.py
│       ├── characters.py
│       ├── scripts.py
│       ├── storyboards.py
│       ├── audio.py
│       ├── render.py
│       └── workflows.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   └── test_auth.py
├── alembic.ini
├── requirements.txt
├── .env.example
└── pyproject.toml
```

### 前端文件结构 (`frontend/`)
```
frontend/
├── public/
├── src/
│   ├── main.tsx                   # React 入口
│   ├── App.tsx                    # 根组件 + Provider
│   ├── api/
│   │   ├── client.ts              # Axios 实例
│   │   ├── auth.ts                # 认证 API
│   │   ├── projects.ts            # 项目 API
│   │   ├── characters.ts          # 角色 API
│   │   └── workflows.ts           # 工作流 API
│   ├── types/
│   │   ├── index.ts               # 统一导出
│   │   ├── user.ts
│   │   ├── project.ts
│   │   ├── character.ts
│   │   ├── script.ts
│   │   ├── storyboard.ts
│   │   └── workflow.ts
│   ├── stores/
│   │   ├── authStore.ts           # Zustand 认证状态
│   │   ├── editorStore.ts         # 编辑器状态
│   │   └── projectStore.ts        # 项目状态
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useProjects.ts
│   │   └── useCharacters.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── MainLayout.tsx     # TRAE 风格主布局
│   │   │   ├── Sidebar.tsx        # 左侧导航
│   │   │   └── TopBar.tsx         # 顶部栏
│   │   ├── workflow/
│   │   │   ├── WorkflowEditor.tsx # React Flow 编辑器
│   │   │   └── nodes/
│   │   │       ├── ImageGenNode.tsx
│   │   │       └── CharacterNode.tsx
│   │   └── common/
│   │       └── ProtectedRoute.tsx
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── ProjectListPage.tsx
│   │   └── ProjectEditorPage.tsx
│   ├── routes/
│   │   └── index.tsx              # 路由配置
│   ├── utils/
│   │   └── token.ts               # Token 管理
│   ├── styles/
│   │   └── global.css             # Tailwind + 全局样式
│   └── vite-env.d.ts
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

### DevOps 文件结构 (`docker/`)
```
docker/
├── docker-compose.yml             # 基础设施编排
├── Dockerfile.backend             # 后端镜像
├── Dockerfile.frontend            # 前端镜像
└── init-db.sql                    # 数据库初始化 (扩展)
```

### 根目录文件
```
comic-studio-ai/                   # = c:\漫剧软件项目\
├── backend/
├── frontend/
├── docker/
├── ai-models/                     # 模型权重占位目录
├── docs/                          # 已存在的设计文档
├── scripts/
│   ├── dev.ps1                    # Windows 开发启动脚本
│   └── dev.sh                     # Linux/macOS 开发启动脚本
├── .gitignore
├── .env.example
└── README.md                      # 已存在
```

---

## Task 1: 项目根目录初始化

**Files:**
- Create: `c:\漫剧软件项目\.gitignore`
- Create: `c:\漫剧软件项目\.env.example`
- Create: `c:\漫剧软件项目\ai-models\.gitkeep`
- Create: `c:\漫剧软件项目\scripts\dev.ps1`
- Create: `c:\漫剧软件项目\scripts\dev.sh`

- [ ] **Step 1: 创建 `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
env/
ENV/
env.bak/
venv.bak/
.venv/

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.project
.classpath
.settings/

# OS
.DS_Store
Thumbs.db
desktop.ini

# Node.js
node_modules/
dist/
dist-ssr/
*.local
.npm
.yarn-integrity
.pnpm-store/

# Frontend build
frontend/dist/
frontend/build/

# Testing
coverage/
.coverage
htmlcov/
.pytest_cache/
.tox/

# Database
*.sqlite
*.sqlite3
*.db

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# AI models (大文件)
ai-models/*.safetensors
ai-models/*.bin
ai-models/*.ckpt
ai-models/*.pt
ai-models/*.pth
ai-models/*.onnx

# Generated content
generated/
exports/
uploads/

# Docker
docker/data/

# Alembic
backend/alembic/versions/__pycache__/

# Electron
desktop/dist/
desktop/out/
desktop/release/

# Temp files
*.tmp
*.temp
.cache/
```

- [ ] **Step 2: 创建 `.env.example`**

```env
# ===========================================
# 漫剧生成软件 - 环境变量配置模板
# 复制此文件为 .env 并填入实际值
# ===========================================

# 应用配置
APP_NAME=ComicStudio AI
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
APP_SECRET_KEY=change-me-to-a-random-secret-key-in-production

# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=comic_user
DB_PASSWORD=comic_password
DB_NAME=comic_studio
DATABASE_URL=postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0

# MinIO / S3 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_ASSETS=assets
MINIO_BUCKET_GENERATED=generated

# JWT 配置
JWT_SECRET_KEY=change-me-to-a-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS 配置 (逗号分隔)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Celery 配置
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AI 模型配置
MODEL_CACHE_DIR=./ai-models
SDXL_MODEL_PATH=./ai-models/sdxl-base
SD_MODEL_PATH=./ai-models/sd15
DEVICE=cpu

# DeepSeek API (LLM 剧本生成)
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com

# 前端配置
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

- [ ] **Step 3: 创建 `ai-models/.gitkeep` 占位文件**

```
# 此目录用于存放 AI 模型权重文件
# 实际模型文件不纳入版本控制（见 .gitignore）
# 子目录示例：
# - sdxl-base/        Stable Diffusion XL 基础模型
# - sd15/             Stable Diffusion 1.5
# - lora/             LoRA 微调模型
# - controlnet/       ControlNet 模型
# - ip-adapter/       IP-Adapter 模型
# - tts/              TTS 模型
```

- [ ] **Step 4: 创建 Windows 开发启动脚本 `scripts\dev.ps1`**

```powershell
# 漫剧生成软件 - Windows 开发环境启动脚本
# 用法: .\scripts\dev.ps1

param(
    [switch]$SkipDocker,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ROOT = Resolve-Path "$PSScriptRoot\.."

Write-Host "🚀 启动 ComicStudio AI 开发环境..." -ForegroundColor Cyan

# 检查 .env 文件
if (-not (Test-Path "$ROOT\.env")) {
    if (Test-Path "$ROOT\.env.example") {
        Write-Host "📋 复制 .env.example 到 .env" -ForegroundColor Yellow
        Copy-Item "$ROOT\.env.example" "$ROOT\.env"
        Write-Host "⚠️  请编辑 .env 文件填入实际配置后重新运行" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "❌ 未找到 .env 或 .env.example 文件" -ForegroundColor Red
        exit 1
    }
}

# 启动基础设施服务
if (-not $SkipDocker) {
    Write-Host "🐳 启动 Docker 基础设施 (postgres, redis, minio)..." -ForegroundColor Green
    Push-Location "$ROOT\docker"
    docker-compose up -d postgres redis minio
    Pop-Location
    Write-Host "✅ 基础设施已启动" -ForegroundColor Green
}

# 启动后端
if (-not $FrontendOnly) {
    Write-Host "🐍 启动后端服务 (http://localhost:8000)..." -ForegroundColor Green
    $backendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\backend"
        if (-not (Test-Path ".venv")) {
            python -m venv .venv
        }
        & ".\.venv\Scripts\Activate.ps1"
        pip install -r requirements.txt --quiet
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    } -ArgumentList $ROOT
}

# 启动前端
if (-not $BackendOnly) {
    Write-Host "⚛️  启动前端服务 (http://localhost:5173)..." -ForegroundColor Green
    $frontendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm install --silent
        npm run dev
    } -ArgumentList $ROOT
}

Write-Host ""
Write-Host "✨ 开发环境已启动:" -ForegroundColor Cyan
Write-Host "   后端 API:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "   前端 UI:   http://localhost:5173" -ForegroundColor White
Write-Host "   MinIO:     http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务" -ForegroundColor Yellow

try {
    Wait-Job $backendJob, $frontendJob -Any
} finally {
    Write-Host "🛑 停止服务..." -ForegroundColor Yellow
    if ($backendJob) { Stop-Job $backendJob -ErrorAction SilentlyContinue; Remove-Job $backendJob -ErrorAction SilentlyContinue }
    if ($frontendJob) { Stop-Job $frontendJob -ErrorAction SilentlyContinue; Remove-Job $frontendJob -ErrorAction SilentlyContinue }
}
```

- [ ] **Step 5: 创建 Linux/macOS 开发启动脚本 `scripts\dev.sh`**

```bash
#!/bin/bash
# 漫剧生成软件 - Linux/macOS 开发环境启动脚本
# 用法: ./scripts/dev.sh

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 启动 ComicStudio AI 开发环境..."

# 检查 .env 文件
if [ ! -f "$ROOT/.env" ]; then
    if [ -f "$ROOT/.env.example" ]; then
        echo "📋 复制 .env.example 到 .env"
        cp "$ROOT/.env.example" "$ROOT/.env"
        echo "⚠️  请编辑 .env 文件填入实际配置后重新运行"
        exit 1
    else
        echo "❌ 未找到 .env 或 .env.example 文件"
        exit 1
    fi
fi

# 启动基础设施
if [ "$1" != "--no-docker" ]; then
    echo "🐳 启动 Docker 基础设施 (postgres, redis, minio)..."
    cd "$ROOT/docker"
    docker-compose up -d postgres redis minio
    echo "✅ 基础设施已启动"
fi

# 启动后端
echo "🐍 启动后端服务 (http://localhost:8000)..."
cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt --quiet
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "⚛️  启动前端服务 (http://localhost:5173)..."
cd "$ROOT/frontend"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✨ 开发环境已启动:"
echo "   后端 API:  http://localhost:8000/docs"
echo "   前端 UI:   http://localhost:5173"
echo "   MinIO:     http://localhost:9001"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "echo '🛑 停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
```

- [ ] **Step 6: 提交**

```bash
cd "c:\漫剧软件项目"
git init 2>$null
git add .gitignore .env.example ai-models/.gitkeep scripts/
git commit -m "chore: 初始化项目根目录结构与开发脚本"
```

---

## Task 2: 后端依赖与项目配置

**Files:**
- Create: `c:\漫剧软件项目\backend\requirements.txt`
- Create: `c:\漫剧软件项目\backend\pyproject.toml`
- Create: `c:\漫剧软件项目\backend\.env.example`
- Create: `c:\漫剧软件项目\backend\app\__init__.py`

- [ ] **Step 1: 创建 `backend/requirements.txt`**

```txt
# ===========================================
# ComicStudio AI - 后端依赖
# ===========================================

# Web 框架
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
websockets==12.0

# 数据库 ORM
sqlalchemy[asyncio]==2.0.23
alembic==1.13.0
asyncpg==0.29.0

# Redis
redis[hiredis]==5.0.1

# 任务队列
celery==5.3.6
flower==2.0.1

# 认证授权
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# 限流
fastapi-limiter==0.1.5

# 对象存储
minio==7.2.3
boto3==1.34.11

# 工具库
pydantic==2.5.3
pydantic-settings==2.1.0
loguru==0.7.2
httpx==0.26.0
python-dotenv==1.0.0
email-validator==2.1.0

# 测试
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0

# AI 相关 (基础包，重型依赖在后续阶段添加)
# torch, diffusers, transformers 等在 ai-requirements.txt 中
Pillow==10.2.0
numpy==1.26.2

# TTS
edge-tts==6.1.9

# FFmpeg Python 封装
ffmpeg-python==0.2.0
```

- [ ] **Step 2: 创建 `backend/pyproject.toml`**

```toml
[project]
name = "comic-studio-backend"
version = "0.1.0"
description = "ComicStudio AI - 商业化漫剧生成软件后端"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]
```

- [ ] **Step 3: 创建 `backend/.env.example`**

```env
# 后端专用环境变量 (根目录 .env 已包含完整配置，此文件为后端独立部署时使用)

APP_NAME=ComicStudio AI
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
APP_SECRET_KEY=change-me

DATABASE_URL=postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio
REDIS_URL=redis://localhost:6379/0

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

JWT_SECRET_KEY=change-me-to-a-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:5173,http://localhost:3000

CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

MODEL_CACHE_DIR=./ai-models
DEVICE=cpu

DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
```

- [ ] **Step 4: 创建 `backend/app/__init__.py`**

```python
"""ComicStudio AI 后端应用包"""

__version__ = "0.1.0"
```

- [ ] **Step 5: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/requirements.txt backend/pyproject.toml backend/.env.example backend/app/__init__.py
git commit -m "feat(backend): 添加依赖清单与项目配置"
```

---

## Task 3: 后端核心配置与数据库连接

**Files:**
- Create: `c:\漫剧软件项目\backend\app\core\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\core\config.py`
- Create: `c:\漫剧软件项目\backend\app\core\database.py`
- Test: `c:\漫剧软件项目\backend\tests\test_config.py`

- [ ] **Step 1: 创建 `app/core/__init__.py`**

```python
"""核心组件包"""
```

- [ ] **Step 2: 创建 `app/core/config.py`**

```python
"""应用配置 - 基于 Pydantic Settings"""
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类，从环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "ComicStudio AI"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me"

    # 数据库
    database_url: str = "postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "change-me-to-a-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440
    jwt_refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # AI 模型
    model_cache_dir: str = "./ai-models"
    device: str = "cpu"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """保留原始字符串，通过属性访问解析后的列表"""
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """获取 CORS 来源列表"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# 全局配置单例
settings = Settings()
```

- [ ] **Step 3: 创建 `app/core/database.py`**

```python
"""数据库连接管理 - SQLAlchemy 2.0 异步引擎"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


# 异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库 (创建所有表 - 仅用于开发)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()
```

- [ ] **Step 4: 编写测试 `tests/test_config.py`**

```python
"""配置测试"""
import pytest
from app.core.config import Settings, settings


def test_settings_loads_defaults():
    """测试配置能正常加载"""
    assert settings.app_name == "ComicStudio AI"
    assert settings.app_env in ["development", "production", "testing"]
    assert settings.jwt_algorithm == "HS256"


def test_cors_origins_list():
    """测试 CORS 来源解析"""
    s = Settings(cors_origins="http://a.com, http://b.com ,http://c.com")
    assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]


def test_environment_flags():
    """测试环境标志"""
    s = Settings(app_env="development")
    assert s.is_development is True
    assert s.is_production is False

    s = Settings(app_env="production")
    assert s.is_development is False
    assert s.is_production is True
```

- [ ] **Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: 3 个测试通过

- [ ] **Step 6: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/core/__init__.py backend/app/core/config.py backend/app/core/database.py backend/tests/test_config.py
git commit -m "feat(backend): 添加应用配置与异步数据库连接"
```

---

## Task 4: 数据模型基类与所有实体模型

**Files:**
- Create: `c:\漫剧软件项目\backend\app\models\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\models\base.py`
- Create: `c:\漫剧软件项目\backend\app\models\user.py`
- Create: `c:\漫剧软件项目\backend\app\models\project.py`
- Create: `c:\漫剧软件项目\backend\app\models\character.py`
- Create: `c:\漫剧软件项目\backend\app\models\script.py`
- Create: `c:\漫剧软件项目\backend\app\models\storyboard.py`
- Create: `c:\漫剧软件项目\backend\app\models\audio.py`
- Create: `c:\漫剧软件项目\backend\app\models\render.py`
- Create: `c:\漫剧软件项目\backend\app\models\workflow.py`
- Create: `c:\漫剧软件项目\backend\app\models\billing.py`
- Test: `c:\漫剧软件项目\backend\tests\test_models.py`

- [ ] **Step 1: 创建 `app/models/base.py` 基类与混入**

```python
"""ORM 模型基类与混入"""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 基类 - 与 database.py 中的 Base 共用"""
    pass


class UUIDMixin:
    """UUID 主键混入"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)


class TimestampMixin:
    """时间戳混入"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SoftDeleteMixin:
    """软删除混入"""
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
```

- [ ] **Step 2: 创建 `app/models/user.py`**

```python
"""用户模型"""
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, JSON
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """用户实体"""
    __tablename__ = "users"

    # 基本信息
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    avatar_url = Column(String(500))
    bio = Column(Text)

    # 账户状态
    status = Column(String(20), default="active")  # active/banned/inactive
    email_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime)

    # 订阅信息
    plan = Column(String(20), default="free")  # free/pro/enterprise
    plan_expires_at = Column(DateTime)
    credits = Column(Integer, default=100)

    # 偏好设置
    preferences = Column(JSON, default=lambda: {
        "language": "zh-CN",
        "theme": "dark",
        "default_model": "sdxl",
        "auto_save": True,
    })
```

- [ ] **Step 3: 创建 `app/models/project.py`**

```python
"""项目模型"""
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class Project(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """项目实体"""
    __tablename__ = "projects"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50))  # romance/action/mystery/comedy/drama

    status = Column(String(20), default="active")  # active/archived/deleted

    config = Column(JSON, default=lambda: {
        "resolution": "1920x1080",
        "fps": 24,
        "style": "anime",
    })

    # 统计
    character_count = Column(Integer, default=0)
    scene_count = Column(Integer, default=0)
    frame_count = Column(Integer, default=0)

    # 协作
    is_shared = Column(Boolean, default=False)
    collaborators = Column(JSON, default=list)
```

- [ ] **Step 4: 创建 `app/models/character.py`**

```python
"""角色模型"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class Character(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """角色实体"""
    __tablename__ = "characters"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)

    # 外观特征
    style = Column(String(50), default="anime")
    gender = Column(String(20))
    age = Column(String(50))
    hair_color = Column(String(50))
    eye_color = Column(String(50))
    skin_tone = Column(String(50))
    body_type = Column(String(50))

    # LoRA 模型
    lora_model_path = Column(String(500))
    lora_training_status = Column(String(20), default="none")  # none/training/ready/failed

    # 图像
    main_image_url = Column(String(500))
    reference_images = Column(JSON, default=list)

    # 元数据
    tags = Column(JSON, default=list)
    usage_count = Column(Integer, default=0)
```

- [ ] **Step 5: 创建 `app/models/script.py` (Script + Scene + Dialogue)**

```python
"""剧本模型 (Script + Scene + Dialogue)"""
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin


class Script(Base, UUIDMixin, TimestampMixin):
    """剧本实体"""
    __tablename__ = "scripts"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)

    structure = Column(String(50), default="three_act")
    genre = Column(String(50))
    outline = Column(Text)

    total_scenes = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    status = Column(String(20), default="draft")  # draft/published/archived


class Scene(Base, UUIDMixin, TimestampMixin):
    """剧本场景实体"""
    __tablename__ = "script_scenes"

    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False, index=True)
    scene_number = Column(Integer, nullable=False)
    title = Column(String(200))
    location = Column(String(200))
    time_of_day = Column(String(50))
    description = Column(Text)
    mood = Column(String(50))
    intensity = Column(Integer, default=5)
    order_index = Column(Integer, default=0)


class Dialogue(Base, UUIDMixin, TimestampMixin):
    """对话实体"""
    __tablename__ = "dialogues"

    scene_id = Column(UUID(as_uuid=True), ForeignKey("script_scenes.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True)
    character_name = Column(String(100))

    content = Column(Text, nullable=False)
    emotion = Column(String(50))  # happy/sad/angry/surprised/neutral
    action = Column(Text)

    bubble_type = Column(String(50), default="normal")
    bubble_position = Column(String(50), default="right")
    duration = Column(Float, default=2.0)
    order_index = Column(Integer, default=0)
```

- [ ] **Step 6: 创建 `app/models/storyboard.py`**

```python
"""分镜模型"""
from sqlalchemy import Column, String, Text, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin


class StoryboardFrame(Base, UUIDMixin, TimestampMixin):
    """分镜帧"""
    __tablename__ = "storyboard_frames"

    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False, index=True)
    scene_id = Column(UUID(as_uuid=True), ForeignKey("script_scenes.id"), nullable=True)
    frame_number = Column(Integer, nullable=False)

    # 镜头信息
    shot_type = Column(String(50))  # extreme_wide/wide/medium/close_up
    camera_angle = Column(String(50))  # eye_level/high_angle/low_angle
    composition = Column(String(50))  # rule_of_thirds/center/symmetry
    camera_movement = Column(String(50))  # static/pan/zoom/tracking

    # 内容
    description = Column(Text)
    prompt = Column(Text)
    negative_prompt = Column(Text)

    # 角色配置
    characters_in_frame = Column(JSON, default=list)

    # 时间
    duration = Column(Float, default=2.0)
    transition = Column(String(50), default="cut")
    transition_duration = Column(Float, default=0.5)

    # 生成结果
    generated_image_url = Column(String(500), nullable=True)
    generation_status = Column(String(20), default="pending")  # pending/generating/completed/failed
```

- [ ] **Step 7: 创建 `app/models/audio.py` (VoiceProfile + AudioTrack)**

```python
"""音频模型 (VoiceProfile + AudioTrack)"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class VoiceProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音色配置"""
    __tablename__ = "voice_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=True)

    name = Column(String(100), nullable=False)
    engine = Column(String(50), default="edge_tts")  # edge_tts/vits/volcano
    voice_id = Column(String(100))
    language = Column(String(10), default="zh-CN")

    rate = Column(Integer, default=0)  # -100 到 100
    pitch = Column(Integer, default=0)
    volume = Column(Integer, default=100)

    gender = Column(String(20))
    age_group = Column(String(20))
    tone = Column(String(50))


class AudioTrack(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音频轨道"""
    __tablename__ = "audio_tracks"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    track_type = Column(String(50), nullable=False)  # voice/bgm/sfx/ambient
    name = Column(String(200))

    audio_url = Column(String(500))
    duration = Column(Float)

    start_time = Column(Float, default=0)
    end_time = Column(Float)

    frame_id = Column(UUID(as_uuid=True), ForeignKey("storyboard_frames.id"), nullable=True)
    dialogue_id = Column(UUID(as_uuid=True), ForeignKey("dialogues.id"), nullable=True)
    voice_profile_id = Column(UUID(as_uuid=True), ForeignKey("voice_profiles.id"), nullable=True)

    volume = Column(Float, default=1.0)
    fade_in = Column(Float, default=0)
    fade_out = Column(Float, default=0)
```

- [ ] **Step 8: 创建 `app/models/render.py`**

```python
"""渲染任务模型"""
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin


class RenderTask(Base, UUIDMixin, TimestampMixin):
    """渲染任务"""
    __tablename__ = "render_tasks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)

    name = Column(String(200))
    status = Column(String(20), default="pending")  # pending/processing/completed/failed/cancelled
    progress = Column(Integer, default=0)

    config = Column(JSON)
    output_url = Column(String(500), nullable=True)
    output_size = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    credits_cost = Column(Integer, default=0)
```

- [ ] **Step 9: 创建 `app/models/workflow.py` (Workflow + WorkflowExecution)**

```python
"""工作流模型 (Workflow + WorkflowExecution)"""
from sqlalchemy import Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class Workflow(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """工作流定义"""
    __tablename__ = "workflows"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    name = Column(String(200), nullable=False)
    description = Column(Text)

    # 工作流数据
    nodes = Column(JSON, nullable=False, default=list)
    edges = Column(JSON, nullable=False, default=list)

    # 元数据
    category = Column(String(50), default="custom")
    is_template = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)

    # 版本
    version = Column(Integer, default=1)
    parent_version_id = Column(UUID(as_uuid=True), nullable=True)


class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    """工作流执行记录"""
    __tablename__ = "workflow_executions"

    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(String(20), default="running")  # running/completed/failed/cancelled
    inputs = Column(JSON)
    results = Column(JSON)
    errors = Column(JSON)

    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)

    node_executions = Column(JSON, default=list)
```

- [ ] **Step 10: 创建 `app/models/billing.py` (Subscription + CreditTransaction)**

```python
"""计费模型 (Subscription + CreditTransaction)"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin


class Subscription(Base, UUIDMixin, TimestampMixin):
    """订阅记录"""
    __tablename__ = "subscriptions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan = Column(String(20), nullable=False)  # free/pro/enterprise
    status = Column(String(20), default="active")  # active/cancelled/expired

    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)

    amount = Column(Integer)  # 金额（分）
    payment_method = Column(String(50))
    payment_id = Column(String(200))

    auto_renew = Column(Boolean, default=False)


class CreditTransaction(Base, UUIDMixin, TimestampMixin):
    """积分交易记录"""
    __tablename__ = "credit_transactions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String(20), nullable=False)  # recharge/deduct/bonus/refund
    amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    reason = Column(String(50))  # create_character/render/lora_train/recharge
    description = Column(String(200))

    related_id = Column(UUID(as_uuid=True), nullable=True)
    related_type = Column(String(50))
```

- [ ] **Step 11: 创建 `app/models/__init__.py` 统一导出**

```python
"""数据模型包 - 统一导出所有实体"""
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.user import User
from app.models.project import Project
from app.models.character import Character
from app.models.script import Script, Scene, Dialogue
from app.models.storyboard import StoryboardFrame
from app.models.audio import VoiceProfile, AudioTrack
from app.models.render import RenderTask
from app.models.workflow import Workflow, WorkflowExecution
from app.models.billing import Subscription, CreditTransaction

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "User",
    "Project",
    "Character",
    "Script",
    "Scene",
    "Dialogue",
    "StoryboardFrame",
    "VoiceProfile",
    "AudioTrack",
    "RenderTask",
    "Workflow",
    "WorkflowExecution",
    "Subscription",
    "CreditTransaction",
]
```

- [ ] **Step 12: 编写测试 `tests/test_models.py`**

```python
"""模型测试 - 验证表结构与关系"""
import pytest
from sqlalchemy import inspect
from app.models import (
    Base, User, Project, Character, Script, Scene, Dialogue,
    StoryboardFrame, VoiceProfile, AudioTrack, RenderTask,
    Workflow, WorkflowExecution, Subscription, CreditTransaction,
)


def test_all_models_registered():
    """测试所有模型已注册到 Base.metadata"""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users", "projects", "characters", "scripts", "script_scenes",
        "dialogues", "storyboard_frames", "voice_profiles", "audio_tracks",
        "render_tasks", "workflows", "workflow_executions",
        "subscriptions", "credit_transactions",
    }
    assert expected.issubset(table_names), f"缺少表: {expected - table_names}"


def test_user_model_columns():
    """测试 User 模型字段"""
    mapper = inspect(User)
    column_names = {c.key for c in mapper.columns}
    required = {"id", "username", "email", "password_hash", "status", "plan", "credits"}
    assert required.issubset(column_names)


def test_project_user_relationship():
    """测试 Project.user_id 外键指向 users.id"""
    fk = Project.__table__.c.user_id.foreign_keys
    assert len(fk) == 1
    assert fk.pop().column.table.name == "users"


def test_character_project_relationship():
    """测试 Character.project_id 外键指向 projects.id"""
    fk = Character.__table__.c.project_id.foreign_keys
    assert len(fk) == 1
    assert fk.pop().column.table.name == "projects"
```

- [ ] **Step 13: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: 4 个测试通过

- [ ] **Step 14: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat(backend): 添加全部数据模型 (14个实体表)"
```

---

## Task 5: 后端核心工具 (响应、安全、依赖注入)

**Files:**
- Create: `c:\漫剧软件项目\backend\app\core\response.py`
- Create: `c:\漫剧软件项目\backend\app\core\security.py`
- Create: `c:\漫剧软件项目\backend\app\core\deps.py`
- Test: `c:\漫剧软件项目\backend\tests\test_security.py`

- [ ] **Step 1: 创建 `app/core/response.py` 统一响应**

```python
"""统一 API 响应模型"""
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, Field
import time

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应"""
    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> "ApiResponse[T]":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, message: str, code: int = -1, data: T = None) -> "ApiResponse[T]":
        return cls(code=code, message=message, data=data)


class PaginatedData(BaseModel, Generic[T]):
    """分页数据"""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    code: int = 0
    message: str = "success"
    data: PaginatedData[T]
    timestamp: int = Field(default_factory=lambda: int(time.time()))
```

- [ ] **Step 2: 创建 `app/core/security.py` JWT 与密码哈希**

```python
"""安全工具 - JWT 令牌与密码哈希"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    """创建刷新令牌"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    """解码令牌，失败返回 None"""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
```

- [ ] **Step 3: 创建 `app/core/deps.py` 依赖注入**

```python
"""依赖注入 - 数据库会话与当前用户"""
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    token_type = payload.get("type")
    if user_id is None or token_type != "access":
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    return user
```

- [ ] **Step 4: 编写测试 `tests/test_security.py`**

```python
"""安全工具测试"""
import pytest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_password_hashing():
    """测试密码哈希与验证"""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_access_token_creation():
    """测试访问令牌生成与解码"""
    user_id = "test-user-id"
    token = create_access_token(user_id)

    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"


def test_refresh_token_creation():
    """测试刷新令牌"""
    user_id = "test-user-id"
    token = create_refresh_token(user_id)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"


def test_invalid_token_returns_none():
    """测试无效令牌解码返回 None"""
    payload = decode_token("invalid.token.here")
    assert payload is None
```

- [ ] **Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/test_security.py -v`
Expected: 4 个测试通过

- [ ] **Step 6: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/core/response.py backend/app/core/security.py backend/app/core/deps.py backend/tests/test_security.py
git commit -m "feat(backend): 添加统一响应、JWT安全与依赖注入"
```

---

## Task 6: Pydantic Schema 与 BaseService

**Files:**
- Create: `c:\漫剧软件项目\backend\app\schemas\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\common.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\user.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\project.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\character.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\script.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\storyboard.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\audio.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\render.py`
- Create: `c:\漫剧软件项目\backend\app\schemas\workflow.py`
- Create: `c:\漫剧软件项目\backend\app\services\base_service.py`

- [ ] **Step 1: 创建 `app/schemas/__init__.py` 与 `app/schemas/common.py`**

`app/schemas/__init__.py`:
```python
"""Pydantic Schema 包"""
```

`app/schemas/common.py`:
```python
"""通用 Schema"""
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel

T = TypeVar("T")


class ORMModel(BaseModel):
    """支持从 ORM 模型转换的基类"""
    model_config = {"from_attributes": True}


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = 1
    page_size: int = 20
```

- [ ] **Step 2: 创建 `app/schemas/user.py`**

```python
"""用户 Schema"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field
from app.schemas.common import ORMModel


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    account: str = Field(..., description="用户名或邮箱")
    password: str


class UserUpdate(BaseModel):
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    preferences: Optional[dict] = None


class UserResponse(ORMModel):
    id: str
    username: str
    email: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    status: str
    plan: str
    credits: int
    preferences: Optional[Any] = None
    email_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
```

- [ ] **Step 3: 创建 `app/schemas/project.py`**

```python
"""项目 Schema"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    genre: Optional[str] = None
    config: Optional[dict] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    status: Optional[str] = None
    config: Optional[dict] = None


class ProjectResponse(ORMModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    genre: Optional[str] = None
    status: str
    config: Optional[Any] = None
    character_count: int
    scene_count: int
    frame_count: int
    is_shared: bool
    collaborators: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: 创建 `app/schemas/character.py`**

```python
"""角色 Schema"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    style: str = "anime"
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    tags: List[str] = []


class CharacterCreate(CharacterBase):
    project_id: Optional[str] = None
    reference_images: List[str] = []


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    style: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    main_image_url: Optional[str] = None
    reference_images: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class CharacterResponse(ORMModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    style: str
    gender: Optional[str] = None
    age: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    skin_tone: Optional[str] = None
    body_type: Optional[str] = None
    lora_model_path: Optional[str] = None
    lora_training_status: str
    main_image_url: Optional[str] = None
    reference_images: Optional[Any] = None
    tags: Optional[Any] = None
    usage_count: int
    created_at: datetime
```

- [ ] **Step 5: 创建 `app/schemas/script.py`**

```python
"""剧本 Schema"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class ScriptBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    structure: str = "three_act"
    genre: Optional[str] = None
    outline: Optional[str] = None


class ScriptCreate(ScriptBase):
    project_id: str


class ScriptUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    structure: Optional[str] = None
    genre: Optional[str] = None
    outline: Optional[str] = None
    status: Optional[str] = None


class ScriptResponse(ORMModel):
    id: str
    user_id: str
    project_id: str
    title: str
    description: Optional[str] = None
    structure: str
    genre: Optional[str] = None
    outline: Optional[str] = None
    total_scenes: int
    total_duration: int
    status: str
    created_at: datetime
    updated_at: datetime


class SceneBase(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    mood: Optional[str] = None
    intensity: int = 5


class SceneCreate(SceneBase):
    script_id: str
    scene_number: int


class SceneResponse(ORMModel):
    id: str
    script_id: str
    scene_number: int
    title: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    mood: Optional[str] = None
    intensity: int
    order_index: int


class DialogueBase(BaseModel):
    character_name: Optional[str] = None
    content: str
    emotion: Optional[str] = None
    action: Optional[str] = None
    bubble_type: str = "normal"
    bubble_position: str = "right"
    duration: float = 2.0


class DialogueCreate(DialogueBase):
    scene_id: str
    character_id: Optional[str] = None


class DialogueResponse(ORMModel):
    id: str
    scene_id: str
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    content: str
    emotion: Optional[str] = None
    action: Optional[str] = None
    bubble_type: str
    bubble_position: str
    duration: float
    order_index: int
```

- [ ] **Step 6: 创建 `app/schemas/storyboard.py`**

```python
"""分镜 Schema"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class StoryboardFrameBase(BaseModel):
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: List[dict] = []
    duration: float = 2.0
    transition: str = "cut"
    transition_duration: float = 0.5


class StoryboardFrameCreate(StoryboardFrameBase):
    script_id: str
    scene_id: Optional[str] = None
    frame_number: int


class StoryboardFrameUpdate(BaseModel):
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: Optional[List[dict]] = None
    duration: Optional[float] = None
    transition: Optional[str] = None
    transition_duration: Optional[float] = None
    generated_image_url: Optional[str] = None
    generation_status: Optional[str] = None


class StoryboardFrameResponse(ORMModel):
    id: str
    script_id: str
    scene_id: Optional[str] = None
    frame_number: int
    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    composition: Optional[str] = None
    camera_movement: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    characters_in_frame: Optional[Any] = None
    duration: float
    transition: str
    transition_duration: float
    generated_image_url: Optional[str] = None
    generation_status: str
    created_at: datetime
```

- [ ] **Step 7: 创建 `app/schemas/audio.py`**

```python
"""音频 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class VoiceProfileBase(BaseModel):
    name: str = Field(..., max_length=100)
    engine: str = "edge_tts"
    voice_id: Optional[str] = None
    language: str = "zh-CN"
    rate: int = 0
    pitch: int = 0
    volume: int = 100
    gender: Optional[str] = None
    age_group: Optional[str] = None
    tone: Optional[str] = None


class VoiceProfileCreate(VoiceProfileBase):
    character_id: Optional[str] = None


class VoiceProfileResponse(ORMModel):
    id: str
    user_id: str
    character_id: Optional[str] = None
    name: str
    engine: str
    voice_id: Optional[str] = None
    language: str
    rate: int
    pitch: int
    volume: int
    gender: Optional[str] = None
    age_group: Optional[str] = None
    tone: Optional[str] = None
    created_at: datetime


class AudioTrackBase(BaseModel):
    track_type: str  # voice/bgm/sfx/ambient
    name: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    start_time: float = 0
    end_time: Optional[float] = None
    volume: float = 1.0
    fade_in: float = 0
    fade_out: float = 0


class AudioTrackCreate(AudioTrackBase):
    project_id: str
    frame_id: Optional[str] = None
    dialogue_id: Optional[str] = None
    voice_profile_id: Optional[str] = None


class AudioTrackResponse(ORMModel):
    id: str
    project_id: str
    track_type: str
    name: Optional[str] = None
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    start_time: float
    end_time: Optional[float] = None
    frame_id: Optional[str] = None
    dialogue_id: Optional[str] = None
    voice_profile_id: Optional[str] = None
    volume: float
    fade_in: float
    fade_out: float
    created_at: datetime
```

- [ ] **Step 8: 创建 `app/schemas/render.py`**

```python
"""渲染 Schema"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.schemas.common import ORMModel


class RenderTaskCreate(BaseModel):
    project_id: str
    script_id: str
    name: Optional[str] = None
    config: Optional[dict] = None


class RenderTaskResponse(ORMModel):
    id: str
    user_id: str
    project_id: str
    script_id: str
    name: Optional[str] = None
    status: str
    progress: int
    config: Optional[Any] = None
    output_url: Optional[str] = None
    output_size: Optional[int] = None
    duration: Optional[float] = None
    frame_count: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    credits_cost: int
    created_at: datetime
```

- [ ] **Step 9: 创建 `app/schemas/workflow.py`**

```python
"""工作流 Schema"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    nodes: List[dict] = []
    edges: List[dict] = []
    category: str = "custom"


class WorkflowCreate(WorkflowBase):
    project_id: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None


class WorkflowResponse(ORMModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    nodes: Any
    edges: Any
    category: str
    is_template: bool
    is_public: bool
    version: int
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionCreate(BaseModel):
    workflow_id: str
    inputs: Optional[dict] = None


class WorkflowExecutionResponse(ORMModel):
    id: str
    workflow_id: str
    user_id: str
    status: str
    inputs: Optional[Any] = None
    results: Optional[Any] = None
    errors: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    node_executions: Optional[Any] = None
```

- [ ] **Step 10: 创建 `app/services/base_service.py` 服务基类**

```python
"""服务基类 - 提供通用 CRUD 操作"""
from typing import Generic, TypeVar, Optional, List, Type, Any
from abc import ABC
from uuid import UUID
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType], ABC):
    """业务服务基类，提供异步 CRUD 操作"""

    model: Type[ModelType]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> ModelType:
        """创建实体"""
        entity = self.model(**data)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> Optional[ModelType]:
        """根据 ID 获取实体"""
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        result = await self.db.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[dict] = None,
    ) -> List[ModelType]:
        """列表查询"""
        stmt = select(self.model)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)
        # 软删除过滤
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted == False)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: Optional[dict] = None) -> int:
        """计数"""
        stmt = select(func.count(self.model.id))
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted == False)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update(self, entity_id: UUID | str, data: dict) -> Optional[ModelType]:
        """更新实体"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return None
        for key, value in data.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity_id: UUID | str, soft: bool = True) -> bool:
        """删除实体（默认软删除）"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        if soft and hasattr(entity, "is_deleted"):
            from datetime import datetime
            entity.is_deleted = True
            entity.deleted_at = datetime.utcnow()
        else:
            await self.db.delete(entity)
        await self.db.flush()
        return True
```

- [ ] **Step 11: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/schemas/ backend/app/services/base_service.py
git commit -m "feat(backend): 添加 Pydantic Schemas 与 BaseService 基类"
```

---

## Task 7: 业务服务层实现

**Files:**
- Create: `c:\漫剧软件项目\backend\app\services\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\services\user_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\project_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\character_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\script_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\storyboard_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\audio_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\render_service.py`
- Create: `c:\漫剧软件项目\backend\app\services\workflow_service.py`

- [ ] **Step 1: 创建 `app/services/__init__.py`**

```python
"""业务服务包"""
from app.services.user_service import UserService
from app.services.project_service import ProjectService
from app.services.character_service import CharacterService
from app.services.script_service import ScriptService
from app.services.storyboard_service import StoryboardService
from app.services.audio_service import AudioService
from app.services.render_service import RenderService
from app.services.workflow_service import WorkflowService

__all__ = [
    "UserService", "ProjectService", "CharacterService",
    "ScriptService", "StoryboardService", "AudioService",
    "RenderService", "WorkflowService",
]
```

- [ ] **Step 2: 创建 `app/services/user_service.py`**

```python
"""用户服务"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import hash_password, verify_password
from app.services.base_service import BaseService


class UserService(BaseService[User]):
    model = User

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名查询"""
        result = await self.db.execute(
            select(User).where(User.username == username, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查询"""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_account(self, account: str) -> Optional[User]:
        """根据用户名或邮箱查询（用于登录）"""
        result = await self.db.execute(
            select(User).where(
                or_(User.username == account, User.email == account),
                User.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def register(self, username: str, email: str, password: str) -> User:
        """注册用户"""
        # 检查用户名/邮箱是否已存在
        if await self.get_by_username(username):
            raise ValueError("用户名已存在")
        if await self.get_by_email(email):
            raise ValueError("邮箱已被注册")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate(self, account: str, password: str) -> Optional[User]:
        """验证用户凭据"""
        user = await self.get_by_account(account)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        # 更新最后登录时间
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user
```

- [ ] **Step 3: 创建 `app/services/project_service.py`**

```python
"""项目服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.project import Project
from app.services.base_service import BaseService


class ProjectService(BaseService[Project]):
    model = Project

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 20) -> List[Project]:
        """获取用户的项目列表"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id, Project.is_deleted == False)
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: 创建 `app/services/character_service.py`**

```python
"""角色服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select, or_
from app.models.character import Character
from app.services.base_service import BaseService


class CharacterService(BaseService[Character]):
    model = Character

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 50) -> List[Character]:
        """获取用户的角色库"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Character)
            .where(Character.user_id == user_id, Character.is_deleted == False)
            .order_by(Character.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_project(self, project_id: UUID | str) -> List[Character]:
        """获取项目内的角色"""
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(Character)
            .where(
                Character.project_id == project_id,
                Character.is_deleted == False,
            )
            .order_by(Character.created_at)
        )
        return list(result.scalars().all())
```

- [ ] **Step 5: 创建 `app/services/script_service.py`**

```python
"""剧本服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.script import Script, Scene, Dialogue
from app.services.base_service import BaseService


class ScriptService(BaseService[Script]):
    model = Script

    async def list_by_project(self, project_id: UUID | str) -> List[Script]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(Script)
            .where(Script.project_id == project_id)
            .order_by(Script.updated_at.desc())
        )
        return list(result.scalars().all())


class SceneService(BaseService[Scene]):
    model = Scene

    async def list_by_script(self, script_id: UUID | str) -> List[Scene]:
        if isinstance(script_id, str):
            script_id = UUID(script_id)
        result = await self.db.execute(
            select(Scene)
            .where(Scene.script_id == script_id)
            .order_by(Scene.order_index, Scene.scene_number)
        )
        return list(result.scalars().all())


class DialogueService(BaseService[Dialogue]):
    model = Dialogue

    async def list_by_scene(self, scene_id: UUID | str) -> List[Dialogue]:
        if isinstance(scene_id, str):
            scene_id = UUID(scene_id)
        result = await self.db.execute(
            select(Dialogue)
            .where(Dialogue.scene_id == scene_id)
            .order_by(Dialogue.order_index)
        )
        return list(result.scalars().all())
```

- [ ] **Step 6: 创建 `app/services/storyboard_service.py`**

```python
"""分镜服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.storyboard import StoryboardFrame
from app.services.base_service import BaseService


class StoryboardService(BaseService[StoryboardFrame]):
    model = StoryboardFrame

    async def list_by_script(self, script_id: UUID | str) -> List[StoryboardFrame]:
        if isinstance(script_id, str):
            script_id = UUID(script_id)
        result = await self.db.execute(
            select(StoryboardFrame)
            .where(StoryboardFrame.script_id == script_id)
            .order_by(StoryboardFrame.frame_number)
        )
        return list(result.scalars().all())

    async def list_by_scene(self, scene_id: UUID | str) -> List[StoryboardFrame]:
        if isinstance(scene_id, str):
            scene_id = UUID(scene_id)
        result = await self.db.execute(
            select(StoryboardFrame)
            .where(StoryboardFrame.scene_id == scene_id)
            .order_by(StoryboardFrame.frame_number)
        )
        return list(result.scalars().all())
```

- [ ] **Step 7: 创建 `app/services/audio_service.py`**

```python
"""音频服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.audio import VoiceProfile, AudioTrack
from app.services.base_service import BaseService


class VoiceProfileService(BaseService[VoiceProfile]):
    model = VoiceProfile

    async def list_by_user(self, user_id: UUID | str) -> List[VoiceProfile]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(VoiceProfile)
            .where(VoiceProfile.user_id == user_id, VoiceProfile.is_deleted == False)
            .order_by(VoiceProfile.created_at.desc())
        )
        return list(result.scalars().all())


class AudioTrackService(BaseService[AudioTrack]):
    model = AudioTrack

    async def list_by_project(self, project_id: UUID | str) -> List[AudioTrack]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(AudioTrack)
            .where(AudioTrack.project_id == project_id, AudioTrack.is_deleted == False)
            .order_by(AudioTrack.start_time)
        )
        return list(result.scalars().all())


# 统一服务类，兼容外部调用
class AudioService:
    """音频服务统一入口"""

    def __init__(self, db):
        self.voice_profile = VoiceProfileService(db)
        self.track = AudioTrackService(db)
```

- [ ] **Step 8: 创建 `app/services/render_service.py`**

```python
"""渲染服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.render import RenderTask
from app.services.base_service import BaseService


class RenderService(BaseService[RenderTask]):
    model = RenderTask

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 20) -> List[RenderTask]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(RenderTask)
            .where(RenderTask.user_id == user_id)
            .order_by(RenderTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_project(self, project_id: UUID | str) -> List[RenderTask]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(RenderTask)
            .where(RenderTask.project_id == project_id)
            .order_by(RenderTask.created_at.desc())
        )
        return list(result.scalars().all())
```

- [ ] **Step 9: 创建 `app/services/workflow_service.py`**

```python
"""工作流服务"""
from typing import List
from uuid import UUID
from sqlalchemy import select
from app.models.workflow import Workflow, WorkflowExecution
from app.services.base_service import BaseService


class WorkflowService(BaseService[Workflow]):
    model = Workflow

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 50) -> List[Workflow]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.user_id == user_id, Workflow.is_deleted == False)
            .order_by(Workflow.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_templates(self, category: str = None) -> List[Workflow]:
        """获取公开模板"""
        stmt = select(Workflow).where(
            Workflow.is_template == True,
            Workflow.is_deleted == False,
        )
        if category:
            stmt = stmt.where(Workflow.category == category)
        result = await self.db.execute(stmt.order_by(Workflow.created_at.desc()))
        return list(result.scalars().all())


class WorkflowExecutionService(BaseService[WorkflowExecution]):
    model = WorkflowExecution

    async def list_by_workflow(self, workflow_id: UUID | str) -> List[WorkflowExecution]:
        if isinstance(workflow_id, str):
            workflow_id = UUID(workflow_id)
        result = await self.db.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())
```

- [ ] **Step 10: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/services/
git commit -m "feat(backend): 实现全部业务服务层 (8个服务)"
```

---

## Task 8: API 路由 - 认证与用户

**Files:**
- Create: `c:\漫剧软件项目\backend\app\api\__init__.py`
- Create: `c:\漫剧软件项目\backend\app\api\auth.py`
- Create: `c:\漫剧软件项目\backend\app\api\users.py`
- Test: `c:\漫剧软件项目\backend\tests\test_auth.py`

- [ ] **Step 1: 创建 `app/api/__init__.py`**

```python
"""API 路由包"""
```

- [ ] **Step 2: 创建 `app/api/auth.py` 认证路由**

```python
"""认证路由 - 注册/登录/刷新令牌"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.core.response import ApiResponse

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    service = UserService(db)
    try:
        user = await service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return ApiResponse.success(data=UserResponse.model_validate(user), message="注册成功")


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    service = UserService(db)
    user = await service.authenticate(payload.account, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        ),
        message="登录成功",
    )


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """刷新访问令牌"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    user_id = payload.get("sub")
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    new_access = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))
    return ApiResponse.success(
        data=TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            user=UserResponse.model_validate(user),
        )
    )
```

- [ ] **Step 3: 创建 `app/api/users.py` 用户路由**

```python
"""用户路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.user_service import UserService
from app.schemas.user import UserUpdate, UserResponse
from app.core.response import ApiResponse

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return ApiResponse.success(data=UserResponse.model_validate(current_user))


@router.put("/me", response_model=ApiResponse[UserResponse])
async def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户信息"""
    service = UserService(db)
    updated = await service.update(current_user.id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=UserResponse.model_validate(updated), message="更新成功")
```

- [ ] **Step 4: 编写认证测试 `tests/test_auth.py`**

```python
"""认证 API 测试"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_register_validation_error():
    """测试注册参数校验"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 缺少必填字段
        response = await client.post("/api/auth/register", json={"username": "ab"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_fields():
    """测试登录缺少字段"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"account": ""})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_protected_endpoint_without_token():
    """测试未认证访问受保护接口"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me")
        assert response.status_code == 401
```

- [ ] **Step 5: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/api/__init__.py backend/app/api/auth.py backend/app/api/users.py backend/tests/test_auth.py
git commit -m "feat(backend): 实现认证与用户 API 路由"
```

---

## Task 9: API 路由 - 项目、角色、剧本、分镜、音频、渲染、工作流

**Files:**
- Create: `c:\漫剧软件项目\backend\app\api\projects.py`
- Create: `c:\漫剧软件项目\backend\app\api\characters.py`
- Create: `c:\漫剧软件项目\backend\app\api\scripts.py`
- Create: `c:\漫剧软件项目\backend\app\api\storyboards.py`
- Create: `c:\漫剧软件项目\backend\app\api\audio.py`
- Create: `c:\漫剧软件项目\backend\app\api\render.py`
- Create: `c:\漫剧软件项目\backend\app\api\workflows.py`
- Create: `c:\漫剧软件项目\backend\app\api\router.py`

- [ ] **Step 1: 创建 `app/api/projects.py` 项目路由**

```python
"""项目路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.project_service import ProjectService
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.response import ApiResponse, PaginatedResponse, PaginatedData

router = APIRouter(prefix="/projects", tags=["项目"])


@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的项目列表"""
    service = ProjectService(db)
    skip = (page - 1) * page_size
    items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
    total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[ProjectResponse])
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建项目"""
    service = ProjectService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    project = await service.create(data)
    return ApiResponse.success(data=ProjectResponse.model_validate(project), message="创建成功")


@router.get("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ApiResponse.success(data=ProjectResponse.model_validate(project))


@router.put("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新项目"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    updated = await service.update(project_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=ProjectResponse.model_validate(updated), message="更新成功")


@router.delete("/{project_id}", response_model=ApiResponse)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除项目（软删除）"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    await service.delete(project_id, soft=True)
    return ApiResponse.success(message="删除成功")
```

- [ ] **Step 2: 创建 `app/api/characters.py` 角色路由**

```python
"""角色路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.character_service import CharacterService
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterResponse
from app.core.response import ApiResponse, PaginatedResponse, PaginatedData

router = APIRouter(prefix="/characters", tags=["角色"])


@router.get("", response_model=PaginatedResponse[CharacterResponse])
async def list_characters(
    project_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    service = CharacterService(db)
    if project_id:
        items = await service.list_by_project(project_id)
        total = len(items)
    else:
        skip = (page - 1) * page_size
        items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
        total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[CharacterResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[CharacterResponse])
async def create_character(
    payload: CharacterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建角色"""
    service = CharacterService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    character = await service.create(data)
    return ApiResponse.success(data=CharacterResponse.model_validate(character), message="创建成功")


@router.get("/{character_id}", response_model=ApiResponse[CharacterResponse])
async def get_character(
    character_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    return ApiResponse.success(data=CharacterResponse.model_validate(character))


@router.put("/{character_id}", response_model=ApiResponse[CharacterResponse])
async def update_character(
    character_id: UUID,
    payload: CharacterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    updated = await service.update(character_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=CharacterResponse.model_validate(updated), message="更新成功")


@router.delete("/{character_id}", response_model=ApiResponse)
async def delete_character(
    character_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    await service.delete(character_id, soft=True)
    return ApiResponse.success(message="删除成功")
```

- [ ] **Step 3: 创建 `app/api/scripts.py` 剧本路由**

```python
"""剧本路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.script_service import ScriptService, SceneService, DialogueService
from app.schemas.script import (
    ScriptCreate, ScriptUpdate, ScriptResponse,
    SceneCreate, SceneResponse,
    DialogueCreate, DialogueResponse,
)
from app.core.response import ApiResponse

router = APIRouter(prefix="/scripts", tags=["剧本"])


# === 剧本 CRUD ===
@router.post("", response_model=ApiResponse[ScriptResponse])
async def create_script(
    payload: ScriptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    script = await service.create(data)
    return ApiResponse.success(data=ScriptResponse.model_validate(script), message="创建成功")


@router.get("/{script_id}", response_model=ApiResponse[ScriptResponse])
async def get_script(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    script = await service.get_by_id(script_id)
    if not script or script.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return ApiResponse.success(data=ScriptResponse.model_validate(script))


@router.put("/{script_id}", response_model=ApiResponse[ScriptResponse])
async def update_script(
    script_id: UUID,
    payload: ScriptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    script = await service.get_by_id(script_id)
    if not script or script.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="剧本不存在")
    updated = await service.update(script_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=ScriptResponse.model_validate(updated), message="更新成功")


# === 场景 ===
@router.post("/scenes", response_model=ApiResponse[SceneResponse])
async def create_scene(
    payload: SceneCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SceneService(db)
    scene = await service.create(payload.model_dump())
    return ApiResponse.success(data=SceneResponse.model_validate(scene), message="创建成功")


@router.get("/{script_id}/scenes", response_model=ApiResponse[list[SceneResponse]])
async def list_scenes(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SceneService(db)
    items = await service.list_by_script(script_id)
    return ApiResponse.success(data=[SceneResponse.model_validate(s) for s in items])


# === 对话 ===
@router.post("/dialogues", response_model=ApiResponse[DialogueResponse])
async def create_dialogue(
    payload: DialogueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DialogueService(db)
    dialogue = await service.create(payload.model_dump())
    return ApiResponse.success(data=DialogueResponse.model_validate(dialogue), message="创建成功")
```

- [ ] **Step 4: 创建 `app/api/storyboards.py` 分镜路由**

```python
"""分镜路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.storyboard_service import StoryboardService
from app.schemas.storyboard import (
    StoryboardFrameCreate, StoryboardFrameUpdate, StoryboardFrameResponse,
)
from app.core.response import ApiResponse

router = APIRouter(prefix="/storyboards", tags=["分镜"])


@router.post("", response_model=ApiResponse[StoryboardFrameResponse])
async def create_frame(
    payload: StoryboardFrameCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    frame = await service.create(payload.model_dump())
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(frame), message="创建成功")


@router.get("/{frame_id}", response_model=ApiResponse[StoryboardFrameResponse])
async def get_frame(
    frame_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    frame = await service.get_by_id(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(frame))


@router.put("/{frame_id}", response_model=ApiResponse[StoryboardFrameResponse])
async def update_frame(
    frame_id: UUID,
    payload: StoryboardFrameUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    updated = await service.update(frame_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(updated), message="更新成功")


@router.get("/by-script/{script_id}", response_model=ApiResponse[list[StoryboardFrameResponse]])
async def list_frames_by_script(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    items = await service.list_by_script(script_id)
    return ApiResponse.success(data=[StoryboardFrameResponse.model_validate(f) for f in items])
```

- [ ] **Step 5: 创建 `app/api/audio.py` 音频路由**

```python
"""音频路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.audio_service import VoiceProfileService, AudioTrackService
from app.schemas.audio import (
    VoiceProfileCreate, VoiceProfileResponse,
    AudioTrackCreate, AudioTrackResponse,
)
from app.core.response import ApiResponse

router = APIRouter(prefix="/audio", tags=["音频"])


# === 音色配置 ===
@router.get("/voices", response_model=ApiResponse[list[VoiceProfileResponse]])
async def list_voice_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceProfileService(db)
    items = await service.list_by_user(current_user.id)
    return ApiResponse.success(data=[VoiceProfileResponse.model_validate(v) for v in items])


@router.post("/voices", response_model=ApiResponse[VoiceProfileResponse])
async def create_voice_profile(
    payload: VoiceProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceProfileService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    voice = await service.create(data)
    return ApiResponse.success(data=VoiceProfileResponse.model_validate(voice), message="创建成功")


# === 音频轨道 ===
@router.get("/tracks/{project_id}", response_model=ApiResponse[list[AudioTrackResponse]])
async def list_tracks(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioTrackService(db)
    items = await service.list_by_project(project_id)
    return ApiResponse.success(data=[AudioTrackResponse.model_validate(t) for t in items])


@router.post("/tracks", response_model=ApiResponse[AudioTrackResponse])
async def create_track(
    payload: AudioTrackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioTrackService(db)
    track = await service.create(payload.model_dump())
    return ApiResponse.success(data=AudioTrackResponse.model_validate(track), message="创建成功")
```

- [ ] **Step 6: 创建 `app/api/render.py` 渲染路由**

```python
"""渲染路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.render_service import RenderService
from app.schemas.render import RenderTaskCreate, RenderTaskResponse
from app.core.response import ApiResponse

router = APIRouter(prefix="/render", tags=["渲染"])


@router.post("", response_model=ApiResponse[RenderTaskResponse])
async def create_render_task(
    payload: RenderTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建渲染任务 (实际执行在后续 AI 引擎阶段实现)"""
    service = RenderService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    data["status"] = "pending"
    task = await service.create(data)
    return ApiResponse.success(data=RenderTaskResponse.model_validate(task), message="渲染任务已创建")


@router.get("/{task_id}", response_model=ApiResponse[RenderTaskResponse])
async def get_render_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RenderService(db)
    task = await service.get_by_id(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return ApiResponse.success(data=RenderTaskResponse.model_validate(task))


@router.get("", response_model=ApiResponse[list[RenderTaskResponse]])
async def list_render_tasks(
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RenderService(db)
    if project_id:
        items = await service.list_by_project(project_id)
    else:
        items = await service.list_by_user(current_user.id)
    return ApiResponse.success(data=[RenderTaskResponse.model_validate(t) for t in items])
```

- [ ] **Step 7: 创建 `app/api/workflows.py` 工作流路由**

```python
"""工作流路由"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.workflow_service import WorkflowService
from app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    WorkflowExecutionCreate, WorkflowExecutionResponse,
)
from app.core.response import ApiResponse, PaginatedResponse, PaginatedData

router = APIRouter(prefix="/workflows", tags=["工作流"])


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    skip = (page - 1) * page_size
    items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
    total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[WorkflowResponse.model_validate(w) for w in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[WorkflowResponse])
async def create_workflow(
    payload: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    workflow = await service.create(data)
    return ApiResponse.success(data=WorkflowResponse.model_validate(workflow), message="创建成功")


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def get_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return ApiResponse.success(data=WorkflowResponse.model_validate(workflow))


@router.put("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    updated = await service.update(workflow_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=WorkflowResponse.model_validate(updated), message="更新成功")


@router.delete("/{workflow_id}", response_model=ApiResponse)
async def delete_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    await service.delete(workflow_id, soft=True)
    return ApiResponse.success(message="删除成功")
```

- [ ] **Step 8: 创建 `app/api/router.py` 路由聚合**

```python
"""路由聚合 - 注册所有 API 路由"""
from fastapi import APIRouter
from app.api import auth, users, projects, characters, scripts, storyboards, audio, render, workflows

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(characters.router)
api_router.include_router(scripts.router)
api_router.include_router(storyboards.router)
api_router.include_router(audio.router)
api_router.include_router(render.router)
api_router.include_router(workflows.router)
```

- [ ] **Step 9: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/api/
git commit -m "feat(backend): 实现全部业务 API 路由 (9个模块)"
```

---

## Task 10: FastAPI 主应用与 Alembic 迁移

**Files:**
- Create: `c:\漫剧软件项目\backend\app\main.py`
- Create: `c:\漫剧软件项目\backend\alembic.ini`
- Create: `c:\漫剧软件项目\backend\alembic\env.py`
- Create: `c:\漫剧软件项目\backend\alembic\script.py.mako`
- Create: `c:\漫剧软件项目\backend\tests\conftest.py`
- Create: `c:\漫剧软件项目\backend\tests\test_health.py`

- [ ] **Step 1: 创建 `app/main.py` FastAPI 入口**

```python
"""ComicStudio AI - FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.response import ApiResponse
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"启动 {settings.app_name} ({settings.app_env})")
    # 开发环境自动建表
    if settings.is_development:
        try:
            await init_db()
            logger.info("数据库表已就绪")
        except Exception as e:
            logger.warning(f"数据库初始化失败 (请确保 PostgreSQL 已启动): {e}")
    yield
    logger.info("关闭数据库连接")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="商业化漫剧生成软件 - 后端 API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ApiResponse.error(message="服务器内部错误", code=-1).model_dump(),
    )


# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return ApiResponse.success(data={"status": "ok", "version": "0.1.0"})


@app.get("/", tags=["系统"])
async def root():
    """根路径"""
    return ApiResponse.success(
        data={"name": settings.app_name, "docs": "/docs"},
        message=f"欢迎使用 {settings.app_name}",
    )


# 注册路由
app.include_router(api_router)
```

- [ ] **Step 2: 创建 `alembic.ini`**

```ini
# Alembic 配置
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: 创建 `alembic/env.py`**

```python
"""Alembic 迁移环境"""
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.models import Base  # 导入所有模型以注册到 metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: 创建 `alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: 创建 `tests/conftest.py` 测试配置**

```python
"""测试配置"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def db_session() -> AsyncSession:
    """数据库会话 fixture (用于集成测试)"""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 6: 创建 `tests/test_health.py` 健康检查测试**

```python
"""健康检查测试"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_check():
    """测试健康检查端点"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_root():
    """测试根路径"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "ComicStudio" in data["data"]["name"]


@pytest.mark.asyncio
async def test_openapi_docs():
    """测试 OpenAPI 文档可访问"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert "/api/auth/login" in data["paths"]
    assert "/api/projects" in data["paths"]
```

- [ ] **Step 7: 运行测试验证**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 所有测试通过（健康检查 + OpenAPI + 配置 + 模型 + 安全 + 认证校验）

- [ ] **Step 8: 提交**

```bash
cd "c:\漫剧软件项目"
git add backend/app/main.py backend/alembic.ini backend/alembic/ backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): 完成 FastAPI 主应用 + Alembic 迁移配置 + 测试"
```

---

## Task 11: 前端项目初始化与依赖配置

**Files:**
- Create: `c:\漫剧软件项目\frontend\package.json`
- Create: `c:\漫剧软件项目\frontend\tsconfig.json`
- Create: `c:\漫剧软件项目\frontend\tsconfig.node.json`
- Create: `c:\漫剧软件项目\frontend\vite.config.ts`
- Create: `c:\漫剧软件项目\frontend\tailwind.config.js`
- Create: `c:\漫剧软件项目\frontend\postcss.config.js`
- Create: `c:\漫剧软件项目\frontend\index.html`
- Create: `c:\漫剧软件项目\frontend\src\vite-env.d.ts`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "comic-studio-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.3",
    "@tanstack/react-query": "^5.17.9",
    "zustand": "^4.4.7",
    "immer": "^10.0.3",
    "axios": "^1.6.5",
    "reactflow": "^12.3.5",
    "antd": "^5.12.8",
    "@ant-design/icons": "^5.2.6",
    "dayjs": "^1.11.10",
    "lodash-es": "^4.17.21"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@types/lodash-es": "^4.17.12",
    "@typescript-eslint/eslint-plugin": "^6.19.0",
    "@typescript-eslint/parser": "^6.19.0",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.56.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.12"
  }
}
```

- [ ] **Step 2: 创建 `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: 创建 `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: 创建 `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

- [ ] **Step 5: 创建 `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // TRAE 风格配色
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        sidebar: {
          bg: '#1e1e2e',
          hover: '#2a2a3e',
          active: '#3b3f54',
          text: '#cdd6f4',
        },
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 6: 创建 `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 7: 创建 `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ComicStudio AI - 漫剧生成软件</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: 创建 `frontend/src/vite-env.d.ts`**

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

- [ ] **Step 9: 提交**

```bash
cd "c:\漫剧软件项目"
git add frontend/package.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/tailwind.config.js frontend/postcss.config.js frontend/index.html frontend/src/vite-env.d.ts
git commit -m "feat(frontend): 初始化 Vite + React + TypeScript 项目配置"
```

---

## Task 12: 前端类型定义与 API 客户端

**Files:**
- Create: `c:\漫剧软件项目\frontend\src\types\index.ts`
- Create: `c:\漫剧软件项目\frontend\src\types\user.ts`
- Create: `c:\漫剧软件项目\frontend\src\types\project.ts`
- Create: `c:\漫剧软件项目\frontend\src\types\character.ts`
- Create: `c:\漫剧软件项目\frontend\src\types\workflow.ts`
- Create: `c:\漫剧软件项目\frontend\src\api\client.ts`
- Create: `c:\漫剧软件项目\frontend\src\api\auth.ts`
- Create: `c:\漫剧软件项目\frontend\src\api\projects.ts`
- Create: `c:\漫剧软件项目\frontend\src\api\characters.ts`
- Create: `c:\漫剧软件项目\frontend\src\api\workflows.ts`
- Create: `c:\漫剧软件项目\frontend\src\utils\token.ts`

- [ ] **Step 1: 创建类型定义 `src/types/user.ts`**

```typescript
export interface User {
  id: string
  username: string
  email: string
  avatar_url: string | null
  bio: string | null
  status: string
  plan: string
  credits: number
  preferences: Record<string, unknown>
  email_verified: boolean
  last_login_at: string | null
  created_at: string
}

export interface LoginRequest {
  account: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  timestamp: number
}

export interface PaginatedResponse<T> {
  code: number
  message: string
  data: {
    items: T[]
    total: number
    page: number
    page_size: number
  }
  timestamp: number
}
```

- [ ] **Step 2: 创建类型定义 `src/types/project.ts` 与 `src/types/character.ts`**

`src/types/project.ts`:
```typescript
export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  genre: string | null
  status: string
  config: {
    resolution?: string
    fps?: number
    style?: string
  }
  character_count: number
  scene_count: number
  frame_count: number
  is_shared: boolean
  collaborators: unknown[]
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  genre?: string
  config?: Partial<Project['config']>
}

export interface ProjectUpdate {
  name?: string
  description?: string
  genre?: string
  status?: string
  config?: Partial<Project['config']>
}
```

`src/types/character.ts`:
```typescript
export interface Character {
  id: string
  user_id: string
  project_id: string | null
  name: string
  description: string | null
  style: string
  gender: string | null
  age: string | null
  hair_color: string | null
  eye_color: string | null
  skin_tone: string | null
  body_type: string | null
  lora_model_path: string | null
  lora_training_status: string
  main_image_url: string | null
  reference_images: string[]
  tags: string[]
  usage_count: number
  created_at: string
}

export interface CharacterCreate {
  name: string
  description?: string
  style?: string
  gender?: string
  age?: string
  hair_color?: string
  eye_color?: string
  skin_tone?: string
  body_type?: string
  tags?: string[]
  project_id?: string
  reference_images?: string[]
}
```

- [ ] **Step 3: 创建类型定义 `src/types/workflow.ts`**

```typescript
export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

export interface Workflow {
  id: string
  user_id: string
  project_id: string | null
  name: string
  description: string | null
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  category: string
  is_template: boolean
  is_public: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface WorkflowCreate {
  name: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  category?: string
  project_id?: string
}

export interface WorkflowUpdate {
  name?: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  category?: string
  is_public?: boolean
}
```

- [ ] **Step 4: 创建类型统一导出 `src/types/index.ts`**

```typescript
export * from './user'
export * from './project'
export * from './character'
export * from './workflow'
```

- [ ] **Step 5: 创建 Token 工具 `src/utils/token.ts`**

```typescript
const ACCESS_TOKEN_KEY = 'comic_access_token'
const REFRESH_TOKEN_KEY = 'comic_refresh_token'

export const tokenStorage = {
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  },
  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },
  setTokens(access: string, refresh: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}
```

- [ ] **Step 6: 创建 API 客户端 `src/api/client.ts`**

```typescript
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { tokenStorage } from '@/utils/token'
import type { ApiResponse } from '@/types'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：附加 Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccessToken()
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiResponse<unknown>>) => {
    if (error.response) {
      const { status, data } = error.response
      // 401 未授权 - 清除 Token 并跳转登录
      if (status === 401) {
        tokenStorage.clear()
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
      const message = data?.message || '请求失败'
      return Promise.reject(new Error(message))
    }
    return Promise.reject(new Error('网络错误'))
  }
)
```

- [ ] **Step 7: 创建 `src/api/auth.ts`**

```typescript
import { apiClient } from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User, ApiResponse } from '@/types'

export const authApi = {
  login(data: LoginRequest) {
    return apiClient.post<ApiResponse<TokenResponse>>('/auth/login', data)
  },
  register(data: RegisterRequest) {
    return apiClient.post<ApiResponse<User>>('/auth/register', data)
  },
  getCurrentUser() {
    return apiClient.get<ApiResponse<User>>('/users/me')
  },
  updateCurrentUser(data: Partial<User>) {
    return apiClient.put<ApiResponse<User>>('/users/me', data)
  },
}
```

- [ ] **Step 8: 创建 `src/api/projects.ts`**

```typescript
import { apiClient } from './client'
import type { Project, ProjectCreate, ProjectUpdate, ApiResponse, PaginatedResponse } from '@/types'

export const projectApi = {
  list(page = 1, pageSize = 20) {
    return apiClient.get<PaginatedResponse<Project>>('/projects', {
      params: { page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Project>>(`/projects/${id}`)
  },
  create(data: ProjectCreate) {
    return apiClient.post<ApiResponse<Project>>('/projects', data)
  },
  update(id: string, data: ProjectUpdate) {
    return apiClient.put<ApiResponse<Project>>(`/projects/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/projects/${id}`)
  },
}
```

- [ ] **Step 9: 创建 `src/api/characters.ts` 与 `src/api/workflows.ts`**

`src/api/characters.ts`:
```typescript
import { apiClient } from './client'
import type { Character, CharacterCreate, ApiResponse, PaginatedResponse } from '@/types'

export const characterApi = {
  list(projectId?: string, page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<Character>>('/characters', {
      params: { project_id: projectId, page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Character>>(`/characters/${id}`)
  },
  create(data: CharacterCreate) {
    return apiClient.post<ApiResponse<Character>>('/characters', data)
  },
  update(id: string, data: Partial<Character>) {
    return apiClient.put<ApiResponse<Character>>(`/characters/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/characters/${id}`)
  },
}
```

`src/api/workflows.ts`:
```typescript
import { apiClient } from './client'
import type { Workflow, WorkflowCreate, WorkflowUpdate, ApiResponse, PaginatedResponse } from '@/types'

export const workflowApi = {
  list(page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<Workflow>>('/workflows', {
      params: { page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Workflow>>(`/workflows/${id}`)
  },
  create(data: WorkflowCreate) {
    return apiClient.post<ApiResponse<Workflow>>('/workflows', data)
  },
  update(id: string, data: WorkflowUpdate) {
    return apiClient.put<ApiResponse<Workflow>>(`/workflows/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/workflows/${id}`)
  },
}
```

- [ ] **Step 10: 提交**

```bash
cd "c:\漫剧软件项目"
git add frontend/src/types/ frontend/src/utils/ frontend/src/api/
git commit -m "feat(frontend): 添加类型定义、Token 工具与 API 客户端"
```

---

## Task 13: Zustand 状态管理与路由

**Files:**
- Create: `c:\漫剧软件项目\frontend\src\stores\authStore.ts`
- Create: `c:\漫剧软件项目\frontend\src\stores\editorStore.ts`
- Create: `c:\漫剧软件项目\frontend\src\components\common\ProtectedRoute.tsx`
- Create: `c:\漫剧软件项目\frontend\src\routes\index.tsx`

- [ ] **Step 1: 创建 `src/stores/authStore.ts`**

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { tokenStorage } from '@/utils/token'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
        }),
      logout: () => {
        tokenStorage.clear()
        set({ user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'comic-auth',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
```

- [ ] **Step 2: 创建 `src/stores/editorStore.ts`**

```typescript
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type { WorkflowNode, WorkflowEdge } from '@/types'

interface EditorState {
  selectedNodeId: string | null
  isPlaying: boolean
  currentFrame: number
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  selectNode: (id: string | null) => void
  setNodes: (nodes: WorkflowNode[]) => void
  setEdges: (edges: WorkflowEdge[]) => void
  addNode: (node: WorkflowNode) => void
  removeNode: (id: string) => void
  play: () => void
  pause: () => void
  setFrame: (frame: number) => void
}

export const useEditorStore = create<EditorState>()(
  immer((set) => ({
    selectedNodeId: null,
    isPlaying: false,
    currentFrame: 0,
    nodes: [],
    edges: [],
    selectNode: (id) =>
      set((state) => {
        state.selectedNodeId = id
      }),
    setNodes: (nodes) =>
      set((state) => {
        state.nodes = nodes
      }),
    setEdges: (edges) =>
      set((state) => {
        state.edges = edges
      }),
    addNode: (node) =>
      set((state) => {
        state.nodes.push(node)
      }),
    removeNode: (id) =>
      set((state) => {
        state.nodes = state.nodes.filter((n) => n.id !== id)
        state.edges = state.edges.filter((e) => e.source !== id && e.target !== id)
      }),
    play: () =>
      set((state) => {
        state.isPlaying = true
      }),
    pause: () =>
      set((state) => {
        state.isPlaying = false
      }),
    setFrame: (frame) =>
      set((state) => {
        state.currentFrame = frame
      }),
  }))
)
```

- [ ] **Step 3: 创建 `src/components/common/ProtectedRoute.tsx`**

```typescript
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { tokenStorage } from '@/utils/token'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()
  const token = tokenStorage.getAccessToken()

  if (!isAuthenticated || !token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
```

- [ ] **Step 4: 创建 `src/routes/index.tsx`**

```typescript
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import ProtectedRoute from '@/components/common/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectListPage = lazy(() => import('@/pages/ProjectListPage'))
const ProjectEditorPage = lazy(() => import('@/pages/ProjectEditorPage'))

const Loading = () => (
  <div className="flex items-center justify-center h-screen">
    <Spin size="large" />
  </div>
)

export default function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectListPage />} />
          <Route path="/projects/:projectId" element={<ProjectEditorPage />} />
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  )
}
```

- [ ] **Step 5: 提交**

```bash
cd "c:\漫剧软件项目"
git add frontend/src/stores/ frontend/src/components/common/ frontend/src/routes/
git commit -m "feat(frontend): 添加 Zustand 状态管理、路由守卫与路由配置"
```

---

## Task 14: TRAE 风格布局与登录页

**Files:**
- Create: `c:\漫剧软件项目\frontend\src\styles\global.css`
- Create: `c:\漫剧软件项目\frontend\src\components\layout\MainLayout.tsx`
- Create: `c:\漫剧软件项目\frontend\src\components\layout\Sidebar.tsx`
- Create: `c:\漫剧软件项目\frontend\src\components\layout\TopBar.tsx`
- Create: `c:\漫剧软件项目\frontend\src\pages\LoginPage.tsx`
- Create: `c:\漫剧软件项目\frontend\src\pages\RegisterPage.tsx`

- [ ] **Step 1: 创建 `src/styles/global.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#root {
  height: 100%;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 滚动条样式 (TRAE 风格) */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

/* React Flow 节点样式 */
.react-flow__node {
  font-size: 12px;
}
```

- [ ] **Step 2: 创建 `src/components/layout/MainLayout.tsx`**

```typescript
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

export default function MainLayout() {
  return (
    <div className="flex h-screen bg-[#1e1e2e] text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto bg-[#181825]">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 创建 `src/components/layout/Sidebar.tsx`**

```typescript
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined,
  ProjectOutlined,
  TeamOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Tooltip } from 'antd'

const navItems = [
  { path: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { path: '/projects', icon: <ProjectOutlined />, label: '项目' },
  { path: '/characters', icon: <TeamOutlined />, label: '角色库' },
  { path: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside className="w-16 bg-[#11111b] flex flex-col items-center py-4 gap-2 border-r border-[#313244]">
      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold mb-4">
        C
      </div>
      {navItems.map((item) => {
        const isActive = location.pathname.startsWith(item.path)
        return (
          <Tooltip key={item.path} title={item.label} placement="right">
            <button
              onClick={() => navigate(item.path)}
              className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg transition-colors ${
                isActive
                  ? 'bg-[#3b3f54] text-white'
                  : 'text-gray-400 hover:bg-[#2a2a3e] hover:text-white'
              }`}
            >
              {item.icon}
            </button>
          </Tooltip>
        )
      })}
    </aside>
  )
}
```

- [ ] **Step 4: 创建 `src/components/layout/TopBar.tsx`**

```typescript
import { Avatar, Dropdown, Space, Typography } from 'antd'
import { UserOutlined, LogoutOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

export default function TopBar() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-14 bg-[#1e1e2e] border-b border-[#313244] flex items-center justify-between px-6">
      <Typography.Title level={5} className="!text-white !mb-0">
        ComicStudio AI
      </Typography.Title>
      <Dropdown
        menu={{
          items: [
            {
              key: 'logout',
              icon: <LogoutOutlined />,
              label: '退出登录',
              onClick: handleLogout,
            },
          ],
        }}
        placement="bottomRight"
      >
        <Space className="cursor-pointer">
          <Avatar icon={<UserOutlined />} src={user?.avatar_url || undefined} />
          <span className="text-white">{user?.username}</span>
        </Space>
      </Dropdown>
    </header>
  )
}
```

- [ ] **Step 5: 创建 `src/pages/LoginPage.tsx`**

```typescript
import { useState } from 'react'
import { Form, Input, Button, Card, Typography, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { tokenStorage } from '@/utils/token'
import { useAuthStore } from '@/stores/authStore'
import type { LoginRequest } from '@/types'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)

  const onFinish = async (values: LoginRequest) => {
    setLoading(true)
    try {
      const res = await authApi.login(values)
      const { access_token, refresh_token, user } = res.data.data
      tokenStorage.setTokens(access_token, refresh_token)
      setUser(user)
      message.success('登录成功')
      navigate('/dashboard')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e1e2e] to-[#11111b]">
      <Card className="w-96 !bg-[#1e1e2e] !border-[#313244]">
        <div className="text-center mb-6">
          <div className="w-16 h-16 mx-auto rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-2xl mb-3">
            C
          </div>
          <Typography.Title level={3} className="!text-white !mb-0">
            ComicStudio AI
          </Typography.Title>
          <Typography.Text className="!text-gray-400">登录您的账户</Typography.Text>
        </div>
        <Form onFinish={onFinish} size="large">
          <Form.Item name="account" rules={[{ required: true, message: '请输入用户名或邮箱' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名或邮箱" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
          <div className="text-center">
            <Link to="/register" className="!text-blue-400">
              还没有账户？立即注册
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
```

- [ ] **Step 6: 创建 `src/pages/RegisterPage.tsx`**

```typescript
import { useState } from 'react'
import { Form, Input, Button, Card, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '@/api/auth'
import type { RegisterRequest } from '@/types'

export default function RegisterPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onFinish = async (values: RegisterRequest) => {
    setLoading(true)
    try {
      await authApi.register(values)
      message.success('注册成功，请登录')
      navigate('/login')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e1e2e] to-[#11111b]">
      <Card className="w-96 !bg-[#1e1e2e] !border-[#313244]">
        <div className="text-center mb-6">
          <Typography.Title level={3} className="!text-white !mb-0">
            创建账户
          </Typography.Title>
          <Typography.Text className="!text-gray-400">开始您的漫剧创作之旅</Typography.Text>
        </div>
        <Form onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, min: 3, message: '用户名至少 3 个字符' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="email" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input prefix={<MailOutlined />} placeholder="邮箱" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, min: 6, message: '密码至少 6 位' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              注册
            </Button>
          </Form.Item>
          <div className="text-center">
            <Link to="/login" className="!text-blue-400">
              已有账户？返回登录
            </Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
```

- [ ] **Step 7: 提交**

```bash
cd "c:\漫剧软件项目"
git add frontend/src/styles/ frontend/src/components/layout/ frontend/src/pages/LoginPage.tsx frontend/src/pages/RegisterPage.tsx
git commit -m "feat(frontend): 实现 TRAE 风格布局与登录/注册页"
```

---

## Task 15: 仪表盘、项目列表与 React Flow 编辑器

**Files:**
- Create: `c:\漫剧软件项目\frontend\src\pages\DashboardPage.tsx`
- Create: `c:\漫剧软件项目\frontend\src\pages\ProjectListPage.tsx`
- Create: `c:\漫剧软件项目\frontend\src\pages\ProjectEditorPage.tsx`
- Create: `c:\漫剧软件项目\frontend\src\components\workflow\WorkflowEditor.tsx`
- Create: `c:\漫剧软件项目\frontend\src\components\workflow\nodes\ImageGenNode.tsx`
- Create: `c:\漫剧软件项目\frontend\src\components\workflow\nodes\CharacterNode.tsx`
- Create: `c:\漫剧软件项目\frontend\src\hooks\useProjects.ts`
- Create: `c:\漫剧软件项目\frontend\src\hooks\useCharacters.ts`
- Create: `c:\漫剧软件项目\frontend\src\main.tsx`
- Create: `c:\漫剧软件项目\frontend\src\App.tsx`

- [ ] **Step 1: 创建 `src/hooks/useProjects.ts`**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectApi } from '@/api/projects'
import type { ProjectCreate } from '@/types'

export function useProjects(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['projects', page, pageSize],
    queryFn: async () => {
      const res = await projectApi.list(page, pageSize)
      return res.data.data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: ProjectCreate) => {
      const res = await projectApi.create(data)
      return res.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await projectApi.delete(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
```

- [ ] **Step 2: 创建 `src/hooks/useCharacters.ts`**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { characterApi } from '@/api/characters'
import type { CharacterCreate } from '@/types'

export function useCharacters(projectId?: string) {
  return useQuery({
    queryKey: ['characters', projectId],
    queryFn: async () => {
      const res = await characterApi.list(projectId)
      return res.data.data
    },
    enabled: true,
  })
}

export function useCreateCharacter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: CharacterCreate) => {
      const res = await characterApi.create(data)
      return res.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters'] })
    },
  })
}
```

- [ ] **Step 3: 创建 `src/components/workflow/nodes/ImageGenNode.tsx`**

```typescript
import { Handle, Position } from 'reactflow'
import { PictureOutlined } from '@ant-design/icons'

interface ImageGenNodeData {
  label?: string
  model?: string
  prompt?: string
}

export default function ImageGenNode({ data }: { data: ImageGenNodeData }) {
  return (
    <div className="bg-[#2a2a3e] border border-[#313244] rounded-lg p-3 w-56 text-white">
      <Handle type="target" position={Position.Left} className="!bg-blue-500" />
      <div className="flex items-center gap-2 mb-2">
        <PictureOutlined className="text-blue-400" />
        <span className="font-semibold text-sm">{data.label || '图像生成'}</span>
      </div>
      <div className="text-xs text-gray-400 mb-1">模型: {data.model || 'SDXL'}</div>
      <div className="text-xs text-gray-300 truncate">
        {data.prompt || '请输入提示词...'}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-green-500" />
    </div>
  )
}
```

- [ ] **Step 4: 创建 `src/components/workflow/nodes/CharacterNode.tsx`**

```typescript
import { Handle, Position } from 'reactflow'
import { UserOutlined } from '@ant-design/icons'

interface CharacterNodeData {
  label?: string
  name?: string
  style?: string
}

export default function CharacterNode({ data }: { data: CharacterNodeData }) {
  return (
    <div className="bg-[#2a2a3e] border border-[#313244] rounded-lg p-3 w-48 text-white">
      <Handle type="source" position={Position.Right} className="!bg-purple-500" />
      <div className="flex items-center gap-2 mb-2">
        <UserOutlined className="text-purple-400" />
        <span className="font-semibold text-sm">{data.label || '角色'}</span>
      </div>
      <div className="text-xs text-gray-400">名称: {data.name || '未命名'}</div>
      <div className="text-xs text-gray-400">风格: {data.style || 'anime'}</div>
    </div>
  )
}
```

- [ ] **Step 5: 创建 `src/components/workflow/WorkflowEditor.tsx`**

```typescript
import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type NodeTypes,
} from 'reactflow'
import 'reactflow/dist/style.css'
import ImageGenNode from './nodes/ImageGenNode'
import CharacterNode from './nodes/CharacterNode'
import { useEditorStore } from '@/stores/editorStore'

const nodeTypes: NodeTypes = {
  imageGen: ImageGenNode,
  character: CharacterNode,
}

const defaultEdgeOptions = {
  style: { stroke: '#6366f1', strokeWidth: 2 },
  animated: true,
}

export default function WorkflowEditor() {
  const { nodes, edges, setNodes, setEdges } = useEditorStore()

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      const updated = applyNodeChanges(changes, nodes as Node[])
      setNodes(updated)
    },
    [nodes, setNodes]
  )

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      const updated = applyEdgeChanges(changes, edges as Edge[])
      setEdges(updated)
    },
    [edges, setEdges]
  )

  const onConnect: OnConnect = useCallback(
    (connection) => {
      const updated = addEdge({ ...connection, ...defaultEdgeOptions }, edges as Edge[])
      setEdges(updated)
    },
    [edges, setEdges]
  )

  const minimapStyle = useMemo(() => ({ backgroundColor: '#1e1e2e' }), [])

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        className="bg-[#181825]"
      >
        <Background color="#313244" gap={16} />
        <Controls className="!bg-[#2a2a3e] !border-[#313244]" />
        <MiniMap style={minimapStyle} nodeColor="#6366f1" maskColor="rgba(0,0,0,0.5)" />
      </ReactFlow>
    </div>
  )
}
```

- [ ] **Step 6: 创建 `src/pages/DashboardPage.tsx`**

```typescript
import { Card, Col, Row, Statistic, Typography } from 'antd'
import { ProjectOutlined, TeamOutlined, FileTextOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const stats = [
    { title: '项目数', value: 0, icon: <ProjectOutlined />, color: '#3b82f6' },
    { title: '角色数', value: 0, icon: <TeamOutlined />, color: '#8b5cf6' },
    { title: '剧本数', value: 0, icon: <FileTextOutlined />, color: '#10b981' },
    { title: '渲染任务', value: 0, icon: <VideoCameraOutlined />, color: '#f59e0b' },
  ]

  return (
    <div className="p-6">
      <Typography.Title level={3} className="!text-white !mb-6">
        欢迎回来，{user?.username} 👋
      </Typography.Title>
      <Row gutter={[16, 16]}>
        {stats.map((s) => (
          <Col xs={12} sm={12} md={6} key={s.title}>
            <Card className="!bg-[#1e1e2e] !border-[#313244]">
              <Statistic
                title={<span className="!text-gray-400">{s.title}</span>}
                value={s.value}
                prefix={<span style={{ color: s.color }}>{s.icon}</span>}
                valueStyle={{ color: '#fff' }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card
        title={<span className="!text-white">快速开始</span>}
        className="!bg-[#1e1e2e] !border-[#313244] mt-6"
      >
        <Row gutter={[16, 16]}>
          <Col span={8}>
            <Card
              hoverable
              className="!bg-[#2a2a3e] !border-[#313244] text-center"
              onClick={() => navigate('/projects')}
            >
              <ProjectOutlined style={{ fontSize: 32, color: '#3b82f6' }} />
              <Typography.Text className="!text-white block mt-2">新建项目</Typography.Text>
            </Card>
          </Col>
          <Col span={8}>
            <Card hoverable className="!bg-[#2a2a3e] !border-[#313244] text-center">
              <TeamOutlined style={{ fontSize: 32, color: '#8b5cf6' }} />
              <Typography.Text className="!text-white block mt-2">创建角色</Typography.Text>
            </Card>
          </Col>
          <Col span={8}>
            <Card hoverable className="!bg-[#2a2a3e] !border-[#313244] text-center">
              <FileTextOutlined style={{ fontSize: 32, color: '#10b981' }} />
              <Typography.Text className="!text-white block mt-2">编写剧本</Typography.Text>
            </Card>
          </Col>
        </Row>
      </Card>
    </div>
  )
}
```

- [ ] **Step 7: 创建 `src/pages/ProjectListPage.tsx`**

```typescript
import { useState } from 'react'
import { Card, Row, Col, Button, Modal, Form, Input, Select, Empty, Spin, message } from 'antd'
import { PlusOutlined, ProjectOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useProjects, useCreateProject } from '@/hooks/useProjects'

export default function ProjectListPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useProjects()
  const createMutation = useCreateProject()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      const project = await createMutation.mutateAsync(values)
      message.success('创建成功')
      setModalOpen(false)
      form.resetFields()
      navigate(`/projects/${project.id}`)
    } catch (e) {
      // 校验错误已处理
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-white text-xl">我的项目</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建项目
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      ) : !data?.items?.length ? (
        <Empty
          description={<span className="text-gray-400">暂无项目，点击右上角创建</span>}
          className="py-20"
        />
      ) : (
        <Row gutter={[16, 16]}>
          {data.items.map((p) => (
            <Col xs={24} sm={12} md={8} lg={6} key={p.id}>
              <Card
                hoverable
                className="!bg-[#1e1e2e] !border-[#313244]"
                onClick={() => navigate(`/projects/${p.id}`)}
              >
                <div className="flex items-center gap-3">
                  <ProjectOutlined className="text-blue-400 text-2xl" />
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-medium truncate">{p.name}</div>
                    <div className="text-gray-400 text-xs truncate">
                      {p.description || '暂无描述'}
                    </div>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="新建项目"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="项目名称" rules={[{ required: true }]}>
            <Input placeholder="输入项目名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="项目描述" rows={3} />
          </Form.Item>
          <Form.Item name="genre" label="类型">
            <Select
              placeholder="选择类型"
              options={[
                { value: 'romance', label: '言情' },
                { value: 'action', label: '动作' },
                { value: 'mystery', label: '悬疑' },
                { value: 'comedy', label: '喜剧' },
                { value: 'drama', label: '剧情' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 8: 创建 `src/pages/ProjectEditorPage.tsx`**

```typescript
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Typography, message } from 'antd'
import { ArrowLeftOutlined, PlayCircleOutlined, SaveOutlined } from '@ant-design/icons'
import WorkflowEditor from '@/components/workflow/WorkflowEditor'
import { useEditorStore } from '@/stores/editorStore'

export default function ProjectEditorPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { nodes, edges } = useEditorStore()

  const handleSave = () => {
    message.success(`已保存工作流 (${nodes.length} 节点, ${edges.length} 连线)`)
  }

  const handleRun = () => {
    message.info('工作流执行功能将在 AI 引擎阶段实现')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e2e] border-b border-[#313244]">
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/projects')}
            className="!text-white"
          />
          <Typography.Text className="!text-white">
            项目: {projectId}
          </Typography.Text>
        </Space>
        <Space>
          <Button icon={<SaveOutlined />} onClick={handleSave} className="!text-white">
            保存
          </Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun}>
            运行
          </Button>
        </Space>
      </div>
      <div className="flex-1">
        <WorkflowEditor />
      </div>
    </div>
  )
}
```

- [ ] **Step 9: 创建 `src/App.tsx`**

```typescript
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppRoutes from '@/routes'
import '@/styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#3b82f6',
          borderRadius: 6,
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  )
}
```

- [ ] **Step 10: 创建 `src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 11: 提交**

```bash
cd "c:\漫剧软件项目"
git add frontend/src/pages/ frontend/src/components/workflow/ frontend/src/hooks/ frontend/src/App.tsx frontend/src/main.tsx
git commit -m "feat(frontend): 实现仪表盘、项目列表与 React Flow 工作流编辑器"
```

---

## Task 16: Docker 开发环境

**Files:**
- Create: `c:\漫剧软件项目\docker\docker-compose.yml`
- Create: `c:\漫剧软件项目\docker\Dockerfile.backend`
- Create: `c:\漫剧软件项目\docker\Dockerfile.frontend`
- Create: `c:\漫剧软件项目\docker\init-db.sql`

- [ ] **Step 1: 创建 `docker/docker-compose.yml`**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: comic-postgres
    environment:
      POSTGRES_DB: comic_studio
      POSTGRES_USER: comic_user
      POSTGRES_PASSWORD: comic_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U comic_user -d comic_studio"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: comic-redis
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    container_name: comic-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

- [ ] **Step 2: 创建 `docker/init-db.sql`**

```sql
-- 数据库初始化脚本
-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 注意: pgvector 扩展需要单独安装，如需使用请运行:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- 注释
\echo '数据库 comic_studio 初始化完成'
```

- [ ] **Step 3: 创建 `docker/Dockerfile.backend`**

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: 创建 `docker/Dockerfile.frontend`**

```dockerfile
# 构建阶段
FROM node:18-alpine as build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build

# 生产阶段
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 5: 提交**

```bash
cd "c:\漫剧软件项目"
git add docker/
git commit -m "feat(devops): 添加 Docker Compose 编排与 Dockerfile"
```

---

## Task 17: 集成验证与文档更新

**Files:**
- Create: `c:\漫剧软件项目\backend\tests\test_integration.py`
- Modify: `c:\漫剧软件项目\README.md` (添加开发指南)

- [ ] **Step 1: 编写集成测试 `backend/tests/test_integration.py`**

```python
"""集成测试 - 验证 API 路由注册"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_all_api_routes_registered():
    """测试所有 API 路由已正确注册"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    expected_paths = [
        "/api/auth/register",
        "/api/auth/login",
        "/api/users/me",
        "/api/projects",
        "/api/characters",
        "/api/scripts",
        "/api/storyboards",
        "/api/audio/voices",
        "/api/render",
        "/api/workflows",
        "/health",
    ]
    for path in expected_paths:
        assert path in paths, f"缺少路由: {path}"


@pytest.mark.asyncio
async def test_cors_headers():
    """测试 CORS 头"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code in [200, 204]


@pytest.mark.asyncio
async def test_error_response_format():
    """测试错误响应格式"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 访问需要认证的接口
        response = await client.get("/api/users/me")
    assert response.status_code == 401
    # FastAPI 默认错误格式，不是我们的 ApiResponse 格式（受 OAuth2 拦截）
    data = response.json()
    assert "detail" in data
```

- [ ] **Step 2: 运行完整测试套件验证**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: 所有测试通过

- [ ] **Step 3: 更新 `README.md` 添加开发指南**

在 README.md 末尾追加（使用 Edit 工具）：

```markdown

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Docker 24+

### 一键启动（推荐）

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 启动开发环境 (Windows)
.\scripts\dev.ps1

# 或 (Linux/macOS)
./scripts/dev.sh
```

### 手动启动

```bash
# 1. 启动基础设施服务
cd docker
docker-compose up -d postgres redis minio

# 2. 启动后端
cd ../backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动前端
cd ../frontend
npm install
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 UI | http://localhost:5173 |
| 后端 API 文档 | http://localhost:8000/docs |
| MinIO 控制台 | http://localhost:9001 |

### 运行测试

```bash
# 后端测试
cd backend
python -m pytest tests/ -v
```
```

- [ ] **Step 4: 最终提交**

```bash
cd "c:\漫剧软件项目"
git add backend/tests/test_integration.py README.md
git commit -m "test: 添加集成测试并更新 README 开发指南"
```

---

## 完成检查清单

实施完成后，验证以下功能：

- [ ] Docker 基础设施可启动：`docker-compose up -d` 成功启动 postgres/redis/minio
- [ ] 后端可启动：`uvicorn app.main:app --reload` 在 8000 端口运行
- [ ] 后端健康检查通过：访问 `http://localhost:8000/health` 返回 `{"code":0,"data":{"status":"ok"}}`
- [ ] API 文档可访问：`http://localhost:8000/docs` 显示 Swagger UI
- [ ] 所有 API 路由已注册：OpenAPI 包含 9 个模块的所有端点
- [ ] 后端测试全部通过：`python -m pytest tests/ -v` 通过
- [ ] 前端可启动：`npm run dev` 在 5173 端口运行
- [ ] 前端登录页可访问：`http://localhost:5173/login` 显示登录表单
- [ ] 用户注册→登录→跳转仪表盘流程完整
- [ ] 项目创建→跳转编辑器流程完整
- [ ] React Flow 工作流编辑器可拖拽、连线
- [ ] TRAE 风格暗色主题正确显示

---

## 后续阶段

完成本基础骨架后，后续阶段将实现：

- **Phase 2**: AI 引擎层 - 图像生成 (SDXL)、角色一致性 (IP-Adapter + LoRA)、TTS (Edge-TTS)、视频合成 (FFmpeg)
- **Phase 3**: 工作流引擎 - DAG 节点调度、模板系统、执行记录
- **Phase 4**: 桌面端封装 - Electron 打包
- **Phase 5**: 部署运维 - K8s 部署、CI/CD、监控
- **Phase 6**: 商业化 - 计费、订阅、API 开放平台、素材市场

每个阶段将基于本骨架的目录结构和接口契约进行扩展。
