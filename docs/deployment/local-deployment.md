# 本地部署指南

> 本文档指导开发者在本地搭建漫剧生成软件的开发环境。

---

## 一、环境要求

### 1.1 硬件要求

| 配置 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 2.5GHz | 8核 3.0GHz+ |
| 内存 | 16GB | 32GB+ |
| GPU | 无（CPU推理） | NVIDIA RTX 3060 12GB+ |
| 硬盘 | 50GB | 200GB+ SSD |
| 网络 | 宽带 | 100Mbps+ |

### 1.2 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| PostgreSQL | 15+ | 主数据库 |
| Redis | 7+ | 缓存与队列 |
| Docker | 24+ | 容器化（可选） |
| Git | 2.40+ | 版本控制 |
| CUDA | 11.8+ | GPU加速（可选） |

---

## 二、环境搭建

### 2.1 克隆项目

```bash
git clone <repository-url>
cd comic-studio-ai
```

### 2.2 使用Docker快速启动（推荐）

```bash
# 1. 复制环境配置
cp .env.example .env
# 编辑.env文件，设置数据库密码等

# 2. 启动基础设施服务
cd docker
docker-compose up -d postgres redis minio

# 3. 验证服务状态
docker-compose ps
```

### 2.3 手动安装（不使用Docker）

#### 安装PostgreSQL

```bash
# Windows: 下载安装包
# https://www.postgresql.org/download/windows/

# macOS
brew install postgresql@15
brew services start postgresql@15

# Ubuntu
sudo apt install postgresql-15
sudo systemctl start postgresql
```

#### 安装Redis

```bash
# Windows: 使用WSL或Memurai
# https://www.memurai.com/

# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl start redis-server
```

#### 创建数据库

```bash
# 登录PostgreSQL
psql -U postgres

# 创建数据库和用户
CREATE DATABASE comic_studio;
CREATE USER comic_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE comic_studio TO comic_user;
\q
```

---

## 三、后端部署

### 3.1 创建虚拟环境

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3.2 安装依赖

```bash
# 安装基础依赖
pip install -r requirements.txt

# 如果有GPU，安装GPU版本PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3.3 配置环境变量

```bash
# backend/.env
DATABASE_URL=postgresql://comic_user:your_password@localhost:5432/comic_studio
REDIS_URL=redis://localhost:6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# JWT密钥
JWT_SECRET_KEY=your-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=120

# AI模型路径
MODEL_BASE_PATH=../ai-models
SD_MODEL_PATH=../ai-models/sd15
SDXL_MODEL_PATH=../ai-models/sdxl

# LLM API（剧本生成）
DEEPSEEK_API_KEY=your-api-key
# 或
OPENAI_API_KEY=your-api-key

# 应用配置
APP_ENV=development
APP_PORT=8000
CORS_ORIGINS=http://localhost:5173
```

### 3.4 数据库迁移

```bash
# 运行数据库迁移
alembic upgrade head

# 初始化基础数据
python scripts/init_data.py
```

### 3.5 下载AI模型

```bash
# 下载基础模型（约5GB）
python scripts/download_models.py --model sd15
python scripts/download_models.py --model sdxl

# 下载ControlNet模型
python scripts/download_models.py --model controlnet

# 下载IP-Adapter模型
python scripts/download_models.py --model ip_adapter
```

### 3.6 启动后端

```bash
# 开发模式（热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 启动Celery Worker（另开终端）
celery -A app.celery worker --loglevel=info --concurrency=4

# 启动Celery Beat（定时任务，另开终端）
celery -A app.celery beat --loglevel=info
```

### 3.7 验证后端

```bash
# 访问API文档
curl http://localhost:8000/docs

# 健康检查
curl http://localhost:8000/health
```

---

## 四、前端部署

### 4.1 安装依赖

```bash
cd frontend
npm install
# 或使用pnpm（更快）
pnpm install
```

### 4.2 配置环境变量

```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_MINIO_URL=http://localhost:9000
```

### 4.3 启动开发服务器

```bash
npm run dev
# 访问 http://localhost:5173
```

### 4.4 构建生产版本

```bash
npm run build
# 产物在 dist/ 目录
```

---

## 五、桌面端部署

### 5.1 开发模式

```bash
cd desktop
npm install
npm run electron:dev
```

### 5.2 打包

```bash
# Windows
npm run electron:build:win

# macOS
npm run electron:build:mac

# Linux
npm run electron:build:linux
```

---

## 六、开发工具配置

### 6.1 VS Code推荐插件

```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "esbenp.prettier-vscode",
    "dbaeumer.vscode-eslint",
    "mtxr.sqltools",
    "mtxr.sqltools-driver-pg",
    "redhat.vscode-yaml"
  ]
}
```

### 6.2 VS Code配置

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  
  "typescript.tsdk": "frontend/node_modules/typescript/lib"
}
```

---

## 七、常见问题

### Q1: GPU显存不足

```
OutOfMemoryError: CUDA out of memory
```

**解决方案：**
1. 启用CPU offload：`pipe.enable_model_cpu_offload()`
2. 降低分辨率：512x512
3. 启用注意力切片：`pipe.enable_attention_slicing()`
4. 减少批量大小

### Q2: 模型下载慢

**解决方案：**
1. 使用国内镜像源
2. 使用hf-mirror.com：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q3: PostgreSQL连接失败

**解决方案：**
1. 检查pg_hba.conf是否允许本地连接
2. 确认用户密码正确
3. 检查防火墙设置

### Q4: 前端构建内存溢出

```
FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed
```

**解决方案：**
```bash
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build
```

---

*本文档最后更新：2026-07-18*
