"""
Y·NEX支付系统测试
测试目标：验证支付流程的安全性和正确性
- 订单创建与查询
- 支付回调验签
- 并发支付处理（防重复发货）
- 佣金计算与结算
- 金额校验
"""
import os
import sys
import time
import unittest
import tempfile
import hashlib
import hmac
from unittest.mock import patch, MagicMock
import threading

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestPaymentOrderManagement(unittest.TestCase):
    """订单管理测试"""

    def setUp(self):
        """测试前准备"""
        # 使用临时数据库
        import payment_system
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        payment_system.PAYMENT_DB_PATH = Path(os.path.join(self.temp_dir, "test_payments.db"))
        payment_system.init_payment_db()
        
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_order(self):
        """测试订单创建"""
        from payment_system import create_order, get_order
        
        order = create_order(
            user_id="test_user_001",
            amount=100.0,
            method="alipay",
            product_type="recharge"
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.user_id, "test_user_001")
        self.assertEqual(order.amount, 100.0)
        self.assertEqual(order.method, "alipay")
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.product_type, "recharge")
        
        # 验证订单可查询
        retrieved = get_order(order.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, order.id)

    def test_order_status_update(self):
        """测试订单状态更新"""
        from payment_system import create_order, update_order_status, get_order
        
        order = create_order(
            user_id="test_user_002",
            amount=50.0,
            method="wechat",
            product_type="recharge"
        )
        
        # 更新为成功
        success = update_order_status(
            order.id,
            status="success",
            transaction_id="TXN123456"
        )
        self.assertTrue(success)
        
        # 验证状态已更新
        updated = get_order(order.id)
        self.assertEqual(updated.status, "success")
        self.assertEqual(updated.transaction_id, "TXN123456")
        self.assertIsNotNone(updated.paid_at)

    def test_duplicate_order_id(self):
        """测试订单ID唯一性"""
        from payment_system import create_order
        
        # 创建多个订单，ID应不同
        order1 = create_order("user1", 10.0, "alipay")
        order2 = create_order("user2", 20.0, "wechat")
        
        self.assertNotEqual(order1.id, order2.id)


class TestPaymentCallbackVerification(unittest.TestCase):
    """支付回调验签测试"""

    def setUp(self):
        """测试前准备"""
        import payment_system
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        payment_system.PAYMENT_DB_PATH = Path(os.path.join(self.temp_dir, "test_payments.db"))
        payment_system.init_payment_db()
        
        # 设置沙箱密钥
        self.sandbox_key = "test_sandbox_key_12345"
        os.environ["PAYMENT_SANDBOX_CALLBACK_KEY"] = self.sandbox_key

    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_alipay_sandbox_callback_valid(self):
        """测试支付宝沙箱回调验签（有效签名）"""
        from payment_system import AlipaySandbox, create_order
        
        alipay = AlipaySandbox()
        order = create_order("user001", 100.0, "alipay")
        
        # 生成有效签名
        callback_data = {
            "out_trade_no": order.id,
            "trade_no": "MOCK123456",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "100.00",
        }
        sign = hmac.new(
            self.sandbox_key.encode(),
            f"{order.id}:100.00:{alipay.app_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        callback_data["sign"] = sign
        
        # 验签应成功
        self.assertTrue(alipay.verify_callback(callback_data))

    def test_alipay_sandbox_callback_invalid_sign(self):
        """测试支付宝沙箱回调验签（无效签名）"""
        from payment_system import AlipaySandbox, create_order
        
        alipay = AlipaySandbox()
        order = create_order("user002", 50.0, "alipay")
        
        # 错误签名
        callback_data = {
            "out_trade_no": order.id,
            "trade_no": "MOCK789",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "50.00",
            "sign": "invalid_signature_here"
        }
        
        # 验签应失败
        self.assertFalse(alipay.verify_callback(callback_data))

    def test_alipay_callback_without_sandbox_key(self):
        """测试未配置沙箱密钥时的回调拒绝"""
        from payment_system import AlipaySandbox, create_order
        
        # 临时移除密钥
        original_key = os.environ.pop("PAYMENT_SANDBOX_CALLBACK_KEY", None)
        
        try:
            alipay = AlipaySandbox()
            order = create_order("user003", 30.0, "alipay")
            
            callback_data = {
                "out_trade_no": order.id,
                "trade_status": "TRADE_SUCCESS",
                "total_amount": "30.00",
                "sign": "any_sign"
            }
            
            # 应拒绝回调
            self.assertFalse(alipay.verify_callback(callback_data))
        finally:
            if original_key:
                os.environ["PAYMENT_SANDBOX_CALLBACK_KEY"] = original_key

    def test_wechat_pay_callback_valid(self):
        """测试微信支付回调验签"""
        from payment_system import WechatPay, create_order
        
        wxpay = WechatPay()
        order = create_order("user004", 80.0, "wechat")
        
        # 生成有效签名
        sign = hmac.new(
            self.sandbox_key.encode(),
            f"{order.id}:8000:{wxpay.app_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        callback_data = {
            "out_trade_no": order.id,
            "result_code": "SUCCESS",
            "total_fee": "8000",  # 单位：分
            "sign": sign
        }
        
        valid, params = wxpay.verify_callback(callback_data)
        self.assertTrue(valid)

    def test_callback_wrong_trade_status(self):
        """测试错误的交易状态"""
        from payment_system import AlipaySandbox
        
        alipay = AlipaySandbox()
        
        # 非 SUCCESS 状态
        callback_data = {
            "out_trade_no": "ORD123",
            "trade_status": "TRADE_CLOSED",
            "total_amount": "100.00",
            "sign": "any"
        }
        
        self.assertFalse(alipay.verify_callback(callback_data))


class TestConcurrentPaymentHandling(unittest.TestCase):
    """并发支付处理测试"""

    def setUp(self):
        """测试前准备"""
        import payment_system
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        payment_system.PAYMENT_DB_PATH = Path(os.path.join(self.temp_dir, "test_payments.db"))
        payment_system.init_payment_db()
        
        # 模拟 billing 模块
        sys.modules['billing'] = MagicMock()
        
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if 'billing' in sys.modules:
            del sys.modules['billing']

    def test_confirm_payment_idempotency(self):
        """测试支付确认的幂等性"""
        from payment_system import create_order, confirm_payment, get_order
        
        order = create_order("user001", 100.0, "alipay")
        
        # 第一次确认
        success1, msg1 = confirm_payment(order.id, "TXN001", verified_amount=100.0)
        self.assertTrue(success1)
        
        # 第二次确认（应幂等返回成功）
        success2, msg2 = confirm_payment(order.id, "TXN002", verified_amount=100.0)
        self.assertTrue(success2)
        self.assertIn("已支付", msg2)
        
        # 验证订单状态仍为 success
        final_order = get_order(order.id)
        self.assertEqual(final_order.status, "success")
        # 首次确认的交易ID应保留
        self.assertEqual(final_order.transaction_id, "TXN001")

    def test_concurrent_payment_callbacks(self):
        """测试并发支付回调（防双倍发货）"""
        from payment_system import create_order, confirm_payment, get_order
        from billing import recharge_balance
        
        # 模拟充值函数
        call_count = [0]
        def mock_recharge(user_id, amount, method):
            call_count[0] += 1
            return True, "充值成功"
        
        recharge_balance.side_effect = mock_recharge
        
        order = create_order("user002", 100.0, "alipay")
        
        # 并发执行两个确认请求
        results = []
        def confirm_thread():
            success, msg = confirm_payment(order.id, f"TXN_{threading.current_thread().name}", verified_amount=100.0)
            results.append((success, msg))
        
        threads = [
            threading.Thread(target=confirm_thread, name="T1"),
            threading.Thread(target=confirm_thread, name="T2")
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 充值应只调用一次（防止双倍发货）
        self.assertEqual(call_count[0], 1)
        
        # 至少一个线程成功
        self.assertTrue(any(success for success, _ in results))

    def test_payment_amount_mismatch(self):
        """测试支付金额不匹配"""
        from payment_system import create_order, confirm_payment
        
        order = create_order("user003", 100.0, "alipay")
        
        # 回调金额与订单不符
        success, msg = confirm_payment(
            order.id,
            "TXN_MISMATCH",
            verified_amount=99.0  # 订单是 100 元
        )
        
        self.assertFalse(success)
        self.assertIn("金额不匹配", msg)


class TestCommissionSystem(unittest.TestCase):
    """佣金系统测试"""

    def setUp(self):
        """测试前准备"""
        import payment_system
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        payment_system.PAYMENT_DB_PATH = Path(os.path.join(self.temp_dir, "test_payments.db"))
        payment_system.init_payment_db()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_commission(self):
        """测试佣金计算"""
        from payment_system import calculate_commission, update_agent_settings, create_order
        
        agent_id = "agent001"
        order = create_order("user001", 100.0, "alipay")
        
        # 设置佣金比例
        update_agent_settings(agent_id, commission_rate=0.15)
        
        # 计算佣金
        commission, rate = calculate_commission(order, agent_id)
        
        self.assertEqual(rate, 0.15)
        self.assertEqual(commission, 15.0)  # 100 * 0.15

    def test_agent_settings_default(self):
        """测试分销商默认设置"""
        from payment_system import get_agent_settings
        
        # 新分销商应使用默认值
        settings = get_agent_settings("new_agent")
        
        self.assertEqual(settings["commission_rate"], 0.2)
        self.assertEqual(settings["custom_price_multiplier"], 1.0)

    def test_agent_settings_update(self):
        """测试分销商设置更新"""
        from payment_system import update_agent_settings, get_agent_settings
        
        agent_id = "agent002"
        update_agent_settings(
            agent_id,
            commission_rate=0.25,
            custom_price_multiplier=1.2,
            bank_info="中国银行 6222..."
        )
        
        settings = get_agent_settings(agent_id)
        self.assertEqual(settings["commission_rate"], 0.25)
        self.assertEqual(settings["custom_price_multiplier"], 1.2)
        self.assertEqual(settings["bank_info"], "中国银行 6222...")


class TestPaymentValidation(unittest.TestCase):
    """支付校验测试"""

    def setUp(self):
        """测试前准备"""
        import payment_system
        from pathlib import Path
        self.temp_dir = tempfile.mkdtemp()
        payment_system.PAYMENT_DB_PATH = Path(os.path.join(self.temp_dir, "test_payments.db"))
        payment_system.init_payment_db()
        
        # 模拟 billing 模块
        sys.modules['billing'] = MagicMock()

    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if 'billing' in sys.modules:
            del sys.modules['billing']

    def test_process_payment_invalid_user(self):
        """测试无效用户支付请求"""
        from payment_system import process_payment
        from billing import get_user_info
        
        get_user_info.return_value = None
        
        result = process_payment(
            user_id="invalid_user",
            amount=100.0,
            method="alipay"
        )
        
        self.assertFalse(result["success"])
        self.assertIn("用户不存在", result["error"])

    def test_process_payment_negative_amount(self):
        """测试负数金额"""
        from payment_system import process_payment
        from billing import get_user_info
        
        get_user_info.return_value = {"id": "user001"}
        
        result = process_payment(
            user_id="user001",
            amount=-10.0,
            method="alipay"
        )
        
        self.assertFalse(result["success"])
        self.assertIn("大于0", result["error"])

    def test_process_payment_unsupported_method(self):
        """测试不支持的支付方式"""
        from payment_system import process_payment
        from billing import get_user_info
        
        get_user_info.return_value = {"id": "user001"}
        
        result = process_payment(
            user_id="user001",
            amount=100.0,
            method="unknown"
        )
        
        self.assertFalse(result["success"])
        self.assertIn("不支持", result["error"])


if __name__ == '__main__':
    unittest.main(verbosity=2)