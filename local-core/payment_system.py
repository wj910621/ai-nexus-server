"""
Y·NEX支付系统 - 支付宝/微信支付集成
支持：
  - 支付宝沙箱（开发测试用）
  - 微信支付（预留接口）
  - 支付订单管理
  - 支付回调处理
  - 分销佣金结算

注意：实际生产环境需要替换为正式的支付商户号和密钥
"""

import json
import time
import uuid
import hashlib
import base64
import os
import hmac
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from logger import logger

# =============================================================================
# 支付配置（优先从环境变量读取）
# =============================================================================
ALIPAY_APP_ID = os.environ.get("ALIPAY_APP_ID", "")
ALIPAY_PRIVATE_KEY = os.environ.get("ALIPAY_PRIVATE_KEY", "")
ALIPAY_PUBLIC_KEY = os.environ.get("ALIPAY_PUBLIC_KEY", "")
ALIPAY_SANDBOX_APP_ID = os.environ.get("ALIPAY_SANDBOX_APP_ID", "sandbox_app_id")
ALIPAY_SANDBOX_KEY = os.environ.get("ALIPAY_SANDBOX_KEY", "")

WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
WECHAT_MCH_ID = os.environ.get("WECHAT_MCH_ID", "")
WECHAT_API_KEY = os.environ.get("WECHAT_API_KEY", "")
WECHAT_SANDBOX_KEY = os.environ.get("WECHAT_SANDBOX_KEY", "")

# 沙箱模式下回调签名校验密钥；若未设置则拒绝沙箱回调（开发环境可配置）
PAYMENT_SANDBOX_CALLBACK_KEY = os.environ.get("PAYMENT_SANDBOX_CALLBACK_KEY", "")


class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(Enum):
    ALIPAY = "alipay"
    WECHAT = "wechat"
    MANUAL = "manual"


@dataclass
class PaymentOrder:
    id: str
    user_id: str
    amount: float
    method: str
    status: str
    product_type: str
    product_id: str
    created_at: float
    paid_at: Optional[float]
    transaction_id: Optional[str]


# =============================================================================
# 数据库
# =============================================================================

PAYMENT_DB_PATH = Path("data/payments.db")


def _get_db():
    import sqlite3
    PAYMENT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PAYMENT_DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_payment_db():
    """初始化支付数据库"""
    conn = _get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            product_type TEXT NOT NULL,
            product_id TEXT,
            created_at REAL NOT NULL,
            paid_at REAL,
            transaction_id TEXT,
            callback_data TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS commissions (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            rate REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at REAL NOT NULL,
            settled_at REAL,
            FOREIGN KEY (agent_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_settings (
            agent_id TEXT PRIMARY KEY,
            commission_rate REAL DEFAULT 0.2,
            custom_price_multiplier REAL DEFAULT 1.0,
            bank_info TEXT,
            created_at REAL,
            updated_at REAL,
            FOREIGN KEY (agent_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    logger.info("支付数据库初始化完成")


# =============================================================================
# 订单管理
# =============================================================================

def create_order(user_id: str, amount: float, method: str,
                 product_type: str = "recharge", product_id: str = None) -> PaymentOrder:
    """
    创建支付订单
    product_type: recharge / subscription / agent
    """
    order_id = "ORD" + uuid.uuid4().hex[:24].upper()
    now = time.time()

    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO payment_orders (id, user_id, amount, method, status,
                                    product_type, product_id, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
    """, (order_id, user_id, amount, method, product_type, product_id, now))
    conn.commit()
    conn.close()

    logger.info(f"创建支付订单: {order_id} | 用户: {user_id} | 金额: {amount}元 | 方式: {method}")
    return PaymentOrder(
        id=order_id, user_id=user_id, amount=amount, method=method,
        status="pending", product_type=product_type, product_id=product_id,
        created_at=now, paid_at=None, transaction_id=None
    )


def get_order(order_id: str) -> Optional[PaymentOrder]:
    """获取订单信息"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        d = dict(row)
        return PaymentOrder(
            id=d["id"], user_id=d["user_id"], amount=d["amount"],
            method=d["method"], status=d["status"],
            product_type=d["product_type"], product_id=d.get("product_id"),
            created_at=d["created_at"], paid_at=d.get("paid_at"),
            transaction_id=d.get("transaction_id")
        )
    return None


def update_order_status(order_id: str, status: str, transaction_id: str = None,
                        callback_data: dict = None) -> bool:
    """更新订单状态"""
    now = time.time()
    conn = _get_db()
    c = conn.cursor()

    updates = ["status = ?"]
    params = [status]

    if status == "success":
        updates.append("paid_at = ?")
        params.append(now)

    if transaction_id:
        updates.append("transaction_id = ?")
        params.append(transaction_id)

    if callback_data:
        updates.append("callback_data = ?")
        params.append(json.dumps(callback_data, ensure_ascii=False))

    params.append(order_id)

    c.execute(f"""
        UPDATE payment_orders SET {', '.join(updates)} WHERE id = ?
    """, params)

    success = c.rowcount > 0
    conn.commit()
    conn.close()

    if success:
        logger.info(f"订单状态更新: {order_id} -> {status}")
    return success


def list_user_orders(user_id: str, limit: int = 20) -> list:
    """列出用户订单"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, amount, method, status, product_type, created_at, paid_at
        FROM payment_orders WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# 支付宝支付（沙箱模式）
# =============================================================================

class AlipaySandbox:
    """
    支付宝沙箱支付
    开发测试使用，真实环境需替换为正式支付宝SDK
    """

    def __init__(self, app_id: str = None, private_key: str = None, public_key: str = None):
        # 生产环境优先使用真实配置；未配置时回退到沙箱配置
        self.app_id = app_id or ALIPAY_APP_ID or ALIPAY_SANDBOX_APP_ID
        self.private_key = private_key or ALIPAY_PRIVATE_KEY or ""
        self.public_key = public_key or ALIPAY_PUBLIC_KEY or ""
        self.sandbox_key = ALIPAY_SANDBOX_KEY or PAYMENT_SANDBOX_CALLBACK_KEY or ""
        self.is_sandbox = "sandbox" in self.app_id or not ALIPAY_APP_ID
        self.gateway = "https://openapi.alipaydev.com/gateway.do"
        self.notify_url = ""

    def create_payment_url(self, order: PaymentOrder, return_url: str = "",
                           notify_url: str = "") -> Tuple[bool, str, str]:
        """
        创建支付宝支付链接
        返回 (success, pay_url, qr_code_url)
        """
        try:
            order_id = order.id
            amount = order.amount
            subject = "Y·NEX充值" if order.product_type == "recharge" else "Y·NEX订阅"

            params = {
                "app_id": self.app_id,
                "method": "alipay.trade.page.pay",
                "charset": "utf-8",
                "sign_type": "RSA2",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0",
                "notify_url": notify_url or self.notify_url,
                "return_url": return_url,
                "biz_content": json.dumps({
                    "out_trade_no": order_id,
                    "product_code": "FAST_INSTANT_TRADE_PAY",
                    "total_amount": f"{amount:.2f}",
                    "subject": subject,
                    "body": f"{subject} - {amount}元",
                }, ensure_ascii=False),
            }

            sign = self._sign(params)
            params["sign"] = sign

            query_string = "&".join(f"{k}={self._url_encode(v)}" for k, v in params.items())
            pay_url = f"{self.gateway}?{query_string}"

            return True, pay_url, ""
        except Exception as e:
            logger.error(f"支付宝创建支付链接失败: {e}")
            return False, "", str(e)

    def create_qr_code(self, order: PaymentOrder) -> Tuple[bool, str]:
        """
        创建扫码支付（沙箱模拟）
        返回 (success, qr_code_url_or_payment_info)
        """
        try:
            order_id = order.id
            amount = order.amount

            payment_info = {
                "order_id": order_id,
                "amount": amount,
                "method": "alipay_sandbox",
                "mock_qr": f"alipay://sandbox/pay/{order_id}",
                "instruction": "沙箱模式：点击下方模拟支付按钮完成支付",
            }

            return True, json.dumps(payment_info, ensure_ascii=False)
        except Exception as e:
            logger.error(f"支付宝二维码创建失败: {e}")
            return False, str(e)

    def verify_callback(self, params: dict) -> bool:
        """验证支付宝回调签名。沙箱模式下使用 HMAC-SHA256 校验，真实模式必须接入官方 SDK。"""
        if not params:
            return False
        out_trade_no = params.get("out_trade_no", "")
        trade_status = params.get("trade_status", "")
        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return False

        if self.is_sandbox:
            # 沙箱环境：若未配置回调密钥，则拒绝回调（阻断任意伪造充值）
            if not self.sandbox_key:
                logger.warning("沙箱支付回调被拒绝：未配置 ALIPAY_SANDBOX_KEY 或 PAYMENT_SANDBOX_CALLBACK_KEY")
                return False
            sign = params.get("sign", "")
            expected = hmac.new(
                self.sandbox_key.encode(),
                f"{out_trade_no}:{params.get('total_amount','')}:{self.app_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sign, expected):
                logger.warning(f"沙箱支付回调签名无效: order={out_trade_no}")
                return False
            return True

        # 生产环境：必须配置真实密钥；优先尝试官方 alipay 库 RSA 验签，未安装则拒绝
        if not self.public_key:
            logger.error("生产环境支付宝回调被拒绝：未配置 ALIPAY_PUBLIC_KEY")
            return False
        try:
            from alipay import AliPay
            alipay = AliPay(
                appid=self.app_id,
                app_notify_url=self.notify_url,
                app_private_key_string=self.private_key,
                alipay_public_key_string=self.public_key,
                sign_type="RSA2",
                debug=False
            )
            return alipay.verify(params, params.get("sign", ""))
        except ImportError:
            logger.error("生产环境支付宝回调被拒绝：未安装 alipay 官方 SDK（pip install alipay-sdk-python）")
            return False
        except Exception as e:
            logger.error(f"生产环境支付宝回调验签失败: {e}")
            return False

    def _sign(self, params: dict) -> str:
        """签名：沙箱模式下优先使用 HMAC-SHA256（与回调验签一致），未配置密钥时回退 MD5。生产环境需接入官方 SDK。"""
        if self.is_sandbox:
            content = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            if self.sandbox_key:
                return hmac.new(self.sandbox_key.encode(), content.encode(), hashlib.sha256).hexdigest()
            return hashlib.md5(content.encode()).hexdigest()
        return "production_signature_requires_official_sdk"

    def _url_encode(self, s: str) -> str:
        from urllib.parse import quote
        return quote(str(s), safe='')


# =============================================================================
# 微信支付（预留接口）
# =============================================================================

class WechatPay:
    """微信支付（预留接口，待接入）"""

    def __init__(self, app_id: str = None, mch_id: str = None, key: str = None):
        self.app_id = app_id or WECHAT_APP_ID or "wx_sandbox_appid"
        self.mch_id = mch_id or WECHAT_MCH_ID or "sandbox_mch_id"
        self.key = key or WECHAT_API_KEY or WECHAT_SANDBOX_KEY or PAYMENT_SANDBOX_CALLBACK_KEY or ""
        self.is_sandbox = not WECHAT_APP_ID or "sandbox" in self.app_id
        self.notify_url = ""

    def create_native_payment(self, order: PaymentOrder) -> Tuple[bool, str]:
        """创建Native扫码支付"""
        try:
            payment_info = {
                "order_id": order.id,
                "amount": order.amount,
                "method": "wechat_sandbox",
                "mock_qr": f"weixin://wxpay/sandbox/{order.id}",
                "instruction": "微信支付开发中，使用模拟支付",
            }
            return True, json.dumps(payment_info, ensure_ascii=False)
        except Exception as e:
            return False, str(e)

    def verify_callback(self, xml_data: str) -> Tuple[bool, dict]:
        """验证微信支付回调。沙箱模式下使用 HMAC-SHA256 校验，真实模式必须接入官方 SDK。"""
        try:
            params = {}
            if isinstance(xml_data, dict):
                params = xml_data
            elif isinstance(xml_data, str) and xml_data.strip().startswith("<"):
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_data)
                params = {child.tag: child.text or "" for child in root}
            elif isinstance(xml_data, str):
                # 尝试 key=value 形式
                params = dict(part.split("=", 1) for part in xml_data.split("&") if "=" in part)

            result_code = params.get("result_code", "")
            out_trade_no = params.get("out_trade_no", "")
            if result_code != "SUCCESS" or not out_trade_no:
                return False, {}

            if self.is_sandbox:
                if not self.key:
                    logger.warning("沙箱微信支付回调被拒绝：未配置 WECHAT_SANDBOX_KEY 或 PAYMENT_SANDBOX_CALLBACK_KEY")
                    return False, {}
                sign = params.get("sign", "")
                expected = hmac.new(
                    self.key.encode(),
                    f"{out_trade_no}:{params.get('total_fee','')}:{self.app_id}".encode(),
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(sign, expected):
                    logger.warning(f"沙箱微信支付回调签名无效: order={out_trade_no}")
                    return False, {}
                return True, params

            # 生产环境：未接入官方 SDK 前拒绝回调，避免绕过
            if not WECHAT_API_KEY:
                logger.error("生产环境微信支付回调被拒绝：未配置 WECHAT_API_KEY")
                return False, {}
            logger.warning("生产环境微信支付回调验签尚未接入官方 SDK，当前拒绝所有回调")
            return False, {}
        except Exception as e:
            logger.error(f"微信支付回调解析失败: {e}")
            return False, {}


# =============================================================================
# 分销佣金系统
# =============================================================================

def get_agent_settings(agent_id: str) -> dict:
    """获取分销商设置"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM agent_settings WHERE agent_id = ?", (agent_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    default = {
        "agent_id": agent_id,
        "commission_rate": 0.2,
        "custom_price_multiplier": 1.0,
        "bank_info": "",
    }
    return default


def update_agent_settings(agent_id: str, commission_rate: float = None,
                          custom_price_multiplier: float = None,
                          bank_info: str = None) -> bool:
    """更新分销商设置"""
    now = time.time()
    conn = _get_db()
    c = conn.cursor()

    c.execute("SELECT agent_id FROM agent_settings WHERE agent_id = ?", (agent_id,))
    exists = c.fetchone()

    if exists:
        updates = []
        params = []
        if commission_rate is not None:
            updates.append("commission_rate = ?")
            params.append(commission_rate)
        if custom_price_multiplier is not None:
            updates.append("custom_price_multiplier = ?")
            params.append(custom_price_multiplier)
        if bank_info is not None:
            updates.append("bank_info = ?")
            params.append(bank_info)
        updates.append("updated_at = ?")
        params.append(now)
        params.append(agent_id)
        c.execute(f"UPDATE agent_settings SET {', '.join(updates)} WHERE agent_id = ?", params)
    else:
        c.execute("""
            INSERT INTO agent_settings (agent_id, commission_rate, custom_price_multiplier,
                                        bank_info, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_id, commission_rate or 0.2, custom_price_multiplier or 1.0,
              bank_info or "", now, now))

    conn.commit()
    conn.close()
    return True


def calculate_commission(order: PaymentOrder, agent_id: str) -> Tuple[float, float]:
    """
    计算分销佣金
    返回 (commission_amount, rate)
    """
    settings = get_agent_settings(agent_id)
    rate = settings.get("commission_rate", 0.2)
    commission = order.amount * rate
    return round(commission, 2), rate


def create_commission(agent_id: str, order: PaymentOrder):
    """创建佣金记录"""
    from billing import get_user_info

    commission_amount, rate = calculate_commission(order, agent_id)

    if commission_amount <= 0:
        return

    comm_id = "COMM" + uuid.uuid4().hex[:20].upper()
    now = time.time()

    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO commissions (id, agent_id, order_id, user_id, amount, rate,
                                 status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (comm_id, agent_id, order.id, order.user_id, commission_amount, rate, now))
    conn.commit()
    conn.close()

    logger.info(f"创建佣金记录: {comm_id} | 分销商: {agent_id} | 金额: {commission_amount}元")


def settle_commission(commission_id: str) -> bool:
    """结算佣金（打款到分销商余额）"""
    from billing import recharge_balance

    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM commissions WHERE id = ? AND status = 'pending'",
              (commission_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return False

    d = dict(row)
    agent_id = d["agent_id"]
    amount = d["amount"]

    ok, msg = recharge_balance(agent_id, amount, "commission")
    if ok:
        now = time.time()
        c.execute("""
            UPDATE commissions SET status = 'settled', settled_at = ? WHERE id = ?
        """, (now, commission_id))
        conn.commit()
        logger.info(f"佣金结算完成: {commission_id} | 金额: {amount}元")

    conn.close()
    return ok


def get_agent_commissions(agent_id: str, status: str = None) -> list:
    """获取分销商佣金记录"""
    conn = _get_db()
    c = conn.cursor()

    if status:
        c.execute("""
            SELECT * FROM commissions WHERE agent_id = ? AND status = ?
            ORDER BY created_at DESC LIMIT 50
        """, (agent_id, status))
    else:
        c.execute("""
            SELECT * FROM commissions WHERE agent_id = ?
            ORDER BY created_at DESC LIMIT 50
        """, (agent_id,))

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_commission_summary(agent_id: str) -> dict:
    """获取分销商佣金统计"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT
            COUNT(*) as total_count,
            SUM(CASE WHEN status = 'settled' THEN amount ELSE 0 END) as total_settled,
            SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as total_pending
        FROM commissions WHERE agent_id = ?
    """, (agent_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"total_count": 0, "total_settled": 0, "total_pending": 0}


# =============================================================================
# 支付处理入口
# =============================================================================

_payment_systems = {}


def get_alipay() -> AlipaySandbox:
    if "alipay" not in _payment_systems:
        _payment_systems["alipay"] = AlipaySandbox()
    return _payment_systems["alipay"]


def get_wechat_pay() -> WechatPay:
    if "wechat" not in _payment_systems:
        _payment_systems["wechat"] = WechatPay()
    return _payment_systems["wechat"]


def process_payment(user_id: str, amount: float, method: str = "alipay",
                    product_type: str = "recharge", product_id: str = None,
                    return_url: str = "", notify_url: str = "") -> dict:
    """
    统一支付入口
    返回 {success, order_id, pay_url, qr_code, method, instruction}
    """
    from billing import get_user_info

    user = get_user_info(user_id)
    if not user:
        return {"success": False, "error": "用户不存在"}

    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}

    order = create_order(user_id, amount, method, product_type, product_id)

    result = {
        "success": True,
        "order_id": order.id,
        "amount": amount,
        "method": method,
    }

    if method == "alipay":
        alipay = get_alipay()
        ok, pay_url, qr_url = alipay.create_payment_url(order, return_url, notify_url)
        ok_qr, qr_info = alipay.create_qr_code(order)
        result["pay_url"] = pay_url if ok else ""
        result["qr_info"] = qr_info if ok_qr else ""
        result["instruction"] = "请使用支付宝扫码或点击链接完成支付（沙箱环境）"

    elif method == "wechat":
        wxpay = get_wechat_pay()
        ok, qr_info = wxpay.create_native_payment(order)
        result["qr_info"] = qr_info if ok else ""
        result["instruction"] = "请使用微信扫码完成支付（开发中，沙箱模式）"

    elif method == "manual":
        result["instruction"] = "请联系管理员手动充值"

    else:
        order = None
        result = {"success": False, "error": f"不支持的支付方式: {method}"}

    return result


def confirm_payment(order_id: str, transaction_id: str = None,
                    callback_data: dict = None, verified_amount: float = None) -> Tuple[bool, str]:
    """
    确认支付成功（回调/模拟）
    返回 (success, message)

    安全性：使用原子条件 UPDATE（WHERE status='pending'）防止并发回调
    导致的双倍发货/重复充值。
    """
    from billing import recharge_balance, subscribe_tier, get_user_info

    order = get_order(order_id)
    if not order:
        return False, "订单不存在"

    # 幂等：已成功的订单直接返回（不重复发货）
    if order.status == "success":
        return True, "订单已支付"

    # 只允许 pending 订单转为 success，防止失败/退款订单被伪造回调重复利用
    if order.status != "pending":
        return False, f"订单状态异常: {order.status}"

    # 校验回调金额与订单金额一致（允许 1 分误差）
    if verified_amount is not None:
        if abs(verified_amount - order.amount) > 0.01:
            logger.warning(f"支付金额不匹配: order={order_id} 订单金额={order.amount} 回调金额={verified_amount}")
            return False, "支付金额不匹配"

    # 原子状态机：仅当订单仍为 pending 时才转为 success，并返回受影响行数。
    # 并发回调只有一个能成功转换，其余会得到 rowcount=0，从而避免双倍发货。
    now = time.time()
    conn = _get_db()
    c = conn.cursor()
    c.execute("BEGIN IMMEDIATE")
    try:
        updates = ["status = ?", "paid_at = ?"]
        params = ["success", now]
        if transaction_id:
            updates.append("transaction_id = ?")
            params.append(transaction_id)
        if callback_data:
            updates.append("callback_data = ?")
            params.append(json.dumps(callback_data, ensure_ascii=False))
        params.append(order_id)
        c.execute(
            f"UPDATE payment_orders SET {', '.join(updates)} WHERE id = ? AND status = 'pending'",
            params,
        )
        transitioned = c.rowcount == 1
        if not transitioned:
            conn.rollback()
            conn.close()
            # 并发竞争落败，或订单状态已被改变；返回当前状态
            cur = get_order(order_id)
            if cur and cur.status == "success":
                return True, "订单已支付（并发回调）"
            return False, f"订单状态转换失败: {cur.status if cur else '未知'}"
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"订单状态原子转换失败: {e}")
        return False, f"订单状态转换异常: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 重新读取订单，确保使用最新数据
    order = get_order(order_id)

    # 支付成功后创建佣金记录（避免未支付订单产生刷单佣金）
    try:
        from billing import get_user_info
        user = get_user_info(order.user_id)
        referrer_id = user.get("referrer_id") if user else None
        if referrer_id and user.get("role") != "agent":
            create_commission(referrer_id, order)
    except Exception as e:
        logger.error(f"创建佣金失败: {e}")

    if order.product_type == "recharge":
        ok, msg = recharge_balance(order.user_id, order.amount, order.method)
        logger.info(f"充值成功: 订单{order_id} | 用户{order.user_id} | {order.amount}元")
        return ok, msg

    elif order.product_type == "subscription":
        ok, msg = subscribe_tier(order.user_id, order.product_id or "pro", paid_order_amount=order.amount)
        return ok, msg

    elif order.product_type == "agent":
        from billing import create_agent_account
        ok, msg = create_agent_account(order.user_id, paid_order_amount=order.amount)
        return ok, msg

    return True, "支付成功"


def mock_payment_callback(order_id: str) -> Tuple[bool, str]:
    """
    模拟支付回调（沙箱测试用）
    """
    order = get_order(order_id)
    if not order:
        return False, "订单不存在"
    alipay = get_alipay()
    callback_data = {
        "out_trade_no": order_id,
        "trade_no": "MOCK" + uuid.uuid4().hex[:16],
        "trade_status": "TRADE_SUCCESS",
        "total_amount": f"{order.amount:.2f}",
    }
    # 沙箱模式下生成回调签名
    if alipay.is_sandbox and alipay.sandbox_key:
        callback_data["sign"] = hmac.new(
            alipay.sandbox_key.encode(),
            f"{order_id}:{callback_data['total_amount']}:{alipay.app_id}".encode(),
            hashlib.sha256
        ).hexdigest()
    return confirm_payment(order_id, callback_data["trade_no"], callback_data, verified_amount=order.amount)


# 初始化
init_payment_db()
