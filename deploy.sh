#!/bin/bash
# ==============================================================
# TriGen 一键部署脚本 v2.0
# 用法: bash deploy.sh [frontend|backend|all]
# ==============================================================
set -e

SSH_KEY=""
SERVER="root@120.79.17.184"
SSH_CMD="ssh -o StrictHostKeyChecking=no"
SCP_CMD="scp -o StrictHostKeyChecking=no"
FRONTEND_DIR="/home/admin/nexus-studio"
BACKEND_DIR="/home/admin/ai-nexus"

echo "========================================"
echo "  TriGen 一键部署 v2.0"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

deploy_frontend() {
  echo "🌐 [前端] 部署 TriGen Desktop..."
  $SCP_CMD new-nexus/index.html $SERVER:$FRONTEND_DIR/index.html
  echo "  ✅ 前端更新完成"
  echo "  📎 http://120.79.17.184:3001/studio/"
}

deploy_backend() {
  echo "⚙️  [后端] 部署 API Server..."
  $SCP_CMD server.js $SERVER:$BACKEND_DIR/server.js
  $SSH_CMD $SERVER "cd $BACKEND_DIR && pm2 restart server.js"
  echo "  ✅ 后端更新 + 重启完成"
}

deploy_env() {
  echo "🔑 [环境] 部署 .env 配置..."
  $SCP_CMD .env $SERVER:$BACKEND_DIR/.env
  $SSH_CMD $SERVER "cd $BACKEND_DIR && pm2 restart server.js"
  echo "  ✅ .env 已更新，服务已重启"
}

# Main
case "${1:-all}" in
  frontend)  deploy_frontend ;;
  backend)   deploy_backend ;;
  env)       deploy_env ;;
  all)
    deploy_frontend
    deploy_backend
    echo ""
    echo "🎉 全量部署完成！"
    echo "   🌐 http://120.79.17.184:3001/studio/"
    echo "   ⚙️  http://120.79.17.184:3001/"
    ;;
  *)
    echo "用法: bash deploy.sh [frontend|backend|env|all]"
    echo "  frontend  - 仅部署前端"
    echo "  backend   - 仅部署后端"
    echo "  env       - 仅更新环境变量"
    echo "  all       - 全量部署 (默认)"
    exit 1
    ;;
esac
