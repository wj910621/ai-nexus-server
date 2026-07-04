"""
真实 DeepSeek API 测试脚本
填入 DEEPSEEK_API_KEY 后运行，验证 LLM 是否能正确调用工具
"""

from config import settings
from brain import get_ai_response, validate_api_key
from memory import save_memory


def main():
    print("=== DeepSeek API 真实工具调用测试 ===\n")

    # 第一步：验证 API Key
    print("正在验证 API Key...")
    ok, msg = validate_api_key()
    if ok:
        print(f"✅ {msg}\n")
    else:
        print(f"❌ {msg}")
        print("   请在 .env 文件中正确填写 DEEPSEEK_API_KEY。")
        return

    print(f"✅ 已配置 API Key，模型：{settings.online_model}\n")

    # 清空记忆，避免上下文干扰
    save_memory([])

    test_cases = [
        ("天气查询", "北京今天天气怎么样？"),
        ("时间查询", "现在几点？"),
        ("文件搜索", "帮我搜索合同文件"),
        ("提醒设置", "提醒我明天上午10点开会"),
        ("打开应用", "打开记事本"),
        ("系统状态", "看一下系统状态"),
        ("写笔记", "写笔记 会议纪要：讨论下季度计划"),
        ("讲笑话", "讲个笑话"),
        ("普通闲聊", "你好，Y·NEX"),
    ]

    passed = 0
    failed = 0

    for case_name, user_text in test_cases:
        print(f"【{case_name}】")
        print(f"用户: {user_text}")
        try:
            reply = get_ai_response(user_text, use_mock=False)
            print(f"Y·NEX: {reply}")
            print("✅ 成功\n")
            passed += 1
        except Exception as e:
            print(f"❌ 失败: {e}\n")
            failed += 1

    print("=== 测试结束 ===")
    print(f"通过：{passed} / {len(test_cases)}，失败：{failed}")


if __name__ == "__main__":
    main()
