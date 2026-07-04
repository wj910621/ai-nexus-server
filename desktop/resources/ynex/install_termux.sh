#!/bin/bash
# Y·NEX Termux 安装脚本（手机端运行）
# 复制到 Termux 后执行: bash <(curl -L <此脚本URL>)

set -e

YNEX_HOST="${YNEX_HOST:-http://192.168.1.100:7788}"
API_KEY="${API_KEY:-}"

echo "=== Y·NEX Termux 客户端安装 ==="
echo "Y·NEX 服务器: $YNEX_HOST"

# 安装依赖
echo ">>> 安装系统依赖..."
pkg update -y
pkg install -y python curl termux-api

# 下载客户端脚本
echo ">>> 下载 Y·NEX 客户端..."
curl -sL "https://你的服务器地址/termux_client.py" -o ~/ynex_client.py 2>/dev/null || {
    echo "提示：将 termux_client.py 手动复制到 Termux HOME 目录"
}

# 配置
echo ""
echo ">>> 请编辑 ~/.bashrc 设置以下环境变量："
echo "    export YNEX_URL=\"$YNEX_HOST\""
echo "    export YNEX_API_KEY=\"$API_KEY\""
echo ""

# 添加快捷命令到 bashrc
cat >> ~/.bashrc <<'BASHRC'

# Y·NEX AI 管家
alias ynex='python ~/ynex_client.py'
alias jchat='python ~/ynex_client.py --chat'
alias jstatus='python ~/ynex_client.py --status'
alias ywake='python ~/ynex_client.py --wake'
BASHRC

echo ">>> 安装完成！"
echo ""
echo "启动交互模式: jarvis"
echo "快速对话: jchat <消息>"
echo "查看状态: jstatus"
echo "唤醒 Y·NEX: jwake <消息>"
echo ""
echo "提示：在 Termux 中长按屏幕 → More → Selective browser 可选"
echo "      实现通知悬浮窗口效果。"
