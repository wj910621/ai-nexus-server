"""
ESP32 传感器接入模块
让 ESP32 人体存在、门窗、温湿度等传感器接入Y·NEX，
通过 MQTT 上报数据，触发自动化规则。

支持设备类型：
- pir: 人体红外
- mmwave: 人体存在雷达（LD2410、LD2450 等）
- door: 门窗磁传感器
- temp_humi: 温湿度
- light: 光照度
- button: 无线按钮

约定 MQTT Topic：
  jarvis/sensor/<location>/<device_type>/<device_id>
  例如：jarvis/sensor/living_room/pir/001

约定 Payload：
  {
    "state": "on" | "off" | "open" | "close" | "detected" | "clear",
    "value": <float>,       # 数值型传感器使用
    "battery": <int>,       # 电量百分比
    "timestamp": "ISO8601"  # 设备时间
  }
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from logger import logger
from mqtt_bus import subscribe, publish


# 传感器状态存储
_sensor_states: Dict[str, dict] = {}
_listeners: List[Callable] = []


@dataclass
class SensorEvent:
    topic: str
    location: str
    device_type: str
    device_id: str
    state: str
    value: Optional[float] = None
    battery: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def _parse_topic(topic: str) -> Optional[tuple]:
    """解析 MQTT topic，返回 (location, device_type, device_id)"""
    parts = topic.split("/")
    if len(parts) >= 5 and parts[0] == "jarvis" and parts[1] == "sensor":
        return parts[2], parts[3], parts[4]
    return None


def _normalize_state(state_raw, device_type: str) -> str:
    """标准化传感器状态"""
    if isinstance(state_raw, bool):
        return "on" if state_raw else "off"
    state = str(state_raw).lower().strip()
    if device_type in ("pir", "mmwave"):
        if state in ("1", "true", "detected", "occupied", "有人"):
            return "detected"
        return "clear"
    if device_type == "door":
        if state in ("1", "true", "open", "opened"):
            return "open"
        return "close"
    return state


def _on_sensor_message(topic: str, payload):
    """MQTT 传感器消息回调"""
    parsed = _parse_topic(topic)
    if not parsed:
        return

    location, device_type, device_id = parsed

    data = payload if isinstance(payload, dict) else {}
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            data = {"state": payload}

    state = _normalize_state(data.get("state", ""), device_type)
    value = data.get("value")
    battery = data.get("battery")

    event = SensorEvent(
        topic=topic,
        location=location,
        device_type=device_type,
        device_id=device_id,
        state=state,
        value=float(value) if value is not None else None,
        battery=battery,
        timestamp=data.get("timestamp", datetime.now().isoformat())
    )

    # 保存状态
    _sensor_states[f"{location}.{device_type}.{device_id}"] = {
        "state": state,
        "value": event.value,
        "battery": event.battery,
        "last_seen": time.time(),
        "timestamp": event.timestamp
    }

    logger.info(f"传感器 {location}/{device_type}/{device_id}: {state}")

    # 通知监听者
    for listener in _listeners:
        try:
            listener(event)
        except Exception as e:
            logger.exception(f"传感器监听器异常：{e}")


def start_sensor_listener():
    """启动传感器监听"""
    subscribe("jarvis/sensor/+/+/+", _on_sensor_message)
    logger.info("ESP32 传感器监听已启动，订阅 jarvis/sensor/+/+/+")


def add_listener(callback: Callable[[SensorEvent], None]):
    """添加传感器事件监听"""
    _listeners.append(callback)


def get_sensor_states() -> Dict[str, dict]:
    """获取所有传感器当前状态"""
    return dict(_sensor_states)


def get_sensor_state(key: str) -> Optional[dict]:
    """获取指定传感器状态"""
    return _sensor_states.get(key)


def is_someone_present(timeout: int = 300) -> bool:
    """
    是否有人在家。
    最近 timeout 秒内，任意人体存在传感器 detected 则认为有人。
    """
    now = time.time()
    for key, state in _sensor_states.items():
        if ".pir." in key or ".mmwave." in key:
            if state.get("state") == "detected":
                return True
            last_seen = state.get("last_seen", 0)
            if now - last_seen < timeout and state.get("state") == "detected":
                return True
    return False


def is_door_open() -> bool:
    """是否有门窗未关"""
    for key, state in _sensor_states.items():
        if ".door." in key and state.get("state") == "open":
            return True
    return False


def human_summary() -> str:
    """生成传感器状态摘要"""
    lines = ["当前环境感知："]
    if not _sensor_states:
        lines.append("  暂无传感器数据。")
        return "\n".join(lines)

    for key, state in sorted(_sensor_states.items()):
        loc, dtype, did = key.split(".")
        status = state.get("state", "unknown")
        val = state.get("value")
        battery = state.get("battery")
        parts = [f"  {loc} {dtype}({did}): {status}"]
        if val is not None:
            parts.append(f"value={val}")
        if battery is not None:
            parts.append(f"battery={battery}%")
        lines.append(" ".join(parts))

    presence = "有人" if is_someone_present() else "无人"
    door = "门窗未关" if is_door_open() else "门窗正常"
    lines.append(f"综合：{presence}，{door}")

    return "\n".join(lines)


# 预置自动化规则模板
PRESET_RULES = {
    "离家模式": {
        "trigger": {"type": "time", "at": "22:00"},
        "condition": {"sensor_present": False},
        "actions": [
            {"type": "command", "command": "ha.light.living_room.off"},
            {"type": "command", "command": "pc.lock"},
            {"type": "notify", "message": "先生，已执行离家模式。"}
        ]
    },
    "起夜灯": {
        "trigger": {"type": "sensor", "device_type": "pir", "state": "detected"},
        "condition": {"time_between": ["22:00", "06:00"]},
        "actions": [
            {"type": "command", "command": "ha.light.hallway.on"},
            {"type": "command", "command": "ha.light.hallway.brightness.30"},
            {"type": "delay", "seconds": 60},
            {"type": "command", "command": "ha.light.hallway.off"}
        ]
    },
    "门窗未关提醒": {
        "trigger": {"type": "sensor", "device_type": "door", "state": "open"},
        "condition": {"duration": 300},
        "actions": [
            {"type": "notify", "message": "先生，{location} 的门窗超过5分钟未关。"}
        ]
    },
    "回家开灯": {
        "trigger": {"type": "sensor", "device_type": "mmwave", "state": "detected"},
        "conditions": [{"type": "time_range", "start": "18:00", "end": "23:59"}],
        "actions": [
            {"type": "device", "command": "ha.light.living_room.on"},
            {"type": "notify", "message": "先生，欢迎回家，已为您开灯。"}
        ]
    }
}


def get_presets() -> Dict:
    """获取预置规则模板"""
    return PRESET_RULES


if __name__ == "__main__":
    start_sensor_listener()
    print("测试：模拟传感器上报")
    publish("jarvis/sensor/living_room/pir/001", {"state": "detected", "battery": 85})
    time.sleep(0.5)
    print(human_summary())
