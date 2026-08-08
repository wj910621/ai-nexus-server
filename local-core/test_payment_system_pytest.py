"""
pytest 测试文件 - payment_system.py
覆盖：订单创建/查询/状态转换、支付宝/微信回调验签、佣金计算、支付确认幂等与金额校验
"""

import sys
import os
import time
import hmac
import hashlib
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# 确保 local-core 在 sys.path 中，优先于其他同名包
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _redirect_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库，避免跨测试污染。"""
    db_file = tmp_path / "payments.db"
    import payment_system
    monkeypatch.setattr(payment_system, "PAYMENT_DB_PATH", db_file)
    payment_system.init_payment_db()
    yield
    # 测试结束后关闭可能残留的连接（_payment_systems 缓存）
    payment_system._payment_systems.clear()


# ===================================================================
# 1. create_order
# ===================================================================
class TestCreateOrder:
    def test_basic_fields(self):
        import payment_system as ps
        order = ps.create_order("user1", 99.9, "alipay", "recharge", "prod1")
        assert order.user_id == "user1"
        assert order.amount == 99.9
        assert order.method == "alipay"
        assert order.status == "pending"
        assert order.product_type == "recharge"
        assert order.product_id == "prod1"
        assert order.paid_at is None
        assert order.transaction_id is None
        assert order.created_at > 0

    def test_order_id_prefix(self):
        import payment_system as ps
        order = ps.create_order("user1", 10, "alipay")
        assert order.id.startswith("ORD")

    def test_order_id_unique(self):
        import payment_system as ps
        o1 = ps.create_order("u", 1, "alipay")
        o2 = ps.create_order("u", 1, "alipay")
        assert o1.id != o2.id

    def test_default_product_type(self):
        import payment_system as ps
        order = ps.create_order("u", 5, "wechat")
        assert order.product_type == "recharge"


# ===================================================================
# 2. get_order
# ===================================================================
class TestGetOrder:
    def test_valid_id(self):
        import payment_system as ps
        created = ps.create_order("u1", 50, "alipay")
        fetched = ps.get_order(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.amount == 50

    def test_invalid_id_returns_none(self):
        import payment_system as ps
        assert ps.get_order("ORD_NOTEXIST") is None

    def test_empty_id_returns_none(self):
        import payment_system as ps
        assert ps.get_order("") is None


# ===================================================================
# 3. update_order_status
# ===================================================================
class TestUpdateOrderStatus:
    def test_pending_to_success_sets_paid_at(self):
        import payment_system as ps
        order = ps.create_order("u1", 100, "alipay")
        assert order.status == "pending"

        ok = ps.update_order_status(order.id, "success", transaction_id="TX123")
        assert ok is True

        updated = ps.get_order(order.id)
        assert updated.status == "success"
        assert updated.paid_at is not None
        assert updated.paid_at > 0
        assert updated.transaction_id == "TX123"

    def test_pending_to_failed(self):
        import payment_system as ps
        order = ps.create_order("u1", 10, "wechat")
        ok = ps.update_order_status(order.id, "failed")
        assert ok is True
        updated = ps.get_order(order.id)
        assert updated.status == "failed"
        # failed 不设置 paid_at
        assert updated.paid_at is None

    def test_nonexistent_order(self):
        import payment_system as ps
        ok = ps.update_order_status("ORD_FAKE", "success")
        assert ok is False

    def test_callback_data_stored(self):
        import payment_system as ps
        order = ps.create_order("u1", 10, "alipay")
        cb = {"trade_no": "T123", "trade_status": "TRADE_SUCCESS"}
        ps.update_order_status(order.id, "success", callback_data=cb)
        # 通过直接查库验证 callback_data 存入
        conn = sqlite3.connect(str(ps.PAYMENT_DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT callback_data FROM payment_orders WHERE id=?", (order.id,)).fetchone()
        conn.close()
        import json
        assert json.loads(row["callback_data"])["trade_no"] == "T123"


# ===================================================================
# 4. AlipaySandbox.verify_callback
# ===================================================================
class TestAlipayVerifyCallback:
    def test_rejects_empty_params(self):
        import payment_system as ps
        alipay = ps.AlipaySandbox()
        assert alipay.verify_callback({}) is False
        assert alipay.verify_callback(None) is False

    def test_rejects_non_success_trade_status(self):
        import payment_system as ps
        alipay = ps.AlipaySandbox()
        assert alipay.verify_callback({"out_trade_no": "X", "trade_status": "WAIT_BUYER_PAY"}) is False
        assert alipay.verify_callback({"out_trade_no": "X", "trade_status": "TRADE_CLOSED"}) is False

    def test_sandbox_rejects_without_key_configured(self):
        """sandbox_key 为空时应拒绝回调"""
        import payment_system as ps
        alipay = ps.AlipaySandbox()
        alipay.is_sandbox = True
        alipay.sandbox_key = ""
        params = {
            "out_trade_no": "ORD_TEST",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "10.00",
            "sign": "whatever",
        }
        assert alipay.verify_callback(params) is False

    def test_sandbox_verifies_correct_hmac(self):
        """配置 sandbox_key 后，正确的 HMAC 签名应通过验签"""
        import payment_system as ps
        key = "test_sandbox_secret"
        alipay = ps.AlipaySandbox()
        alipay.is_sandbox = True
        alipay.sandbox_key = key
        alipay.app_id = "sandbox_app_id"

        out_trade_no = "ORD_HMAC_TEST"
        total_amount = "99.90"
        # 生成正确签名
        expected_sign = hmac.new(
            key.encode(),
            f"{out_trade_no}:{total_amount}:{alipay.app_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

        params = {
            "out_trade_no": out_trade_no,
            "trade_status": "TRADE_SUCCESS",
            "total_amount": total_amount,
            "sign": expected_sign,
        }
        assert alipay.verify_callback(params) is True

    def test_sandbox_rejects_wrong_hmac(self):
        """错误签名应被拒绝"""
        import payment_system as ps
        key = "test_sandbox_secret"
        alipay = ps.AlipaySandbox()
        alipay.is_sandbox = True
        alipay.sandbox_key = key
        alipay.app_id = "sandbox_app_id"

        params = {
            "out_trade_no": "ORD_BAD",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "10.00",
            "sign": "wrong_signature_value",
        }
        assert alipay.verify_callback(params) is False

    def test_trade_finished_also_accepted(self):
        """TRADE_FINISHED 也应被接受"""
        import payment_system as ps
        key = "sk"
        alipay = ps.AlipaySandbox()
        alipay.is_sandbox = True
        alipay.sandbox_key = key
        alipay.app_id = "sandbox_app_id"

        out_trade_no = "ORD_FIN"
        total_amount = "1.00"
        sign = hmac.new(
            key.encode(),
            f"{out_trade_no}:{total_amount}:{alipay.app_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        params = {
            "out_trade_no": out_trade_no,
            "trade_status": "TRADE_FINISHED",
            "total_amount": total_amount,
            "sign": sign,
        }
        assert alipay.verify_callback(params) is True


# ===================================================================
# 5. WechatPay.verify_callback
# ===================================================================
class TestWechatVerifyCallback:
    def test_rejects_empty_params(self):
        import payment_system as ps
        wx = ps.WechatPay()
        ok, data = wx.verify_callback({})
        assert ok is False
        assert data == {}

    def test_rejects_non_success_result_code(self):
        import payment_system as ps
        wx = ps.WechatPay()
        ok, data = wx.verify_callback({"result_code": "FAIL", "out_trade_no": "X"})
        assert ok is False

    def test_rejects_missing_out_trade_no(self):
        """result_code=SUCCESS 但缺少 out_trade_no 也应拒绝"""
        import payment_system as ps
        wx = ps.WechatPay()
        ok, data = wx.verify_callback({"result_code": "SUCCESS"})
        assert ok is False

    def test_sandbox_rejects_without_key(self):
        """沙箱模式未配置 key 时拒绝回调"""
        import payment_system as ps
        wx = ps.WechatPay()
        wx.is_sandbox = True
        wx.key = ""
        ok, data = wx.verify_callback({"result_code": "SUCCESS", "out_trade_no": "ORD_WX"})
        assert ok is False

    def test_sandbox_verifies_correct_hmac(self):
        """沙箱模式 + 正确 HMAC 签名应通过"""
        import payment_system as ps
        key = "wx_sandbox_secret"
        wx = ps.WechatPay()
        wx.is_sandbox = True
        wx.key = key
        wx.app_id = "wx_sandbox_appid"

        out_trade_no = "ORD_WX_OK"
        total_fee = "100"
        sign = hmac.new(
            key.encode(),
            f"{out_trade_no}:{total_fee}:{wx.app_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        params = {
            "result_code": "SUCCESS",
            "out_trade_no": out_trade_no,
            "total_fee": total_fee,
            "sign": sign,
        }
        ok, data = wx.verify_callback(params)
        assert ok is True
        assert data["out_trade_no"] == out_trade_no

    def test_xml_input_parsing(self):
        """XML 格式输入应被正确解析"""
        import payment_system as ps
        key = "wx_sk"
        wx = ps.WechatPay()
        wx.is_sandbox = True
        wx.key = key
        wx.app_id = "wx_appid"

        out_trade_no = "ORD_XML"
        total_fee = "50"
        sign = hmac.new(
            key.encode(),
            f"{out_trade_no}:{total_fee}:{wx.app_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        xml = (
            f"<xml>"
            f"<result_code>SUCCESS</result_code>"
            f"<out_trade_no>{out_trade_no}</out_trade_no>"
            f"<total_fee>{total_fee}</total_fee>"
            f"<sign>{sign}</sign>"
            f"</xml>"
        )
        ok, data = wx.verify_callback(xml)
        assert ok is True


# ===================================================================
# 6. calculate_commission
# ===================================================================
class TestCalculateCommission:
    def test_default_commission_rate(self):
        """默认佣金率 20%"""
        import payment_system as ps
        order = ps.PaymentOrder(
            id="ORD_C", user_id="u", amount=100, method="alipay",
            status="pending", product_type="recharge", product_id=None,
            created_at=time.time(), paid_at=None, transaction_id=None,
        )
        commission, rate = ps.calculate_commission(order, "agent_new")
        assert rate == 0.2
        assert commission == 20.0

    def test_custom_commission_rate(self):
        """自定义佣金率"""
        import payment_system as ps
        # 先写入自定义设置
        ps.update_agent_settings("agent_custom", commission_rate=0.3)
        order = ps.PaymentOrder(
            id="ORD_CC", user_id="u", amount=200, method="alipay",
            status="pending", product_type="recharge", product_id=None,
            created_at=time.time(), paid_at=None, transaction_id=None,
        )
        commission, rate = ps.calculate_commission(order, "agent_custom")
        assert rate == 0.3
        assert commission == 60.0

    def test_zero_amount(self):
        import payment_system as ps
        order = ps.PaymentOrder(
            id="ORD_Z", user_id="u", amount=0, method="alipay",
            status="pending", product_type="recharge", product_id=None,
            created_at=time.time(), paid_at=None, transaction_id=None,
        )
        commission, rate = ps.calculate_commission(order, "agent_z")
        assert commission == 0.0


# ===================================================================
# 7. confirm_payment - 幂等性
# ===================================================================
class TestConfirmPaymentIdempotency:
    def test_already_successful_returns_true(self, monkeypatch):
        """已成功的订单再次确认应返回 True（幂等）"""
        import payment_system as ps

        # confirm_payment 内部 import billing，需 mock
        import billing as _billing_mod
        monkeypatch.setattr(_billing_mod, "recharge_balance", lambda *a, **kw: (True, "ok"))
        monkeypatch.setattr(_billing_mod, "subscribe_tier", lambda *a, **kw: (True, "ok"))
        monkeypatch.setattr(_billing_mod, "get_user_info", lambda uid: {"referrer_id": None})

        order = ps.create_order("u_idem", 10, "alipay", "recharge")
        ps.update_order_status(order.id, "success", transaction_id="TX1")

        ok, msg = ps.confirm_payment(order.id, transaction_id="TX2")
        assert ok is True
        assert "已支付" in msg


# ===================================================================
# 8. confirm_payment - 金额不匹配
# ===================================================================
class TestConfirmPaymentAmountMismatch:
    def test_amount_mismatch_detected(self, monkeypatch):
        """回调金额与订单金额不一致时应拒绝"""
        import payment_system as ps

        order = ps.create_order("u_mismatch", 100, "alipay", "recharge")
        # verified_amount 与 order.amount 差距 > 0.01
        ok, msg = ps.confirm_payment(order.id, verified_amount=50.0)
        assert ok is False
        assert "不匹配" in msg

    def test_amount_within_tolerance(self, monkeypatch):
        """1 分误差内应通过金额校验（进入后续状态检查）"""
        import payment_system as ps
        import billing as _billing_mod
        monkeypatch.setattr(_billing_mod, "recharge_balance", lambda *a, **kw: (True, "ok"))
        monkeypatch.setattr(_billing_mod, "get_user_info", lambda uid: {"referrer_id": None})

        order = ps.create_order("u_tol", 100, "alipay", "recharge")
        # 误差 0.005 <= 0.01，应通过金额校验
        ok, msg = ps.confirm_payment(order.id, verified_amount=100.005)
        # 只要不是因为金额不匹配被拒绝即可
        if not ok:
            assert "不匹配" not in msg


# ===================================================================
# 9. confirm_payment - 非pending订单
# ===================================================================
class TestConfirmPaymentInvalidStatus:
    def test_failed_order_rejected(self):
        """failed 状态的订单不能被 confirm"""
        import payment_system as ps
        order = ps.create_order("u_fail", 10, "alipay", "recharge")
        ps.update_order_status(order.id, "failed")
        ok, msg = ps.confirm_payment(order.id)
        assert ok is False
        assert "异常" in msg

    def test_nonexistent_order(self):
        import payment_system as ps
        ok, msg = ps.confirm_payment("ORD_NOPE")
        assert ok is False
        assert "不存在" in msg
