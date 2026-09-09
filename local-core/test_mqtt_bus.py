"""
mqtt_bus.py 单元测试
====================
覆盖范围：
  - _topic_match：MQTT 主题通配符匹配（+ / #）
  - _decode_payload：JSON 解析 + 字符串 fallback
  - subscribe / publish / unsubscribe：内存队列模式下的 pub/sub
  - _dispatch_local：正确分发到匹配订阅者，回调异常不影响其他
  - get_status / get_recent_messages：状态查询
  - 并发安全：多线程同时 publish + subscribe 不丢消息、不崩溃
"""

import os
import sys
import time
import threading


def _fresh_mqtt_bus():
    """清理模块级可变状态，返回干净的 mqtt_bus 模块。"""
    import importlib
    # 先 import 以获得模块引用
    import mqtt_bus
    # 重置所有全局可变状态
    mqtt_bus._memory_messages.clear()
    mqtt_bus._subscribers.clear()
    mqtt_bus._client = None
    mqtt_bus._connected = False
    return mqtt_bus


def main():
    mb = _fresh_mqtt_bus()
    _run_tests(mb)


def _run_tests(mb):
    errors = []

    # ================================
    # 1. _topic_match —— MQTT 通配符匹配
    # ================================
    print("1. _topic_match 主题通配符匹配")

    # 精确匹配
    assert mb._topic_match("a/b/c", "a/b/c")
    print("   ✓ 精确匹配 a/b/c == a/b/c")

    # + 单层通配
    assert mb._topic_match("a/+/c", "a/b/c")
    assert mb._topic_match("a/+/c", "a/x/c")
    assert not mb._topic_match("a/+/c", "a/b/d")
    assert not mb._topic_match("a/+/c", "a/c")  # 层级不符
    print("   ✓ + 单层通配")

    # # 多层通配
    assert mb._topic_match("a/#", "a/b/c")
    assert mb._topic_match("a/#", "a")  # # 也匹配空子树
    assert mb._topic_match("a/#", "a/x/y/z")
    assert not mb._topic_match("a/#", "b/x")
    print("   ✓ # 多层通配")

    # # 只能出现在末尾（MQTT 规范），虽然实现不强校验，但验证行为
    assert mb._topic_match("#", "anything/is/ok")
    assert mb._topic_match("#", "just_one")
    print("   ✓ # 作为根订阅匹配一切")

    # 多层 + 和 # 混合
    assert mb._topic_match("ynex/+/sensor/#", "ynex/device1/sensor/temp")
    assert mb._topic_match("ynex/+/sensor/#", "ynex/x/sensor/a/b/c")
    assert not mb._topic_match("ynex/+/sensor/#", "ynex/sensor/temp")
    print("   ✓ 混合 + # 通配")

    # 不匹配场景
    assert not mb._topic_match("a/b/c", "a/b")
    assert not mb._topic_match("a/b", "a/b/c")
    print("   ✓ 层级严格匹配（无通配时）")

    # ================================
    # 2. _decode_payload
    # ================================
    print("\n2. _decode_payload payload 解码")

    # JSON dict
    payload = b'{"hello": "world", "n": 42}'
    decoded = mb._decode_payload(payload)
    assert decoded == {"hello": "world", "n": 42}
    print("   ✓ JSON dict 正确解码")

    # JSON list
    decoded = mb._decode_payload(b'[1,2,3]')
    assert decoded == [1, 2, 3]
    print("   ✓ JSON list 正确解码")

    # 非 JSON 字符串
    decoded = mb._decode_payload(b'hello world')
    assert decoded == "hello world"
    print("   ✓ 非 JSON 作为字符串返回")

    # 空 bytes
    decoded = mb._decode_payload(b'')
    assert decoded == ""
    print("   ✓ 空 bytes 返回空字符串")

    # ================================
    # 3. subscribe / publish —— 内存队列模式
    # ================================
    print("\n3. subscribe / publish 内存模式")

    # 确认当前是内存模式（没有 MQTT broker 也没关系）
    status = mb.get_status()
    print(f"   当前状态: connected={status['connected']}, broker={status['broker']}")

    received = []
    lock = threading.Lock()

    def on_any(topic, payload):
        with lock:
            received.append((topic, payload))

    mb.subscribe("ynex/+/status", on_any)
    mb.publish("ynex/device1/status", {"online": True})
    mb.publish("ynex/device2/status", "hello")
    mb.publish("ynex/something_else", "ignored")  # 不应匹配

    time.sleep(0.05)  # 给分发一点时间（虽然内存模式是同步的）

    with lock:
        matched = received[:]

    assert len(matched) == 2, f"应收到 2 条，实际 {len(matched)}: {matched}"
    topics_seen = {t for t, _ in matched}
    assert "ynex/device1/status" in topics_seen
    assert "ynex/device2/status" in topics_seen
    print(f"   ✓ 通配订阅正确匹配收到 {len(matched)} 条")

    # 消息进入内存队列
    recent = mb.get_recent_messages(limit=10)
    assert len(recent) >= 3  # 3 次 publish
    print(f"   ✓ 内存队列积累 {len(recent)} 条消息")

    # ================================
    # 4. 多订阅者同主题都收到
    # ================================
    print("\n4. 多订阅者同主题")

    r1, r2 = [], []
    l1, l2 = threading.Lock(), threading.Lock()

    def cb1(t, p):
        with l1:
            r1.append((t, p))

    def cb2(t, p):
        with l2:
            r2.append((t, p))

    mb.subscribe("ynex/broadcast", cb1)
    mb.subscribe("ynex/broadcast", cb2)
    mb.publish("ynex/broadcast", "hello_broadcast")

    time.sleep(0.05)

    with l1, l2:
        assert len(r1) == 1 and len(r2) == 1
    print("   ✓ 同主题多订阅者都收到")

    # ================================
    # 5. 取消订阅
    # ================================
    print("\n5. unsubscribe")

    r3 = []
    l3 = threading.Lock()

    def cb3(t, p):
        with l3:
            r3.append(t)

    mb.subscribe("ynex/unsub_test", cb3)
    mb.publish("ynex/unsub_test", "msg1")
    time.sleep(0.02)
    mb.unsubscribe("ynex/unsub_test", cb3)
    mb.publish("ynex/unsub_test", "msg2")
    time.sleep(0.02)
    with l3:
        assert len(r3) == 1, f"unsubscribe 后不应再收到，实际 {len(r3)}: {r3}"
    print("   ✓ unsubscribe 生效，后续消息不再到达")

    # 取消不存在的回调 / 主题不应抛异常
    mb.unsubscribe("non/existent", lambda t, p: None)
    print("   ✓ unsubscribe 对不存在的主题/回调不抛异常")

    # ================================
    # 6. 订阅者回调异常隔离
    # ================================
    print("\n6. 回调异常隔离")

    bad_received = []
    good_received = []
    lb = threading.Lock()
    lg = threading.Lock()

    def bad_cb(t, p):
        raise RuntimeError("故意的 bug!")

    def good_cb(t, p):
        with lg:
            good_received.append(t)

    mb.subscribe("ynex/isolation", bad_cb)
    mb.subscribe("ynex/isolation", good_cb)

    # 只要 good_cb 能收到，说明 bad_cb 异常没有中断分发
    # 注意 _dispatch_local 中 logger.exception 会记录但继续
    mb.publish("ynex/isolation", "should_reach_good_only")
    time.sleep(0.05)
    with lg:
        assert len(good_received) >= 1, "good_cb 应收到（异常隔离）"
    print("   ✓ 某订阅者抛异常不影响其他订阅者")

    # ================================
    # 7. 并发安全 —— 多线程 pub + sub
    # ================================
    print("\n7. 并发安全（16 线程 × 50 次 publish）")

    mb2 = _fresh_mqtt_bus()
    global_received = []
    global_lock = threading.Lock()
    exceptions = []

    def collect(t, p):
        with global_lock:
            global_received.append((t, p))

    mb2.subscribe("test/#", collect)

    def publish_worker(i):
        try:
            for j in range(50):
                mb2.publish(f"test/worker-{i}/msg-{j}", {"i": i, "j": j})
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=publish_worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(0.1)  # 等分发完

    assert not exceptions, f"并发 publish 出现异常: {exceptions}"
    with global_lock:
        count = len(global_received)
    assert count == 16 * 50, f"应收到 800 条，实际 {count}"
    print(f"   ✓ 16 线程并发 publish 全部收到 ({count} 条)，无异常")

    # 订阅者数量验证
    status = mb2.get_status()
    assert status["memory_queue_size"] >= 800
    print(f"   ✓ 内存队列 size={status['memory_queue_size']}")

    # ================================
    # 8. 并发 subscribe + unsubscribe + publish 混合
    # ================================
    print("\n8. 混合并发（subscribe/unsubscribe/publish）")

    mb3 = _fresh_mqtt_bus()
    per_subscriber_received = {}
    per_subscriber_lock = threading.Lock()
    mixed_exceptions = []

    def make_cb(name):
        def cb(t, p):
            with per_subscriber_lock:
                per_subscriber_received[name] = per_subscriber_received.get(name, 0) + 1
        return cb

    def sched_subscribe(name, topic):
        try:
            mb3.subscribe(topic, make_cb(name))
        except Exception as e:
            mixed_exceptions.append(e)

    def sched_publish(topic):
        try:
            mb3.publish(topic, "mixed_payload")
        except Exception as e:
            mixed_exceptions.append(e)

    threads = []
    for i in range(10):
        t = threading.Thread(target=sched_subscribe, args=(f"sub{i}", f"mix/{i}"))
        threads.append(t)
    for _ in range(20):
        for i in range(10):
            t = threading.Thread(target=sched_publish, args=(f"mix/{i}",))
            threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not mixed_exceptions, f"混合并发出现异常: {mixed_exceptions}"
    with per_subscriber_lock:
        total = sum(per_subscriber_received.values())
    assert total > 0
    print(f"   ✓ 10 subscribe + 200 publish 混合并发无异常，总到达 {total}")

    # ================================
    # 结果
    # ================================
    print("\n" + "=" * 50)
    if errors:
        print(f"❌ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("🎉 mqtt_bus.py 全部测试通过")


if __name__ == "__main__":
    main()
