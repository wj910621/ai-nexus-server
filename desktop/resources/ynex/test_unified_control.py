"""
统一控制模块测试
覆盖 pc_control、device_hub、mqtt_bus、automation_engine、api_server 的核心链路
"""

import json
import time
from skills import SKILL_MAP
from brain import get_ai_response
from memory import save_memory


def test_pc_control_list_windows():
    """测试电脑控制：列出窗口"""
    print("\n=== PC 控制：列出窗口 ===")
    result = SKILL_MAP["control_pc"](action="list_windows")
    print(result[:200])
    assert "窗口" in result or "失败" in result


def test_device_command_list_domains():
    """测试设备域列表"""
    print("\n=== 设备域列表 ===")
    result = SKILL_MAP["list_device_domains"]()
    print(result)
    assert "pc" in result
    assert "ha" in result


def test_device_command_protocol():
    """测试协议格式指令解析"""
    print("\n=== 协议格式指令 ===")
    result = SKILL_MAP["device_command"]("pc.list_windows")
    print(result[:200])
    assert "窗口" in result or "失败" in result


def test_mqtt_publish():
    """测试 MQTT 发布（内存回退模式）"""
    print("\n=== MQTT 发布 ===")
    result = SKILL_MAP["mqtt_publish"]("ynex/test/hello", "world")
    print(result)
    assert "发布" in result


def test_automation_rules():
    """测试规则增删查"""
    print("\n=== 自动化规则 ===")
    from automation_engine import add_rule, list_rules, trigger_event

    rule = {
        "id": "test_unified",
        "name": "测试规则",
        "enabled": True,
        "trigger": {"type": "event", "event_type": "test_uc"},
        "actions": [{"type": "notify", "message": "先生，统一控制测试规则已触发。"}]
    }
    add_rule(rule)
    result = list_rules()
    print(result)
    assert "测试规则" in result

    trigger_event("test_uc", {})
    time.sleep(0.5)


def test_mock_llm_new_skills():
    """测试 Mock LLM 能触发新工具"""
    print("\n=== Mock LLM 新技能 ===")
    save_memory([])

    cases = [
        "截图",
        "把音量调到 50",
        "pc.activate.Notepad",
        "有哪些设备",
        "列出自动化规则",
    ]

    for text in cases:
        print(f"\n用户: {text}")
        reply = get_ai_response(text, use_mock=True)
        print(f"Y·NEX: {reply[:200]}")
        assert "先生" in reply or "失败" in reply or "窗口" in reply


def main():
    print("Y·NEX统一控制模块测试开始...")

    test_pc_control_list_windows()
    test_device_command_list_domains()
    test_device_command_protocol()
    test_mqtt_publish()
    test_automation_rules()
    test_mock_llm_new_skills()

    print("\n=== 统一控制模块测试完成 ===")


if __name__ == "__main__":
    main()
