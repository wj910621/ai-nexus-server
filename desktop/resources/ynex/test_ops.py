"""
测试运维工具箱：启动报告 + 数据库自动备份
"""

import os
import json
import time
import shutil
import zipfile
from pathlib import Path


def _clean(backups_dir="backups_test"):
    if os.path.exists(backups_dir):
        shutil.rmtree(backups_dir)
    if os.path.exists("restored"):
        shutil.rmtree("restored")
    if os.path.exists("data_test"):
        shutil.rmtree("data_test")


def test_startup_report():
    from ops import generate_startup_report, StartupReport

    report = generate_startup_report()
    assert isinstance(report, StartupReport)
    assert isinstance(report.ok, bool)
    assert isinstance(report.errors, list)
    assert isinstance(report.warnings, list)
    print("✓ 启动报告生成正常")


def test_backup_manager():
    from ops import DatabaseBackupManager

    _clean()
    os.makedirs("data_test", exist_ok=True)
    with open("data_test/memory.db", "w", encoding="utf-8") as f:
        f.write("fake sqlite")

    mgr = DatabaseBackupManager(backup_dir="backups_test", interval_hours=9999, keep_count=2)
    record = mgr.backup(sources=["data_test/memory.db"])

    assert os.path.exists(record.path)
    assert record.size_bytes > 0
    assert record.id

    records = mgr.list_backups()
    assert len(records) >= 1

    # 测试恢复
    result = mgr.restore(record.id, target_dir="restored")
    assert result["ok"]
    assert os.path.exists("restored/data/memory.db")

    # 测试清理：生成 3 个备份，只保留 2 个
    for _ in range(2):
        time.sleep(0.1)
        mgr.backup(sources=["data_test/memory.db"])
    records = mgr.list_backups()
    assert len(records) <= 2, f"备份保留策略失效: {len(records)}"

    _clean()
    print("✓ 数据库备份/恢复/清理正常")


def test_plugin_hot_reload_keeps_dir():
    """测试热重载不会删除插件目录"""
    import tempfile
    from plugin_system import PluginManager

    tmpdir = tempfile.mkdtemp(prefix="yijie_plugin_test_")
    plugin_dir = os.path.join(tmpdir, "demo")
    os.makedirs(plugin_dir)
    with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('''def register(manager):\n    manager.register_skill("demo", "hello", hello)\n\ndef hello():\n    return "hello v1"\n''')
    with open(os.path.join(plugin_dir, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "demo", "name": "demo", "version": "1.0.0", "author": "test", "enabled": True}, f)

    mgr = PluginManager()
    mgr._hot_reload_enabled = False
    mgr.load_plugins(plugins_dir=tmpdir)

    assert "demo" in mgr.plugins
    assert mgr.call_skill("hello") == "hello v1"

    # 修改文件
    time.sleep(0.5)
    with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('''def register(manager):\n    manager.register_skill("demo", "hello", hello)\n\ndef hello():\n    return "hello v2"\n''')

    ok = mgr.reload_plugin("demo")
    assert ok, "热重载失败"
    assert os.path.exists(plugin_dir), "热重载不应该删除插件目录"
    assert mgr.call_skill("hello") == "hello v2"

    shutil.rmtree(tmpdir)
    print("✓ 插件热重载保留目录正常")


if __name__ == "__main__":
    test_startup_report()
    test_backup_manager()
    test_plugin_hot_reload_keeps_dir()
    print("\n运维与插件热重载测试全部通过")
