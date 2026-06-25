#!/bin/bash
# TriGen 部署脚本
# 服务器执行此脚本完成部署

set -e

echo "=========================================="
echo "  TriGen 部署脚本"
echo "=========================================="

# 配置
PROJECT_DIR="/home/admin/he-wiki-rag"
BACKUP_DIR="/home/admin/he-wiki-rag/backup"
LOG_FILE="/home/admin/he-wiki-rag/deploy.log"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[ERROR] $1" >> "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查 root 权限
if [ "$EUID" -eq 0 ]; then
    warn "建议不要使用 root 用户运行此脚本"
fi

# 1. 创建目录
log "创建目录..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$BACKUP_DIR/$(date +%Y%m%d_%H%M%S)"

# 2. 备份当前版本
if [ -f "$PROJECT_DIR/server.js" ]; then
    log "备份当前版本..."
    cp -r "$PROJECT_DIR"/* "$BACKUP_DIR/$(date +%Y%m%d_%H%M%S)/" 2>/dev/null || true
fi

# 3. 停止 PM2 进程
log "停止当前服务..."
pm2 stop trigen-hub 2>/dev/null || true
pm2 delete trigen-hub 2>/dev/null || true

# 4. 更新代码
log "更新代码..."

# 如果是 git 部署
if [ -d ".git" ]; then
    git pull origin main
else
    error "请先通过 SFTP 上传最新代码"
fi

# 5. 安装依赖
log "安装依赖..."
npm install

# 6. 检查环境变量
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f ".env.example" ]; then
        log "创建 .env 文件..."
        cp .env.example .env
        warn "请编辑 $PROJECT_DIR/.env 配置文件"
    fi
fi

# 7. 创建日志目录
mkdir -p logs

# 8. 启动服务
log "启动服务..."
pm2 start ecosystem.config.js
pm2 save

# 9. 设置开机自启
pm2 startup 2>/dev/null || true

# 10. 检查服务状态
sleep 2
STATUS=$(pm2 show trigen-hub | grep "status" | head -1)
if [[ "$STATUS" == *"online"* ]]; then
    log "✅ 服务启动成功！"
else
    error "服务启动失败，请检查日志: pm2 logs trigen-hub"
fi

# 11. 显示状态
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
pm2 status
echo ""
log "日志查看: pm2 logs trigen-hub"
log "监控面板: pm2 monit"
log "重启服务: pm2 restart trigen-hub"
echo ""
