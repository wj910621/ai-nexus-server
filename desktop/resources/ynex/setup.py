#!/usr/bin/env python3
"""
Y·NEX AI 管家 - 一键安装与配置脚本
自动检测依赖、引导配置、运行自检。

用法：
  python setup.py               # 交互式安装
  python setup.py --check       # 仅检查状态
  python setup.py --install     # 直接安装依赖
  python setup.py --env        # 仅生成 .env 文件
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / ".env"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"


def run_cmd(cmd: list, env=None, cwd=None):
    """执行命令，返回 (success, stdout+stderr)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env or os.environ,
            cwd=cwd or PROJECT_ROOT,
            timeout=120,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as e:
        return False, str(e)


def green(msg): print(f"\033[92m✓ {msg}\033[0m")
def red(msg): print(f"\033[91m✗ {msg}\033[0m")
def yellow(msg): print(f"\033[93m⚠ {msg}\033[0m")
def info(msg): print(f"\033[94mℹ {msg}\033[0m")


# =============================================================================
# 依赖检测与安装
# =============================================================================

ESSENTIAL_DEPS = [
    ("requests", "requests"),
    ("openai", "openai"),
    ("SpeechRecognition", "SpeechRecognition"),
    ("edge-tts", "edge-tts"),
    ("pygame", "pygame"),
    ("loguru", "loguru"),
    ("python-dotenv", "python-dotenv"),
    ("pydantic-settings", "pydantic-settings"),
]

OPTIONAL_DEPS = [
    ("opencv-python", "opencv-python"),
    ("mediapipe", "mediapipe"),
    ("psutil", "psutil"),
    ("chromadb", "chromadb"),
    ("sentence-transformers", "sentence-transformers"),
    ("PyQt6", "PyQt6"),
    ("APScheduler", "APScheduler"),
    ("playwright", "playwright"),
    ("pyautogui", "pyautogui"),
    ("pyperclip", "pyperclip"),
    ("pygetwindow", "pygetwindow"),
    ("pynput", "pynput"),
    ("paho-mqtt", "paho-mqtt"),
    ("flask", "flask"),
    ("pystray", "pystray"),
    ("pillow", "pillow"),
    ("python-telegram-bot", "python-telegram-bot"),
    ("noisereduce", "noisereduce"),
    ("webrtcvad", "webrtcvad"),
    ("openwakeword", "openwakeword"),
    ("sounddevice", "sounddevice"),
    ("numpy", "numpy"),
]

EXTRA_LINUX_DEPS = [
    ("portaudio19-dev", "alsa"),
    ("libasound2-dev", "alsa"),
]


def check_dependency(name: str, import_name: str) -> bool:
    """检测单个依赖是否可用"""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def check_all_dependencies():
    """检查所有依赖状态"""
    info("\n=== 依赖检测 ===")

    essential_ok = 0
    optional_ok = 0
    missing = []

    for name, import_name in ESSENTIAL_DEPS:
        if check_dependency(name, import_name):
            green(f"核心 {name}")
            essential_ok += 1
        else:
            red(f"核心 {name} (缺失)")
            missing.append(name)

    for name, import_name in OPTIONAL_DEPS:
        if check_dependency(name, import_name):
            green(f"可选 {name}")
            optional_ok += 1
        else:
            yellow(f"可选 {name} (未安装)")

    print(f"\n核心依赖: {essential_ok}/{len(ESSENTIAL_DEPS)} 已就绪")
    print(f"可选依赖: {optional_ok}/{len(OPTIONAL_DEPS)} 已安装")
    if missing:
        print(f"\n缺失核心依赖: {', '.join(missing)}")
    return len(missing) == 0


def install_missing():
    """安装缺失的依赖"""
    print("\n=== 安装依赖 ===")
    missing = []
    for name, import_name in ESSENTIAL_DEPS + OPTIONAL_DEPS:
        if not check_dependency(name, import_name):
            missing.append(name)

    if not missing:
        green("所有依赖已就绪，无需安装")
        return True

    print(f"将安装 {len(missing)} 个缺失包...")
    # 批量安装
    pkgs = " ".join(missing)
    ok, out = run_cmd([sys.executable, "-m", "pip", "install", "-q", pkgs])
    if ok:
        green(f"成功安装 {len(missing)} 个包")
        return True
    else:
        red(f"安装失败: {out}")
        return False


# =============================================================================
# 配置引导
# =============================================================================

def guess_env_var(key: str, current: str) -> str:
    """从当前 .env 或环境变量猜测默认值"""
    if current:
        return current
    return os.environ.get(key, "")


def load_existing_env() -> dict:
    """读取现有 .env 配置"""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def save_env(env: dict):
    """保存配置到 .env"""
    lines = ["# Y·NEX AI 管家配置", "# 请勿将敏感信息泄露给他人", ""]
    for key, value in env.items():
        if value:
            lines.append(f'{key}="{value}"')
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")
    green(f"配置已保存到 {ENV_FILE}")


def guess_defaults():
    """从当前环境猜测默认配置"""
    env = load_existing_env()
    result = {}

    result["DEEPSEEK_API_KEY"] = guess_env_var("DEEPSEEK_API_KEY", env.get("DEEPSEEK_API_KEY", ""))
    result["HOME_ASSISTANT_URL"] = guess_env_var("HOME_ASSISTANT_URL", env.get("HOME_ASSISTANT_URL", ""))
    result["HOME_ASSISTANT_TOKEN"] = guess_env_var("HOME_ASSISTANT_TOKEN", env.get("HOME_ASSISTANT_TOKEN", ""))
    result["TELEGRAM_BOT_TOKEN"] = guess_env_var("TELEGRAM_BOT_TOKEN", env.get("TELEGRAM_BOT_TOKEN", ""))
    result["PAPERLESS_URL"] = guess_env_var("PAPERLESS_URL", env.get("PAPERLESS_URL", ""))
    result["PAPERLESS_TOKEN"] = guess_env_var("PAPERLESS_TOKEN", env.get("PAPERLESS_TOKEN", ""))
    result["IMMICH_URL"] = guess_env_var("IMMICH_URL", env.get("IMMICH_URL", ""))
    result["IMMICH_API_KEY"] = guess_env_var("IMMICH_API_KEY", env.get("IMMICH_API_KEY", ""))
    result["N8N_URL"] = guess_env_var("N8N_URL", env.get("N8N_URL", ""))
    result["N8N_API_KEY"] = guess_env_var("N8N_API_KEY", env.get("N8N_API_KEY", ""))
    result["LOCAL_BASE_URL"] = guess_env_var("LOCAL_BASE_URL", env.get("LOCAL_BASE_URL", "http://localhost:11434"))

    return result


def interactive_setup():
    """交互式配置引导"""
    print("\n" + "=" * 50)
    print("Y·NEX AI 管家 - 配置向导")
    print("=" * 50)
    print("按 Enter 使用默认值（已有值），输入新值覆盖。\n")

    defaults = guess_defaults()
    env = {}

    questions = [
        ("DEEPSEEK_API_KEY", "DeepSeek API Key（核心必需，用于 AI 对话）", True),
        ("HOME_ASSISTANT_URL", "Home Assistant URL（如 http://192.168.1.100:8123）", False),
        ("HOME_ASSISTANT_TOKEN", "Home Assistant Long-Lived Access Token", False),
        ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token（/newbot 获取，全球通用控制）", False),
        ("PAPERLESS_URL", "Paperless-ngx URL（文档管理）", False),
        ("PAPERLESS_TOKEN", "Paperless API Token", False),
        ("IMMICH_URL", "Immich URL（相册管理）", False),
        ("IMMICH_API_KEY", "Immich API Key", False),
        ("N8N_URL", "n8n URL（工作流自动化）", False),
        ("N8N_API_KEY", "n8n API Key", False),
        ("LOCAL_BASE_URL", "Ollama 本地地址（可选，如 http://localhost:11434）", False),
    ]

    for key, question, required in questions:
        default = defaults.get(key, "")
        prompt = f"\n{question}"
        if required:
            prompt += " [必填]"
        if default:
            prompt += f"\n  当前: {default[:20]}{'***' if len(default) > 20 else ''}"
        prompt += "\n  新值: "

        try:
            value = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n配置取消。")
            sys.exit(0)

        env[key] = value or default

    save_env(env)
    return env


# =============================================================================
# 核心功能自检
# =============================================================================

def check_imports():
    """检测核心模块导入"""
    info("\n=== 模块导入检查 ===")
    modules = [
        ("config", "配置"),
        ("memory", "记忆"),
        ("brain", "AI大脑"),
        ("skills", "技能"),
        ("speech", "语音"),
        ("automation_engine", "自动化引擎"),
        ("api_server", "API服务"),
        ("auth", "认证"),
        ("telegram_bot", "Telegram Bot"),
        ("mqtt_bus", "MQTT总线"),
        ("device_hub", "设备中枢"),
        ("selfhost", "自托管服务"),
        ("vision", "视觉感知"),
        ("far_field_mic", "远场麦克风"),
        ("wake_word_zh", "唤醒词"),
        ("esp_sensors", "传感器"),
        ("clipboard_listener", "剪贴板"),
        ("remote_voice", "远程语音"),
        ("pc_control", "PC控制"),
        ("home_assistant", "Home Assistant"),
        ("scheduler", "调度器"),
        ("knowledge_base", "知识库"),
    ]

    ok_count = 0
    fail_count = 0
    for module, desc in modules:
        try:
            __import__(module)
            green(f"{desc} ({module})")
            ok_count += 1
        except ImportError as e:
            red(f"{desc} ({module}): {e}")
            fail_count += 1
        except Exception as e:
            yellow(f"{desc} ({module}): 其他错误 - {e}")
            ok_count += 1

    print(f"\n模块: {ok_count} 正常, {fail_count} 失败")
    return fail_count == 0


def check_deepseek_api():
    """检测 DeepSeek API 是否可用"""
    info("\n=== DeepSeek API 检测 ===")
    try:
        from config import settings
        key = settings.deepseek_api_key
        if not key:
            yellow("未配置 DeepSeek API Key，跳过 API 测试")
            return None

        import requests
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
            timeout=15,
        )
        if resp.status_code == 200:
            green("DeepSeek API 连接正常")
            return True
        else:
            red(f"API 返回 {resp.status_code}: {resp.text[:100]}")
            return False
    except Exception as e:
        red(f"API 检测失败: {e}")
        return False


def check_local_ollama():
    """检测 Ollama 本地模型"""
    info("\n=== 本地 Ollama 检测 ===")
    try:
        from config import settings
        url = settings.local_base_url
        if not url:
            yellow("未配置 Ollama，跳过")
            return None

        import requests
        resp = requests.get(f"{url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            green(f"Ollama 连接正常 ({len(models)} 个模型)")
            for m in models[:3]:
                info(f"  - {m.get('name', 'unknown')}")
            return True
        else:
            yellow(f"Ollama 返回 {resp.status_code}")
            return False
    except Exception as e:
        yellow(f"Ollama 未运行: {e}")
        return False


def check_home_assistant():
    """检测 Home Assistant 连接"""
    info("\n=== Home Assistant 检测 ===")
    try:
        from config import settings
        if not settings.home_assistant_url:
            yellow("未配置 Home Assistant")
            return None

        import requests
        resp = requests.get(
            f"{settings.home_assistant_url}/api/states",
            headers={"Authorization": f"Bearer {settings.home_assistant_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            entities = len(resp.json())
            green(f"Home Assistant 连接正常 ({entities} 个实体)")
            return True
        else:
            red(f"HA 返回 {resp.status_code}")
            return False
    except Exception as e:
        yellow(f"HA 连接失败: {e}")
        return False


def check_telegram():
    """检测 Telegram Bot Token"""
    info("\n=== Telegram Bot 检测 ===")
    try:
        from config import settings
        token = settings.telegram_bot_token
        if not token:
            yellow("未配置 Telegram Bot Token")
            return None

        import requests
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                green(f"Telegram Bot 正常: @{data['result']['username']}")
                return True
        red(f"Bot Token 无效: {resp.text[:100]}")
        return False
    except Exception as e:
        yellow(f"Telegram 检测失败: {e}")
        return None


def check_ports():
    """检查端口占用"""
    import socket
    info("\n=== 端口检测 ===")
    ports = {
        "7788": "HTTP API",
        "7799": "远程语音",
        "1883": "MQTT",
    }
    for port, name in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", int(port)))
            sock.close()
            green(f"{name} 端口 {port} 可用")
        except OSError:
            yellow(f"{name} 端口 {port} 已被占用")


def check_hardware():
    """检测硬件能力"""
    info("\n=== 硬件检测 ===")

    # 摄像头
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            green("摄像头 已就绪")
            cap.release()
        else:
            yellow("摄像头 无法打开（请检查是否被其他程序占用）")
    except ImportError:
        yellow("opencv-python 未安装，无法检测摄像头")
    except Exception as e:
        yellow(f"摄像头检测失败: {e}")

    # 麦克风
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev["maxInputChannels"] > 0:
                green(f"麦克风 {i}: {dev['name'][:50]}")
                break
        p.terminate()
    except ImportError:
        yellow("pyaudio 未安装，无法检测麦克风")
    except Exception as e:
        yellow(f"麦克风检测失败: {e}")


def check_data_dirs():
    """检查数据目录"""
    info("\n=== 数据目录 ===")
    dirs = ["data", "data/snapshots", "data/knowledge", "logs"]
    for d in dirs:
        path = PROJECT_ROOT / d
        if path.exists():
            green(f"{d}/ 存在")
        else:
            path.mkdir(parents=True, exist_ok=True)
            green(f"{d}/ 已创建")


# =============================================================================
# 一键自检报告
# =============================================================================

def full_check():
    """完整自检"""
    print("\n" + "=" * 55)
    print("  Y·NEX AI 管家 - 系统状态自检")
    print("=" * 55)

    check_data_dirs()
    deps_ok = check_all_dependencies()
    imports_ok = check_imports()

    api_ok = check_deepseek_api()
    ollama_ok = check_local_ollama()
    ha_ok = check_home_assistant()
    tg_ok = check_telegram()
    check_ports()
    check_hardware()

    print("\n" + "=" * 55)
    print("  自检报告摘要")
    print("=" * 55)

    items = [
        ("核心依赖", deps_ok, deps_ok is True or deps_ok is None),
        ("模块导入", imports_ok, True),
        ("DeepSeek API", api_ok, api_ok is not False),
        ("Ollama 本地", ollama_ok, True),
        ("Home Assistant", ha_ok, True),
        ("Telegram Bot", tg_ok, True),
    ]

    all_pass = True
    for name, result, acceptable in items:
        if result is True:
            green(f"{name}: 正常")
        elif result is False:
            red(f"{name}: 失败")
            all_pass = False
        else:
            yellow(f"{name}: 未配置")

    if all_pass:
        print("\n✅ 系统就绪，可以启动！")
        print("\n启动方式：")
        print("  python main.py --text              # 文本对话模式")
        print("  python main.py --text --mock-llm   # 测试模式（无需 API Key）")
        print("  python main.py --text --tray       # 后台托盘模式")
    else:
        print("\n⚠️  部分模块异常，修复后体验更佳")

    return all_pass


# =============================================================================
# 入口
# =============================================================================

def main():
    args = set(sys.argv[1:])

    if "--check" in args:
        full_check()
        return

    if "--install" in args:
        install_missing()
        full_check()
        return

    if "--env" in args:
        interactive_setup()
        return

    # 完整流程
    print("\n" + "=" * 55)
    print("  Y·NEX AI 管家 - 初始化安装")
    print("=" * 55)

    # Step 1: 安装依赖
    install_missing()

    # Step 2: 配置引导
    env = load_existing_env()
    if env:
        print(f"\n检测到已有 .env 配置，共 {len(env)} 项。")
        try:
            ans = input("重新配置？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans == "y":
            interactive_setup()
    else:
        interactive_setup()

    # Step 3: 自检
    full_check()

    print("\n" + "=" * 55)
    print("  安装完成！")
    print("=" * 55)
    print("\n下一步：")
    print("  1. 配置 Telegram Bot（如需手机控制）")
    print("  2. 配置 Home Assistant（如已有智能家居）")
    print("  3. 运行: python main.py --text --mock-llm  测试")
    print("  4. 没问题后: python main.py --text  正式运行")


if __name__ == "__main__":
    main()
