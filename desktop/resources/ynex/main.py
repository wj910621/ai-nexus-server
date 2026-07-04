"""
Y·NEX AI 管家 - 主入口
用法：
  python main.py --gui               启动 3D 粒子可视化界面（默认）
  python main.py --text              文本对话
  python main.py --text --mock-llm   测试模式，无需 API Key
  python main.py --text --tray       后台托盘模式
  python main.py --check             仅检查状态
  python main.py --light             轻量模式

首次使用请先运行：
  python setup.py                    交互式安装配置
"""

import sys
import os

# 轻量模式：关闭重后台任务以节省笔记本资源
USE_LIGHT_MODE = "--light" in sys.argv
IS_TEXT_MODE = "--text" in sys.argv

# 语音引擎唤醒事件（由后台语音引擎设置，主循环等待）
_wake_event = None


def _banner():
    """启动横幅"""
    print("""
╔══════════════════════════════════════════════╗
║       Y·NEX AI 管家  v2.0                     ║
║       您的私人智能助手                        ║
╚══════════════════════════════════════════════╝
    """.strip())


def _load_essential():
    """加载核心模块（同步导入）"""
    from config import settings, validate_config
    from logger import logger
    from memory import get_memory, save_memory
    from brain import get_ai_response
    return settings, logger, get_ai_response


def _start_background_services():
    """启动后台服务（全部独立线程，互不影响）"""
    from logger import logger

    services = {}
    errors = []

    # 定时调度器
    try:
        from scheduler import get_scheduler, set_reminder_callback, add_daily_report_job

        def _reminder_callback(msg: str):
            try:
                from speech import speak
                speak(msg)
            except Exception:
                print(f"\n⏰ 提醒: {msg}")

        set_reminder_callback(_reminder_callback)
        get_scheduler()
        add_daily_report_job(9, 0)
        services["定时调度器"] = "✓"
    except Exception as e:
        errors.append(f"定时调度器: {e}")
        services["定时调度器"] = "✗"

    # 自动化规则引擎
    try:
        from automation_engine import start_engine
        start_engine()
        services["自动化引擎"] = "✓"
    except Exception as e:
        errors.append(f"自动化引擎: {e}")
        services["自动化引擎"] = "✗"

    # HTTP API 服务器
    try:
        from api_server import start_api_server
        start_api_server()
        services["HTTP API"] = "✓"
    except Exception as e:
        errors.append(f"HTTP API: {e}")
        services["HTTP API"] = "✗"

    # Telegram Bot
    try:
        from telegram_bot import start_bot
        start_bot()
        services["Telegram Bot"] = "✓"
    except Exception as e:
        errors.append(f"Telegram Bot: {e}")
        services["Telegram Bot"] = "✗"

    # 远程语音通道
    try:
        from remote_voice import start_remote_voice_server
        start_remote_voice_server()
        services["远程语音"] = "✓"
    except Exception as e:
        errors.append(f"远程语音: {e}")
        services["远程语音"] = "✗"

    # 新版语音交互引擎（后台唤醒词监听）
    try:
        from voice_engine import start_voice_engine
        import threading

        global _wake_event
        _wake_event = threading.Event()

        def _on_wake(word):
            _wake_event.set()
            try:
                from speech import speak
                speak("我在，先生。")
            except Exception:
                pass

        start_voice_engine(
            wake_words=["hey_jarvis"],
            sensitivity=0.5,
            on_wake=_on_wake,
        )
        services["语音引擎"] = "✓"
    except Exception as e:
        errors.append(f"语音引擎: {e}")
        services["语音引擎"] = "✗"

    # 轻量模式跳过重后台任务
    if not USE_LIGHT_MODE:
        # 剪贴板监听
        try:
            from clipboard_listener import start_clipboard_listener
            start_clipboard_listener()
            services["剪贴板监听"] = "✓"
        except Exception as e:
            errors.append(f"剪贴板监听: {e}")
            services["剪贴板监听"] = "✗"

        # PC 自动化增强（状态轮询 + 全局热键）
        try:
            from pc_automation import start_state_polling, register_hotkey
            start_state_polling(interval=3.0)
            # Ctrl+Shift+Y 语音播报最近剪贴板
            def _hotkey_ynex_clipboard():
                try:
                    from pc_automation import get_clipboard_history
                    from speech import speak
                    items = get_clipboard_history(3)
                    speak(f"最近复制了 {len(items)} 条内容")
                except Exception:
                    pass
            register_hotkey("<ctrl>+<shift>+y", _hotkey_ynex_clipboard)
            services["PC 自动化"] = "✓"
        except Exception as e:
            errors.append(f"PC 自动化: {e}")
            services["PC 自动化"] = "✗"

        # ESP32 传感器
        try:
            from esp_sensors import start_sensor_listener
            start_sensor_listener()
            services["传感器监听"] = "✓"
        except Exception as e:
            errors.append(f"传感器监听: {e}")
            services["传感器监听"] = "✗"

        # 视觉感知（重负载）
        try:
            from vision import start_vision_guard
            start_vision_guard(interval=15.0)  # 15秒巡检，降低 CPU
            services["视觉守护"] = "✓"
        except Exception as e:
            errors.append(f"视觉守护: {e}")
            services["视觉守护"] = "✗"
    else:
        services["剪贴板监听"] = "⊘ (轻量模式)"
        services["PC 自动化"] = "⊘ (轻量模式)"
        services["传感器监听"] = "⊘ (轻量模式)"
        services["视觉守护"] = "⊘ (轻量模式)"

    return services, errors


def _show_startup_status(services: dict, errors: list):
    """显示启动状态"""
    from logger import logger

    print("\n启动状态：")
    for name, status in services.items():
        prefix = "  "
        if status == "✓":
            print(f"{prefix}✓ {name}")
        elif status == "✗":
            print(f"{prefix}✗ {name}")
        else:
            print(f"{prefix}⊘ {name}")

    if errors:
        print(f"\n后台服务异常（不影响核心功能）：")
        for err in errors:
            logger.warning(f"  {err}")

    ready = sum(1 for v in services.values() if v == "✓")
    total = len(services)
    print(f"\n后台服务: {ready}/{total} 就绪")


def _check_config(use_mock: bool):
    """配置检查"""
    if use_mock:
        return

    try:
        from config import validate_config
        issues = validate_config()
        if issues:
            print("⚠️  配置提醒：")
            for issue in issues:
                print(f"  - {issue}")
    except Exception:
        pass


def _listen_text():
    """文本输入"""
    try:
        return input("\n先生: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _main_loop():
    """主对话循环"""
    from speech import speak, listen
    from brain import get_ai_response
    from wake_word import wait_for_wake_word, _PORCUPINE_AVAILABLE

    use_text_mode = IS_TEXT_MODE
    use_mock = "--mock-llm" in sys.argv
    use_tray = "--tray" in sys.argv

    print("\n💬 进入对话模式（输入 q/退出 结束）")

    if use_tray:
        try:
            from system_tray import start_tray_and_hotkey

            def _on_tray_input(text: str):
                reply = get_ai_response(text, use_mock=use_mock)
                print(f"\nY·NEX: {reply}")
                try:
                    speak(reply)
                except Exception:
                    pass

            start_tray_and_hotkey(
                input_callback=_on_tray_input,
                exit_callback=lambda: sys.exit(0)
            )
            print("✓ 系统托盘已启动（Ctrl+Shift+J 唤醒）")
        except Exception as e:
            print(f"托盘启动失败: {e}")

    if use_mock:
        print("🔧 Mock LLM 模式（无需 API Key）")

    while True:
        # 唤醒词（仅语音模式）
        if not use_text_mode:
            try:
                global _wake_event
                if _wake_event is not None:
                    # 新版后台语音引擎：等待唤醒事件
                    _wake_event.wait(timeout=None)
                    _wake_event.clear()
                elif _PORCUPINE_AVAILABLE:
                    # 旧版阻塞式唤醒词
                    wait_for_wake_word()
                    speak("我在，先生。")
                else:
                    # 无唤醒引擎，降级文本
                    use_text_mode = True
                    continue
            except Exception:
                use_text_mode = True
                continue

        # 获取输入
        if use_text_mode:
            user_input = _listen_text()
        else:
            try:
                user_input = listen()
            except Exception as e:
                from logger import logger
                logger.error(f"语音识别失败: {e}")
                user_input = ""

        if not user_input:
            continue

        if user_input.lower() in ["q", "退出", "关闭", "再见", "休眠"]:
            print("Y·NEX: 随时待命，先生。")
            try:
                from scheduler import shutdown_scheduler
                shutdown_scheduler()
            except Exception:
                pass
            break

        try:
            reply = get_ai_response(user_input, use_mock=use_mock)
        except Exception as e:
            from logger import logger
            logger.exception("AI 回复失败")
            reply = "先生，处理时出了点问题。"

        if use_text_mode:
            print(f"Y·NEX: {reply}")
        else:
            try:
                speak(reply)
            except Exception:
                print(f"Y·NEX: {reply}")


def _launch_gui(use_mock: bool):
    """启动 3D 粒子可视化界面"""
    global IS_TEXT_MODE
    print("\n🎨 启动 3D 粒子可视化界面...")
    try:
        from gui.particle_window import launch_gui
        launch_gui(use_mock=use_mock)
    except Exception as e:
        print(f"⚠️  GUI 启动失败，降级到文本模式: {e}")
        IS_TEXT_MODE = True
        _main_loop()


def main():
    global IS_TEXT_MODE
    # 状态检查
    if "--check" in sys.argv:
        from setup import full_check
        full_check()
        return

    use_mock = "--mock-llm" in sys.argv
    use_gui = "--gui" in sys.argv

    # 默认模式：如果有 GUI 环境，优先启动 GUI
    if not IS_TEXT_MODE and not use_gui and not use_mock:
        try:
            from PyQt6 import QtWidgets
            use_gui = True
        except ImportError:
            use_gui = False
            IS_TEXT_MODE = True

    if not use_gui:
        _banner()

    # 配置检查
    _check_config(use_mock)

    # 启动后台服务
    if not use_gui:
        print("\n🚀 启动后台服务...")
    services, errors = _start_background_services()
    if not use_gui:
        _show_startup_status(services, errors)

    # 启动 GUI 或主循环
    if use_gui:
        _launch_gui(use_mock)
    else:
        # 启动语音（失败则降级为文本）
        if not IS_TEXT_MODE:
            try:
                from speech import speak
                speak("Y·NEX系统在线，先生。")
            except Exception as e:
                print(f"⚠️  语音启动失败，自动切换文本模式: {e}")
                IS_TEXT_MODE = True

        print("\n" + "─" * 40)
        _main_loop()


if __name__ == "__main__":
    main()
