"""
自动化测试脚本：验证工具调用链、记忆系统和各技能
无需 API Key，直接调用 skill 函数和 mock LLM
"""

import os
from skills import SKILL_MAP, _parse_chinese_time
from brain import get_ai_response
from memory import get_memory, save_memory, set_profile, get_profile


def test_skills():
    """测试所有技能函数"""
    print("\n=== 测试技能函数 ===")

    print("\n[天气]")
    print(SKILL_MAP["get_weather"]("北京"))

    print("\n[时间]")
    print(SKILL_MAP["get_time"]())

    print("\n[文件搜索]")
    print(SKILL_MAP["search_file"]("简历"))

    print("\n[提醒]")
    print(SKILL_MAP["set_reminder"]("开会", "明天上午9点"))

    print("\n[系统状态]")
    print(SKILL_MAP["get_system_info"]())

    print("\n[写笔记]")
    print(SKILL_MAP["write_note"]("测试", "这是一条测试笔记"))

    print("\n[读笔记]")
    print(SKILL_MAP["read_notes"]())

    print("\n[笑话]")
    print(SKILL_MAP["tell_joke"]())

    print("\n[列出提醒]")
    print(SKILL_MAP["list_reminders"]())

    print("\n[取消提醒]")
    print(SKILL_MAP["cancel_reminder"](999))

    print("\n[列出 HA 场景]")
    print(SKILL_MAP["list_ha_scenes"]())

    print("\n[列出 HA 区域]")
    print(SKILL_MAP["list_ha_areas"]())

    print("\n[读取 HA 传感器]")
    print(SKILL_MAP["get_ha_sensor"]("living_room_temperature"))


def test_time_parser():
    """测试中文时间解析"""
    print("\n=== 测试中文时间解析 ===")
    cases = [
        "明天上午10点",
        "今天下午3点",
        "晚上8点",
        "20:30",
        "后天早上9点",
    ]
    for c in cases:
        result = _parse_chinese_time(c)
        print(f"  {c} -> {result}")
        assert result is not None, f"解析失败：{c}"
    print("✅ 中文时间解析全部通过")


def test_memory():
    """测试 SQLite 记忆"""
    print("\n=== 测试 SQLite 记忆 ===")

    # 清空记忆
    save_memory([])
    print("清空记忆后:", get_memory())

    # 保存测试消息
    test_messages = [
        {"role": "system", "content": "你是Y·NEX"},
        {"role": "user", "content": "我叫张三"},
        {"role": "assistant", "content": "好的，张先生。"}
    ]
    save_memory(test_messages)
    loaded = get_memory()
    print("保存后读取:", loaded)
    assert len(loaded) == 3, "记忆读写失败"

    # 测试用户画像
    set_profile("name", "张三")
    name = get_profile("name")
    print(f"用户画像 name: {name}")
    assert name == "张三", "用户画像读写失败"


def test_mock_llm():
    """测试 Mock LLM 工具调用链"""
    print("\n=== 测试 Mock LLM 工具调用链 ===")

    # 清空记忆，避免上下文干扰
    save_memory([])

    test_cases = [
        "北京今天天气怎么样",
        "现在几点",
        "帮我搜索简历文件",
        "提醒我明天开会",
        "打开记事本",
        "看一下系统状态",
        "写笔记 会议纪要",
        "看笔记",
        "讲个笑话",
        "列出提醒",
        "打开客厅灯",
        "列出智能家居",
        "有哪些场景",
        "激活场景 movie_mode",
        "家里有哪些区域",
        "客厅温度传感器多少度",
        "查看邮件",
        "添加日程 项目评审 明天下午3点",
        "搜索 最新 AI 新闻",
        "打开 example.com",
        "帮我准备今天的晨间日报",
        "截图",
        "把音量调到 50",
        "pc.activate.Notepad",
        "有哪些设备",
        "列出自动化规则",
        "你好Y·NEX"
    ]

    for text in test_cases:
        print(f"\n用户: {text}")
        reply = get_ai_response(text, use_mock=True)
        print(f"Y·NEX: {reply}")


def main():
    print("Y·NEX项目自动化测试开始...")

    test_skills()
    test_time_parser()
    test_memory()
    test_mock_llm()

    print("\n=== 全部测试完成 ===")

    # 清理测试产生的提醒文件
    if os.path.exists("data/reminders.txt"):
        print("提醒：测试产生的 data/reminders.txt 已生成，如需清理请手动删除。")


if __name__ == "__main__":
    main()
