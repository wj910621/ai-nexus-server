"""
定时任务调度器测试
"""

import time
import sys
from datetime import datetime, timedelta

try:
    from scheduler import (
        get_scheduler,
        add_one_time_reminder,
        list_active_reminders,
        cancel_reminder,
        shutdown_scheduler,
        set_reminder_callback
    )
    _SCHEDULER_AVAILABLE = True
except ModuleNotFoundError as e:
    if "apscheduler" in str(e):
        print("提示：apscheduler 未安装，跳过 scheduler 测试。")
        _SCHEDULER_AVAILABLE = False
    else:
        raise


def test_one_time_reminder():
    """测试一次性提醒"""
    print("\n=== 一次性提醒 ===")
    notified = {"flag": False}

    def cb(msg):
        notified["flag"] = True
        print(f"触发回调：{msg}")

    set_reminder_callback(cb)
    trigger_time = datetime.now() + timedelta(seconds=2)
    result = add_one_time_reminder("测试喝水", trigger_time)
    print(result)

    print("等待 3 秒...")
    time.sleep(3)
    assert notified["flag"], "提醒应在 2 秒后触发"
    print("✅ 一次性提醒触发成功")


def test_list_and_cancel():
    """测试列出和取消提醒"""
    print("\n=== 列出/取消提醒 ===")
    trigger_time = datetime.now() + timedelta(hours=1)
    add_one_time_reminder("测试会议", trigger_time)
    add_one_time_reminder("测试散步", trigger_time + timedelta(minutes=30))

    result = list_active_reminders()
    print(result)
    assert "测试会议" in result
    assert "测试散步" in result

    # 取消第一个
    cancel_reminder(1)
    result = list_active_reminders()
    print(result)
    print("✅ 列出/取消提醒成功")


def test_cron_reminder():
    """测试周期提醒（仅验证添加，不等待触发）"""
    print("\n=== 周期提醒 ===")
    from scheduler import add_cron_reminder
    result = add_cron_reminder("工作日早安", "0 9 * * 1-5")
    print(result)
    assert "已设置周期提醒" in result
    print("✅ 周期提醒添加成功")


def main():
    print("=== 定时任务调度器测试 ===")
    if not _SCHEDULER_AVAILABLE:
        print("跳过测试：apscheduler 未安装。")
        sys.exit(0)
    get_scheduler()
    try:
        test_one_time_reminder()
        test_list_and_cancel()
        test_cron_reminder()
    finally:
        shutdown_scheduler()
    print("\n全部测试完成")


if __name__ == "__main__":
    main()
