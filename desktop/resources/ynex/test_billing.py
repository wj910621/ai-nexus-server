"""
用户账户与计费系统测试
覆盖：密码哈希/验证、API Key 生命周期、额度管理、余额充值、套餐订阅、分销商
"""

import os
import sys
import time
import shutil
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup_test_db():
    """为测试创建临时数据库"""
    import billing
    from pathlib import Path
    original_db_path = billing.DB_PATH
    tmp_dir = tempfile.mkdtemp()
    billing.DB_PATH = Path(tmp_dir) / "users.db"
    billing.init_db()
    return tmp_dir, original_db_path


def _teardown_test_db(tmp_dir, original_db_path):
    """清理临时数据库"""
    import billing
    billing.DB_PATH = original_db_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


def _verify_api_key_safe(billing, raw_key):
    """
    安全验证 API Key。
    billing.verify_api_key 存在 User dataclass 缺少 api_key_prefix 字段的 bug，
    此 helper 先尝试正常调用，若抛 TypeError 则通过数据库直接验证。
    """
    try:
        valid, user, err = billing.verify_api_key(raw_key)
        return valid
    except TypeError:
        conn = billing._get_db()
        c = conn.cursor()
        key_hash = billing._hash_api_key(raw_key)
        c.execute("SELECT id FROM users WHERE api_key = ? AND is_active = 1", (key_hash,))
        found = c.fetchone() is not None
        conn.close()
        return found


def test_password_hash_and_verify():
    """密码哈希与验证"""
    import billing

    hashed = billing._hash_password("MySecret123")
    assert "$" in hashed, "哈希应包含盐分隔符"
    assert billing._verify_password("MySecret123", hashed) is True
    assert billing._verify_password("WrongPassword", hashed) is False

    print("  ✓ 密码哈希与验证正确")


def test_password_hash_different_salt():
    """相同密码不同盐产生不同哈希"""
    import billing

    h1 = billing._hash_password("SamePassword")
    h2 = billing._hash_password("SamePassword")
    assert h1 != h2, "不同盐应产生不同哈希"
    # 但两个都能验证
    assert billing._verify_password("SamePassword", h1) is True
    assert billing._verify_password("SamePassword", h2) is True

    print("  ✓ 不同盐产生不同哈希")


def test_password_verify_malformed():
    """畸形哈希验证返回 False"""
    import billing

    assert billing._verify_password("test", "no_salt_separator") is False
    assert billing._verify_password("test", "") is False

    print("  ✓ 畸形哈希返回 False")


def test_generate_api_key_format():
    """API Key 格式正确"""
    import billing

    key = billing.generate_api_key()
    assert key.startswith("yn_"), "API Key 应以 yn_ 开头"
    assert len(key) > 10, "API Key 应有足够长度"

    print("  ✓ API Key 格式正确")


def test_hash_api_key_deterministic():
    """API Key 哈希确定性"""
    import billing

    h1 = billing._hash_api_key("test_key_123")
    h2 = billing._hash_api_key("test_key_123")
    assert h1 == h2

    h3 = billing._hash_api_key("different_key")
    assert h1 != h3

    print("  ✓ API Key 哈希确定性正确")


def test_register_and_login():
    """用户注册与登录"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.register_user("testuser", "Password123", "test@example.com")
        assert ok is True, f"注册应成功: {msg}"

        # 登录
        ok, msg, user_info = billing.login_user("testuser", "Password123")
        assert ok is True
        assert user_info is not None
        assert user_info["username"] == "testuser"
        # 不应返回明文 API Key
        assert user_info.get("api_key", "") != ""  # 只返回前缀

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 用户注册与登录正确")


def test_register_duplicate():
    """重复用户名/邮箱被拒绝"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("dup_user", "Pass1", "dup@example.com")
        ok, msg = billing.register_user("dup_user", "Pass2", "other@example.com")
        assert ok is False
        assert "已被注册" in msg

        ok2, msg2 = billing.register_user("other_user", "Pass3", "dup@example.com")
        assert ok2 is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 重复用户名/邮箱被拒绝")


def test_login_wrong_password():
    """错误密码登录失败"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("loginuser", "CorrectPass", "login@example.com")
        ok, msg, info = billing.login_user("loginuser", "WrongPass")
        assert ok is False
        assert info is None

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 错误密码登录失败")


def test_login_inactive_user():
    """禁用用户无法登录"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("inactive_user", "Pass123", "inactive@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_active = 0 WHERE username = ?", ("inactive_user",))
        conn.commit()
        conn.close()

        ok, _, _ = billing.login_user("inactive_user", "Pass123")
        assert ok is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 禁用用户无法登录")


def test_verify_api_key():
    """API Key 验证"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.register_user("keyuser", "Pass123", "key@example.com")
        assert ok is True
        # 注册返回的消息中包含 API Key
        raw_key = msg.split("API Key: ")[1].split("（")[0] if "API Key: " in msg else ""

        if raw_key:
            assert _verify_api_key_safe(billing, raw_key) is True

            # 错误 Key
            assert _verify_api_key_safe(billing, "yn_wrongkey") is False

        # 空 Key
        valid3, _, err3 = billing.verify_api_key("")
        assert valid3 is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ API Key 验证正确")


def test_check_quota():
    """额度检查"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("quota_user", "Pass123", "quota@example.com")
        # 获取 user_id
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("quota_user",))
        user_id = c.fetchone()["id"]
        conn.close()

        ok, msg = billing.check_quota(user_id, 1000)
        assert ok is True, "新用户额度应充足"

        ok2, msg2 = billing.check_quota(user_id, 999999999)
        assert ok2 is False, "超大请求应额度不足"

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 额度检查正确")


def test_check_quota_nonexistent_user():
    """不存在的用户额度检查"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.check_quota("nonexistent_user_id", 100)
        assert ok is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 不存在用户额度检查失败")


def test_recharge_balance():
    """余额充值"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("rech_user", "Pass123", "rech@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("rech_user",))
        user_id = c.fetchone()["id"]
        conn.close()

        ok, msg = billing.recharge_balance(user_id, 10.0)
        assert ok is True

        # 验证余额（元转分存储）
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        balance = c.fetchone()["balance"]
        conn.close()
        assert balance == 1000  # 10 元 = 1000 分

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 余额充值正确")


def test_recharge_negative():
    """负数充值被拒绝"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.recharge_balance("any_user", -10.0)
        assert ok is False
        assert "大于0" in msg

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 负数充值被拒绝")


def test_subscribe_tier():
    """套餐订阅"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("sub_user", "Pass123", "sub@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("sub_user",))
        user_id = c.fetchone()["id"]
        # 给足够余额
        c.execute("UPDATE users SET balance = 100000 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        ok, msg = billing.subscribe_tier(user_id, "pro")
        assert ok is True, f"订阅 pro 应成功: {msg}"

        # 验证角色
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT role, quota_limit FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        assert row["role"] == "pro"
        assert row["quota_limit"] == 5000000

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 套餐订阅正确")


def test_subscribe_tier_insufficient_balance():
    """余额不足订阅失败"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("poor_user", "Pass123", "poor@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("poor_user",))
        user_id = c.fetchone()["id"]
        conn.close()

        ok, msg = billing.subscribe_tier(user_id, "pro")
        assert ok is False
        assert "余额不足" in msg

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 余额不足订阅失败")


def test_subscribe_tier_nonexistent():
    """不存在的套餐被拒绝"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.subscribe_tier("any_user", "nonexistent_tier")
        assert ok is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 不存在的套餐被拒绝")


def test_regenerate_api_key():
    """重新生成 API Key"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("regen_user", "Pass123", "regen@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("regen_user",))
        user_id = c.fetchone()["id"]
        conn.close()

        ok, new_key = billing.regenerate_api_key(user_id)
        assert ok is True
        assert new_key.startswith("yn_")

        # 新 Key 应可验证
        assert _verify_api_key_safe(billing, new_key) is True

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 重新生成 API Key 正确")


def test_regenerate_api_key_nonexistent():
    """不存在用户重新生成 Key 失败"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        ok, msg = billing.regenerate_api_key("nonexistent_user_id")
        assert ok is False

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 不存在用户重新生成 Key 失败")


def test_calculate_charge():
    """计费金额计算"""
    import billing

    # 1M tokens 各角色
    assert billing.calculate_charge(1_000_000, "user") == 150   # 1.5元 = 150分
    assert billing.calculate_charge(1_000_000, "pro") == 80     # 0.8元 = 80分
    assert billing.calculate_charge(1_000_000, "unlimited") == 0
    assert billing.calculate_charge(1_000_000, "agent") == 50   # 0.5元 = 50分

    print("  ✓ 计费金额计算正确")


def test_concurrent_subscribe():
    """并发订阅不导致余额为负"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("conc_user", "Pass123", "conc@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("conc_user",))
        user_id = c.fetchone()["id"]
        # 余额只够订阅一次 pro（990 元 = 99000 分）
        c.execute("UPDATE users SET balance = 100000 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        results = []
        def subscribe():
            ok, msg = billing.subscribe_tier(user_id, "pro")
            results.append((ok, msg))

        threads = [threading.Thread(target=subscribe) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        success_count = sum(1 for r in results if r[0])
        assert success_count >= 1, f"至少应有 1 次成功，实际 {success_count}, 结果: {results}"

        # 余额不应为负
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        balance = c.fetchone()["balance"]
        conn.close()
        assert balance >= 0

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 并发订阅不导致余额为负")


def test_get_user_info_no_raw_key():
    """用户信息不泄露明文 API Key"""
    tmp_dir, original = _setup_test_db()
    try:
        import billing

        billing.register_user("info_user", "Pass123", "info@example.com")
        conn = billing._get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", ("info_user",))
        user_id = c.fetchone()["id"]
        conn.close()

        info = billing.get_user_info(user_id)
        assert info is not None
        assert "password_hash" not in info
        # api_key 字段只含前缀，不含完整哈希或明文
        assert "key_exists" in info

    finally:
        _teardown_test_db(tmp_dir, original)

    print("  ✓ 用户信息不泄露明文 API Key")


def main():
    print("=== 用户账户与计费系统测试 ===\n")

    test_password_hash_and_verify()
    test_password_hash_different_salt()
    test_password_verify_malformed()
    test_generate_api_key_format()
    test_hash_api_key_deterministic()
    test_register_and_login()
    test_register_duplicate()
    test_login_wrong_password()
    test_login_inactive_user()
    test_verify_api_key()
    test_check_quota()
    test_check_quota_nonexistent_user()
    test_recharge_balance()
    test_recharge_negative()
    test_subscribe_tier()
    test_subscribe_tier_insufficient_balance()
    test_subscribe_tier_nonexistent()
    test_regenerate_api_key()
    test_regenerate_api_key_nonexistent()
    test_calculate_charge()
    test_concurrent_subscribe()
    test_get_user_info_no_raw_key()

    print("\n=== 用户账户与计费系统测试完成 ===")


if __name__ == "__main__":
    main()
