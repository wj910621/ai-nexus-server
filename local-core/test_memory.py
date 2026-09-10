"""
记忆模块测试
覆盖对话历史读写、system 消息去重、历史长度限制、用户画像读写。
"""

import os
import sys
import tempfile
import shutil

# 隔离测试数据库
TEST_DIR = tempfile.mkdtemp(prefix="ynex_memory_test_")
os.environ["MEMORY_DB"] = os.path.join(TEST_DIR, "memory.db")

# memory 使用 settings.memory_db，需在导入前调整配置路径
import config
config.settings.memory_db = os.path.join(TEST_DIR, "memory.db")

import memory


def _clean_db():
    """清理数据库文件以重置状态"""
    db_path = config.settings.memory_db
    if os.path.exists(db_path):
        os.remove(db_path)
    # 重置模块内部状态（_init_db 会重新建表）


def test_save_and_get_memory():
    """基本对话历史保存与读取"""
    print("\n=== 对话历史保存与读取 ===")
    _clean_db()

    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "您好！"},
    ]
    memory.save_memory(messages)
    retrieved = memory.get_memory()

    assert len(retrieved) == 3
    assert retrieved[0]["role"] == "system"
    assert retrieved[1]["role"] == "user"
    assert retrieved[2]["role"] == "assistant"
    assert retrieved[2]["content"] == "您好！"
    print("  ✅ 基本读写正确")


def test_system_message_dedup():
    """system 消息去重：仅保留最新一条"""
    print("\n=== system 消息去重 ===")
    _clean_db()

    batch1 = [
        {"role": "system", "content": "旧系统提示"},
        {"role": "user", "content": "问题1"},
    ]
    memory.save_memory(batch1)

    batch2 = [
        {"role": "system", "content": "新系统提示"},
        {"role": "user", "content": "问题2"},
    ]
    memory.save_memory(batch2)

    retrieved = memory.get_memory()
    system_msgs = [m for m in retrieved if m["role"] == "system"]
    assert len(system_msgs) == 1, f"应仅保留 1 条 system 消息，实际 {len(system_msgs)}"
    assert system_msgs[0]["content"] == "新系统提示"
    print("  ✅ system 消息去重正确")


def test_history_length_limit():
    """历史长度限制：非 system 消息超过 max_history*4 后应截断"""
    print("\n=== 历史长度限制 ===")
    _clean_db()

    # 临时降低 max_history 以便测试
    original_max = config.settings.max_history
    config.settings.max_history = 3

    try:
        messages = [{"role": "system", "content": "助手"}]
        for i in range(20):
            messages.append({"role": "user", "content": f"消息{i}"})
        memory.save_memory(messages)

        retrieved = memory.get_memory()
        non_system = [m for m in retrieved if m["role"] != "system"]
        # 应保留最近 max_history*4 = 12 条
        assert len(non_system) <= 12, f"非 system 消息应 <=12，实际 {len(non_system)}"
    finally:
        config.settings.max_history = original_max
    print("  ✅ 历史长度限制正确")


def test_tool_calls_persistence():
    """tool_calls 字段的序列化与反序列化"""
    print("\n=== tool_calls 持久化 ===")
    _clean_db()

    messages = [
        {"role": "system", "content": "助手"},
        {
            "role": "assistant",
            "content": "调用工具",
            "tool_calls": [{"id": "call_1", "function": {"name": "get_time"}}],
        },
        {"role": "tool", "content": "10:00", "tool_call_id": "call_1"},
    ]
    memory.save_memory(messages)
    retrieved = memory.get_memory()

    assistant_msg = [m for m in retrieved if m["role"] == "assistant"][0]
    assert "tool_calls" in assistant_msg
    assert assistant_msg["tool_calls"][0]["id"] == "call_1"

    tool_msg = [m for m in retrieved if m["role"] == "tool"][0]
    assert tool_msg.get("tool_call_id") == "call_1"
    print("  ✅ tool_calls 持久化正确")


def test_profile_read_write():
    """用户画像读写与默认值"""
    print("\n=== 用户画像读写 ===")
    _clean_db()

    assert memory.get_profile("nonexistent_key", default="fallback") == "fallback"

    memory.set_profile("username", "Alice")
    assert memory.get_profile("username") == "Alice"

    memory.set_profile("username", "Bob")
    assert memory.get_profile("username") == "Bob"

    memory.set_profile("preference", "dark_mode")
    assert memory.get_profile("preference") == "dark_mode"
    print("  ✅ 用户画像读写正确")


def test_get_memory_ordering():
    """get_memory 返回顺序：system 在前，其余按时间正序"""
    print("\n=== 读取顺序验证 ===")
    _clean_db()

    for i in range(5):
        memory.save_memory([
            {"role": "user", "content": f"Q{i}"},
            {"role": "assistant", "content": f"A{i}"},
        ])

    retrieved = memory.get_memory()
    # 没有 system 消息时，顺序应为正序
    user_contents = [m["content"] for m in retrieved if m["role"] == "user"]
    assert user_contents == [f"Q{i}" for i in range(5)]
    print("  ✅ 读取顺序正确")


def main():
    print("=" * 60)
    print("  记忆模块测试")
    print("=" * 60)

    try:
        test_save_and_get_memory()
        test_system_message_dedup()
        test_history_length_limit()
        test_tool_calls_persistence()
        test_profile_read_write()
        test_get_memory_ordering()
    finally:
        shutil.rmtree(TEST_DIR, ignore_errors=True)

    print("\n" + "=" * 60)
    print("  ✅ 全部记忆测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
