"""
记忆增强模块测试
测试事实提取、用户画像更新、对话摘要
"""

from memory import set_profile, get_profile, save_memory, get_memory
from memory_enhancer import (
    extract_facts,
    get_profile_summary,
    should_summarize,
    summarize_old_messages,
    enhance_memory
)


def test_rule_extraction():
    """测试规则提取"""
    print("\n=== 规则事实提取 ===")
    messages = [
        {"role": "user", "content": "我叫张三，住在北京。"},
        {"role": "assistant", "content": "好的，张先生。"},
        {"role": "user", "content": "我喜欢喝咖啡。"},
    ]
    facts = extract_facts(messages)
    print(f"提取到的事实：{facts}")
    assert "name" in facts or "city" in facts or "preference" in facts, "规则提取应至少返回一个事实"
    print("✅ 规则提取通过")


def test_profile_update():
    """测试用户画像更新"""
    print("\n=== 用户画像更新 ===")
    set_profile("name", "测试用户")
    set_profile("city", "上海")
    summary = get_profile_summary()
    print(f"画像摘要：\n{summary}")
    assert "name: 测试用户" in summary
    assert "city: 上海" in summary
    print("✅ 用户画像通过")


def test_summarize():
    """测试对话摘要判断"""
    print("\n=== 对话摘要 ===")
    messages = [{"role": "system", "content": "你是Y·NEX"}]
    for i in range(50):
        messages.append({"role": "user", "content": f"消息{i}"})
        messages.append({"role": "assistant", "content": f"回复{i}"})

    print(f"消息数：{len(messages)}，需要摘要：{should_summarize(messages)}")
    assert should_summarize(messages) is True

    # 如果配置了 API Key，实际测试摘要生成
    from config import settings
    has_real_key = settings.deepseek_api_key and settings.deepseek_api_key.startswith("sk-") and "xxxx" not in settings.deepseek_api_key
    if has_real_key:
        summarized = summarize_old_messages(messages)
        print(f"摘要后消息数：{len(summarized)}")
        print("✅ 摘要生成通过")
    else:
        print("⏭️  未配置真实 API Key，跳过实际摘要生成测试")


def test_enhance_memory():
    """测试完整记忆增强流程"""
    print("\n=== 完整记忆增强流程 ===")
    save_memory([
        {"role": "system", "content": "你是Y·NEX"},
        {"role": "user", "content": "我叫李四，工作是程序员。"},
        {"role": "assistant", "content": "好的，李先生。"},
    ])

    messages = enhance_memory(get_memory())
    print(f"增强后消息数：{len(messages)}")

    name = get_profile("name")
    job = get_profile("job")
    print(f"画像：name={name}, job={job}")
    assert name == "李四" or job == "程序员", "应自动提取姓名或职业"
    print("✅ 完整流程通过")


def main():
    print("=== 记忆增强模块测试 ===")
    test_rule_extraction()
    test_profile_update()
    test_summarize()
    test_enhance_memory()
    print("\n全部测试完成")


if __name__ == "__main__":
    main()
