"""
MQTT消息总线测试
测试主题匹配、消息发布订阅、内存回退等功能
"""

import time
import threading
from mqtt_bus import (
    publish,
    subscribe,
    unsubscribe,
    get_status,
    get_recent_messages,
    is_available,
    _topic_match,
    _decode_payload,
)


def test_topic_matching():
    """测试MQTT主题匹配"""
    print("\n=== 测试MQTT主题匹配 ===")

    # 精确匹配
    assert _topic_match("ynex/test", "ynex/test") is True
    assert _topic_match("ynex/test", "ynex/other") is False

    # 单层通配符 +
    assert _topic_match("ynex/+/status", "ynex/phone/status") is True
    assert _topic_match("ynex/+/status", "ynex/phone/online") is False
    assert _topic_match("+/test", "ynex/test") is True

    # 多层通配符 #
    assert _topic_match("ynex/#", "ynex/test/hello") is True
    assert _topic_match("ynex/#", "ynex/test") is True
    assert _topic_match("ynex/#", "other/test") is False

    # 混合通配符
    assert _topic_match("ynex/+/sensor/#", "ynex/home/sensor/temp") is True
    assert _topic_match("ynex/+/sensor/#", "ynex/home/light/1") is False

    print("  ✓ MQTT主题匹配测试通过")


def test_decode_payload():
    """测试Payload解码"""
    print("\n=== 测试Payload解码 ===")

    # JSON解析
    payload = b'{"key": "value"}'
    result = _decode_payload(payload)
    assert result == {"key": "value"}

    # 字符串
    payload = b'hello world'
    result = _decode_payload(payload)
    assert result == "hello world"

    # 无效JSON返回字符串
    payload = b'not a json'
    result = _decode_payload(payload)
    assert result == "not a json"

    # 二进制数据
    payload = b'\x00\x01\x02'
    result = _decode_payload(payload)
    assert isinstance(result, str)

    print("  ✓ Payload解码测试通过")


def test_memory_fallback():
    """测试内存回退模式"""
    print("\n=== 测试内存回退模式 ===")

    received_messages = []

    def callback(topic, payload):
        received_messages.append((topic, payload))

    # 订阅主题
    subscribe("ynex/test/#", callback)

    # 发布消息
    publish("ynex/test/hello", {"msg": "world"})

    # 等待消息处理
    time.sleep(0.5)

    # 检查消息接收
    assert len(received_messages) > 0
    topic, payload = received_messages[0]
    assert "ynex/test/hello" in topic
    assert payload.get("msg") == "world"

    # 取消订阅
    unsubscribe("ynex/test/#", callback)

    print(f"  收到消息: {received_messages[0]}")
    print("  ✓ 内存回退模式测试通过")


def test_multiple_subscribers():
    """测试多个订阅者"""
    print("\n=== 测试多个订阅者 ===")

    messages1 = []
    messages2 = []

    def callback1(topic, payload):
        messages1.append(payload)

    def callback2(topic, payload):
        messages2.append(payload)

    # 多个订阅者订阅同一主题
    subscribe("ynex/broadcast", callback1)
    subscribe("ynex/broadcast", callback2)

    # 发布消息
    publish("ynex/broadcast", {"event": "test"})
    time.sleep(0.5)

    # 两个订阅者都应收到
    assert len(messages1) > 0
    assert len(messages2) > 0

    # 清理
    unsubscribe("ynex/broadcast", callback1)
    unsubscribe("ynex/broadcast", callback2)

    print("  ✓ 多个订阅者测试通过")


def test_status_api():
    """测试状态API"""
    print("\n=== 测试状态API ===")

    status = get_status()

    assert "broker" in status
    assert "connected" in status
    assert "subscribed_topics" in status
    assert "memory_queue_size" in status

    print(f"  状态: {status}")
    print("  ✓ 状态API测试通过")


def test_recent_messages():
    """测试最近消息查询"""
    print("\n=== 测试最近消息查询 ===")

    # 发布几条消息
    publish("ynex/msg1", "test1")
    publish("ynex/msg2", "test2")

    time.sleep(0.3)

    # 获取最近消息
    messages = get_recent_messages(limit=10)

    assert isinstance(messages, list)
    assert len(messages) >= 2

    print(f"  最近消息数: {len(messages)}")
    print("  ✓ 最近消息查询测试通过")


def test_availability_check():
    """测试可用性检查"""
    print("\n=== 测试可用性检查 ===")

    # 这个测试不依赖实际MQTT服务器
    # 在没有MQTT时应回退到内存模式
    available = is_available()

    print(f"  MQTT可用: {available}")
    print("  ✓ 可用性检查测试通过")


def test_wildcard_subscription():
    """测试通配符订阅"""
    print("\n=== 测试通配符订阅 ===")

    messages = []

    def callback(topic, payload):
        messages.append((topic, payload))

    # 订阅通配符主题
    subscribe("ynex/sensor/#", callback)

    # 发布到不同子主题
    publish("ynex/sensor/temp", {"value": 25})
    publish("ynex/sensor/humidity", {"value": 60})
    publish("ynex/light/1", {"state": "on"})  # 不匹配

    time.sleep(0.5)

    # 应收到两条匹配消息
    assert len(messages) >= 2

    # 清理
    unsubscribe("ynex/sensor/#", callback)

    print(f"  收到 {len(messages)} 条匹配消息")
    print("  ✓ 通配符订阅测试通过")


def test_payload_types():
    """测试不同类型Payload"""
    print("\n=== 测试不同类型Payload ===")

    received = []

    def callback(topic, payload):
        received.append(payload)

    subscribe("ynex/types", callback)

    # 字符串
    publish("ynex/types", "string message")
    time.sleep(0.2)

    # 字典
    publish("ynex/types", {"key": "value", "number": 42})
    time.sleep(0.2)

    # 列表
    publish("ynex/types", [1, 2, 3, 4, 5])
    time.sleep(0.2)

    assert len(received) >= 3

    unsubscribe("ynex/types", callback)

    print(f"  收到 {len(received)} 种类型消息")
    print("  ✓ 不同类型Payload测试通过")


def test_concurrent_publish():
    """测试并发发布"""
    print("\n=== 测试并发发布 ===")

    messages = []
    lock = threading.Lock()

    def callback(topic, payload):
        with lock:
            messages.append(payload)

    subscribe("ynex/concurrent", callback)

    def publisher(thread_id):
        for i in range(5):
            publish("ynex/concurrent", {"thread": thread_id, "msg": i})
            time.sleep(0.01)

    threads = [threading.Thread(target=publisher, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(0.5)

    # 应收到所有消息（15条）
    assert len(messages) >= 15

    unsubscribe("ynex/concurrent", callback)

    print(f"  收到 {len(messages)} 条并发消息")
    print("  ✓ 并发发布测试通过")


def main():
    print("=" * 60)
    print("  MQTT消息总线测试")
    print("=" * 60)

    test_topic_matching()
    test_decode_payload()
    test_memory_fallback()
    test_multiple_subscribers()
    test_status_api()
    test_recent_messages()
    test_availability_check()
    test_wildcard_subscription()
    test_payload_types()
    test_concurrent_publish()

    print("\n" + "=" * 60)
    print("  所有MQTT测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()