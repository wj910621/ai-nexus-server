"""
Y·NEX Desktop 开发模式一键启动
- 启动Y·NEX 核心服务
- 启动 Y·NEX Desktop Electron 桌面端（如果存在）
"""
import os
import sys
import subprocess
import time
import socket

YNEX_PORT = int(os.environ.get("YNEX_PORT", "7777"))
TRIGEN_DIR = r"C:\Users\13111\TriGenClaw"
PYTHON = sys.executable


def is_port_open(port, host="127.0.0.1"):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def wait_for_ynex(timeout=30):
    print("⏳ 等待Y·NEX 服务就绪...")
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(YNEX_PORT):
            print(f"✅ Y·NEX 服务已就绪: http://127.0.0.1:{YNEX_PORT}")
            return True
        time.sleep(0.5)
    print("⚠ Y·NEX 服务启动超时")
    return False


def main():
    print("=" * 60)
    print("  Y·NEX + TriGenClaw 开发模式")
    print("=" * 60)

    # 启动Y·NEX 服务
    print("\n🚀 启动Y·NEX 本地AI核心服务...")
    ynex_proc = subprocess.Popen(
        [PYTHON, "ynex_server.py", "--port", str(YNEX_PORT)],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    if not wait_for_ynex():
        print("❌ Y·NEX 服务启动失败")
        ynex_proc.terminate()
        return

    # 启动 TriGenClaw（如果存在 package.json）
    trigen_pkg = os.path.join(TRIGEN_DIR, "package.json")
    if os.path.exists(trigen_pkg):
        print("\n🚀 启动 TriGenClaw 桌面端...")
        try:
            subprocess.Popen(
                ["npm.cmd", "run", "dev"],
                cwd=TRIGEN_DIR,
                shell=False,
            )
            print(f"✅ TriGenClaw 已启动，工作目录: {TRIGEN_DIR}")
        except Exception as e:
            print(f"⚠ TriGenClaw 启动失败: {e}")
    else:
        print(f"\n⚠ 未找到 TriGenClaw: {TRIGEN_DIR}")

    print("\n按 Ctrl+C 停止所有服务...")
    try:
        ynex_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        ynex_proc.terminate()
        ynex_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
