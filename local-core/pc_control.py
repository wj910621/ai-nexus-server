"""
电脑控制模块
让Y·NEX能接管 Windows PC：窗口、键鼠、剪贴板、音量、电源、进程等。
所有依赖均做懒加载和优雅降级，未安装库时返回友好提示。
"""

import os
import re
import subprocess
import time
from typing import List, Dict, Optional

from logger import logger


# ---------------- 应用/进程 ----------------


def list_running_apps() -> str:
    """列出正在运行的前台应用窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getAllWindows()
        visible = [w for w in wins if w.title.strip() and w.visible]
        lines = []
        for w in visible[:20]:
            lines.append(f"- {w.title}")
        if not lines:
            return "先生，当前没有可见窗口。"
        return "先生，当前可见窗口：\n" + "\n".join(lines)
    except Exception as e:
        return f"先生，列出窗口失败：{e}"


def find_window(keyword: str) -> Optional[Dict[str, any]]:
    """按标题关键词查找窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(keyword)
        if wins:
            w = wins[0]
            return {"title": w.title, "left": w.left, "top": w.top, "width": w.width, "height": w.height}
        return None
    except Exception:
        return None


def activate_window(name: str) -> str:
    """激活指定窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(name)
        if not wins:
            return f"先生，未找到标题包含「{name}」的窗口。"
        wins[0].activate()
        return f"先生，已激活窗口「{wins[0].title}」。"
    except Exception as e:
        return f"先生，激活窗口失败：{e}"


def minimize_window(name: str) -> str:
    """最小化窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(name)
        if not wins:
            return f"先生，未找到窗口「{name}」。"
        wins[0].minimize()
        return f"先生，已最小化「{wins[0].title}」。"
    except Exception as e:
        return f"先生，最小化失败：{e}"


def maximize_window(name: str) -> str:
    """最大化窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(name)
        if not wins:
            return f"先生，未找到窗口「{name}」。"
        wins[0].maximize()
        return f"先生，已最大化「{wins[0].title}」。"
    except Exception as e:
        return f"先生，最大化失败：{e}"


def close_window(name: str) -> str:
    """关闭窗口"""
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(name)
        if not wins:
            return f"先生，未找到窗口「{name}」。"
        wins[0].close()
        return f"先生，已关闭「{wins[0].title}」。"
    except Exception as e:
        return f"先生，关闭窗口失败：{e}"


def list_processes(keyword: str = "") -> str:
    """列出进程"""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name"]):
            name = p.info["name"] or ""
            if not keyword or keyword.lower() in name.lower():
                procs.append(f"{p.info['pid']}: {name}")
            if len(procs) >= 15:
                break
        if not procs:
            return f"先生，未找到匹配「{keyword}」的进程。"
        return "先生，进程列表：\n" + "\n".join(procs)
    except Exception as e:
        return f"先生，列出进程失败：{e}"


def kill_process(name: str) -> str:
    """结束指定名称的进程"""
    try:
        import psutil
        killed = 0
        for p in psutil.process_iter(["pid", "name"]):
            if p.info["name"] and name.lower() in p.info["name"].lower():
                p.terminate()
                killed += 1
        if killed:
            return f"先生，已结束 {killed} 个「{name}」进程。"
        return f"先生，未找到「{name}」进程。"
    except Exception as e:
        return f"先生，结束进程失败：{e}"


# ---------------- 键鼠与剪贴板 ----------------


def type_text(text: str, interval: float = 0.01) -> str:
    """在当前焦点处输入文本"""
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=interval)
        return f"先生，已输入「{text[:30]}{'...' if len(text) > 30 else ''}」。"
    except Exception as e:
        return f"先生，输入文本失败：{e}"


def press_key(keys: str) -> str:
    """按下组合键，如 ctrl+c、alt+tab、win+d"""
    try:
        import pyautogui
        parts = keys.lower().replace("win", "command").split("+")
        pyautogui.hotkey(*parts)
        return f"先生，已按下「{keys}」。"
    except Exception as e:
        return f"先生，按键失败：{e}"


def click_mouse(x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> str:
    """鼠标点击，未指定坐标则点击当前位置"""
    try:
        import pyautogui
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
            return f"先生，已在 ({x}, {y}) 点击{button}键。"
        pyautogui.click(button=button)
        return f"先生，已点击{button}键。"
    except Exception as e:
        return f"先生，鼠标点击失败：{e}"


def take_screenshot(save_path: str = "data/screenshot.png") -> str:
    """截屏并保存"""
    try:
        import pyautogui
        os.makedirs(os.path.dirname(save_path) or "data", exist_ok=True)
        img = pyautogui.screenshot()
        img.save(save_path)
        return f"先生，已截图并保存到 {save_path}。"
    except Exception as e:
        return f"先生，截图失败：{e}"


def get_clipboard() -> str:
    """读取剪贴板"""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "先生，剪贴板为空。"
        return f"先生，剪贴板内容：\n{text[:500]}{'...' if len(text) > 500 else ''}"
    except Exception as e:
        return f"先生，读取剪贴板失败：{e}"


def set_clipboard(text: str) -> str:
    """写入剪贴板"""
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"先生，已将「{text[:50]}{'...' if len(text) > 50 else ''}」写入剪贴板。"
    except Exception as e:
        return f"先生，写入剪贴板失败：{e}"


# ---------------- 系统控制 ----------------


def set_volume(level: int) -> str:
    """设置音量 0-100"""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)
        return f"先生，音量已设为 {level}%。"
    except Exception as e:
        return f"先生，设置音量失败：{e}"


def mute(muted: bool = True) -> str:
    """静音/取消静音"""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(1 if muted else 0, None)
        return "先生，已静音。" if muted else "先生，已取消静音。"
    except Exception as e:
        return f"先生，静音操作失败：{e}"


def lock_screen() -> str:
    """锁定屏幕"""
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        return "先生，屏幕已锁定。"
    except Exception as e:
        return f"先生，锁定屏幕失败：{e}"


def shutdown_pc(mode: str = "shutdown") -> str:
    """关机/重启/注销"""
    try:
        if mode == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "60"], shell=False)
            return "先生，电脑将在 60 秒后关机。说「取消关机」可撤销。"
        elif mode == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "60"], shell=False)
            return "先生，电脑将在 60 秒后重启。"
        elif mode == "logout":
            subprocess.Popen(["shutdown", "/l"], shell=False)
            return "先生，正在注销。"
        elif mode == "abort":
            subprocess.Popen(["shutdown", "/a"], shell=False)
            return "先生，已取消关机/重启。"
        return f"先生，不支持的电源模式：{mode}"
    except Exception as e:
        return f"先生，电源操作失败：{e}"


def sleep_pc() -> str:
    """让电脑睡眠"""
    try:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
        return "先生，电脑即将进入睡眠。"
    except Exception as e:
        return f"先生，睡眠失败：{e}"


def empty_recycle_bin() -> str:
    """清空回收站"""
    try:
        import winshell
        winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
        return "先生，回收站已清空。"
    except Exception as e:
        return f"先生，清空回收站失败：{e}"


# ---------------- 统一入口 ----------------


def control_pc(action: str, **kwargs) -> str:
    """
    统一电脑控制入口
    action 取值：
    list_windows, activate, minimize, maximize, close,
    list_processes, kill_process,
    type, press, click, screenshot,
    clipboard_get, clipboard_set,
    volume, mute, lock, shutdown, restart, logout, abort_shutdown, sleep,
    empty_trash
    """
    action = action.lower().replace("-", "_")

    mapping = {
        "list_windows": lambda: list_running_apps(),
        "activate": lambda: activate_window(kwargs.get("name", "")),
        "minimize": lambda: minimize_window(kwargs.get("name", "")),
        "maximize": lambda: maximize_window(kwargs.get("name", "")),
        "close": lambda: close_window(kwargs.get("name", "")),
        "list_processes": lambda: list_processes(kwargs.get("keyword", "")),
        "kill_process": lambda: kill_process(kwargs.get("name", "")),
        "type": lambda: type_text(kwargs.get("text", "")),
        "press": lambda: press_key(kwargs.get("keys", "")),
        "click": lambda: click_mouse(kwargs.get("x"), kwargs.get("y"), kwargs.get("button", "left")),
        "screenshot": lambda: take_screenshot(kwargs.get("save_path", "data/screenshot.png")),
        "clipboard_get": lambda: get_clipboard(),
        "clipboard_set": lambda: set_clipboard(kwargs.get("text", "")),
        "volume": lambda: set_volume(int(kwargs.get("level", 50))),
        "mute": lambda: mute(True),
        "unmute": lambda: mute(False),
        "lock": lambda: lock_screen(),
        "shutdown": lambda: shutdown_pc("shutdown"),
        "restart": lambda: shutdown_pc("restart"),
        "logout": lambda: shutdown_pc("logout"),
        "abort_shutdown": lambda: shutdown_pc("abort"),
        "sleep": lambda: sleep_pc(),
        "empty_trash": lambda: empty_recycle_bin(),
    }

    func = mapping.get(action)
    if not func:
        return f"先生，不支持的电脑控制动作：{action}"

    try:
        return func()
    except Exception as e:
        logger.exception(f"control_pc 失败：{action}")
        return f"先生，电脑控制失败：{e}"


if __name__ == "__main__":
    print(control_pc("list_windows"))
