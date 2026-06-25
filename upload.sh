#!/bin/bash
# TriGen 本地打包脚本
# 在本地执行，生成部署包

set -e

echo "=========================================="
echo "  TriGen 打包脚本"
echo "=========================================="

# 配置
DEPLOY_DIR="/tmp/trigen-deploy"
PACKAGE_NAME="trigen-hub-$(date +%Y%m%d_%H%M%S).tar.gz"

# 需要包含的文件
INCLUDE_FILES=(
    "server.js"
    "package.json"
    "ecosystem.config.js"
    "index.html"
    "manifest.json"
    "sw.js"
    "js/"
    "css/"
    ".env.example"
)

# 不需要包含的文件/目录
EXCLUDE_PATTERN=(
    "node_modules"
    ".git"
    "*.log"
    "logs"
    "backup"
    ".workbuddy"
    ".github"
    "claude-code-source"
    "claude-code-prompts"
    "codex-source"
    "trae-source"
    "docs"
    "*_backup*"
    "deploy.sh"
    "upload.sh"
)

echo "1. 清理旧文件..."
rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"

echo "2. 复制文件..."
for item in "${INCLUDE_FILES[@]}"; do
    if [ -e "$item" ]; then
        cp -r "$item" "$DEPLOY_DIR/"
        echo "   ✅ $item"
    else
        echo "   ⚠️ 跳过 $item (不存在)"
    fi
done

echo "3. 复制桌面端..."
if [ -d "download/TriGenClaw-Portable" ]; then
    cp -r download/TriGenClaw-Portable "$DEPLOY_DIR/"
    echo "   ✅ download/TriGenClaw-Portable"
fi

echo "4. 清理不需要的文件..."
cd "$DEPLOY_DIR"
for pattern in "${EXCLUDE_PATTERN[@]}"; do
    rm -rf $pattern 2>/dev/null || true
done

echo "5. 生成部署包..."
cd /tmp
tar -czf "$PACKAGE_NAME" -C "$DEPLOY_DIR" .

echo "6. 显示包信息..."
ls -lh "$PACKAGE_NAME"

echo ""
echo "=========================================="
echo "  打包完成！"
echo "=========================================="
echo ""
echo "部署包位置: $PACKAGE_NAME"
echo ""
echo "上传到服务器:"
echo "  scp $PACKAGE_NAME admin@120.79.17.184:/home/admin/"
echo ""
echo "或在服务器上执行:"
echo "  cd /home/admin"
echo "  tar -xzf $PACKAGE_NAME"
echo "  ./deploy.sh"
echo ""
