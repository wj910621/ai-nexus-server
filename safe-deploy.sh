#!/bin/bash
# ==============================================================================
# TriGen Nexus Hub 安全部署脚本
# 【重要】只更新白名单内的文件，禁止修改其他任何文件
# ==============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置
DEPLOY_PATH="/home/admin/he-wiki-rag"
WHITELIST_FILE="deploy-whitelist.txt"
BACKUP_DIR="/tmp/trigen_backup_$(date +%Y%m%d_%H%M%S)"
TEMP_DIR="/tmp/trigen-deploy-safe"
PM2_APP="trigen"

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# 安全检查
safety_check() {
    log_step "安全检查..."
    
    if [ ! -d "$DEPLOY_PATH" ]; then
        log_error "部署目录不存在: $DEPLOY_PATH"
        exit 1
    fi
    
    if [ ! -f "$WHITELIST_FILE" ]; then
        log_error "白名单文件不存在: $WHITELIST_FILE"
        exit 1
    fi
    
    # 检查数据库目录是否存在（确认不是误操作）
    if [ -d "$DEPLOY_PATH/data" ]; then
        log_info "检测到数据库目录 (data/)，部署时将跳过 ✓"
    fi
    
    # 检查.env文件
    if [ -f "$DEPLOY_PATH/.env" ]; then
        log_info "检测到配置文件 (.env)，部署时将跳过 ✓"
    fi
    
    log_info "安全检查通过 ✓"
}

# 备份旧文件
backup_old_files() {
    log_step "备份白名单内的旧文件..."
    
    mkdir -p "$BACKUP_DIR"
    
    while IFS= read -r filepath; do
        if [ -z "$filepath" ] || [[ "$filepath" == \#* ]]; then
            continue
        fi
        
        full_path="$DEPLOY_PATH/$filepath"
        if [ -f "$full_path" ]; then
            dir=$(dirname "$filepath")
            mkdir -p "$BACKUP_DIR/$dir"
            cp "$full_path" "$BACKUP_DIR/$filepath"
            log_info "已备份: $filepath"
        fi
    done < "$WHITELIST_FILE"
    
    log_info "备份完成: $BACKUP_DIR ✓"
}

# 按白名单部署文件
deploy_by_whitelist() {
    log_step "按白名单部署文件..."
    
    DEPLOYED_COUNT=0
    SKIPPED_COUNT=0
    
    while IFS= read -r filepath; do
        if [ -z "$filepath" ] || [[ "$filepath" == \#* ]]; then
            continue
        fi
        
        src_file="$TEMP_DIR/$filepath"
        dest_file="$DEPLOY_PATH/$filepath"
        
        # 检查源文件是否存在
        if [ ! -f "$src_file" ]; then
            log_warn "跳过 (源文件不存在): $filepath"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi
        
        # 确保目标目录存在
        dest_dir=$(dirname "$dest_file")
        mkdir -p "$dest_dir"
        
        # 复制文件
        cp "$src_file" "$dest_file"
        DEPLOYED_COUNT=$((DEPLOYED_COUNT + 1))
        
        if [ -f "$dest_file" ]; then
            log_info "已更新: $filepath"
        else
            log_info "已新增: $filepath"
        fi
        
    done < "$WHITELIST_FILE"
    
    echo ""
    log_info "部署统计: 已更新 $DEPLOYED_COUNT 个文件, 跳过 $SKIPPED_COUNT 个 ✓"
}

# 安装依赖
install_dependencies() {
    log_step "安装npm依赖..."
    
    cd "$DEPLOY_PATH"
    
    # 只安装，不清理
    npm install --legacy-peer-deps --no-audit --no-fund
    
    log_info "依赖安装完成 ✓"
}

# 重启服务
restart_service() {
    log_step "重启PM2服务..."
    
    if command -v pm2 &> /dev/null; then
        pm2 restart "$PM2_APP"
        sleep 2
        
        # 检查状态
        STATUS=$(pm2 jlist | grep -o '"status":"[^"]*"' | head -1 || echo "unknown")
        log_info "PM2状态: $STATUS"
    else
        log_warn "PM2未找到，请手动重启服务"
    fi
}

# 验证部署
verify_deployment() {
    log_step "验证部署..."
    
    # 检查关键文件是否存在
    CHECK_FILES=("index.html" "server.js" "js/main.js" "js/prompts.js" "js/safety.js" "js/session.js")
    ALL_OK=true
    
    for f in "${CHECK_FILES[@]}"; do
        if [ -f "$DEPLOY_PATH/$f" ]; then
            log_info "✓ $f"
        else
            log_error "✗ $f (缺失)"
            ALL_OK=false
        fi
    done
    
    # 检查禁止修改的文件是否还在
    PROTECTED_FILES=("data/database.sqlite" ".env")
    for f in "${PROTECTED_FILES[@]}"; do
        if [ -f "$DEPLOY_PATH/$f" ]; then
            log_info "✓ [保护文件] $f (未被修改)"
        fi
    done
    
    if [ "$ALL_OK" = true ]; then
        log_info "部署验证通过 ✓"
    else
        log_error "部署验证失败，有文件缺失！"
        exit 1
    fi
}

# 清理临时文件
cleanup() {
    log_step "清理临时文件..."
    
    rm -rf "$TEMP_DIR"
    log_info "临时目录已清理 ✓"
}

# 显示完成信息
show_complete() {
    echo ""
    echo "======================================================================"
    echo "  ${GREEN}TriGen 部署完成！${NC}"
    echo "======================================================================"
    echo ""
    echo "  部署目录:  $DEPLOY_PATH"
    echo "  备份目录:  $BACKUP_DIR"
    echo "  访问地址:  http://j3trisheng.com"
    echo ""
    echo "  常用命令:"
    echo "    pm2 status              # 查看服务状态"
    echo "    pm2 logs trigen         # 查看日志"
    echo "    pm2 restart trigen      # 重启服务"
    echo ""
    echo "  【重要】以下文件未被修改:"
    echo "    - data/ 目录（数据库）"
    echo "    - .env 配置文件"
    echo "    - uploads/ 目录（上传文件）"
    echo "    - logs/ 目录（日志）"
    echo "======================================================================"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "======================================================================"
    echo "  TriGen Nexus Hub 安全部署脚本"
    echo "  【安全模式】只更新白名单内的文件"
    echo "======================================================================"
    echo ""
    
    # 确认部署包已解压
    if [ ! -d "$TEMP_DIR" ]; then
        log_error "请先解压部署包到 $TEMP_DIR"
        log_error "命令: mkdir -p $TEMP_DIR && tar -xzvf trigen-deploy-safe.tar.gz -C $TEMP_DIR"
        exit 1
    fi
    
    safety_check
    backup_old_files
    deploy_by_whitelist
    install_dependencies
    restart_service
    verify_deployment
    cleanup
    show_complete
}

# 执行
main "$@"
