"""
设备统一控制中枢
把所有设备抽象成 domain.action.entity 的指令协议，
让Y·NEX可以用同一套语言控制电脑、手机、智能家居、浏览器等。

示例指令：
    pc.activate.Notepad
    pc.volume.30
    ha.light.living_room.on
    phone.wechat.send
    browser.open.https://example.com
"""

import json
import os
import re
from typing import Dict, Any, Callable, Optional

from logger import logger


DEVICE_REGISTRY_PATH = "data/device_registry.json"


# 默认设备注册表，启动时自动加载/保存
DEFAULT_REGISTRY = {
    "pc": {
        "type": "pc",
        "name": "本机电脑",
        "actions": ["activate", "minimize", "maximize", "close", "volume", "mute", "unmute",
                    "lock", "shutdown", "restart", "sleep", "screenshot", "clipboard_get",
                    "clipboard_set", "type", "press", "click", "list_windows", "list_processes",
                    "kill_process", "empty_trash"]
    },
    "ha": {
        "type": "home_assistant",
        "name": "Home Assistant",
        "actions": ["on", "off", "toggle", "brightness", "temperature", "open", "close", "stop", "list"]
    },
    "phone": {
        "type": "phone",
        "name": "手机",
        "actions": ["send", "notify", "call", "sms", "location", "battery", "wifi", "bluetooth"]
    },
    "browser": {
        "type": "browser",
        "name": "浏览器",
        "actions": ["open", "search", "click", "type", "screenshot"]
    },
    "media": {
        "type": "media",
        "name": "媒体控制",
        "actions": ["play", "pause", "next", "prev", "volume"]
    }
}


def _load_registry() -> Dict[str, Any]:
    """加载设备注册表"""
    if os.path.exists(DEVICE_REGISTRY_PATH):
        try:
            with open(DEVICE_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载设备注册表失败：{e}")
    return dict(DEFAULT_REGISTRY)


def _save_registry(registry: Dict[str, Any]):
    """保存设备注册表"""
    try:
        os.makedirs(os.path.dirname(DEVICE_REGISTRY_PATH) or "data", exist_ok=True)
        with open(DEVICE_REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存设备注册表失败：{e}")


# 注册表懒加载
_REGISTRY = None


def get_registry() -> Dict[str, Any]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _load_registry()
    return _REGISTRY


def register_device(domain: str, device_type: str, name: str, actions: list):
    """动态注册新设备域"""
    reg = get_registry()
    reg[domain] = {"type": device_type, "name": name, "actions": actions}
    _save_registry(reg)


def _route_to_pc(action: str, entity: str, value: str = "") -> str:
    """路由到 pc_control"""
    from pc_control import control_pc

    kwargs = {}
    if entity:
        kwargs["name"] = entity
    if value:
        kwargs["text"] = value
        kwargs["keys"] = value
        kwargs["level"] = value

    # 特殊参数映射
    if action in ["type"] and value:
        kwargs = {"text": value}
    elif action in ["press"] and value:
        kwargs = {"keys": value}
    elif action == "volume" and value:
        kwargs = {"level": int(value)}
    elif action in ["activate", "minimize", "maximize", "close"] and entity:
        kwargs = {"name": entity}
    elif action == "kill_process" and entity:
        kwargs = {"name": entity}
    elif action == "list_processes" and entity:
        kwargs = {"keyword": entity}
    elif action in ["clipboard_set"] and value:
        kwargs = {"text": value}
    elif action == "click" and entity:
        # entity 格式："100,200"
        parts = entity.split(",")
        if len(parts) == 2:
            kwargs = {"x": int(parts[0]), "y": int(parts[1])}

    return control_pc(action, **kwargs)


def _route_to_ha(action: str, entity: str, value: str = "") -> str:
    """路由到 Home Assistant"""
    from home_assistant import control_device, list_entities

    if action == "list":
        return list_entities(domain=entity or None)

    if not entity:
        return "先生，请指定 Home Assistant 设备实体 ID。"

    if action in ["on", "off", "toggle"]:
        return control_device(entity, action)

    if action == "brightness" and value:
        return control_device(entity, f"brightness:{value}")
    if action == "temperature" and value:
        return control_device(entity, f"temperature:{value}")

    return control_device(entity, action)


def _route_to_phone(action: str, entity: str, value: str = "") -> str:
    """路由到手机桥（通过 MQTT/HTTP 桥）"""
    from mqtt_bus import publish
    payload = {"action": action, "entity": entity, "value": value}
    publish(f"ynex/phone/command/{action}", payload)
    return f"先生，已向手机发送指令 {action}。"


def _route_to_browser(action: str, entity: str, value: str = "") -> str:
    """路由到浏览器自动化"""
    from browser_automation import read_webpage, search_web, run_browser_task

    if action == "open":
        url = entity if entity.startswith("http") else f"https://{entity}"
        return read_webpage(url)
    if action == "search":
        return search_web(value or entity)
    return run_browser_task(f"{action} {entity} {value}".strip())


def _route_to_media(action: str, entity: str, value: str = "") -> str:
    """媒体控制（先用 pyautogui 媒体键模拟）"""
    from pc_control import press_key
    key_map = {
        "play": "playpause",
        "pause": "playpause",
        "next": "nexttrack",
        "prev": "prevtrack",
        "mute": "volumemute",
        "volume_up": "volumeup",
        "volume_down": "volumedown",
    }
    key = key_map.get(action, action)
    return press_key(key)


# 路由器映射
ROUTERS: Dict[str, Callable[[str, str, str], str]] = {
    "pc": _route_to_pc,
    "ha": _route_to_ha,
    "phone": _route_to_phone,
    "browser": _route_to_browser,
    "media": _route_to_media,
}


def execute_command(domain: str, action: str, entity: str = "", value: str = "") -> str:
    """执行统一设备指令"""
    domain = domain.lower()
    reg = get_registry()

    if domain not in reg:
        return f"先生，未知设备域：{domain}。已注册域：{', '.join(reg.keys())}"

    router = ROUTERS.get(domain)
    if not router:
        return f"先生，设备域 {domain} 尚未接入控制器。"

    logger.info(f"设备控制：{domain}.{action}.{entity} value={value}")
    return router(action, entity, value)


def parse_and_execute(command: str) -> str:
    """
    解析自然语言或协议格式指令并执行
    支持：
      - 协议格式：pc.activate.Notepad、ha.light.living_room.on
      - 中文格式：打开客厅灯、把音量调到30
    """
    command = command.strip()

    # 协议格式解析
    m = re.match(r"^([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(?:\.([^\s=]+))?(?:=(.+))?$", command)
    if m:
        domain, action, entity, value = m.groups()
        return execute_command(domain, action, entity or "", value or "")

    # 自然语言简单映射
    text = command.lower()

    # 电脑相关
    if any(k in text for k in ["打开窗口", "激活", "切换到"]) or re.search(r"打开\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*窗口", command):
        m = re.search(r"(?:打开|激活|切换到)\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)(?:\s*窗口)?", command)
        return execute_command("pc", "activate", m.group(1) if m else "")

    if "音量" in text:
        m = re.search(r"(\d+)", command)
        if m:
            return execute_command("pc", "volume", value=m.group(1))
        if "静音" in text or "静音" in text:
            return execute_command("pc", "mute")
        if "取消静音" in text:
            return execute_command("pc", "unmute")

    if "锁屏" in text:
        return execute_command("pc", "lock")
    if "关机" in text:
        return execute_command("pc", "shutdown")
    if "重启" in text:
        return execute_command("pc", "restart")
    if "截图" in text:
        return execute_command("pc", "screenshot")

    # 智能家居
    if any(k in text for k in ["灯", "窗帘", "空调", "开关", "设备"]):
        if any(k in text for k in ["打开", "开"]):
            entity = _extract_entity(command)
            return execute_command("ha", "on", entity)
        if any(k in text for k in ["关闭", "关"]):
            entity = _extract_entity(command)
            return execute_command("ha", "off", entity)

    return f"先生，我暂时没理解「{command}」该由哪个设备执行。"


def _extract_entity(text: str) -> str:
    """从中文指令中尽量提取实体名"""
    # 简单规则：把客厅灯映射为 light.living_room
    room_map = {
        "客厅": "living_room",
        "卧室": "bedroom",
        "厨房": "kitchen",
        "书房": "study",
        "卫生间": "bathroom",
    }
    device_map = {
        "灯": "light",
        "空调": "climate",
        "窗帘": "cover",
        "开关": "switch",
    }

    room = ""
    device = "light"
    for cn, en in room_map.items():
        if cn in text:
            room = en
            break
    for cn, en in device_map.items():
        if cn in text:
            device = en
            break

    if room:
        return f"{device}.{room}"
    return ""


def list_domains() -> str:
    """列出已注册设备域"""
    reg = get_registry()
    lines = ["先生，已接入的设备域："]
    for domain, info in reg.items():
        lines.append(f"- {domain}（{info['name']}）：{', '.join(info['actions'][:5])}...")
    return "\n".join(lines)


if __name__ == "__main__":
    print(list_domains())
    print(parse_and_execute("pc.activate.Notepad"))
