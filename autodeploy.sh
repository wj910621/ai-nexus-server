#!/bin/bash
# TriGen (Nexus Hub) 自动部署脚本
# 支持：宝塔面板、1Panel、SSH手动执行、Ansible等

set -e

# ============================================
# 配置区域 - 根据实际情况修改
# ============================================
DEPLOY_PATH="/home/admin/he-wiki-rag"      # 部署目录
DOMAIN="j3trisheng.com"                      # 域名
PORT=3000                                     # Node服务端口
APP_NAME="trigen"                             # PM2应用名称
NODE_VERSION="18"                             # 需要的Node版本

# ============================================
# 颜色输出
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================
# 步骤1: 检查环境
# ============================================
check_environment() {
    log_info "步骤1: 检查运行环境..."
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        log_warn "Node.js 未安装，正在安装..."
        curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash -
        apt-get install -y nodejs
    fi
    
    NODE_VER=$(node -v)
    log_info "Node.js 版本: $NODE_VER"
    
    # 检查npm
    if ! command -v npm &> /dev/null; then
        log_error "npm 未安装"
        exit 1
    fi
    
    npm -v
    log_info "npm 版本: $(npm -v)"
    
    # 检查Git
    if ! command -v git &> /dev/null; then
        log_warn "Git 未安装，安装中..."
        apt-get install -y git
    fi
    
    # 检查PM2
    if ! command -v pm2 &> /dev/null; then
        log_info "安装 PM2..."
        npm install -g pm2
    fi
    
    log_info "环境检查完成 ✓"
}

# ============================================
# 步骤2: 创建目录
# ============================================
prepare_directory() {
    log_info "步骤2: 准备部署目录..."
    
    if [ ! -d "$DEPLOY_PATH" ]; then
        log_info "创建目录: $DEPLOY_PATH"
        mkdir -p "$DEPLOY_PATH"
    fi
    
    cd "$DEPLOY_PATH"
    log_info "当前目录: $(pwd)"
}

# ============================================
# 步骤3: 备份旧版本
# ============================================
backup_old_version() {
    log_info "步骤3: 备份旧版本..."
    
    if [ -f "$DEPLOY_PATH/server.js" ]; then
        BACKUP_DIR="/tmp/trigen_backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # 备份关键文件
        [ -f "$DEPLOY_PATH/server.js" ] && cp "$DEPLOY_PATH/server.js" "$BACKUP_DIR/"
        [ -f "$DEPLOY_PATH/package.json" ] && cp "$DEPLOY_PATH/package.json" "$BACKUP_DIR/"
        [ -d "$DEPLOY_PATH/data" ] && cp -r "$DEPLOY_PATH/data" "$BACKUP_DIR/" 2>/dev/null || true
        [ -d "$DEPLOY_PATH/uploads" ] && cp -r "$DEPLOY_PATH/uploads" "$BACKUP_DIR/" 2>/dev/null || true
        
        log_info "备份完成: $BACKUP_DIR"
    else
        log_warn "未发现旧版本，跳过备份"
    fi
}

# ============================================
# 步骤4: 部署文件
# ============================================
deploy_files() {
    log_info "步骤4: 部署文件..."
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 如果存在部署包，解压
    if [ -f "$SCRIPT_DIR/trigen-deploy.tar.gz" ]; then
        log_info "解压部署包..."
        tar -xzvf "$SCRIPT_DIR/trigen-deploy.tar.gz" -C "$DEPLOY_PATH" --strip-components=1
    else
        log_warn "未找到 trigen-deploy.tar.gz，使用现有文件"
    fi
    
    # 确保必要目录存在
    mkdir -p "$DEPLOY_PATH/data"
    mkdir -p "$DEPLOY_PATH/uploads"
    mkdir -p "$DEPLOY_PATH/logs"
    
    log_info "文件部署完成 ✓"
}

# ============================================
# 步骤5: 安装依赖
# ============================================
install_dependencies() {
    log_info "步骤5: 安装依赖..."
    
    cd "$DEPLOY_PATH"
    
    # 清理可能的问题
    rm -rf node_modules package-lock.json
    
    # 安装依赖
    npm install --legacy-peer-deps
    
    log_info "依赖安装完成 ✓"
}

# ============================================
# 步骤6: 配置PM2
# ============================================
setup_pm2() {
    log_info "步骤6: 配置PM2进程管理..."
    
    cd "$DEPLOY_PATH"
    
    # 创建PM2配置文件
    cat > "$DEPLOY_PATH/ecosystem.config.js" << 'EOF'
module.exports = {
  apps: [{
    name: 'trigen',
    script: 'server.js',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      NODE_ENV: 'production',
      PORT: 3000
    },
    error_file: './logs/error.log',
    out_file: './logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss'
  }]
};
EOF
    
    # 停止旧进程
    pm2 delete $APP_NAME 2>/dev/null || true
    
    # 启动新服务
    pm2 start ecosystem.config.js
    
    # 保存PM2配置
    pm2 save
    
    # 设置开机自启
    pm2 startup
    
    log_info "PM2配置完成 ✓"
}

# ============================================
# 步骤7: 配置Nginx反向代理
# ============================================
setup_nginx() {
    log_info "步骤7: 配置Nginx反向代理..."
    
    if command -v nginx &> /dev/null; then
        cat > "/etc/nginx/sites-available/$DOMAIN" << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # 文件上传大小限制
        client_max_body_size 100M;
    }
    
    location /api {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
        
        # 启用站点
        ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
        
        # 测试配置
        nginx -t
        
        # 重载Nginx
        systemctl reload nginx
        
        log_info "Nginx配置完成 ✓"
    else
        log_warn "Nginx未安装，跳过反向代理配置"
    fi
}

# ============================================
# 步骤8: 配置SSL证书
# ============================================
setup_ssl() {
    log_info "步骤8: 配置SSL证书..."
    
    if command -v certbot &> /dev/null; then
        certbot --nginx -d $DOMAIN --noninteractive --agree-tos --email admin@$DOMAIN -m
        log_info "SSL证书配置完成 ✓"
    else
        log_warn "Certbot未安装，跳过SSL配置"
        log_info "如需SSL，请手动运行: certbot --nginx -d $DOMAIN"
    fi
}

# ============================================
# 步骤9: 验证部署
# ============================================
verify_deployment() {
    log_info "步骤9: 验证部署..."
    
    sleep 2
    
    # 检查PM2状态
    pm2 status
    
    # 检查端口
    if command -v netstat &> /dev/null; then
        netstat -tlnp | grep $PORT || log_warn "端口 $PORT 未监听"
    fi
    
    # 检查服务响应
    if command -v curl &> /dev/null; then
        sleep 1
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$PORT || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            log_info "服务响应正常 ✓ (HTTP $HTTP_CODE)"
        else
            log_warn "服务响应异常 (HTTP $HTTP_CODE)"
        fi
    fi
    
    log_info "验证完成"
}

# ============================================
# 步骤10: 显示访问信息
# ============================================
show_info() {
    echo ""
    echo "=========================================="
    echo "  TriGen (Nexus Hub) 部署完成"
    echo "=========================================="
    echo ""
    echo "访问地址: http://$DOMAIN"
    echo "部署目录: $DEPLOY_PATH"
    echo "Node端口: $PORT"
    echo ""
    echo "常用命令:"
    echo "  pm2 status          # 查看状态"
    echo "  pm2 logs trigen     # 查看日志"
    echo "  pm2 restart trigen  # 重启服务"
    echo "  pm2 stop trigen     # 停止服务"
    echo ""
    echo "=========================================="
}

# ============================================
# 主函数
# ============================================
main() {
    echo ""
    echo "=========================================="
    echo "  TriGen 自动部署脚本 v2.0"
    echo "=========================================="
    echo ""
    
    check_environment
    prepare_directory
    backup_old_version
    deploy_files
    install_dependencies
    setup_pm2
    setup_nginx
    # setup_ssl  # 注释掉，如需SSL请手动运行
    verify_deployment
    show_info
}

# 执行主函数
main "$@"
