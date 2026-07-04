"""
Y·NEX systemd 服务 + 开机自启脚本
适用于：Linux 小主机、树莓派（Ubuntu/Debian/Raspbian）

用法：
  # 一键部署服务（需要 sudo）
  bash deploy.sh

  # 或手动：
  sudo cp Y·NEX.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable Y·NEX
  sudo systemctl start Y·NEX
  sudo systemctl status Y·NEX
"""

import os
import sys
import subprocess

SERVICE_FILE = """[Unit]
Description=Y·NEX AI 管家服务
After=network.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={cwd}
ExecStart={python} {cwd}/main.py --text --tray
Restart=always
RestartSec=10
StandardOutput=append:{log_file}
StandardError=append:{log_file}
Environment="PYTHONUNBUFFERED=1"

# 硬件相关（可选，取消注释以绑定CPU）
# CPUAffinity=0-1

[Install]
WantedBy=multi-user.target
"""

DEPLOY_SCRIPT = """#!/bin/bash
# Y·NEX AI 管家 - systemd 服务安装脚本
# 用法: bash deploy.sh

set -e

echo "=== Y·NEX AI 管家 部署脚本 ==="

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$(which python3 || which python)"

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到 Python，请先安装 Python 3.10+"
    exit 1
fi

echo "项目目录: $PROJECT_DIR"
echo "Python: $PYTHON_BIN"
read -p "确认安装？(y/n) " confirm
[ "$confirm" != "y" ] && echo "取消部署。" && exit 0

# 安装依赖
echo ">>> 安装系统依赖..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3-pip python3-venv libasound2-dev portaudio19-dev
elif command -v pacman &> /dev/null; then
    sudo pacman -S python python-pip alsa-lib portaudio
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip alsa-lib-devel portaudio-devel
fi

# 创建虚拟环境（推荐）
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo ">>> 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo ">>> 安装 Python 依赖..."
pip install -r "$PROJECT_DIR/requirements.txt"

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 生成 systemd 服务文件
USER=$(whoami)
SERVICE_PATH="/etc/systemd/system/Y·NEX.service"
echo ">>> 创建服务文件: $SERVICE_PATH"
cat > /tmp/Y·NEX.service <<EOF
[Unit]
Description=Y·NEX AI 管家服务
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/main.py --text --tray
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/Y·NEX.log
StandardError=append:$PROJECT_DIR/logs/Y·NEX.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
sudo cp /tmp/Y·NEX.service "$SERVICE_PATH"

echo ">>> 启用服务..."
sudo systemctl daemon-reload
sudo systemctl enable Y·NEX
sudo systemctl start Y·NEX

echo ""
echo "=== 部署完成 ==="
echo "服务状态: systemctl status Y·NEX"
echo "实时日志: tail -f $PROJECT_DIR/logs/Y·NEX.log"
echo "重启服务: sudo systemctl restart Y·NEX"
echo "停止服务: sudo systemctl stop Y·NEX"
"""

REMOTE_ACCESS_GUIDE = """
# ============================================================
# Y·NEX远程访问配置指南
# ============================================================

## 方案一：Cloudflare Tunnel（推荐，零暴露端口）

1. 注册 Cloudflare 账号（免费）
2. 在树莓派/小主机上安装 cloudflared：
   bash -c "$(curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb)"
   sudo dpkg -i cloudflared.deb

3. 创建隧道（免费）：
   cloudflared tunnel create Y·NEX
   cloudflared tunnel route dns Y·NEX <your-subdomain>.trycloudflare.com

4. 运行隧道：
   cloudflared tunnel run --token <your-token>

5. 配置开机自启（systemd）：
   sudo cloudflared service install <your-token>

优势：无需公网 IP，不暴露端口，自动 HTTPS，延迟低。

---

## 方案二：Tailscale（需要两台设备组网）

1. 两边都安装 Tailscale：
   curl -fsSL https://tailscale.com/install.sh | sh

2. 登录并组网：
   tailscale up
   tailscale status  # 查看 IP，如 100.x.x.x

3. 直接访问：
   curl http://100.x.x.x:7788/chat -X POST -H "X-API-Key: your-key" -d '{"text":"天气"}'

---

## 方案三：DDNS + 端口映射（传统方案）

1. 路由器设置端口映射：外部 7788 -> 内部 192.168.x.x:7788
2. 申请免费 DDNS 域名（如 noip.com）
3. 在路由器或主机上运行 DDNS 客户端更新 IP

风险：暴露公网端口，安全性较低。

"""


def generate_service_file(python_path: str, cwd: str, log_file: str, user: str) -> str:
    return SERVICE_FILE.format(
        python=python_path,
        cwd=cwd,
        log_file=log_file,
        user=user
    )


def deploy():
    """交互式部署"""
    import os
    cwd = os.path.dirname(os.path.abspath(__file__))
    print("=== Y·NEX部署脚本 ===")
    print(f"项目目录: {cwd}")

    python_bin = sys.executable or "python3"
    user = os.getenv("USER") or os.getenv("USERNAME") or "root"
    log_file = os.path.join(cwd, "logs", "Y·NEX.log")

    os.makedirs(os.path.join(cwd, "logs"), exist_ok=True)

    # 生成 systemd 服务文件
    service_content = generate_service_file(python_bin, cwd, log_file, user)
    service_path = os.path.join(cwd, "Y·NEX.service")

    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_content)

    print(f"\n已生成服务文件: {service_path}")
    print("\n手动部署步骤：")
    print(f"  sudo cp {service_path} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable Y·NEX")
    print("  sudo systemctl start Y·NEX")
    print(f"\n查看日志：tail -f {log_file}")

    # 生成远程访问指南
    guide_path = os.path.join(cwd, "REMOTE_ACCESS.md")
    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(REMOTE_ACCESS_GUIDE)
    print(f"\n远程访问配置指南已生成: {guide_path}")


if __name__ == "__main__":
    deploy()
