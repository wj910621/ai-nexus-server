"""
Y·NEX在线服务 - 用户账户与计费系统
支持：
  1. 用户注册 / 登录 / API Key 管理
  2. 额度充值（按量计费 / 包月）
  3. API Key 鉴权（用户用自己的 Key 访问，平台赚 API 差价）
  4. 使用量统计与报表
  5. 多级分销（推荐返利）

计费模式：
  - 模式A（差价）：用户提供自己的 DeepSeek Key，平台收服务费
  - 模式B（额度）：用户充值到平台账户，平台代付 API，平台吃差价

用户角色：
  - user: 普通用户，有额度限制
  - vip: 付费用户，更高额度
  - agent: 分销商，有推荐链接和返利
"""

import sqlite3
import hashlib
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

DB_PATH = Path("data/users.db")

# API Key 哈希盐：防止彩虹表攻击。
# 安全要求：必须在 .env 中设置 BILLING_API_KEY_PEPPER，否则启动时给出警告。
_API_KEY_PEPPER = os.environ.get("BILLING_API_KEY_PEPPER", "")
if not _API_KEY_PEPPER:
    import warnings as _warnings
    _warnings.warn(
        "BILLING_API_KEY_PEPPER 未设置，正在使用临时随机盐。"
        "重启后所有已签发的 API Key 将失效。请在 .env 中设置固定值。",
        RuntimeWarning,
        stacklevel=2,
    )
    _API_KEY_PEPPER = secrets.token_hex(32)


def _hash_api_key(api_key: str) -> str:
    """对 API Key 进行单向哈希，永不存储明文 Key。"""
    return hashlib.sha256(f"{api_key}:{_API_KEY_PEPPER}".encode()).hexdigest()


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class User:
    id: str
    username: str
    password_hash: str
    email: str
    role: str  # user / vip / agent / admin
    balance: float  # 余额（分）
    quota_used: int  # 本月使用量（tokens）
    quota_limit: int  # 本月额度限制
    api_key: Optional[str]  # 用户的 API Key（存储为哈希值，非明文）
    referrer_id: Optional[str]  # 推荐人 ID
    created_at: float
    is_active: bool

@dataclass
class Transaction:
    id: str
    user_id: str
    type: str  # recharge / payment / refund / reward
    amount: float  # 金额（分）
    description: str
    created_at: float

@dataclass
class ApiKeyUsage:
    id: str
    api_key: str
    user_id: str
    tokens: int
    cost: float  # 实际成本（分）
    charged: float  # 向用户收取（分）
    endpoint: str
    created_at: float


# =============================================================================
# 数据库初始化
# =============================================================================

def _get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提升并发读写性能；busy_timeout 防止写锁冲突立即失败。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    """初始化数据库表"""
    conn = _get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'user',
            balance REAL DEFAULT 0,
            quota_used INTEGER DEFAULT 0,
            quota_limit INTEGER DEFAULT 100000,
            api_key TEXT UNIQUE,         -- 仅存储 API Key 的哈希值，永不存明文
            api_key_prefix TEXT,          -- 用于展示的前 8 位标识
            referrer_id TEXT,
            created_at REAL,
            is_active INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            amount REAL,
            description TEXT,
            created_at REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id TEXT PRIMARY KEY,
            api_key_hash TEXT,  -- 仅存储 API Key 哈希，不存明文
            user_id TEXT,
            tokens INTEGER,
            cost REAL,
            charged REAL,
            endpoint TEXT,
            created_at REAL
        )
    """)

    # 迁移：将明文 API Key 哈希化（一次性，部署后原有明文 Key 失效，需重新生成）
    try:
        c.execute("SELECT name FROM pragma_table_info('users') WHERE name='api_key_prefix'")
        if not c.fetchone():
            c.execute("ALTER TABLE users ADD COLUMN api_key_prefix TEXT")
        c.execute("SELECT id, api_key FROM users WHERE api_key IS NOT NULL AND api_key != ''")
        for row in c.fetchall():
            raw_key = row["api_key"]
            # 若长度较短或不是 yj_/yn_ 前缀，视为已哈希，跳过
            if len(raw_key) < 32 or (not raw_key.startswith("yj_") and not raw_key.startswith("yn_")):
                continue
            key_hash = _hash_api_key(raw_key)
            prefix = raw_key[:8]
            c.execute("UPDATE users SET api_key=?, api_key_prefix=? WHERE id=?",
                      (key_hash, prefix, row["id"]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[billing] API Key 迁移警告（可忽略）: {e}")

    c.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pricing_tiers (
            id TEXT PRIMARY KEY,
            name TEXT,
            monthly_fee REAL,
            quota_limit INTEGER,
            price_per_million REAL,
            description TEXT
        )
    """)

    # 插入默认定价方案
    default_tiers = [
        ("free", "免费版", 0, 100000, 0, "每月10万tokens，适合体验"),
        ("pro", "专业版", 990, 5000000, 0.8, "每月500万tokens，专业使用"),
        ("unlimited", "无限版", 2990, 999999999, 0, "不限量，适合重度用户"),
        ("agent", "代理版", 0, 0, 0.5, "分销商模式，自定义定价"),
    ]
    for tier in default_tiers:
        c.execute("""
            INSERT OR IGNORE INTO pricing_tiers (id, name, monthly_fee, quota_limit, price_per_million, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, tier)

    # 分销商设置表（agent 角色使用）
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_settings (
            agent_id TEXT PRIMARY KEY,
            commission_rate REAL DEFAULT 0.2,
            custom_price_multiplier REAL DEFAULT 1.0,
            bank_info TEXT DEFAULT '',
            created_at REAL,
            updated_at REAL,
            FOREIGN KEY (agent_id) REFERENCES users(id)
        )
    """)

    # 佣金记录表（分销商返利）
    c.execute("""
        CREATE TABLE IF NOT EXISTS commissions (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            referred_user_id TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            description TEXT,
            created_at REAL,
            settled_at REAL,
            FOREIGN KEY (agent_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# =============================================================================
# 用户认证
# =============================================================================

def _hash_password(password: str, salt: str = "") -> str:
    if not salt:
        salt = secrets.token_hex(16)
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex() + "$" + salt


def _verify_password(password: str, stored: str) -> bool:
    try:
        hash_part, salt = stored.rsplit("$", 1)
        import hmac as _hmac
        return _hmac.compare_digest(_hash_password(password, salt), stored)
    except Exception:
        return False


def generate_api_key() -> str:
    """生成用户的 API Key（Y·NEX 品牌前缀）"""
    return "yn_" + secrets.token_urlsafe(32)


def register_user(username: str, password: str, email: str,
                 referrer_id: Optional[str] = None) -> tuple[bool, str]:
    """
    注册新用户。
    返回 (success, message)
    """
    conn = _get_db()
    c = conn.cursor()

    # 检查重复
    c.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if c.fetchone():
        conn.close()
        return False, "用户名或邮箱已被注册"

    user_id = str(uuid.uuid4())
    password_hash = _hash_password(password)
    raw_api_key = generate_api_key()
    api_key_hash = _hash_api_key(raw_api_key)
    api_key_prefix = raw_api_key[:8]
    now = time.time()

    # 检查推荐人
    if referrer_id:
        c.execute("SELECT id, role FROM users WHERE id = ?", (referrer_id,))
        referrer = c.fetchone()
        if not referrer:
            referrer_id = None
        elif referrer["role"] != "agent":
            referrer_id = None

    try:
        c.execute("""
            INSERT INTO users (id, username, password_hash, email, role, balance, api_key, api_key_prefix, referrer_id, created_at)
            VALUES (?, ?, ?, ?, 'user', 0, ?, ?, ?, ?)
        """, (user_id, username, password_hash, email, api_key_hash, api_key_prefix, referrer_id, now))
        conn.commit()

        # 推荐奖励（如果推荐人是 agent）
        if referrer_id:
            c.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description, created_at)
                VALUES (?, ?, 'reward', 100, '推荐奖励', ?)
            """, (str(uuid.uuid4()), referrer_id, now))
            c.execute("UPDATE users SET balance = balance + 100 WHERE id = ?", (referrer_id,))
            conn.commit()

        conn.close()
        return True, f"注册成功！您的 API Key: {raw_api_key}（仅显示一次，请妥善保存）"
    except Exception as e:
        conn.close()
        return False, f"注册失败：{e}"


def login_user(username: str, password: str) -> tuple[bool, str, Optional[dict]]:
    """
    用户登录。
    返回 (success, message, user_info)
    """
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username,))
    user = c.fetchone()
    conn.close()

    if not user:
        return False, "用户名或密码错误", None

    if not _verify_password(password, user["password_hash"]):
        return False, "用户名或密码错误", None

    user_dict = dict(user)
    user_dict.pop("password_hash", None)
    # 永不通过登录接口返回明文 API Key；仅返回前缀供识别
    user_dict["api_key"] = user_dict.get("api_key_prefix") or ""
    return True, "登录成功", user_dict


def verify_api_key(api_key: str) -> tuple[bool, Optional[User], str]:
    """
    验证 API Key，返回用户信息。
    数据库中仅存 Key 的哈希值，传入的明文 Key 会被立即哈希后比对。
    返回 (valid, user_or_None, error_message)
    """
    if not api_key:
        return False, None, "未提供 API Key"

    key_hash = _hash_api_key(api_key)
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE api_key = ? AND is_active = 1", (key_hash,))
    user = c.fetchone()
    conn.close()

    if not user:
        return False, None, "无效的 API Key"

    u = User(**dict(user))
    return True, u, ""


# =============================================================================
# 额度管理
# =============================================================================

def check_quota(user_id: str, tokens_needed: int = 1000) -> tuple[bool, str]:
    """
    检查用户是否有足够额度。
    返回 (allowed, message)
    """
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT quota_used, quota_limit, balance FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return False, "用户不存在"

    used = row["quota_used"]
    limit = row["quota_limit"]
    balance = row["balance"]

    # 余额充足可临时超用
    if used + tokens_needed <= limit:
        return True, "额度充足"

    # 余额充足可临时超用：按 0.1分/1k tokens 估算（≈1元/1M tokens），
    # 略高于 pro 实际扣费（0.8元/1M），低于 user 实际扣费（1.5元/1M），
    # 作为保守的余额预检阈值，实际扣费以 record_usage 为准。
    if balance >= tokens_needed * 0.0001:  # 0.1分/1k tokens
        return True, "额度不足但余额充足"

    return False, f"额度已用完（{used}/{limit}），请充值"


def deduct_quota(user_id: str, tokens: int, cost: float, charged: float):
    """
    扣除用户使用量（异步调用）
    安全：使用 BEGIN IMMEDIATE 写锁 + 原子条件 UPDATE 消除 TOCTOU 竞态
    """
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("""
            UPDATE users
            SET quota_used = quota_used + ?
            WHERE id = ?
        """, (tokens, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_user_usage(user_id: str, days: int = 30) -> List[dict]:
    """获取用户使用统计"""
    conn = _get_db()
    c = conn.cursor()
    since = time.time() - days * 86400
    c.execute("""
        SELECT DATE(datetime(created_at, 'unixepoch', 'localtime')) as date,
               SUM(tokens) as total_tokens,
               SUM(cost) as total_cost, SUM(charged) as total_charged, COUNT(*) as calls
        FROM api_usage
        WHERE user_id = ? AND created_at > ?
        GROUP BY DATE(datetime(created_at, 'unixepoch', 'localtime'))
        ORDER BY date DESC
    """, (user_id, since))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =============================================================================
# 充值
# =============================================================================

TIERS = {
    "free": {"name": "免费版", "monthly": 0, "quota": 100000, "price_per_million": 0},
    "pro": {"name": "专业版", "monthly": 990, "quota": 5000000, "price_per_million": 0.8},
    "unlimited": {"name": "无限版", "monthly": 2990, "quota": 999999999, "price_per_million": 0},
}


def recharge_balance(user_id: str, amount: float, method: str = "manual") -> tuple[bool, str]:
    """
    充值余额。
    amount: 金额（元），会自动转换为分存储
    """
    if amount <= 0:
        return False, "充值金额必须大于0"

    conn = _get_db()
    c = conn.cursor()
    cents = int(amount * 100)

    c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (cents, user_id))
    c.execute("""
        INSERT INTO transactions (id, user_id, type, amount, description, created_at)
        VALUES (?, ?, 'recharge', ?, ?, ?)
    """, (str(uuid.uuid4()), user_id, cents, f"充值 {amount}元 via {method}", time.time()))
    conn.commit()
    conn.close()
    return True, f"充值成功：{amount}元"


def subscribe_tier(user_id: str, tier_id: str, paid_order_amount: float = None) -> tuple[bool, str]:
    """订阅套餐。paid_order_amount 为已支付订单金额（元），None 表示从余额扣费。"""
    if tier_id not in TIERS:
        return False, "不存在的套餐"

    tier = TIERS[tier_id]
    fee_yuan = tier["monthly"]
    fee_cents = int(fee_yuan * 100)

    conn = _get_db()
    c = conn.cursor()

    # 安全：使用 BEGIN IMMEDIATE 写锁 + 原子条件 UPDATE 消除 TOCTOU 竞态。
    # 旧代码先 SELECT balance 再 UPDATE，两个并发订阅请求可同时通过余额检查。
    try:
        c.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        pass

    # 若未通过支付订单，则原子扣减余额
    if paid_order_amount is None:
        c.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (fee_cents, user_id, fee_cents),
        )
        if c.rowcount != 1:
            # 区分用户不存在和余额不足（必须在 conn.close() 之前查询，
            # 否则关闭后再 conn.cursor() 会抛 ProgrammingError）
            c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            conn.rollback()
            conn.close()
            if not row:
                return False, "用户不存在"
            return False, f"余额不足，订阅 {tier['name']} 需要 {fee_yuan} 元"
    else:
        # 支付订单金额与套餐费用必须一致（允许 1 分误差）
        if abs(paid_order_amount - fee_yuan) > 0.01:
            conn.rollback()
            conn.close()
            return False, "支付金额与套餐费用不匹配"

    # 升级套餐时重置当月用量，避免旧用量占用新额度
    c.execute("UPDATE users SET quota_used = 0, quota_limit = ?, role = ? WHERE id = ?",
              (tier["quota"], tier_id if tier_id != "free" else "user", user_id))
    c.execute("""
        INSERT INTO transactions (id, user_id, type, amount, description, created_at)
        VALUES (?, ?, 'payment', ?, ?, ?)
    """, (str(uuid.uuid4()), user_id, fee_cents,
          f"订阅 {tier['name']}", time.time()))
    conn.commit()
    conn.close()
    return True, f"订阅成功：{tier['name']}，月费{fee_yuan}元"


def get_user_info(user_id: str) -> Optional[dict]:
    """获取用户信息摘要（含 API Key 前缀，不含明文 Key）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, username, email, role, balance, quota_used, quota_limit, created_at,
               api_key_prefix, (CASE WHEN api_key IS NOT NULL AND api_key != '' THEN 1 ELSE 0 END) as key_exists
        FROM users WHERE id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def regenerate_api_key(user_id: str) -> tuple[bool, str]:
    """重新生成用户 API Key。返回 (success, raw_key_or_message)，raw_key 仅返回一次。"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE id = ? AND is_active = 1", (user_id,))
    if not c.fetchone():
        conn.close()
        return False, "用户不存在或已禁用"
    raw = generate_api_key()
    key_hash = _hash_api_key(raw)
    prefix = raw[:8]
    c.execute("UPDATE users SET api_key = ?, api_key_prefix = ? WHERE id = ?",
              (key_hash, prefix, user_id))
    conn.commit()
    conn.close()
    return True, raw


# =============================================================================
# Agent 分销
# =============================================================================

AGENT_JOIN_FEE_YUAN = 1000.0  # 分销商准入费（元）


def create_agent_account(user_id: str, custom_price: float = 0.8,
                         paid_order_amount: float = None) -> tuple[bool, str]:
    """升级为分销商。paid_order_amount 为已支付订单金额（元），None 表示从余额扣费。"""
    fee_yuan = AGENT_JOIN_FEE_YUAN
    fee_cents = int(fee_yuan * 100)

    conn = _get_db()
    c = conn.cursor()

    # 安全：使用 BEGIN IMMEDIATE 写锁 + 原子条件 UPDATE 消除 TOCTOU 竞态。
    try:
        c.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError:
        pass

    if paid_order_amount is None:
        # 原子扣减余额：仅当 role='user' 且 balance 充足时才扣减
        c.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ? AND role = 'user'",
            (fee_cents, user_id, fee_cents),
        )
        if c.rowcount != 1:
            # 区分错误类型（必须在 conn.close() 之前查询，
            # 否则关闭后再 conn.cursor() 会抛 ProgrammingError）
            c.execute("SELECT balance, role FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            conn.rollback()
            conn.close()
            if not row:
                return False, "用户不存在"
            if row["role"] != "user":
                return False, "仅普通用户可申请成为分销商"
            return False, f"余额不足，成为分销商需要 {fee_yuan} 元"
    else:
        if abs(paid_order_amount - fee_yuan) > 0.01:
            conn.rollback()
            conn.close()
            return False, "支付金额与分销商准入费不匹配"

    c.execute("UPDATE users SET role = 'agent' WHERE id = ? AND role = 'user'", (user_id,))
    if c.rowcount == 0:
        conn.rollback()
        conn.close()
        return False, "无法升级为分销商"

    c.execute("""
        INSERT INTO transactions (id, user_id, type, amount, description, created_at)
        VALUES (?, ?, 'payment', ?, ?, ?)
    """, (str(uuid.uuid4()), user_id, fee_cents,
          f"升级为分销商，准入费 {fee_yuan}元", time.time()))
    # 初始化分销商默认设置
    c.execute("""
        INSERT OR IGNORE INTO agent_settings (agent_id, commission_rate, custom_price_multiplier, bank_info, created_at, updated_at)
        VALUES (?, 0.2, 1.0, '', ?, ?)
    """, (user_id, time.time(), time.time()))
    conn.commit()
    conn.close()
    return True, "已成为分销商，请设置您的定价"


def get_referral_link(user_id: str, base_url: str = "https://ynexai.cn/register") -> str:
    """获取推荐链接"""
    return f"{base_url}?ref={user_id}"


def get_agent_stats(user_id: str) -> dict:
    """获取分销商统计（推荐人数从 users 表统计，收益从 commissions 表统计）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as total_referrals FROM users WHERE referrer_id = ?
    """, (user_id,))
    row = c.fetchone()
    stats = dict(row) if row else {"total_referrals": 0}
    c.execute("""
        SELECT COALESCE(SUM(amount), 0) as total_earned,
               COALESCE(SUM(CASE WHEN status = 'settled' THEN amount ELSE 0 END), 0) as settled_earned
        FROM commissions WHERE agent_id = ?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        stats["total_earned"] = row["total_earned"]
        stats["settled_earned"] = row["settled_earned"]
    return stats


# =============================================================================
# 计费核心
# =============================================================================

def calculate_charge(tokens: int, user_role: str) -> float:
    """
    计算用户应支付金额（分）。
    差价模式：平台吃 DeepSeek 定价 与 用户支付价 之差。
    """
    COST_PER_MILLION = 0.1  # DeepSeek 成本（分）

    if user_role == "unlimited":
        return 0

    if user_role == "pro":
        return int(tokens * 0.8 / 1000000 * 100)  # 0.8元/百万

    if user_role == "user":
        return int(tokens * 1.5 / 1000000 * 100)  # 1.5元/百万

    if user_role == "agent":
        return int(tokens * 0.5 / 1000000 * 100)  # 分销商默认 0.5元/百万

    return int(tokens * COST_PER_MILLION / 1000000 * 100)


def record_usage(api_key: Optional[str], tokens: int, cost: float, charged: float,
                 endpoint: str = "/chat", user_id: Optional[str] = None):
    """记录一次 API 调用并扣费（异步）。cost/charged 单位：分。
    api_key 为明文时内部立即哈希；也可直接传入 user_id。
    若超出套餐额度，会自动从余额中扣除 charged（余额不足时扣至 0）。"""
    try:
        conn = _get_db()
        c = conn.cursor()
        target_user_id = user_id
        key_hash = None

        if api_key:
            key_hash = _hash_api_key(api_key)
            if not target_user_id:
                c.execute("SELECT id FROM users WHERE api_key = ?", (key_hash,))
                row = c.fetchone()
                if row:
                    target_user_id = row["id"]

        if not target_user_id:
            conn.close()
            return

        # 使用 BEGIN IMMEDIATE 立即获取写锁，确保 SELECT-UPDATE 序列原子，
        # 消除 TOCTOU 竞态（并发请求可能导致余额扣减超出/双扣）。
        try:
            c.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            # 已在事务中（如外层调用者已开启），跳过
            pass

        c.execute("SELECT quota_used, quota_limit, balance FROM users WHERE id = ?", (target_user_id,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            conn.close()
            return
        old_used = row["quota_used"]
        limit = row["quota_limit"]
        # BEGIN IMMEDIATE 持有写锁，事务内读取的 balance 不会被并发修改，
        # 因此可安全用于计算扣减额。
        balance = row["balance"]

        c.execute("""
            INSERT INTO api_usage (id, api_key_hash, user_id, tokens, cost, charged, endpoint, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), key_hash, target_user_id, tokens, cost, charged, endpoint, time.time()))
        c.execute("UPDATE users SET quota_used = quota_used + ? WHERE id = ?", (tokens, target_user_id))

        # 超出套餐额度时，从余额扣费
        if old_used + tokens > limit and charged > 0 and balance > 0:
            # 原子扣减：仅当余额 >= 扣减额时全额扣；否则扣到 0（部分扣费）
            deduction = min(charged, balance)
            c.execute(
                "UPDATE users SET balance = balance - ? WHERE id = ?",
                (deduction, target_user_id),
            )
            c.execute("""
                INSERT INTO transactions (id, user_id, type, amount, description, created_at)
                VALUES (?, ?, 'payment', ?, ?, ?)
            """, (str(uuid.uuid4()), target_user_id, -deduction,
                  f"API 超额扣费 {tokens} tokens", time.time()))

        conn.commit()
        conn.close()
    except Exception as e:
        # 异常路径必须回滚事务并关闭连接，否则 BEGIN IMMEDIATE 获取的写锁
        # 不会释放，后续所有写操作将阻塞 30 秒后抛出 "database is locked"，
        # 导致整个计费系统冻结。
        # 注意：若 _get_db() 本身抛异常，conn 未定义，需用 locals() 守卫。
        if 'conn' in locals() and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        # 记录计费错误而非静默吞掉，便于排查计费丢失问题
        try:
            from logger import logger
            logger.error(f"[billing] record_usage 失败: {e}")
        except Exception:
            print(f"[billing] record_usage 失败: {e}")


# =============================================================================
# 用户管理（admin）
# =============================================================================

def list_users(limit: int = 50, offset: int = 0) -> List[dict]:
    """列出用户（admin）"""
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, username, email, role, balance, quota_used, quota_limit, created_at, is_active
        FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def admin_update_user(user_id: str, role: str = None, quota_limit: int = None,
                      is_active: bool = None) -> bool:
    """管理员修改用户"""
    conn = _get_db()
    c = conn.cursor()
    if role is not None:
        c.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    if quota_limit is not None:
        c.execute("UPDATE users SET quota_limit = ? WHERE id = ?", (quota_limit, user_id))
    if is_active is not None:
        c.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
    conn.commit()
    conn.close()
    return True


# 初始化
init_db()
