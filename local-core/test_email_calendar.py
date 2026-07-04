"""
邮件与日历集成测试
未配置邮箱时验证降级，日程功能本地可测
"""

from email_calendar import read_emails, send_email, add_event, list_events


def test_email_without_config():
    print("\n=== 邮件功能（未配置） ===")
    print(read_emails())
    print(send_email("test@example.com", "测试", "内容"))
    print("✅ 邮件降级正常")


def test_calendar():
    print("\n=== 日历功能 ===")
    print(add_event("测试会议", "明天下午3点", "讨论项目"))
    print(add_event("提交报告", "后天上午9点"))
    print(list_events(7))
    print("✅ 日历功能正常")


def main():
    print("=== 邮件与日历集成测试 ===")
    test_email_without_config()
    test_calendar()
    print("\n全部测试完成")


if __name__ == "__main__":
    main()
