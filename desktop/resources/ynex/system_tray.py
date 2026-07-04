"""
系统托盘与全局热键模块
让Y·NEX可以常驻后台，通过全局快捷键 Ctrl+Shift+J 唤醒输入框。

依赖：
- pynput：全局热键
- tkinter：内置输入对话框
- pystray（可选）：系统托盘图标
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import simpledialog

from logger import logger


HOTKEY = "<ctrl>+<shift>+j"
_input_callback = None
_exit_callback = None
_tray_icon = None
_hotkey_listener = None


def set_callbacks(input_callback, exit_callback=None):
    """设置回调函数"""
    global _input_callback, _exit_callback
    _input_callback = input_callback
    _exit_callback = exit_callback


def _show_input_dialog():
    """显示输入对话框"""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    user_input = simpledialog.askstring("Y·NEX", "先生，请吩咐：", parent=root)
    root.destroy()

    if user_input and _input_callback:
        try:
            threading.Thread(target=_input_callback, args=(user_input,), daemon=True).start()
        except Exception as e:
            logger.error(f"处理输入失败：{e}")


def _on_hotkey():
    """热键触发"""
    logger.info("全局热键触发")
    try:
        _show_input_dialog()
    except Exception as e:
        logger.error(f"显示输入框失败：{e}")


def _start_hotkey_listener():
    """启动全局热键监听"""
    global _hotkey_listener

    try:
        from pynput import keyboard

        def for_canonical(f):
            return lambda k: f(listener.canonical(k))

        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(HOTKEY),
            _on_hotkey
        )

        with keyboard.Listener(
            on_press=for_canonical(hotkey.press),
            on_release=for_canonical(hotkey.release)
        ) as listener:
            _hotkey_listener = listener
            logger.info(f"全局热键已注册：{HOTKEY}")
            listener.join()

    except Exception as e:
        logger.warning(f"全局热键启动失败：{e}。请安装 pynput 库。")


def _create_menu():
    """创建托盘菜单"""
    try:
        from pystray import MenuItem

        return (
            MenuItem("输入指令", lambda icon, item: _show_input_dialog()),
            MenuItem("退出", lambda icon, item: stop_tray()),
        )
    except Exception as e:
        logger.warning(f"创建托盘菜单失败：{e}")
        return None


def _create_default_icon():
    """生成默认图标（蓝底白字 J）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        size = 64
        image = Image.new("RGB", (size, size), color="#1E90FF")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "J", font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) / 2
        y = (size - text_height) / 2 - 5
        draw.text((x, y), "J", font=font, fill="white")
        return image
    except Exception as e:
        logger.warning(f"生成图标失败：{e}")
        return None


def _start_tray_icon():
    """启动系统托盘图标"""
    global _tray_icon

    try:
        import pystray
        from PIL import Image

        icon_image = _create_default_icon()
        if icon_image is None:
            logger.warning("无法创建托盘图标，跳过系统托盘。")
            return

        menu = _create_menu()
        _tray_icon = pystray.Icon("ynex", icon_image, "Y·NEX", menu)
        logger.info("系统托盘已启动")
        _tray_icon.run()

    except ImportError:
        logger.warning("未安装 pystray/PIL，系统托盘不可用。全局热键仍可用。")
    except Exception as e:
        logger.error(f"系统托盘启动失败：{e}")


def start_tray_and_hotkey(input_callback=None, exit_callback=None):
    """启动托盘图标与全局热键"""
    if input_callback:
        set_callbacks(input_callback, exit_callback)

    # 全局热键
    t_hotkey = threading.Thread(target=_start_hotkey_listener, daemon=True)
    t_hotkey.start()

    # 系统托盘
    t_tray = threading.Thread(target=_start_tray_icon, daemon=True)
    t_tray.start()


def stop_tray():
    """停止托盘与热键"""
    global _tray_icon, _hotkey_listener

    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass

    if _hotkey_listener:
        try:
            _hotkey_listener.stop()
        except Exception:
            pass

    if _exit_callback:
        try:
            _exit_callback()
        except Exception:
            pass

    logger.info("系统托盘与热键已停止")


if __name__ == "__main__":
    def on_input(text):
        print(f"收到输入：{text}")

    start_tray_and_hotkey(on_input)
    input("按回车退出...\n")
