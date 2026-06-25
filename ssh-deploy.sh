#!/bin/bash
# TriGen SSH 远程部署脚本
# 本地执行，自动上传并部署到服务器

set -e

# 配置
SERVER_IP="120.79.17.184"
SERVER_PORT="22"
SERVER_USER="admin"
SERVER_PASS="Wjzlt910621."
PROJECT_DIR="/home/admin/he-wiki-rag"
DEPLOY_PACKAGE="/tmp/trigen-deploy.tar.gz"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo "=========================================="
echo "  TriGen 远程部署脚本"
echo "=========================================="

# 1. 检查依赖
log "检查依赖..."

if ! command -v sshpass &> /dev/null; then
    warn "sshpass 未安装，尝试安装..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y sshpass
    elif command -v yum &> /dev/null; then
        sudo yum install -y sshpass
    else
        error "无法安装 sshpass，请手动安装或使用手动部署"
    fi
fi

# 2. 测试 SSH 连接
log "测试 SSH 连接..."
if sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no -p $SERVER_PORT $SERVER_USER@$SERVER_IP "echo '连接成功'" 2>/dev/null; then
    log "SSH 连接成功"
else
    error "SSH 连接失败，请检查用户名密码"
fi

# 3. 创建本地部署包
log "创建部署包..."
cd /workspace

# 定义需要上传的文件
UPLOAD_FILES="server.js package.json ecosystem.config.js index.html manifest.json sw.js .env.example js css routes"

# 在服务器上创建目录
sshpass -p "$SERVER_PASS" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP "mkdir -p $PROJECT_DIR/js $PROJECT_DIR/css $PROJECT_DIR/routes $PROJECT_DIR/logs" 2>/dev/null

# 上传文件
log "上传文件..."
for item in $UPLOAD_FILES; do
    if [ -e "$item" ]; then
        if [ -d "$item" ]; then
            sshpass -p "$SERVER_PASS" scp -r -P $SERVER_PORT "$item" $SERVER_USER@$SERVER_IP:"$PROJECT_DIR/" 2>/dev/null
        else
            sshpass -p "$SERVER_PASS" scp -P $SERVER_PORT "$item" $SERVER_USER@$SERVER_IP:"$PROJECT_DIR/" 2>/dev/null
        fi
        log "   ✅ $item"
    fi
done

# 上传桌面端
if [ -d "download/TriGenClaw-Portable" ]; then
    sshpass -p "$SERVER_PASS" scp -r -P $SERVER_PORT download/TriGenClaw-Portable $SERVER_USER@$SERVER_IP:"$PROJECT_DIR/download/" 2>/dev/null
    log "   ✅ download/TriGenClaw-Portable"
fi

# 4. 在服务器上安装依赖
log "安装依赖..."
sshpass -p "$SERVER_PASS" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP "cd $PROJECT_DIR && npm install --production 2>&1" 2>/dev/null

# 5. 配置 PM2
log "配置 PM2..."
sshpass -p "$SERVER_PASS" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP "
    cd $PROJECT_DIR
    pm2 stop trigen-hub 2>/dev/null || true
    pm2 delete trigen-hub 2>/dev/null || true
    pm2 start ecosystem.config.js
    pm2 save
" 2>/dev/null

# 6. 检查服务状态
log "检查服务状态..."
sleep 2
STATUS=$(sshpass -p "$SERVER_PASS" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP "pm2 show trigen-hub | grep status | head -1" 2>/dev/null)

if [[ "$STATUS" == *"online"* ]]; then
    echo ""
    echo "=========================================="
    log "✅ 部署成功！"
    echo "=========================================="
    sshpass -p "$SERVER_PASS" ssh -p $SERVER_PORT $SERVER_USER@$SERVER_IP "pm2 status" 2>/dev/null
    echo ""
    log "访问地址: http://$SERVER_IP:3001"
    log "管理面板: pm2 monit"
else
    error "服务启动失败，请检查: pm2 logs trigen-hub"
fi
