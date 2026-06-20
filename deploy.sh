#!/bin/bash
# ==============================================================
# TriGen 一键部署脚本 v3.0
# 用法:
#   1. 设置密码: export DEPLOY_PASS=你的密码
#   2. 执行部署: bash deploy.sh [frontend|backend|env|all]
# ==============================================================

if [ -z "$DEPLOY_PASS" ]; then
  echo "❌ 错误：未设置 DEPLOY_PASS 环境变量"
  echo "   export DEPLOY_PASS=你的服务器密码"
  echo ""
  echo "💡 或者直接用 Node.js 脚本（Windows 兼容）："
  echo "   $env:DEPLOY_PASS=\"你的密码\"   (PowerShell)"
  echo "   node deploy-win.js all"
  exit 1
fi

# 检测可用工具
if command -v sshpass &> /dev/null; then
  SSH_CMD="sshpass -p \"$DEPLOY_PASS\" ssh -o StrictHostKeyChecking=no"
  SCP_CMD="sshpass -p \"$DEPLOY_PASS\" scp -o StrictHostKeyChecking=no"
  USE_SSHPASS=true
else
  echo "⚠️  未检测到 sshpass，将改用 Node.js 部署脚本..."
  echo "   正在执行: node deploy-win.js $1"
  node deploy-win.js "$1"
  exit $?
fi

SERVER="root@120.79.17.184"
FRONTEND_DIR="/home/admin/nexus-studio"
BACKEND_DIR="/home/admin/ai-nexus"

echo "========================================"
echo "  TriGen 一键部署 v3.0"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

deploy_frontend() {
  echo "🌐 [前端] 部署前端文件..."
  $SCP_CMD index.html $SERVER:$FRONTEND_DIR/index.html
  $SCP_CMD dashboard.html $SERVER:$FRONTEND_DIR/dashboard.html
  $SCP_CMD landing.html $SERVER:$FRONTEND_DIR/landing.html
  $SCP_CMD -r js $SERVER:$FRONTEND_DIR/js
  echo "  ✅ 前端更新完成"
}

deploy_backend() {
  echo "⚙️  [后端] 部署 API Server..."
  $SCP_CMD server.js $SERVER:$BACKEND_DIR/server.js
  $SSH_CMD $SERVER "cd $BACKEND_DIR && pm2 restart server.js" 2>&1 | tail -2
  echo "  ✅ 后端更新 + 重启完成"
}

deploy_env() {
  echo "🔑 [环境] 部署 .env 配置..."
  $SCP_CMD .env $SERVER:$BACKEND_DIR/.env
  $SSH_CMD $SERVER "cd $BACKEND_DIR && pm2 restart server.js" 2>&1 | tail -2
  echo "  ✅ .env 已更新，服务已重启"
}

case "${1:-all}" in
  frontend) deploy_frontend ;;
  backend)  deploy_backend ;;
  env)      deploy_env ;;
  all)
    deploy_frontend
    deploy_backend
    echo "🎉 全量部署完成！"
    echo "   🌐 https://j3trisheng.com"
    ;;
  *)
    echo "用法: bash deploy.sh [frontend|backend|env|all]"
    exit 1
    ;;
esac
