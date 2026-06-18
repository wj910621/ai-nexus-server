#!/bin/bash
# ==============================================================
# TriGen 一键部署脚本 v3.0
# 用法: bash deploy.sh [frontend|backend|env|all]
# 安全提示: 密码从环境变量读取 DEPLOY_PASS
# ==============================================================
set -e

SSH_KEY=""
SERVER="root@120.79.17.184"
SSH_CMD="sshpass -p \"$DEPLOY_PASS\" ssh -o StrictHostKeyChecking=no"
SCP_CMD="sshpass -p \"$DEPLOY_PASS\" scp -o StrictHostKeyChecking=no"
FRONTEND_DIR="/home/admin/nexus-studio"
BACKEND_DIR="/home/admin/ai-nexus"

if [ -z "$DEPLOY_PASS" ]; then
  echo "❌ 错误：未设置 DEPLOY_PASS 环境变量"
  echo "   export DEPLOY_PASS=你的服务器密码"
  exit 1
fi

echo "========================================"
echo "  TriGen 一键部署 v3.0"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

deploy_frontend() {
  echo "🌐 [前端] 部署前端文件..."
  $SCP_CMD index.html $SERVER:$FRONTEND_DIR/index.html
  $SCP_CMD -r js $SERVER:$FRONTEND_DIR/js
  echo "  ✅ 前端更新完成"
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
    echo "   🌐 https://j3trisheng.com"
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
