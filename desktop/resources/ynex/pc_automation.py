"""
PC 自动化增强模块
提供全局热键、应用状态轮询、剪贴板历史、窗口事件触发等能力。
所有依赖懒加载，缺失时优雅降级。
"""

import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional

from logger import logger


# ---------------- 全局热键 ----------------

_hotkey_listener = None
_hotkey_registry: Dict[str, Callable[[], None]] = {}


def register_hotkey(combo: str, callback: Callable[[], None]) -> str:
    """注册全局热键，combo 格式如 '<ctrl>+<shift>+j'"""
    try:
        from pynput import keyboard

        combo = combo.lower().replace(" ", "")
        _hotkey_registry[combo] = callback
        _ensure_hotkey_listener()
        return f"已注册热键 {combo}"
    except Exception as e:
        return f"注册热键失败：{e}"


def unregister_hotkey(combo: str) -> str:
    combo = combo.lower().replace(" ", "")
    if combo in _hotkey_registry:
        del _hotkey_registry[combo]
    return f"已注销热键 {combo}"


def _ensure_hotkey_listener():
    global _hotkey_listener
    if _hotkey_listener and _hotkey_listener.is_alive():
        return

    try:
        from pynput import keyboard

        current_keys = set()

        def on_press(key):
            try:
                k = key.char.lower() if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
                current_keys.add(k)
                _check_hotkeys(current_keys)
            except Exception:
                pass

        def on_release(key):
            try:
                k = key.char.lower() if hasattr(key, 'char') and key.char else str(key).replace('Key.', '')
                current_keys.discard(k)
            except Exception:
                pass

        _hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        _hotkey_listener.daemon = True
        _hotkey_listener.start()
        logger.info("PC 自动化全局热键监听器已启动")
    except Exception as e:
        logger.warning(f"启动全局热键监听器失败：{e}")


def _check_hotkeys(current_keys: set):
    for combo, callback in list(_hotkey_registry.items()):
        parts = re.split(r'[\+<>]', combo)
        parts = [p for p in parts if p and p not in ('',)]
        # 简单匹配：所有部分都在当前按键中
        keys_needed = set()
        modifiers = []
        for p in parts:
            p = p.strip().lower()
            if p in ('ctrl', 'shift', 'alt', 'cmd'):
                modifiers.append(p)
            elif p:
                keys_needed.add(p)

        matched = True
        for m in modifiers:
            if m == 'ctrl' and 'ctrl' not in current_keys and 'ctrl_l' not in current_keys and 'ctrl_r' not in current_keys:
                matched = False
            elif m == 'shift' and 'shift' not in current_keys and 'shift_l' not in current_keys and 'shift_r' not in current_keys:
                matched = False
            elif m == 'alt' and 'alt' not in current_keys and 'alt_l' not in current_keys and 'alt_r' not in current_keys:
                matched = False
            elif m == 'cmd' and 'cmd' not in current_keys:
                matched = False
        if matched and keys_needed.issubset(current_keys):
            try:
                logger.info(f"热键触发：{combo}")
                threading.Thread(target=callback, daemon=True).start()
            except Exception as e:
                logger.error(f"热键回调失败：{e}")


# ---------------- 剪贴板历史 ----------------

_CLIPBOARD_HISTORY_FILE = "data/clipboard_history.json"
_clipboard_history: deque = deque(maxlen=50)
_history_lock = threading.Lock()
_clipboard_thread = None
_clipboard_running = False


def get_clipboard_history(limit: int = 10) -> List[Dict[str, Any]]:
    """获取最近剪贴板历史"""
    with _history_lock:
        items = list(_clipboard_history)[-limit:]
        return [{"time": i["time"], "type": i["type"], "preview": i["content"][:100]} for i in items]


def add_clipboard_record(text: str, content_type: str = ""):
    """由 clipboard_listener.py 调用，记录一条剪贴板历史"""
    if not text:
        return
    if not content_type:
        content_type = _detect_clipboard_type(text)
    with _history_lock:
        _clipboard_history.append({
            "time": datetime.now().isoformat(),
            "type": content_type,
            "content": text,
        })
    _save_clipboard_history()


def _load_clipboard_history():
    global _clipboard_history
    try:
        import json
        if os.path.exists(_CLIPBOARD_HISTORY_FILE):
            with open(_CLIPBOARD_HISTORY_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
                _clipboard_history = deque(items[-50:], maxlen=50)
    except Exception as e:
        logger.warning(f"加载剪贴板历史失败：{e}")


def _save_clipboard_history():
    try:
        import json
        os.makedirs(os.path.dirname(_CLIPBOARD_HISTORY_FILE) or "data", exist_ok=True)
        with _history_lock:
            with open(_CLIPBOARD_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(list(_clipboard_history), f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"保存剪贴板历史失败：{e}")


def _detect_clipboard_type(text: str) -> str:
    text = text.strip()
    if re.match(r"^https?://\S+", text):
        return "url"
    if re.match(r"^[a-zA-Z]:\\[^\n]*$", text) or (text.startswith("/") and os.path.exists(text)):
        return "file_path"
    if len(text) > 200:
        return "long_text"
    return "short_text"


def start_clipboard_history():
    """启动剪贴板历史记录线程"""
    global _clipboard_thread, _clipboard_running
    if _clipboard_running:
        return "剪贴板历史已在运行"
    _clipboard_running = True
    _load_clipboard_history()

    def loop():
        last = ""
        while _clipboard_running:
            try:
                import pyperclip
                text = pyperclip.paste() or ""
                if text and text != last:
                    last = text
                    with _history_lock:
                        _clipboard_history.append({
                            "time": datetime.now().isoformat(),
                            "type": _detect_clipboard_type(text),
                            "content": text,
                        })
                    _save_clipboard_history()
            except Exception:
                pass
            time.sleep(0.8)

    _clipboard_thread = threading.Thread(target=loop, daemon=True)
    _clipboard_thread.start()
    logger.info("剪贴板历史记录已启动")
    return "剪贴板历史已启动"


def stop_clipboard_history():
    global _clipboard_running
    _clipboard_running = False
    return "剪贴板历史已停止"


# ---------------- 应用状态轮询 ----------------

_state_thread = None
_state_running = False
_state_callbacks: List[Callable[[Dict[str, Any]], None]] = []
_last_state: Dict[str, Any] = {}


def register_state_callback(callback: Callable[[Dict[str, Any]], None]):
    _state_callbacks.append(callback)


def get_current_pc_state() -> Dict[str, Any]:
    """获取当前 PC 状态快照"""
    state = {
        "timestamp": datetime.now().isoformat(),
        "active_window": None,
        "cpu_percent": None,
        "memory_percent": None,
        "volume": None,
        "locked": False,
    }
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active:
            state["active_window"] = {"title": active.title, "left": active.left, "top": active.top}
    except Exception:
        pass

    try:
        import psutil
        state["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        state["memory_percent"] = psutil.virtual_memory().percent
    except Exception:
        pass

    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        state["volume"] = int(volume.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        pass

    return state


def start_state_polling(interval: float = 3.0):
    """启动应用状态轮询"""
    global _state_thread, _state_running
    if _state_running:
        return "状态轮询已在运行"
    _state_running = True

    def loop():
        global _last_state
        while _state_running:
            try:
                state = get_current_pc_state()
                # 窗口变化时触发回调和自动化事件（在更新 _last_state 之前比较）
                old_title = _last_state.get("active_window", {}).get("title")
                new_title = state.get("active_window", {}).get("title")
                _last_state = state
                if old_title != new_title and new_title:
                    _trigger_window_change(new_title)
                for cb in _state_callbacks:
                    try:
                        cb(state)
                    except Exception as e:
                        logger.error(f"状态回调失败：{e}")
            except Exception as e:
                logger.warning(f"状态轮询异常：{e}")
            time.sleep(interval)

    _state_thread = threading.Thread(target=loop, daemon=True)
    _state_thread.start()
    logger.info(f"PC 状态轮询已启动，间隔 {interval}s")
    return "状态轮询已启动"


def stop_state_polling():
    global _state_running
    _state_running = False
    return "状态轮询已停止"


def _trigger_window_change(title: str):
    try:
        from automation_engine import trigger_event
        trigger_event("window_change", {"title": title})
    except Exception:
        pass


# ---------------- 统一入口 ----------------

_automation_started = False


def start_pc_automation():
    """启动所有 PC 自动化增强功能"""
    global _automation_started
    if _automation_started:
        return "PC 自动化已在运行"
    _automation_started = True

    results = []
    results.append(start_clipboard_history())
    results.append(start_state_polling())

    # 注册默认热键：Ctrl+Shift+Y 显示剪贴板历史
    def show_history():
        from speech import speak
        items = get_clipboard_history(3)
        if items:
            speak(f"最近复制了 {len(items)} 条内容")
        else:
            speak("剪贴板历史为空")

    register_hotkey("<ctrl>+<shift>+y", show_history)
    results.append("已注册默认热键 Ctrl+Shift+Y")

    logger.info("PC 自动化增强已启动")
    return "；".join(results)


def stop_pc_automation():
    global _automation_started
    _automation_started = False
    stop_clipboard_history()
    stop_state_polling()
    return "PC 自动化已停止"


def automation_status() -> Dict[str, Any]:
    return {
        "running": _automation_started,
        "hotkeys": list(_hotkey_registry.keys()),
        "clipboard_history_count": len(_clipboard_history),
        "state_polling": _state_running,
        "last_state": _last_state,
    }
