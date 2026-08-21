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
