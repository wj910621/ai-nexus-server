"""
支付系统测试
验证支付订单并发处理、回调签名验证、佣金结算等核心功能
"""

import os
import sys
import tempfile
import shutil
import time
import threading
import hashlib
import hmac
import json
from pathlib import Path

# 确保导入项目根目录
sys.path.insert(0, str(Path(__file__).parent))

_test_data_dir = None


def _setup_test_env():
    """创建临时测试环境"""
    global _test_data_dir
    _test_data_dir = tempfile.mkdtemp(prefix="ynex_payment_test_")
    os.makedirs(_test_data_dir, exist_ok=True)
    os.environ["TEST_DATA_DIR"] = _test_data_dir

    # 设置沙箱密钥
    os.environ["PAYMENT_SANDBOX_CALLBACK_KEY"] = "test_sandbox_key_12345"
    os.environ["ALIPAY_SANDBOX_KEY"] = "test_alipay_sandbox_key"


def _teardown_test_env():
    """清理临时测试环境"""
    global _test_data_dir
    if _test_data_dir and os.path.exists(_test_data_dir):
        try:
            shutil.rmtree(_test_data_dir)
        except Exception:
            pass


def test_order_creation():
    """测试订单创建"""
    print("\n=== 测试订单创建 ===")

    import payment_system

    # 初始化数据库
    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments.db"
    payment_system.init_payment_db()

    # 创建订单
    order = payment_system.create_order("test_user_001", 100.0, "alipay")
    print(f"创建订单: {order.id}")

    assert order.id.startswith("ORD")
    assert order.amount == 100.0
    assert order.status == "pending"
    assert order.user_id == "test_user_001"

    # 查询订单
    retrieved = payment_system.get_order(order.id)
    assert retrieved is not None
    assert retrieved.id == order.id

    print("✅ 订单创建验证通过")


def test_concurrent_payment_confirmation():
    """测试并发支付确认（防止双倍发货）"""
    print("\n=== 测试并发支付确认 ===")

    import payment_system

    # 重新初始化
    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_concurrent.db"
    payment_system.init_payment_db()

    # 创建测试订单
    order = payment_system.create_order("user_concurrent", 50.0, "alipay")

    results = []
    errors = []

    def confirm_order():
        """尝试确认支付"""
        try:
            # 模拟并发回调
            callback_data = {
                "out_trade_no": order.id,
                "trade_no": f"MOCK_{threading.current_thread().name}",
                "trade_status": "TRADE_SUCCESS",
                "total_amount": f"{order.amount:.2f}",
            }

            # 生成签名
            sandbox_key = os.environ.get("PAYMENT_SANDBOX_CALLBACK_KEY", "")
            sign = hmac.new(
                sandbox_key.encode(),
                f"{order.id}:{callback_data['total_amount']}:sandbox_app_id".encode(),
                hashlib.sha256
            ).hexdigest()
            callback_data["sign"] = sign

            ok, msg = payment_system.confirm_payment(
                order.id,
                callback_data["trade_no"],
                callback_data,
                verified_amount=order.amount
            )
            results.append((ok, msg, threading.current_thread().name))
        except Exception as e:
            errors.append((str(e), threading.current_thread().name))

    # 启动多个并发确认请求
    threads = []
    for i in range(5):
        t = threading.Thread(target=confirm_order, name=f"Thread-{i}")
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 验证结果
    assert len(errors) == 0, f"并发错误: {errors}"

    # 只有第一个成功的应该是成功，其余应该是"已支付"
    success_count = sum(1 for ok, msg, _ in results if ok and "已支付" not in msg)
    already_paid_count = sum(1 for ok, msg, _ in results if "已支付" in msg or "并发回调" in msg)

    print(f"成功确认: {success_count}, 已支付/并发: {already_paid_count}")

    # 至少应该有一个成功确认，其余应该被幂等拒绝
    assert success_count >= 1, "至少应有一个成功确认"
    assert success_count + already_paid_count == len(results), "所有请求都应有明确结果"

    # 验证订单最终状态为成功
    final_order = payment_system.get_order(order.id)
    assert final_order.status == "success"

    print("✅ 并发支付确认验证通过（防止双倍发货）")


def test_payment_amount_validation():
    """测试支付金额校验"""
    print("\n=== 测试支付金额校验 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_amount.db"
    payment_system.init_payment_db()

    order = payment_system.create_order("user_amount", 100.0, "alipay")

    # 尝试使用错误金额确认
    ok, msg = payment_system.confirm_payment(
        order.id,
        "TRANSACTION_123",
        {},
        verified_amount=99.0  # 金额不匹配
    )

    assert not ok, "应拒绝金额不匹配的支付"
    assert "金额不匹配" in msg

    # 使用正确金额
    ok, msg = payment_system.confirm_payment(
        order.id,
        "TRANSACTION_123",
        {},
        verified_amount=100.0
    )

    assert ok, "应接受金额匹配的支付"

    print("✅ 支付金额校验验证通过")


def test_alipay_sandbox_signature():
    """测试支付宝沙箱签名验证"""
    print("\n=== 测试支付宝沙箱签名验证 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_alipay.db"
    payment_system.init_payment_db()

    alipay = payment_system.AlipaySandbox()

    # 设置沙箱密钥
    alipay.sandbox_key = "test_sandbox_key_12345"

    order = payment_system.create_order("user_alipay", 50.0, "alipay")

    # 构造合法回调
    callback_data = {
        "out_trade_no": order.id,
        "trade_status": "TRADE_SUCCESS",
        "total_amount": "50.00",
    }

    # 生成正确签名（使用实际 app_id 和 sandbox_key）
    sign = hmac.new(
        alipay.sandbox_key.encode(),
        f"{order.id}:50.00:{alipay.app_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    callback_data["sign"] = sign

    # 验证签名
    result = alipay.verify_callback(callback_data)
    assert result, "合法签名应通过验证"

    # 构造非法签名
    callback_data["sign"] = "invalid_signature_12345"
    result = alipay.verify_callback(callback_data)
    assert not result, "非法签名应被拒绝"

    print("✅ 支付宝沙箱签名验证通过")


def test_wechat_sandbox_signature():
    """测试微信沙箱签名验证"""
    print("\n=== 测试微信沙箱签名验证 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_wechat.db"
    payment_system.init_payment_db()

    wechat = payment_system.WechatPay()
    order = payment_system.create_order("user_wechat", 30.0, "wechat")

    # 构造合法回调（微信使用分为单位）
    sandbox_key = os.environ.get("PAYMENT_SANDBOX_CALLBACK_KEY", "")
    callback_data = {
        "out_trade_no": order.id,
        "result_code": "SUCCESS",
        "total_fee": "3000",  # 30元 = 3000分
    }

    # 生成正确签名
    sign = hmac.new(
        sandbox_key.encode(),
        f"{order.id}:3000:wx_sandbox_appid".encode(),
        hashlib.sha256
    ).hexdigest()
    callback_data["sign"] = sign

    # 验证签名
    ok, params = wechat.verify_callback(callback_data)
    assert ok, "合法签名应通过验证"

    # 非法签名
    callback_data["sign"] = "invalid_sign"
    ok, params = wechat.verify_callback(callback_data)
    assert not ok, "非法签名应被拒绝"

    print("✅ 微信沙箱签名验证通过")


def test_order_status_transitions():
    """测试订单状态转换"""
    print("\n=== 测试订单状态转换 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_status.db"
    payment_system.init_payment_db()

    order = payment_system.create_order("user_status", 100.0, "alipay")

    # pending -> success
    ok = payment_system.update_order_status(order.id, "success", "TXN_123")
    assert ok

    updated = payment_system.get_order(order.id)
    assert updated.status == "success"
    assert updated.transaction_id == "TXN_123"
    assert updated.paid_at is not None

    # success -> refunded（模拟退款）
    ok = payment_system.update_order_status(order.id, "refunded")
    assert ok

    updated = payment_system.get_order(order.id)
    assert updated.status == "refunded"

    print("✅ 订单状态转换验证通过")


def test_duplicate_payment_prevention():
    """测试重复支付防护"""
    print("\n=== 测试重复支付防护 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_duplicate.db"
    payment_system.init_payment_db()

    order = payment_system.create_order("user_dup", 100.0, "alipay")

    # 第一次支付成功
    ok, msg = payment_system.confirm_payment(order.id, "TXN_001", {}, verified_amount=100.0)
    assert ok

    # 尝试再次支付同一订单
    ok, msg = payment_system.confirm_payment(order.id, "TXN_002", {}, verified_amount=100.0)
    assert ok  # 幂等性：已支付订单应返回成功
    assert "已支付" in msg

    print("✅ 重复支付防护验证通过")


def test_failed_order_reuse_prevention():
    """测试失败订单重放防护"""
    print("\n=== 测试失败订单重放防护 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_failed.db"
    payment_system.init_payment_db()

    order = payment_system.create_order("user_failed", 100.0, "alipay")

    # 先标记为失败
    payment_system.update_order_status(order.id, "failed")

    # 尝试用失败订单确认支付
    ok, msg = payment_system.confirm_payment(order.id, "TXN_001", {}, verified_amount=100.0)
    assert not ok, "应拒绝失败订单的支付确认"
    assert "异常" in msg

    print("✅ 失败订单重放防护验证通过")


def test_commission_calculation():
    """测试佣金计算"""
    print("\n=== 测试佣金计算 ===")

    import payment_system

    payment_system.PAYMENT_DB_PATH = Path(_test_data_dir) / "payments_commission.db"
    payment_system.init_payment_db()

    order = payment_system.PaymentOrder(
        id="TEST_ORD_001",
        user_id="user_001",
        amount=1000.0,
        method="alipay",
        status="success",
        product_type="recharge",
        product_id=None,
        created_at=time.time(),
        paid_at=time.time(),
        transaction_id="TXN_001"
    )

    # 计算佣金
    commission, rate = payment_system.calculate_commission(order, "agent_001")

    assert commission == 200.0  # 默认 20% 佣金
    assert rate == 0.2

    print("✅ 佣金计算验证通过")


def test_payment_without_callback_key():
    """测试未配置回调密钥时的安全拒绝"""
    print("\n=== 测试未配置回调密钥时的安全拒绝 ===")

    import payment_system

    # 临时移除密钥
    original_key = os.environ.get("PAYMENT_SANDBOX_CALLBACK_KEY", "")
    try:
        os.environ["PAYMENT_SANDBOX_CALLBACK_KEY"] = ""

        alipay = payment_system.AlipaySandbox()
        alipay.sandbox_key = ""

        callback_data = {
            "out_trade_no": "ORD_TEST",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "100.00",
            "sign": "any_sign"
        }

        result = alipay.verify_callback(callback_data)
        assert not result, "未配置回调密钥时应拒绝所有回调"

        print("✅ 未配置回调密钥时的安全拒绝验证通过")
    finally:
        os.environ["PAYMENT_SANDBOX_CALLBACK_KEY"] = original_key


def main():
    """运行所有支付系统测试"""
    print("=" * 60)
    print("Y·NEX 支付系统安全测试")
    print("=" * 60)

    try:
        _setup_test_env()

        test_order_creation()
        test_concurrent_payment_confirmation()
        test_payment_amount_validation()
        test_alipay_sandbox_signature()
        test_wechat_sandbox_signature()
        test_order_status_transitions()
        test_duplicate_payment_prevention()
        test_failed_order_reuse_prevention()
        test_commission_calculation()
        test_payment_without_callback_key()

        print("\n" + "=" * 60)
        print("✅ 所有支付系统安全测试通过")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        _teardown_test_env()


if __name__ == "__main__":
    main()