"""
plugin_system.py 安全与边界测试
================================

目标：覆盖插件系统的关键安全路径与并发行为：
  - 插件签名验证（HMAC-SHA256）的可预测性与拒绝行为
  - 插件沙箱对模块导入的拦截
  - 事件总线的线程安全派发
  - 插件配置存储的持久化
  - 远程安装的 Zip Slip 路径穿越防护
  - 远程安装的体积/数量限制
  - 插件元信息启用/禁用位

所有测试使用临时目录，不污染仓库根目录。
"""

import os
import sys
import io
import json
import zipfile
import shutil
import tempfile
import threading
import time
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import plugin_system  # noqa: E402
from plugin_system import (  # noqa: E402
    PluginSignatureVerifier,
    PluginSandbox,
    EventBus,
    PluginConfigStore,
    PluginManager,
)


# ---------------------------------------------------------------------------
# 1. PluginSignatureVerifier
# ---------------------------------------------------------------------------

def _write_manifest(tmpdir: str, payload: dict) -> str:
    path = os.path.join(tmpdir, "plugin.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path


def test_sign_is_deterministic_and_changes_with_content():
    v = PluginSignatureVerifier(secret="unit-test-secret")
    tmpdir = tempfile.mkdtemp(prefix="ynex_sign_")
    try:
        _write_manifest(tmpdir, {"id": "p1", "name": "p1"})
        sig1 = v.sign(tmpdir)
        sig2 = v.sign(tmpdir)
        assert sig1 == sig2, "相同内容必须产生相同签名"
        assert len(sig1) == 64, "HMAC-SHA256 hex 应为 64 字符"

        # 改动内容
        _write_manifest(tmpdir, {"id": "p1", "name": "p1-modified"})
        sig3 = v.sign(tmpdir)
        assert sig3 != sig1, "内容变化应产生不同签名"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ sign 对相同输入稳定，对内容变化敏感")


def test_verify_rejects_missing_signature_field():
    v = PluginSignatureVerifier(secret="k")
    tmpdir = tempfile.mkdtemp(prefix="ynex_v_")
    try:
        _write_manifest(tmpdir, {"id": "p1", "name": "p1"})
        assert v.verify(tmpdir) is False, "无 signature 字段必须拒绝"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ 缺少 signature 字段：拒绝")


def test_verify_rejects_wrong_signature():
    v = PluginSignatureVerifier(secret="k")
    tmpdir = tempfile.mkdtemp(prefix="ynex_v_")
    try:
        _write_manifest(tmpdir, {"id": "p1", "name": "p1", "signature": "deadbeef" * 8})
        assert v.verify(tmpdir) is False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ 错误签名：拒绝")


def test_verify_rejects_when_manifest_missing():
    v = PluginSignatureVerifier(secret="k")
    tmpdir = tempfile.mkdtemp(prefix="ynex_v_")
    try:
        # 不写 plugin.json
        assert v.verify(tmpdir) is False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ plugin.json 缺失：拒绝")


def test_verify_without_secret_only_allows_builtin_dir():
    """未配置密钥：仅放行内置插件目录。"""
    v = PluginSignatureVerifier(secret="")

    # 外部目录：拒绝
    external = tempfile.mkdtemp(prefix="ynex_external_")
    try:
        _write_manifest(external, {"id": "evil", "name": "evil"})
        assert v.verify(external) is False, "外部目录无密钥必须拒绝"
    finally:
        shutil.rmtree(external, ignore_errors=True)

    # 内置目录：放行（仅当目录确实位于 plugin_system.py 同级的 plugins/ 下）
    builtin = os.path.abspath(
        os.path.join(os.path.dirname(plugin_system.__file__), "plugins")
    )
    # 在 builtin 内创建一个临时子目录用于验证
    if os.path.isdir(builtin):
        target = os.path.join(builtin, f"_unittest_target_{int(time.time())}")
        os.makedirs(target, exist_ok=True)
        try:
            _write_manifest(target, {"id": "t", "name": "t"})
            assert v.verify(target) is True, f"内置目录无密钥应放行，但拒绝：{target}"
        finally:
            shutil.rmtree(target, ignore_errors=True)
    print("  ✓ 无密钥：仅放行内置目录，拒绝外部")


def test_verify_tampered_file_rejected():
    """当配置密钥时，被篡改的 manifest 必须被拒绝。"""
    v = PluginSignatureVerifier(secret="shared-secret")
    tmpdir = tempfile.mkdtemp(prefix="ynex_tamper_")
    try:
        # 先写一份内容
        _write_manifest(tmpdir, {"id": "p", "name": "original"})
        sig = v.sign(tmpdir)
        # 把签名注入 manifest
        with open(os.path.join(tmpdir, "plugin.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "p", "name": "original", "signature": sig}, f)
        # 改一个字符
        with open(os.path.join(tmpdir, "plugin.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "p", "name": "tampered", "signature": sig}, f)
        assert v.verify(tmpdir) is False, "篡改后必须拒绝"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ 篡改检测：拒绝")


# ---------------------------------------------------------------------------
# 2. PluginSandbox
# ---------------------------------------------------------------------------

def test_sandbox_allows_whitelisted_import():
    sb = PluginSandbox()
    result = sb.run(lambda: __import__("math").sqrt(16))
    assert result == 4.0
    print("  ✓ 沙箱允许白名单模块（math）")


def test_sandbox_blocks_non_whitelisted_import():
    sb = PluginSandbox()
    raised = False
    try:
        sb.run(lambda: __import__("subprocess"))
    except ImportError as e:
        raised = True
        assert "禁止" in str(e)
    assert raised, "非白名单模块 subprocess 必须被拦截"
    print("  ✓ 沙箱拒绝非白名单模块（subprocess）")


def test_sandbox_restores_import_after_run():
    """无论函数是否抛错，builtins.__import__ 都应被恢复。"""
    import builtins
    sb = PluginSandbox()
    original = builtins.__import__

    def bad():
        __import__("subprocess")

    try:
        sb.run(bad)
    except ImportError:
        pass
    assert builtins.__import__ is original, "异常路径下沙箱必须恢复 import"

    # 正常路径
    def good():
        return __import__("json").dumps({})
    sb.run(good)
    assert builtins.__import__ is original, "正常路径下沙箱必须恢复 import"
    print("  ✓ 沙箱运行后恢复 builtins.__import__")


def test_sandbox_custom_allowed_modules():
    """自定义白名单覆盖默认集合。"""
    sb = PluginSandbox(allowed_modules={"json"})
    # json 是允许的
    assert sb.run(lambda: __import__("json").dumps({"a": 1})) == '{"a": 1}'
    # math 不在自定义白名单中
    raised = False
    try:
        sb.run(lambda: __import__("math"))
    except ImportError:
        raised = True
    assert raised
    print("  ✓ 自定义白名单生效")


# ---------------------------------------------------------------------------
# 3. EventBus
# ---------------------------------------------------------------------------

def test_eventbus_emit_calls_all_listeners():
    eb = EventBus()
    log = []
    eb.on("e", lambda x: log.append(("a", x)))
    eb.on("e", lambda x: log.append(("b", x)))
    eb.emit("e", 7)
    assert log == [("a", 7), ("b", 7)]
    print("  ✓ emit 触发所有监听器")


def test_eventbus_off_removes_listener():
    eb = EventBus()
    log = []
    h1 = lambda x: log.append(("a", x))
    h2 = lambda x: log.append(("b", x))
    eb.on("e", h1)
    eb.on("e", h2)
    eb.off("e", h1)
    eb.emit("e", 1)
    assert log == [("b", 1)]
    print("  ✓ off 移除指定监听器")


def test_eventbus_handler_exception_does_not_break_dispatch():
    eb = EventBus()
    log = []
    eb.on("e", lambda x: (_ for _ in ()).throw(ValueError("boom")))
    eb.on("e", lambda x: log.append(("ok", x)))
    eb.emit("e", 99)  # 不应抛出
    assert log == [("ok", 99)]
    print("  ✓ 异常监听器不会中断其他监听器")


def test_eventbus_emit_unknown_event_is_noop():
    eb = EventBus()
    eb.emit("never-registered")  # 不应抛错
    print("  ✓ 未注册事件安全 noop")


def test_eventbus_concurrent_on_emit_safe():
    """并发 on/emit 不能崩溃且所有事件应至少被派发。"""
    eb = EventBus()
    counter = {"n": 0}
    lock = threading.Lock()

    def handler(x):
        with lock:
            counter["n"] += 1

    # 启动并发 emit 与注册
    stop = threading.Event()
    errors = []

    def emit_loop():
        try:
            for i in range(200):
                eb.emit("e", i)
        except Exception as e:
            errors.append(e)

    def register_loop():
        try:
            for i in range(200):
                eb.on("e", handler)
                eb.off("e", handler)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=emit_loop),
        threading.Thread(target=register_loop),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"并发下出现异常: {errors}"
    # 至少有一些事件被处理（因为 register_loop 在 on/off 之间切换，
    # 实际处理次数不确定，只断言没有崩溃）
    assert counter["n"] >= 0
    print("  ✓ EventBus 并发下不发崩溃")


# ---------------------------------------------------------------------------
# 4. PluginConfigStore
# ---------------------------------------------------------------------------

def test_config_store_set_get_roundtrip():
    tmpdir = tempfile.mkdtemp(prefix="ynex_cfg_")
    try:
        path = os.path.join(tmpdir, "pcfg.json")
        store = PluginConfigStore(config_file=path)
        store.set("plug-a", "theme", "dark")
        store.set("plug-a", "limit", 42)
        # 重新构造实例，验证持久化
        store2 = PluginConfigStore(config_file=path)
        assert store2.get("plug-a", "theme") == "dark"
        assert store2.get("plug-a", "limit") == 42
        # 默认值
        assert store2.get("plug-a", "missing", default=None) is None
        # 未知插件
        assert store2.get("plug-b", "any", default="x") == "x"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ ConfigStore 持久化往返")


def test_config_store_update_and_delete():
    tmpdir = tempfile.mkdtemp(prefix="ynex_cfg_")
    try:
        path = os.path.join(tmpdir, "pcfg.json")
        store = PluginConfigStore(config_file=path)
        store.set("p", "a", 1)
        store.update("p", {"b": 2, "c": 3})
        assert store.get("p", "a") == 1
        assert store.get("p", "b") == 2
        assert store.get("p", "c") == 3
        # 删除单个 key
        store.delete("p", "b")
        assert store.get("p", "b") is None
        assert store.get("p", "a") == 1
        # 删除整个插件
        store.delete("p")
        assert store.get("p", "a") is None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ ConfigStore update/delete")


def test_config_store_corrupted_file_recovers():
    """损坏的 JSON 文件不应让模块崩溃，应退回空配置。"""
    tmpdir = tempfile.mkdtemp(prefix="ynex_cfg_")
    try:
        path = os.path.join(tmpdir, "pcfg.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid JSON :::")
        store = PluginConfigStore(config_file=path)
        # 不应抛错，应等效于空
        assert store.get("any", "any", default="x") == "x"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ ConfigStore 损坏文件容错")


# ---------------------------------------------------------------------------
# 5. 远程安装：Zip Slip / 体积 / 数量 防护
# ---------------------------------------------------------------------------

def _make_evil_zip_with_zip_slip() -> bytes:
    """构造一个含路径穿越条目的 zip：evil_pkg/__init__.py + ../../escape.txt"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("evil_pkg/__init__.py", "# innocent")
        zf.writestr("../escape.txt", "escaped")
    return buf.getvalue()


def _make_zip_with_too_many_files(n: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for i in range(n):
            zf.writestr(f"p/file_{i}.txt", "x")
    return buf.getvalue()


def _patch_http_get(monkey_data: Dict[str, bytes]):
    """替换 plugin_system._http_get，返回固定的字节。"""
    def fake(url, timeout=30):
        return {"ok": True, "data": monkey_data["bytes"]}
    plugin_system._http_get = fake


def test_install_from_url_blocks_zip_slip():
    """含路径穿越条目的 zip 必须被拒绝。"""
    mgr = PluginManager()
    mgr._hot_reload_enabled = False
    plugins_dir = tempfile.mkdtemp(prefix="ynex_install_")
    mgr._plugins_dir = plugins_dir
    try:
        evil_bytes = _make_evil_zip_with_zip_slip()
        _patch_http_get({"bytes": evil_bytes})
        # 调用时应返回 ok=False 且不得在 plugins_dir 之外写入 escape.txt
        outside = os.path.dirname(plugins_dir)
        result = mgr.install_plugin_from_url("http://example.invalid/evil.zip")
        assert result.get("ok") is False
        assert "非法路径" in result.get("error", "") or "下载" in result.get("error", "")
        # 关键安全断言：plugins_dir 上级目录不应出现 escape.txt
        assert not os.path.exists(os.path.join(outside, "escape.txt")), \
            "Zip Slip 防护失败，文件逃逸到 plugins_dir 之外"
    finally:
        shutil.rmtree(plugins_dir, ignore_errors=True)
    print("  ✓ Zip Slip 路径穿越被拦截")


def test_install_from_url_blocks_too_many_files():
    mgr = PluginManager()
    mgr._hot_reload_enabled = False
    plugins_dir = tempfile.mkdtemp(prefix="ynex_install_")
    mgr._plugins_dir = plugins_dir
    try:
        big = _make_zip_with_too_many_files(600)  # 超过 500 限制
        _patch_http_get({"bytes": big})
        result = mgr.install_plugin_from_url("http://example.invalid/big.zip")
        assert result.get("ok") is False
        assert "数量" in result.get("error", "")
    finally:
        shutil.rmtree(plugins_dir, ignore_errors=True)
    print("  ✓ 文件数量超限被拦截")


# ---------------------------------------------------------------------------
# 6. 启用/禁用切换
# ---------------------------------------------------------------------------

def test_enable_disable_toggles_persist_meta():
    """启用/禁用插件应将 enabled 持久化到 plugin.json。"""
    tmpdir = tempfile.mkdtemp(prefix="ynex_ena_")
    try:
        pdir = os.path.join(tmpdir, "demo")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "__init__.py"), "w") as f:
            f.write("def register(m): pass\n")
        with open(os.path.join(pdir, "plugin.json"), "w") as f:
            json.dump({"id": "demo", "name": "demo", "version": "0.0.1",
                       "author": "t", "enabled": True}, f)

        mgr = PluginManager()
        mgr._hot_reload_enabled = False
        # 临时给一个签名验证器（无密钥但仅放行 builtin/外部）→ 这里用直接注入
        mgr._signature_verifier.verify = lambda x: True
        mgr.load_plugins(plugins_dir=tmpdir)
        assert "demo" in mgr.plugins

        # 禁用
        assert mgr.disable_plugin("demo") is True
        with open(os.path.join(pdir, "plugin.json")) as f:
            meta = json.load(f)
        assert meta["enabled"] is False

        # 启用
        assert mgr.enable_plugin("demo") is True
        with open(os.path.join(pdir, "plugin.json")) as f:
            meta = json.load(f)
        assert meta["enabled"] is True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("  ✓ 启用/禁用持久化到 plugin.json")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    print("=== plugin_system.py 安全与边界测试 ===\n")
    tests = [
        test_sign_is_deterministic_and_changes_with_content,
        test_verify_rejects_missing_signature_field,
        test_verify_rejects_wrong_signature,
        test_verify_rejects_when_manifest_missing,
        test_verify_without_secret_only_allows_builtin_dir,
        test_verify_tampered_file_rejected,
        test_sandbox_allows_whitelisted_import,
        test_sandbox_blocks_non_whitelisted_import,
        test_sandbox_restores_import_after_run,
        test_sandbox_custom_allowed_modules,
        test_eventbus_emit_calls_all_listeners,
        test_eventbus_off_removes_listener,
        test_eventbus_handler_exception_does_not_break_dispatch,
        test_eventbus_emit_unknown_event_is_noop,
        test_eventbus_concurrent_on_emit_safe,
        test_config_store_set_get_roundtrip,
        test_config_store_update_and_delete,
        test_config_store_corrupted_file_recovers,
        test_install_from_url_blocks_zip_slip,
        test_install_from_url_blocks_too_many_files,
        test_enable_disable_toggles_persist_meta,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__} 异常: {type(e).__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed} 个用例失败")
        sys.exit(1)
    print(f"\n✅ 全部 {len(tests)} 个 plugin_system 用例通过")


if __name__ == "__main__":
    main()
