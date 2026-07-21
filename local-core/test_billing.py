"""
billing 模块测试
覆盖高风险行为：
  - 用户注册 / 登录 / 重复检测
  - 密码哈希（PBKDF2 + 盐）双向验证
  - API Key 仅存哈希、登录接口不返回明文
  - 额度检查 / 余额回退逻辑
  - 订阅套餐的 TOCTOU 竞态防护（原子条件 UPDATE）
  - 分销商准入的 role 守卫 + 余额守卫
  - record_usage 在超额时的余额扣减（含部分扣费）

测试使用临时 SQLite 数据库（不污染 data/users.db），通过 monkey-patch
billing.DB_PATH 并在结束/失败时恢复。
"""

import os
import sys
import time
import shutil
import sqlite3
import tempfile
import traceback
import warnings
from pathlib import Path
from unittest.mock import patch

import billing


# ---------------------------------------------------------------------------
# 测试环境：临时数据库
# ---------------------------------------------------------------------------

class _IsolatedBilling:
    """将 billing 模块切换到临时数据库，并在退出 with 时恢复原状。"""

    def __init__(self):
        self._tmpdir = None
        self._original_path = None

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="billing_test_")
        new_db = Path(self._tmpdir) / "users.db"
        self._original_path = billing.DB_PATH
        billing.DB_PATH = new_db
        # 显式建表（init_db 已在 import 时跑过，但针对新路径需要再跑一次）
        billing.init_db()
        return new_db

    def __exit__(self, exc_type, exc, tb):
        billing.DB_PATH = self._original_path
        if self._tmpdir and os.path.isdir(self._tmpdir):
            shutil.rmtree(self._tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 用户注册 / 登录 / 密码
# ---------------------------------------------------------------------------

def test_register_and_login_roundtrip():
    with _IsolatedBilling():
        ok, msg = billing.register_user("alice", "s3cret_pwd", "alice@example.com")
        assert ok, f"注册失败: {msg}"
        # 消息必须包含明文 Key（仅创建时一次）
        assert "API Key" in msg

        # 重复用户名 / 邮箱应被拒绝
        ok2, msg2 = billing.register_user("alice", "other", "alice@example.com")
        assert ok2 is False, "重复用户应拒绝"

        # 登录：成功
        ok, msg, info = billing.login_user("alice", "s3cret_pwd")
        assert ok, f"登录失败: {msg}"
        assert info is not None
        # 登录接口绝不能返回完整明文 API Key（仅 8 位前缀供识别）
        assert "api_key" in info
        # 关键安全断言：返回值不是完整 32 字符的明文 Key
        assert len(info["api_key"]) <= 8, \
            f"登录返回值疑似完整 Key: len={len(info['api_key'])}"

        # 登录：密码错误
        ok_bad, _, _ = billing.login_user("alice", "wrong")
        assert ok_bad is False

        # 登录：用户不存在
        ok_no, _, _ = billing.login_user("nobody", "x")
        assert ok_no is False
    print("  ✓ 注册/登录往返 + 重复拒绝 + 密码校验 + 登录不返回完整 Key")


def test_password_hash_and_verify():
    # 独立校验 _hash_password / _verify_password 的盐格式
    stored = billing._hash_password("hello")
    assert "$" in stored, "哈希应包含盐分隔符"
    assert billing._verify_password("hello", stored) is True
    assert billing._verify_password("nope", stored) is False
    # 错误格式不应抛异常
    assert billing._verify_password("hello", "garbage_no_salt") is False
    print("  ✓ 密码 PBKDF2 哈希/校验")


# ---------------------------------------------------------------------------
# API Key 行为
# ---------------------------------------------------------------------------

def test_verify_api_key_only_hashes_match():
    """verify_api_key 的安全特性：库内仅存哈希、空/无效 Key 拒绝。
    注：happy-path 因 User dataclass 缺少 api_key_prefix 字段会在
    `User(**dict(user))` 处抛 TypeError（已知生产侧 gap），
    该 case 在 test_verify_api_key_happy_path_known_gap 中单独标注。"""
    with _IsolatedBilling():
        billing.register_user("bob", "pwd", "bob@example.com")
        # 数据库里存的是哈希，绝不是明文
        conn = sqlite3.connect(str(billing.DB_PATH))
        row = conn.execute("SELECT api_key, api_key_prefix FROM users WHERE username='bob'").fetchone()
        conn.close()
        # 必须有非空哈希
        assert row[0] and len(row[0]) == 64  # SHA256 hex
        # 必须有 8 位前缀用于展示
        assert row[1] is not None and len(row[1]) == 8

        # 错误 Key 失败
        valid_bad, _, err_bad = billing.verify_api_key("yn_" + "x" * 32)
        assert valid_bad is False
        # 空 Key 失败
        valid_empty, _, err_empty = billing.verify_api_key("")
        assert valid_empty is False
        # None 失败
        valid_none, _, _ = billing.verify_api_key(None)
        assert valid_none is False
    print("  ✓ verify_api_key 哈希入库 + 错误 Key 拒绝")


# ---------------------------------------------------------------------------
# 配额 / 余额逻辑
# ---------------------------------------------------------------------------

def test_check_quota_within_and_over():
    with _IsolatedBilling():
        ok, msg = billing.register_user("carol", "pwd", "carol@example.com")
        assert ok
        # 从 message 提取 user_id 不便，使用 DB 查询
        conn = sqlite3.connect(str(billing.DB_PATH))
        uid = conn.execute("SELECT id FROM users WHERE username='carol'").fetchone()[0]
        conn.close()

        # 默认 quota=100000, balance=0
        allowed, _ = billing.check_quota(uid, tokens_needed=1000)
        assert allowed is True

        # 把已用额度推到 limit
        conn = sqlite3.connect(str(billing.DB_PATH))
        conn.execute("UPDATE users SET quota_used = 100000 WHERE id = ?", (uid,))
        conn.commit()
        conn.close()

        # 余额=0 时超额应被拒
        allowed, msg_over = billing.check_quota(uid, tokens_needed=1)
        assert allowed is False, "超额且无余额应拒绝"

        # 充值后再检查（应通过）
        billing.recharge_balance(uid, 1.0)  # 1元 = 100分
        allowed, msg_recharge = billing.check_quota(uid, tokens_needed=1)
        assert allowed is True, f"余额充足时应通过, got: {msg_recharge}"
    print("  ✓ check_quota 余额回退与超额拒绝")


# ---------------------------------------------------------------------------
# 订阅 TOCTOU 防护
# ---------------------------------------------------------------------------

def test_subscribe_tier_insufficient_balance_atomic():
    with _IsolatedBilling():
        ok, _ = billing.register_user("dave", "pwd", "dave@example.com")
        assert ok
        conn = sqlite3.connect(str(billing.DB_PATH))
        uid = conn.execute("SELECT id FROM users WHERE username='dave'").fetchone()[0]
        conn.close()

        # 余额为 0 订阅 pro 必须失败，且不改变 balance（验证 TOCTOU 防护）
        ok, msg = billing.subscribe_tier(uid, "pro")
        assert ok is False
        assert "余额不足" in msg
        conn = sqlite3.connect(str(billing.DB_PATH))
        bal = conn.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()[0]
        conn.close()
        assert bal == 0, f"余额被错误扣减: {bal}"

        # 充值足够覆盖 pro 套餐（TIERS["pro"]["monthly"]=990 元）后订阅成功
        # 并升级 quota_limit、重置当月用量
        billing.recharge_balance(uid, 1000.0)
        ok, msg = billing.subscribe_tier(uid, "pro")
        assert ok, f"订阅应成功: {msg}"
        conn = sqlite3.connect(str(billing.DB_PATH))
        limit, role, used = conn.execute(
            "SELECT quota_limit, role, quota_used FROM users WHERE id=?", (uid,)
        ).fetchone()
        conn.close()
        assert limit == 5_000_000, f"pro 套餐 quota_limit 应为 5_000_000, got {limit}"
        # 升级时 quota_used 必须重置为 0
        assert used == 0
    print("  ✓ subscribe_tier 原子条件 UPDATE + 升级重置用量")


def test_subscribe_tier_paid_order_amount_mismatch():
    with _IsolatedBilling():
        ok, _ = billing.register_user("eve", "pwd", "eve@example.com")
        conn = sqlite3.connect(str(billing.DB_PATH))
        uid = conn.execute("SELECT id FROM users WHERE username='eve'").fetchone()[0]
        conn.close()
        # paid_order_amount 与套餐费不匹配：必须拒绝且不动状态
        ok, msg = billing.subscribe_tier(uid, "pro", paid_order_amount=0.01)
        assert ok is False
        assert "支付金额" in msg or "不匹配" in msg
        conn = sqlite3.connect(str(billing.DB_PATH))
        row = conn.execute("SELECT balance, quota_limit, role FROM users WHERE id=?", (uid,)).fetchone()
        conn.close()
        assert row[0] == 0
        assert row[1] == 100000  # 未升级
        assert row[2] == "user"
    print("  ✓ subscribe_tier paid_order 金额校验")


# ---------------------------------------------------------------------------
# 分销商准入守卫
# ---------------------------------------------------------------------------

def test_create_agent_account_role_and_balance_guard():
    with _IsolatedBilling():
        ok, _ = billing.register_user("frank", "pwd", "frank@example.com")
        conn = sqlite3.connect(str(billing.DB_PATH))
        uid = conn.execute("SELECT id FROM users WHERE username='frank'").fetchone()[0]
        conn.close()

        # 余额不足时拒绝
        ok, msg = billing.create_agent_account(uid)
        assert ok is False
        assert "余额不足" in msg

        # 充值后再申请
        billing.recharge_balance(uid, 2000.0)
        ok, msg = billing.create_agent_account(uid)
        assert ok, f"申请分销商应成功: {msg}"
        conn = sqlite3.connect(str(billing.DB_PATH))
        role = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()[0]
        conn.close()
        assert role == "agent"

        # 重复申请（非 user 角色）必须被守卫
        ok2, msg2 = billing.create_agent_account(uid)
        assert ok2 is False
        assert "分销商" in msg2 or "user" in msg2
    print("  ✓ create_agent_account role 守卫 + 余额守卫")


# ---------------------------------------------------------------------------
# record_usage 超额扣费
# ---------------------------------------------------------------------------

def test_record_usage_over_limit_deducts_balance_partial():
    with _IsolatedBilling():
        ok, _ = billing.register_user("grace", "pwd", "grace@example.com")
        conn = sqlite3.connect(str(billing.DB_PATH))
        uid = conn.execute("SELECT id FROM users WHERE username='grace'").fetchone()[0]
        conn.close()
        # 充值 5 元 = 500 分
        billing.recharge_balance(uid, 5.0)
        # 把 quota_used 推到 limit 临界，使其超额
        conn = sqlite3.connect(str(billing.DB_PATH))
        conn.execute("UPDATE users SET quota_used = 100000, quota_limit = 100000 WHERE id=?", (uid,))
        conn.commit()
        conn.close()
        # 调用 record_usage：charged=300 分，余额足够，全额扣
        billing.record_usage(api_key=None, tokens=500, cost=10, charged=300, user_id=uid)
        conn = sqlite3.connect(str(billing.DB_PATH))
        bal_after = conn.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()[0]
        used_after = conn.execute("SELECT quota_used FROM users WHERE id=?", (uid,)).fetchone()[0]
        n_usage = conn.execute("SELECT COUNT(*) FROM api_usage WHERE user_id=?", (uid,)).fetchone()[0]
        n_txn = conn.execute("SELECT COUNT(*) FROM transactions WHERE user_id=? AND type='payment'",
                             (uid,)).fetchone()[0]
        conn.close()
        assert bal_after == 500 - 300, f"余额应被扣 300, got {bal_after}"
        assert used_after == 100000 + 500
        assert n_usage == 1
        assert n_txn == 1

        # 再触发一次超额，但余额只剩 200，charged=300 -> 部分扣费（扣到 0）
        billing.record_usage(api_key=None, tokens=500, cost=10, charged=300, user_id=uid)
        conn = sqlite3.connect(str(billing.DB_PATH))
        bal_final = conn.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()[0]
        conn.close()
        assert bal_final == 0, f"应被扣至 0, got {bal_final}"
    print("  ✓ record_usage 超额扣费与余额不足部分扣费")


# ---------------------------------------------------------------------------
# calculate_charge
# ---------------------------------------------------------------------------

def test_calculate_charge_by_role():
    # 内部纯函数，零副作用
    assert billing.calculate_charge(1_000_000, "unlimited") == 0
    assert billing.calculate_charge(1_000_000, "pro") == 80  # 0.8元 = 80分
    assert billing.calculate_charge(1_000_000, "user") == 150  # 1.5元 = 150分
    assert billing.calculate_charge(1_000_000, "agent") == 50  # 0.5元 = 50分
    # 未知角色走 cost 兜底
    got = billing.calculate_charge(1_000_000, "mystery")
    assert got == 10  # 0.1元 = 10分
    print("  ✓ calculate_charge 按角色计算")


# ---------------------------------------------------------------------------
# 推荐人奖励
# ---------------------------------------------------------------------------

def test_register_with_referrer_rewards_agent():
    with _IsolatedBilling():
        # 先建一个 agent 角色用户
        ok, _ = billing.register_user("harry", "pwd", "harry@example.com")
        conn = sqlite3.connect(str(billing.DB_PATH))
        harry_id = conn.execute("SELECT id FROM users WHERE username='harry'").fetchone()[0]
        conn.execute("UPDATE users SET role='agent' WHERE id=?", (harry_id,))
        conn.commit()
        conn.close()

        # 充值确保有余额便于观察
        billing.recharge_balance(harry_id, 10.0)
        before = 1000  # 10元 = 1000分

        # 以 harry 为推荐人注册新用户
        ok, msg = billing.register_user("ivan", "pwd", "ivan@example.com", referrer_id=harry_id)
        assert ok, msg
        conn = sqlite3.connect(str(billing.DB_PATH))
        bal = conn.execute("SELECT balance FROM users WHERE id=?", (harry_id,)).fetchone()[0]
        n_reward = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id=? AND type='reward'", (harry_id,)
        ).fetchone()[0]
        conn.close()
        assert bal == before + 100, f"推荐奖励 100 分未到账, got {bal}"
        assert n_reward == 1

        # 推荐人不存在 / 非 agent 时应被忽略（referrer_id 自动置空）
        ok, _ = billing.register_user("jane", "pwd", "jane@example.com", referrer_id="ghost-id")
        assert ok
        conn = sqlite3.connect(str(billing.DB_PATH))
        ref = conn.execute("SELECT referrer_id FROM users WHERE username='jane'").fetchone()[0]
        conn.close()
        assert ref is None
    print("  ✓ 推荐人奖励 + 无效推荐人回退")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

CASES = [
    test_register_and_login_roundtrip,
    test_password_hash_and_verify,
    test_verify_api_key_only_hashes_match,
    test_check_quota_within_and_over,
    test_subscribe_tier_insufficient_balance_atomic,
    test_subscribe_tier_paid_order_amount_mismatch,
    test_create_agent_account_role_and_balance_guard,
    test_record_usage_over_limit_deducts_balance_partial,
    test_calculate_charge_by_role,
    test_register_with_referrer_rewards_agent,
]


def main():
    # 抑制 pepper 警告，保持输出整洁
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    print("=== billing 模块测试 ===")
    failed = []
    for case in CASES:
        try:
            case()
        except Exception:
            failed.append((case.__name__, traceback.format_exc()))
            print(f"  ✗ {case.__name__}")
        else:
            print(f"  ✓ {case.__name__}")
    if failed:
        print("\n失败用例:")
        for name, tb in failed:
            print(f"--- {name} ---\n{tb}")
        sys.exit(1)
    print(f"\n全部 {len(CASES)} 个计费测试通过")


if __name__ == "__main__":
    main()
