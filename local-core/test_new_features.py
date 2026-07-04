"""
新功能集成测试
- 远程语音通道
- ESP32 传感器 + 自动化
- 剪贴板监听
- 认证与权限
"""

import os
import sys
import time
import socket
import threading

# 修改数据目录避免污染
os.environ["YNEX_API_PORT"] = "7798"


def test_auth():
    print("\n=== 测试认证模块 ===")
    from auth import create_api_key, verify_request, check_permission, UserRole

    raw, kid = create_api_key("测试", UserRole.FAMILY)
    ok, role, err = verify_request(raw, "127.0.0.1")
    assert ok, f"认证失败: {err}"
    assert role == UserRole.FAMILY
    assert check_permission(role, "chat")
    assert not check_permission(role, "admin_users")
    print("✅ 认证模块测试通过")


def test_remote_voice_protocol():
    print("\n=== 测试远程语音协议 ===")
    from remote_voice import start_remote_voice_server, REMOTE_VOICE_PORT

    start_remote_voice_server()
    time.sleep(0.3)

    # 构造一个最小 WAV 文件
    import wave
    import io
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 1000)
    wav_data = buffer.getvalue()

    # 发送测试数据包
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    chunk_size = 1400
    sock.sendto(b"\x01" + wav_data[:chunk_size], ("127.0.0.1", REMOTE_VOICE_PORT))
    offset = chunk_size
    while offset < len(wav_data):
        end = min(offset + chunk_size, len(wav_data))
        chunk = wav_data[offset:end]
        flag = b"\xff" if end == len(wav_data) else b"\x02"
        sock.sendto(flag + chunk, ("127.0.0.1", REMOTE_VOICE_PORT))
        offset = end
    sock.close()

    time.sleep(0.5)
    print("✅ 远程语音数据包发送成功（服务器端接收未报错即通过）")


def test_esp_sensors():
    print("\n=== 测试 ESP32 传感器模块 ===")
    from esp_sensors import (
        start_sensor_listener, get_sensor_states, is_someone_present,
        is_door_open, human_summary
    )
    from mqtt_bus import publish

    start_sensor_listener()
    time.sleep(0.2)

    publish("ynex/sensor/living_room/pir/001", {"state": "detected", "battery": 85})
    publish("ynex/sensor/front_door/door/001", {"state": "open"})
    time.sleep(0.5)

    states = get_sensor_states()
    assert "living_room.pir.001" in states
    assert states["living_room.pir.001"]["state"] == "detected"
    assert is_someone_present()
    assert is_door_open()
    summary = human_summary()
    assert "有人" in summary
    assert "门窗未关" in summary
    print("✅ ESP32 传感器模块测试通过")


def test_clipboard_detection():
    print("\n=== 测试剪贴板内容识别 ===")
    from clipboard_listener import _detect_content_type

    cases = [
        ("https://example.com", "url"),
        ("def hello():\n    print('hi')", "code"),
        ("python test.py", "command"),
        ("a" * 300, "long_text"),
        ("hello", "short_text"),
        ("", "empty"),
    ]
    for text, expected in cases:
        result = _detect_content_type(text)
        assert result == expected, f"内容识别失败：'{text[:20]}' -> {result}, 期望 {expected}"
    print("✅ 剪贴板内容识别测试通过")


def main():
    print("=== Y·NEX新功能集成测试 ===")
    test_auth()
    test_remote_voice_protocol()
    test_esp_sensors()
    test_clipboard_detection()
    print("\n=== 全部新功能测试通过 ===")


if __name__ == "__main__":
    main()
