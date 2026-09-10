"""
MQTT 事件总线模块测试
使用纯内存回退模式，无需真实 MQTT broker。
覆盖主题匹配、消息发布/订阅/取消订阅、内存队列、状态查询。
"""

import mqtt_bus


def _reset_mqtt_state():
    """重置 MQTT 模块内存状态"""
    mqtt_bus._memory_messages.clear()
    mqtt_bus._subscribers.clear()
    mqtt_bus._client = None
    mqtt_bus._connected = False


def test_topic_match():
    """MQTT 主题匹配规则"""
    print("\n=== 主题匹配规则 ===")

    assert mqtt_bus._topic_match("ynex/test/hello", "ynex/test/hello") is True
    assert mqtt_bus._topic_match("ynex/test/+", "ynex/test/hello") is True
    assert mqtt_bus._topic_match("ynex/test/+", "ynex/test/hello/world") is False
    assert mqtt_bus._topic_match("ynex/+/hello", "ynex/foo/hello") is True
    assert mqtt_bus._topic_match("ynex/+/hello", "ynex/foo/goodbye") is False
    assert mqtt_bus._topic_match("ynex/#", "ynex/test/hello") is True
    assert mqtt_bus._topic_match("ynex/#", "ynex/a/b/c/d") is True
    assert mqtt_bus._topic_match("ynex/test/#", "ynex/other") is False
    assert mqtt_bus._topic_match("ynex/test", "ynex/test/extra") is False
    assert mqtt_bus._topic_match("ynex/test", "ynex/te") is False
    print("  ✅ 主题匹配规则正确")


def test_publish_and_subscribe_memory_fallback():
    """内存回退模式下的发布与订阅"""
    print("\n=== 内存回退 pub/sub ===")
    _reset_mqtt_state()

    received = []

    def callback(topic, payload):
        received.append((topic, payload))

    mqtt_bus.subscribe("ynex/sensor/temp", callback)
    mqtt_bus.publish("ynex/sensor/temp", {"value": 25.5})

    assert len(received) == 1
    assert received[0][0] == "ynex/sensor/temp"
    assert received[0][1] == {"value": 25.5}
    print("  ✅ 内存回退 pub/sub 正确")


def test_unsubscribe():
    """取消订阅后不应再收到消息"""
    print("\n=== 取消订阅 ===")
    _reset_mqtt_state()

    received = []

    def callback(topic, payload):
        received.append((topic, payload))

    mqtt_bus.subscribe("ynex/cmd", callback)
    mqtt_bus.publish("ynex/cmd", "before")
    assert len(received) == 1

    mqtt_bus.unsubscribe("ynex/cmd", callback)
    mqtt_bus.publish("ynex/cmd", "after")
    assert len(received) == 1  # 不应增加
    print("  ✅ 取消订阅正确")


def test_wildcard_subscription():
    """通配符订阅应匹配多层主题"""
    print("\n=== 通配符订阅 ===")
    _reset_mqtt_state()

    received = []

    def callback(topic, payload):
        received.append((topic, payload))

    mqtt_bus.subscribe("ynex/+/status", callback)
    mqtt_bus.publish("ynex/phone/status", "online")
    mqtt_bus.publish("ynex/sensor/status", "active")
    mqtt_bus.publish("ynex/phone/presence", "yes")  # 不应匹配

    assert len(received) == 2
    assert received[0][0] == "ynex/phone/status"
    assert received[1][0] == "ynex/sensor/status"
    print("  ✅ 通配符订阅正确")


def test_multi_subscribers_same_topic():
    """同一主题多个订阅者应各自收到消息"""
    print("\n=== 多订阅者隔离 ===")
    _reset_mqtt_state()

    r1, r2 = [], []

    def cb1(t, p):
        r1.append(p)

    def cb2(t, p):
        r2.append(p)

    mqtt_bus.subscribe("ynex/alert", cb1)
    mqtt_bus.subscribe("ynex/alert", cb2)
    mqtt_bus.publish("ynex/alert", "fire")

    assert len(r1) == 1 and len(r2) == 1
    assert r1[0] == "fire" and r2[0] == "fire"
    print("  ✅ 多订阅者隔离正确")


def test_callback_exception_isolation():
    """单个回调异常不应影响其他回调"""
    print("\n=== 回调异常隔离 ===")
    _reset_mqtt_state()

    r_good = []

    def bad_cb(t, p):
        raise ValueError("故意异常")

    def good_cb(t, p):
        r_good.append(p)

    mqtt_bus.subscribe("ynex/event", bad_cb)
    mqtt_bus.subscribe("ynex/event", good_cb)
    mqtt_bus.publish("ynex/event", "data")

    assert len(r_good) == 1, "good_cb 应正常收到消息"
    print("  ✅ 回调异常隔离正确")


def test_payload_decode():
    """payload 解码：JSON、字符串、二进制 fallback"""
    print("\n=== payload 解码 ===")

    assert mqtt_bus._decode_payload(b'{"a": 1}') == {"a": 1}
    assert mqtt_bus._decode_payload(b"hello") == "hello"
    assert mqtt_bus._decode_payload(b"\xff\xfe") == str(b"\xff\xfe")
    print("  ✅ payload 解码正确")


def test_memory_queue_and_status():
    """内存队列与状态查询"""
    print("\n=== 内存队列与状态 ===")
    _reset_mqtt_state()

    def dummy_cb(t, p):
        pass

    mqtt_bus.subscribe("ynex/q", dummy_cb)
    for i in range(5):
        mqtt_bus.publish("ynex/q", f"msg{i}")

    status = mqtt_bus.get_status()
    assert status["connected"] is False
    assert status["memory_queue_size"] == 5
    assert "ynex/q" in status["subscribed_topics"]

    recent = mqtt_bus.get_recent_messages(limit=3)
    assert len(recent) == 3
    assert recent[-1]["payload"] == "msg4"

    mqtt_bus.unsubscribe("ynex/q", dummy_cb)
    print("  ✅ 内存队列与状态正确")


def test_is_available_without_broker():
    """无 broker 时 is_available 应返回 False"""
    print("\n=== 无 broker 可用性 ===")
    _reset_mqtt_state()

    assert mqtt_bus.is_available() is False
    print("  ✅ 无 broker 可用性检测正确")


def main():
    print("=" * 60)
    print("  MQTT 事件总线模块测试")
    print("=" * 60)

    test_topic_match()
    test_publish_and_subscribe_memory_fallback()
    test_unsubscribe()
    test_wildcard_subscription()
    test_multi_subscribers_same_topic()
    test_callback_exception_isolation()
    test_payload_decode()
    test_memory_queue_and_status()
    test_is_available_without_broker()

    print("\n" + "=" * 60)
    print("  ✅ 全部 MQTT 测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
