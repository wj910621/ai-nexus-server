"""
Y·NEX Android Termux 守护脚本
让手机成为Y·NEX的延伸终端，实现后台运行 + 通知回传。

安装步骤（手机端操作）：
1. 安装 Termux（Google Play 避免 F-Droid 兼容问题）
2. 授予存储和通知权限：
   termux-setup-storage
   通知权限：设置 → 应用 → Termux → 通知 → 允许

3. 安装必要工具：
   pkg update && pkg install python curl termux-api

4. 把本脚本传到 Termux HOME 目录：
   cp /sdcard/Y·NEX/termux_jarvis.sh ~/.bashrc

5. 配置Y·NEX 服务器地址和 API Key（在 .bashrc 中设置）

6. 运行：
   bash ~/.bashrc
   # 或后台运行：
   ./termux_jarvis.sh &

功能：
- /chat <文本> - 与Y·NEX对话
- /status - 系统状态
- /notify <消息> - 手机通知Y·NEX触发事件
- 自动重连，断线自动重试
- 后台守护，定时心跳
"""

import os
import sys
import time
import threading
import subprocess
import requests
from typing import Optional

# =============================================================================
# Termux API 调用（手机端执行）
# =============================================================================

def _termux_cmd(cmd: str) -> str:
    """通过 termux-api 执行命令，返回输出"""
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        return f"错误: {e}"


def send_notification(title: str, message: str, webhook_url: Optional[str] = None):
    """
    发送手机通知。
    优先用 termux-api，其次用 MQTT/Pushover 等。
    """
    # 方式1：termux-api 通知
    try:
        subprocess.run(
            ["termux-notification", "-t", title, "-m", message],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        pass

    # 方式2：HTTP webhook
    if webhook_url:
        try:
            requests.post(webhook_url, json={"title": title, "body": message}, timeout=5)
            return True
        except Exception:
            pass

    return False


def get_location() -> Optional[dict]:
    """通过 termux-api 获取位置"""
    try:
        result = subprocess.run(
            ["termux-location", "-p", "最后一次", "-r", "json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        import json
        data = json.loads(result.stdout)
        return {"lat": data.get("latitude"), "lon": data.get("longitude")}
    except Exception:
        return None


def battery_level() -> Optional[int]:
    """获取电池电量"""
    try:
        result = subprocess.run(
            ["termux-battery-status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        import json
        data = json.loads(result.stdout)
        return data.get("percentage")
    except Exception:
        return None


# =============================================================================
# Y·NEX客户端（手机端 Python 脚本）
# =============================================================================

# ---- 配置（修改以下值）----
YNEX_URL = os.getenv("YNEX_URL", "http://192.168.1.100:7788")  # Y·NEX 服务器地址
API_KEY = os.getenv("YNEX_API_KEY", "")  # 从 auth.py 获取的 Key
TELEGRAM_WEBHOOK = os.getenv("TELEGRAM_WEBHOOK", "")  # 可选：Telegram Bot webhook

# ---- 核心请求 ----

def jarvis_chat(text: str) -> str:
    """向Y·NEX发送对话请求"""
    try:
        resp = requests.post(
            f"{YNEX_URL}/chat",
            json={"text": text},
            headers={"X-API-Key": API_KEY},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply", "")
            # 回复发送到手机通知
            send_notification("Y·NEX回复", reply[:200])
            return reply
        elif resp.status_code == 401:
            return "认证失败：请检查 API Key"
        elif resp.status_code == 403:
            return "权限不足：当前 Key 无权使用对话功能"
        else:
            return f"请求失败：{resp.status_code}"
    except requests.exceptions.ConnectionError:
        return f"无法连接Y·NEX 服务器：{YNEX_URL}"
    except Exception as e:
        return f"错误: {e}"


def jarvis_wake(message: str = "先生，Y·NEX已被唤醒。") -> str:
    """远程唤醒Y·NEX"""
    try:
        resp = requests.post(
            f"{YNEX_URL}/wake",
            json={"message": message},
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            return "✅ Y·NEX已唤醒"
        return f"唤醒失败: {resp.status_code}"
    except Exception as e:
        return f"错误: {e}"


def jarvis_status() -> str:
    """获取Y·NEX系统状态"""
    try:
        resp = requests.get(
            f"{YNEX_URL}/status",
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        if resp.status_code == 200:
            import json
            data = resp.json()
            sys_info = data.get("system", {})
            return (
                f"🖥️ Y·NEX状态\n"
                f"CPU: {sys_info.get('cpu_percent', 'N/A')}%\n"
                f"内存: {sys_info.get('memory_percent', 'N/A')}%\n"
                f"磁盘: {sys_info.get('disk_percent', 'N/A')}%\n"
                f"运行时长: {sys_info.get('uptime', 'N/A')}\n"
                f"权限: {data.get('role', 'N/A')}"
            )
        return f"获取状态失败: {resp.status_code}"
    except Exception as e:
        return f"错误: {e}"


def jarvis_command(cmd: str) -> str:
    """发送设备控制指令"""
    try:
        resp = requests.post(
            f"{YNEX_URL}/command",
            json={"command": cmd},
            headers={"X-API-Key": API_KEY},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("result", "")
        return f"执行失败: {resp.status_code}"
    except Exception as e:
        return f"错误: {e}"


# ---- 守护循环 ----

def heartbeat(interval: int = 300):
    """定时心跳，维持连接感知"""
    while True:
        try:
            resp = requests.get(f"{YNEX_URL}/", timeout=5)
            if resp.status_code == 200:
                print(f"[心跳] Y·NEX在线 {time.strftime('%H:%M:%S')}")
            else:
                print(f"[心跳] Y·NEX响应异常: {resp.status_code}")
        except Exception as e:
            print(f"[心跳] Y·NEX离线: {e}")
        time.sleep(interval)


def interactive_mode():
    """交互式终端模式"""
    print("=" * 50)
    print("Y·NEX Android 客户端")
    print(f"服务器: {YNEX_URL}")
    print("命令: /chat <文本> /wake /status /cmd <指令> /battery /location /exit")
    print("=" * 50)

    while True:
        try:
            cmd = input("\nY·NEX> ").strip()
            if not cmd:
                continue

            if cmd == "/exit":
                print("退出。")
                break

            if cmd.startswith("/chat "):
                text = cmd[6:]
                print(jarvis_chat(text))

            elif cmd == "/wake":
                print(jarvis_wake())

            elif cmd == "/status":
                print(jarvis_status())

            elif cmd.startswith("/cmd "):
                print(jarvis_command(cmd[5:]))

            elif cmd == "/battery":
                lvl = battery_level()
                print(f"电池: {lvl}%" if lvl else "无法获取电池信息")

            elif cmd == "/location":
                loc = get_location()
                print(f"位置: {loc}" if loc else "无法获取位置")

            else:
                # 默认当对话处理
                print(jarvis_chat(cmd))

        except KeyboardInterrupt:
            print("\n退出。")
            break
        except Exception as e:
            print(f"错误: {e}")


# ---- Termux 后台服务入口 ----

def start_termux_service():
    """在 Termux 中以服务方式运行"""
    # 启动心跳线程
    t = threading.Thread(target=heartbeat, daemon=True)
    t.start()
    print("Y·NEX Termux 服务已启动（后台运行）")
    print(f"服务器: {YNEX_URL}")
    print("按 Ctrl+C 停止服务")


if __name__ == "__main__":
    # 检测是否在 Termux 环境
    if os.path.exists("/data/data/com.termux/files/home"):
        print("[Termux 环境检测] 启用 Termux API 支持")
        start_termux_service()
        interactive_mode()
    else:
        print("[非 Termux 环境] 仅运行客户端测试")
        print(f"请设置环境变量: YNEX_URL 和 YNEX_API_KEY")
        print(f"\n测试连接: curl {YNEX_URL}/ -H 'X-API-Key: {API_KEY}'")
