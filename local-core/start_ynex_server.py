"""
Y·NEX服务一键启动脚本
- 检查Python环境
- 检查核心依赖
- 启动 ynex_server.py
- 可选：自动打开浏览器文档页
"""
import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("YNEX_PORT", "7777"))
# 默认仅监听本地回环，避免局域网/公网任意访问。
# 如需局域网访问，请显式设置 YNEX_HOST=0.0.0.0 并配合防火墙与 Nginx。
HOST = os.environ.get("YNEX_HOST", "127.0.0.1")
PYTHON = sys.executable


def check_dependency(pkg, import_name=None):
    """检查单个依赖是否可用"""
    name = import_name or pkg
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def ensure_dependencies():
    """确保核心依赖已安装"""
    core_deps = [
        ("flask", "flask"),
        ("flask-cors", "flask_cors"),
        ("waitress", "waitress"),
        ("requests", "requests"),
        ("ollama", "ollama"),
        ("psutil", "psutil"),
        ("pyautogui", "pyautogui"),
        ("pyperclip", "pyperclip"),
        ("pynput", "pynput"),
        ("openai", "openai"),
        ("loguru", "loguru"),
        ("pydantic-settings", "pydantic_settings"),
        ("python-dotenv", "dotenv"),
        ("chromadb", "chromadb"),
        ("sentence-transformers", "sentence_transformers"),
    ]

    missing = []
    for pkg, imp in core_deps:
        if not check_dependency(pkg, imp):
            missing.append(pkg)

    if missing:
        print("⚠ 缺少以下核心依赖:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\n正在自动安装...")
        try:
            subprocess.check_call([PYTHON, "-m", "pip", "install", "-U"] + missing)
            print("✅ 依赖安装完成\n")
        except Exception as e:
            print(f"❌ 依赖安装失败: {e}")
            print("请手动运行: pip install -r requirements.txt")
            sys.exit(1)
    else:
        print("✅ 所有核心依赖已就绪")


def wait_for_server(port, timeout=30):
    """等待服务就绪"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    print("=" * 60)
    print("  Y·NEX服务启动器")
    print("=" * 60)

    ensure_dependencies()

    print(f"\n🚀 启动Y·NEX 本地AI核心服务...")
    print(f"   地址: http://{HOST}:{PORT}")
    print(f"   文档: http://127.0.0.1:{PORT}/docs")
    print("-" * 60)

    try:
        proc = subprocess.Popen(
            [PYTHON, "ynex_server.py", "--port", str(PORT), "--host", HOST],
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        print("⏳ 等待服务就绪...")
        if wait_for_server(PORT, timeout=30):
            print(f"✅ 服务已就绪: http://127.0.0.1:{PORT}")
            # 自动打开文档页
            if os.environ.get("YNEX_OPEN_BROWSER", "1") == "1":
                webbrowser.open(f"http://127.0.0.1:{PORT}/docs")
        else:
            print("⚠ 服务启动超时，请检查日志")

        try:
            proc.wait()
        except KeyboardInterrupt:
            print("\n🛑 收到中断信号，正在停止服务...")
            proc.terminate()
            proc.wait(timeout=5)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
