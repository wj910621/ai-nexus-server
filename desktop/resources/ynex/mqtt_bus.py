"""
MQTT 事件总线模块
为Y·NEX提供本地消息总线，让手机、传感器、其他设备可以 pub/sub。

使用方式：
    1. 安装并启动 Mosquitto（Windows 可用官方安装包）
    2. Y·NEX启动时自动连接 localhost:1883
    3. 手机/传感器向 ynex/phone/status、ynex/sensor/+/presence 发布消息
    4. automation_engine 订阅这些主题并触发规则

未安装 paho-mqtt 或未运行 broker 时，自动降级为内存消息队列（同进程内可用）。
"""

import json
import os
import threading
import time
from typing import Dict, Any, Callable, Optional

from logger import logger


BROKER_HOST = os.getenv("MQTT_BROKER", "localhost")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
CLIENT_ID = "ynex_core"

# 内存回退队列（MQTT 不可用时）
_memory_messages: list = []
_subscribers: Dict[str, list] = {}
_client = None
_connected = False
_lock = threading.Lock()


def _ensure_client():
    """懒加载 MQTT 客户端"""
    global _client, _connected

    if _client is not None:
        return _client

    try:
        import paho.mqtt.client as mqtt

        def on_connect(client, userdata, flags, rc):
            global _connected
            if rc == 0:
                _connected = True
                logger.info("MQTT 已连接")
                # 重订阅
                for topic in _subscribers.keys():
                    client.subscribe(topic)
            else:
                logger.warning(f"MQTT 连接失败，返回码：{rc}")

        def on_message(client, userdata, msg):
            payload = _decode_payload(msg.payload)
            logger.debug(f"MQTT 收到 {msg.topic}: {payload}")
            _dispatch_local(msg.topic, payload)

        def on_disconnect(client, userdata, rc):
            global _connected
            _connected = False
            logger.warning("MQTT 已断开")

        _client = mqtt.Client(client_id=CLIENT_ID)
        _client.on_connect = on_connect
        _client.on_message = on_message
        _client.on_disconnect = on_disconnect

        try:
            _client.connect(BROKER_HOST, BROKER_PORT, 60)
            _client.loop_start()
            # 等待一小会儿看是否连上
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"MQTT broker 连接失败（{BROKER_HOST}:{BROKER_PORT}）：{e}，使用内存队列回退。")
            _client = None
            _connected = False

    except ImportError:
        logger.warning("未安装 paho-mqtt，MQTT 功能使用内存队列回退。")
        _client = None
        _connected = False

    return _client


def _decode_payload(payload: bytes) -> Any:
    """尝试把 payload 解析为 JSON，失败则返回字符串"""
    try:
        text = payload.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    except Exception:
        return str(payload)


def _dispatch_local(topic: str, payload: Any):
    """本地分发消息到订阅者"""
    with _lock:
        for sub_topic, callbacks in _subscribers.items():
            if _topic_match(sub_topic, topic):
                for cb in callbacks:
                    try:
                        cb(topic, payload)
                    except Exception as e:
                        logger.exception(f"MQTT 订阅回调异常：{e}")


def _topic_match(subscription: str, topic: str) -> bool:
    """简单 MQTT 主题匹配，支持 + 和 #"""
    sub_parts = subscription.split("/")
    topic_parts = topic.split("/")

    for i, part in enumerate(sub_parts):
        if part == "#":
            return True
        if i >= len(topic_parts):
            return False
        if part != "+" and part != topic_parts[i]:
            return False

    return len(sub_parts) == len(topic_parts)


def publish(topic: str, payload: Any, qos: int = 0):
    """发布消息"""
    client = _ensure_client()

    if isinstance(payload, (dict, list)):
        payload_str = json.dumps(payload, ensure_ascii=False)
    else:
        payload_str = str(payload)

    if client and _connected:
        try:
            client.publish(topic, payload_str, qos=qos)
            return
        except Exception as e:
            logger.warning(f"MQTT 发布失败：{e}")

    # 内存回退
    _memory_messages.append({"topic": topic, "payload": payload, "time": time.time()})
    _dispatch_local(topic, payload)


def subscribe(topic: str, callback: Callable[[str, Any], None]):
    """订阅主题"""
    with _lock:
        if topic not in _subscribers:
            _subscribers[topic] = []
        _subscribers[topic].append(callback)

    client = _ensure_client()
    if client and _connected:
        try:
            client.subscribe(topic)
        except Exception as e:
            logger.warning(f"MQTT 订阅失败：{e}")


def unsubscribe(topic: str, callback: Callable[[str, Any], None]):
    """取消订阅"""
    with _lock:
        if topic in _subscribers:
            if callback in _subscribers[topic]:
                _subscribers[topic].remove(callback)


def get_status() -> Dict[str, Any]:
    """获取 MQTT 状态"""
    return {
        "broker": f"{BROKER_HOST}:{BROKER_PORT}",
        "connected": _connected,
        "subscribed_topics": list(_subscribers.keys()),
        "memory_queue_size": len(_memory_messages)
    }


def get_recent_messages(limit: int = 20) -> list:
    """获取内存队列中的最近消息"""
    return _memory_messages[-limit:]


def is_available() -> bool:
    """MQTT 是否可用"""
    _ensure_client()
    return _connected


if __name__ == "__main__":
    def on_msg(t, p):
        print(f"收到 {t}: {p}")

    subscribe("ynex/test/#", on_msg)
    publish("ynex/test/hello", {"msg": "你好"})
    time.sleep(1)
    print(get_status())
