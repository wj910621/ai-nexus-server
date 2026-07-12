"""
Y·NEX - 积分定价系统
=====================

核心设计：
- 积分体系：按次扣费，而非按月tokens
- 利润率：70-85%（比市场便宜1/3的同时保证高利润）
- 会员体系：免费版 / 订阅版（月/年） / 终身版（限量+逐年涨价）

定价策略：
- 国产模型：利润率 利润率80-85%
- 海外旗舰模型：利润率70-75%
- 免费模型：利润率90%+

1积分 = 0.1元人民币
"""

import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from pathlib import Path

DB_PATH = Path("data/credits.db")

CREDIT_VALUE = 0.1  # 1积分 = 0.1元人民币

# =============================================================================
# 模型成本价（每1M tokens，人民币元）
# 来源：各平台公开定价 + 分析结果
# =============================================================================
MODEL_COSTS = {
    # ===== DeepSeek 官方 =====
    "deepseekv3": {"input": 1, "output": 4, "provider": "DeepSeek官方", "tier": "standard"},
    "deepseekr1": {"input": 4, "output": 16, "provider": "DeepSeek官方", "tier": "premium"},
    
    # ===== 阿里百炼 =====
    "qwen3": {"input": 2, "output": 8, "provider": "阿里百炼", "tier": "standard"},
    "ali_qwen37_max": {"input": 20, "output": 80, "provider": "阿里百炼", "tier": "premium"},
    "ali_qwen36_plus": {"input": 4, "output": 12, "provider": "阿里百炼", "tier": "standard"},
    "ali_qwen36_flash": {"input": 0.5, "output": 2, "provider": "阿里百炼", "tier": "free"},
    "ali_glm51": {"input": 6, "output": 28, "provider": "阿里百炼", "tier": "premium"},
    "ali_kimi_k26": {"input": 12, "output": 12, "provider": "阿里百炼", "tier": "premium"},
    
    # ===== API Nexus（海外模型，约7折成本）=====
    "nx_gpt5": {"input": 12.6, "output": 50.4, "provider": "API Nexus", "tier": "flagship"},
    "nx_gpt5mini": {"input": 0.756, "output": 3.024, "provider": "API Nexus", "tier": "standard"},
    "nx_gpt5chat": {"input": 5.04, "output": 15.12, "provider": "API Nexus", "tier": "premium"},
    "nx_gpt5nano": {"input": 0.504, "output": 1.512, "provider": "API Nexus", "tier": "standard"},
    "nx_claude_opus": {"input": 75.6, "output": 378, "provider": "API Nexus", "tier": "flagship"},
    "nx_claude_sonnet": {"input": 15.12, "output": 75.6, "provider": "API Nexus", "tier": "premium"},
    "nx_claude_haiku": {"input": 5.04, "output": 25.2, "provider": "API Nexus", "tier": "standard"},
    "nx_gemini_pro": {"input": 6.3, "output": 25.2, "provider": "API Nexus", "tier": "premium"},
    
    # ===== 硅基流动 =====
    "sf_qwen35_397b": {"input": 2, "output": 8, "provider": "硅基流动", "tier": "standard"},
    "sf_qwq_32b": {"input": 2, "output": 6, "provider": "硅基流动", "tier": "standard"},
    "sf_glm5": {"input": 6, "output": 28, "provider": "硅基流动", "tier": "premium"},
    "sf_hunyuan_a13b": {"input": 0.5, "output": 0.5, "provider": "硅基流动", "tier": "free"},
    "sf_qwen3_8b": {"input": 0.5, "output": 2, "provider": "硅基流动", "tier": "free"},
    "sf_deepseek_v3_free": {"input": 1, "output": 4, "provider": "硅基流动", "tier": "free"},
    
    # ===== 火山引擎（免费额度内成本为0）=====
    "ark_dsv4p": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dsv4f": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dsv32": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dbs2_pro": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dbs2_lite": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dbs2_mini": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_dbs_code": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    "ark_glm47": {"input": 0, "output": 0, "provider": "火山引擎", "tier": "free"},
    
    # ===== 智谱官方 =====
    "glm4plus": {"input": 0.5, "output": 0.5, "provider": "智谱官方", "tier": "free"},
    
    # ===== 腾讯混元 =====
    "hunyuan": {"input": 1, "output": 2, "provider": "腾讯混元", "tier": "standard"},
    
    # ===== 月之暗面 Kimi =====
    "kimi2": {"input": 12, "output": 12, "provider": "月之暗面", "tier": "premium"},
    
    # ===== 官方旗舰 =====
    "gpt4o": {"input": 18, "output": 72, "provider": "OpenAI官方", "tier": "flagship"},
    "claude4": {"input": 21.6, "output": 108, "provider": "Anthropic官方", "tier": "flagship"},
    "gemini25pro": {"input": 9, "output": 36, "provider": "Google官方", "tier": "flagship"},
}

# =============================================================================
# 用户积分定价（每次调用消耗积分数）
# 定价原则：
#   - free tier（免费模型）：0-1积分，利润率90%+
#   - standard tier（国产主流）：1-3积分，利润率80-85%
#   - premium tier（高端国产）：3-8积分，利润率75-80%
#   - flagship tier（海外旗舰）：8-15积分，利润率70-75%
#
# 计算方式：按一次对话 输入2K + 输出2K tokens 估算成本，向上取整
# =============================================================================
MODEL_CREDIT_PRICES = {
    # ===== free tier（免费/极低价模型）=====
    "sf_qwen3_8b": 0,
    "sf_deepseek_v3_free": 0,
    "sf_hunyuan_a13b": 0,
    "ark_dsv4p": 0,
    "ark_dsv4f": 0,
    "ark_dsv32": 0,
    "ark_dbs2_pro": 0,
    "ark_dbs2_lite": 0,
    "ark_dbs2_mini": 0,
    "ark_dbs_code": 0,
    "ark_glm47": 0,
    "glm4plus": 1,
    
    # ===== standard tier（国产主流模型）=====
    "deepseekv3": 1,
    "qwen3": 2,
    "ali_qwen36_flash": 1,
    "ali_qwen36_plus": 2,
    "sf_qwen35_397b": 1,
    "sf_qwq_32b": 1,
    "hunyuan": 2,
    "nx_gpt5mini": 2,
    "nx_gpt5nano": 2,
    "nx_claude_haiku": 3,
    "bc_baichuan3": 1,
    
    # ===== premium tier（高端模型）=====
    "deepseekr1": 5,
    "ali_qwen37_max": 8,
    "ali_glm51": 5,
    "ali_kimi_k26": 3,
    "sf_glm5": 3,
    "kimi2": 3,
    "nx_gpt5chat": 5,
    "nx_claude_sonnet": 6,
    "nx_gemini_pro": 5,
    "bc_baichuan4": 2,
    
    # ===== flagship tier（海外旗舰模型）=====
    "nx_gpt5": 10,
    "nx_claude_opus": 15,
    "gpt4o": 8,
    "claude4": 12,
    "gemini25pro": 10,
    "or_gpt4o": 10,
    "or_claude_sonnet": 8,
    "or_gemini25pro": 10,
    "qiniu_gpt4o": 10,
    "qiniu_claude37": 10,
    "qiniu_claudeopus4": 15,
}

# =============================================================================
# 会员套餐定义
# =============================================================================
MEMBERSHIP_PLANS = {
    "free": {
        "name": "免费版",
        "price": 0,
        "period": "forever",
        "daily_credits": 10,
        "max_concurrent": 1,
        "features": [
            "每天10积分",
            "基础模型可用",
            "标准排队",
        ],
        "model_tiers": ["free", "standard"],
    },
    "monthly": {
        "name": "月度会员",
        "price": 69,
        "price_credits": 1000,
        "period": "month",
        "max_concurrent": 3,
        "priority_queue": True,
        "features": [
            "每月1000积分",
            "全部模型可用",
            "优先排队",
            "工作流无限使用",
            "多Agent协作",
        ],
        "model_tiers": ["free", "standard", "premium", "flagship"],
    },
    "yearly": {
        "name": "年度会员",
        "price": 599,
        "price_credits": 15000,
        "period": "year",
        "max_concurrent": 5,
        "priority_queue": True,
        "features": [
            "每年15000积分（相当于每月1250，送2个月）",
            "全部模型可用",
            "极速排队",
            "工作流无限使用",
            "多Agent协作",
            "专属客服支持",
        ],
        "model_tiers": ["free", "standard", "premium", "flagship"],
    },
    "lifetime": {
        "name": "终身版",
        "price": 699,
        "price_credits": 50000,
        "period": "lifetime",
        "max_concurrent": 10,
        "priority_queue": True,
        "priority_level": "ultra",
        "features": [
            "永久50000积分",
            "全部模型可用",
            "极速排队（最高优先级）",
            "工作流无限使用",
            "多Agent协作",
            "专属客服支持",
            "未来新功能优先体验",
        ],
        "model_tiers": ["free", "standard", "premium", "flagship"],
        "limited": True,
        "total_limit": 500,
        "price_increase_rate": 0.1,
    },
}

# =============================================================================
# 积分充值包
# =============================================================================
CREDIT_PACKAGES = [
    {"id": "pack_100", "name": "100积分", "credits": 100, "price": 9.9, "bonus": 0},
    {"id": "pack_500", "name": "500积分", "credits": 500, "price": 45, "bonus": 50},
    {"id": "pack_1000", "name": "1000积分", "credits": 1000, "price": 85, "bonus": 150},
    {"id": "pack_3000", "name": "3000积分", "credits": 3000, "price": 240, "bonus": 600},
    {"id": "pack_10000", "name": "10000积分", "credits": 10000, "price": 750, "bonus": 3000},
]


# =============================================================================
# 数据模型
# =============================================================================
@dataclass
class UserCredits:
    user_id: str
    credits: int
    plan: str
    plan_expires_at: Optional[float]
    daily_used: int
    daily_reset_date: str
    total_used: int
    created_at: float


@dataclass
class CreditTransaction:
    id: str
    user_id: str
    type: str
    amount: int
    description: str
    model: Optional[str]
    cost_price: Optional[float]
    created_at: float


@dataclass
class LifetimeSale:
    id: str
    user_id: str
    price: float
    purchase_time: float
    batch_number: int


# =============================================================================
# 数据库
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
    conn = _get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_credits (
            user_id TEXT PRIMARY KEY,
            credits INTEGER DEFAULT 0,
            plan TEXT DEFAULT 'free',
            plan_expires_at REAL,
            daily_used INTEGER DEFAULT 0,
            daily_reset_date TEXT DEFAULT '',
            total_used INTEGER DEFAULT 0,
            created_at REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            amount INTEGER,
            description TEXT,
            model TEXT,
            cost_price REAL,
            created_at REAL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lifetime_sales (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            price REAL,
            purchase_time REAL,
            batch_number INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pricing_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    c.execute("INSERT OR IGNORE INTO pricing_config (key, value) VALUES ('lifetime_sold', '0')")
    c.execute("INSERT OR IGNORE INTO pricing_config (key, value) VALUES ('lifetime_batch', '1')")

    conn.commit()
    conn.close()


# =============================================================================
# 积分核心功能
# =============================================================================
def get_user_credits(user_id: str) -> UserCredits:
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM user_credits WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return UserCredits(**dict(row))
    
    return UserCredits(
        user_id=user_id,
        credits=0,
        plan="free",
        plan_expires_at=None,
        daily_used=0,
        daily_reset_date="",
        total_used=0,
        created_at=time.time(),
    )


def _ensure_user(user_id: str) -> UserCredits:
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM user_credits WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    if not row:
        now = time.time()
        c.execute("""
            INSERT INTO user_credits (user_id, credits, plan, daily_used, daily_reset_date, total_used, created_at)
            VALUES (?, 0, 'free', 0, ?, 0, ?)
        """, (user_id, _today_str(), now))
        conn.commit()
        c.execute("SELECT * FROM user_credits WHERE user_id = ?", (user_id,))
        row = c.fetchone()

    conn.close()
    return UserCredits(**dict(row))


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _check_daily_reset(uc: UserCredits):
    today = _today_str()
    if uc.daily_reset_date != today:
        uc.daily_used = 0
        uc.daily_reset_date = today
        conn = _get_db()
        c = conn.cursor()
        c.execute("UPDATE user_credits SET daily_used = 0, daily_reset_date = ? WHERE user_id = ?",
                  (today, uc.user_id))
        conn.commit()
        conn.close()


def check_plan_active(uc: UserCredits) -> bool:
    if uc.plan == "free":
        return True
    if uc.plan == "lifetime":
        return True
    if uc.plan in ("monthly", "yearly"):
        return uc.plan_expires_at is not None and uc.plan_expires_at > time.time()
    return False


def get_available_credits(uc: UserCredits) -> int:
    _check_daily_reset(uc)
    plan_info = MEMBERSHIP_PLANS.get(uc.plan, MEMBERSHIP_PLANS["free"])

    if uc.plan == "free":
        daily_limit = plan_info.get("daily_credits", 10)
        return max(0, daily_limit - uc.daily_used)

    return uc.credits


def can_use_model(uc: UserCredits, model_id: str) -> Tuple[bool, str]:
    plan_info = MEMBERSHIP_PLANS.get(uc.plan, MEMBERSHIP_PLANS["free"])
    model_info = MODEL_COSTS.get(model_id, {})
    model_tier = model_info.get("tier", "standard")
    allowed_tiers = plan_info.get("model_tiers", ["free", "standard"])

    if model_tier not in allowed_tiers:
        return False, f"当前套餐不支持该模型，请升级套餐"

    return True, ""


def deduct_credits(user_id: str, model_id: str, input_tokens: int = 0,
                output_tokens: int = 0, description: str = "") -> Tuple[bool, str, int]:
    uc = _ensure_user(user_id)
    _check_daily_reset(uc)

    credit_cost = calculate_credit_cost(model_id, input_tokens, output_tokens)

    if credit_cost == 0:
        return True, "免费模型", 0

    ok, msg = can_use_model(uc, model_id)
    if not ok:
        return False, msg, 0

    available = get_available_credits(uc)
    if available < credit_cost:
        return False, f"积分不足，需要{credit_cost}积分，当前可用{available}积分", 0

    conn = _get_db()
    c = conn.cursor()
    # 使用 BEGIN IMMEDIATE 锁写，配合原子条件 UPDATE 消除 TOCTOU：
    # 仅当扣减后余额仍 >= 0（即扣减前 >= credit_cost）才真正扣减，
    # 防止并发请求都通过 available 检查后都执行扣减导致余额为负。
    try:
        c.execute("BEGIN IMMEDIATE")
    except Exception:
        pass

    if uc.plan == "free":
        # free 套餐：原子条件更新，仅当 daily_used + credit_cost <= daily_limit 时才累加。
        # 安全：防止并发请求都通过 available 检查后都执行累加导致 daily_used 超过 daily_limit。
        plan_info_free = MEMBERSHIP_PLANS.get("free", {})
        daily_limit = plan_info_free.get("daily_credits", 10)
        c.execute(
            "UPDATE user_credits SET daily_used = daily_used + ?, total_used = total_used + ? "
            "WHERE user_id = ? AND daily_used + ? <= ?",
            (credit_cost, credit_cost, user_id, credit_cost, daily_limit),
        )
        deducted = c.rowcount == 1
    else:
        # 付费套餐：原子条件扣减，仅当 credits >= credit_cost 时才扣
        c.execute(
            "UPDATE user_credits SET credits = credits - ?, total_used = total_used + ? "
            "WHERE user_id = ? AND credits >= ?",
            (credit_cost, credit_cost, user_id, credit_cost),
        )
        deducted = c.rowcount == 1

    if not deducted:
        conn.rollback()
        conn.close()
        return False, "积分不足（并发竞争）或用户不存在", 0

    tx_id = str(uuid.uuid4())
    cost_price = calculate_cost_price(model_id, input_tokens, output_tokens)
    c.execute("""
        INSERT INTO credit_transactions (id, user_id, type, amount, description, model, cost_price, created_at)
        VALUES (?, ?, 'consume', ?, ?, ?, ?, ?)
    """, (tx_id, user_id, credit_cost, description or f"使用 {model_id}", model_id, cost_price, time.time()))

    conn.commit()
    conn.close()

    return True, "ok", credit_cost


def add_credits(user_id: str, amount: int, description: str = "充值",
                tx_type: str = "recharge") -> bool:
    uc = _ensure_user(user_id)
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute("BEGIN IMMEDIATE")
    except Exception:
        pass
    try:
        c.execute("UPDATE user_credits SET credits = credits + ? WHERE user_id = ?",
                  (amount, user_id))

        tx_id = str(uuid.uuid4())
        c.execute("""
            INSERT INTO credit_transactions (id, user_id, type, amount, description, model, cost_price, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)
        """, (tx_id, user_id, tx_type, amount, description, time.time()))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        from logger import logger
        logger.error(f"[credits] add_credits 失败: {e}")
        return False
    finally:
        conn.close()


def calculate_credit_cost(model_id: str, input_tokens: int = 0, output_tokens: int = 0) -> int:
    base_price = MODEL_CREDIT_PRICES.get(model_id)
    if base_price is not None:
        return base_price

    model_info = MODEL_COSTS.get(model_id)
    if not model_info:
        return 2

    input_cost = model_info["input"] * input_tokens / 1_000_000
    output_cost = model_info["output"] * output_tokens / 1_000_000
    total_cost = input_cost + output_cost

    if total_cost <= 0:
        return 0

    target_revenue = total_cost / 0.2
    credits = max(1, int(target_revenue / CREDIT_VALUE + 0.99))
    return credits


def calculate_cost_price(model_id: str, input_tokens: int = 0, output_tokens: int = 0) -> float:
    model_info = MODEL_COSTS.get(model_id)
    if not model_info:
        return 0.0

    input_cost = model_info["input"] * input_tokens / 1_000_000
    output_cost = model_info["output"] * output_tokens / 1_000_000
    return input_cost + output_cost


def get_profit_margin(model_id: str) -> Optional[float]:
    model_info = MODEL_COSTS.get(model_id)
    if not model_info:
        return None

    base_price = MODEL_CREDIT_PRICES.get(model_id)
    if base_price is None:
        return None

    if base_price == 0:
        return 1.0 if model_info["input"] == 0 and model_info["output"] == 0 else None

    avg_tokens = 4000
    cost = calculate_cost_price(model_id, avg_tokens, avg_tokens)
    revenue = base_price * CREDIT_VALUE

    if revenue <= 0:
        return None

    return (revenue - cost) / revenue


# =============================================================================
# 会员套餐功能
# =============================================================================
def subscribe_plan(user_id: str, plan_id: str) -> Tuple[bool, str]:
    plan = MEMBERSHIP_PLANS.get(plan_id)
    if not plan:
        return False, "套餐不存在"

    uc = _ensure_user(user_id)
    now = time.time()

    conn = _get_db()
    c = conn.cursor()
    batch = None

    # 安全：使用 BEGIN IMMEDIATE 写锁 + 原子条件 UPDATE 消除 TOCTOU 竞态。
    # 旧代码先用独立连接读取 lifetime_sold 再写入，两个并发请求可同时通过
    # 限量检查导致超卖。现在将检查与递增放入同一事务，用原子条件 UPDATE 保证不超限。
    try:
        try:
            c.execute("BEGIN IMMEDIATE")
        except Exception:
            pass

        if plan_id == "lifetime":
            limit = plan.get("total_limit", 500)
            # 原子递增：仅当当前售出数 < limit 时才递增，rowcount=0 表示已售罄
            c.execute(
                "UPDATE pricing_config SET value = CAST(value AS INTEGER) + 1 "
                "WHERE key = 'lifetime_sold' AND CAST(value AS INTEGER) < ?",
                (limit,),
            )
            if c.rowcount != 1:
                conn.rollback()
                return False, "终身版已售罄"
            # 读取递增后的售出数（用于 batch 记录）
            sold_row = c.execute("SELECT CAST(value AS INTEGER) as v FROM pricing_config WHERE key = 'lifetime_sold'").fetchone()
            sold = sold_row["v"] if sold_row else 0
            batch = get_current_lifetime_batch()

        if plan_id == "free":
            expires_at = None
        elif plan_id == "monthly":
            expires_at = now + 30 * 24 * 3600
        elif plan_id == "yearly":
            expires_at = now + 365 * 24 * 3600
        elif plan_id == "lifetime":
            expires_at = now + 100 * 365 * 24 * 3600

        c.execute("UPDATE user_credits SET plan = ?, plan_expires_at = ? WHERE user_id = ?",
                  (plan_id, expires_at, user_id))

        credits = plan.get("price_credits", 0)
        if credits > 0:
            c.execute("UPDATE user_credits SET credits = credits + ? WHERE user_id = ?",
                      (credits, user_id))

        tx_id = str(uuid.uuid4())
        c.execute("""
            INSERT INTO credit_transactions (id, user_id, type, amount, description, model, cost_price, created_at)
            VALUES (?, ?, 'subscription', ?, ?, NULL, NULL, ?)
        """, (tx_id, user_id, credits, f"开通{plan['name']}", now))

        if plan_id == "lifetime":
            sale_id = str(uuid.uuid4())
            c.execute("""
                INSERT INTO lifetime_sales (id, user_id, price, purchase_time, batch_number)
                VALUES (?, ?, ?, ?, ?)
            """, (sale_id, user_id, plan["price"], now, batch))
            # lifetime_sold 已在上方原子递增，无需再次 UPDATE

        conn.commit()
        return True, f"成功开通{plan['name']}"
    except Exception as e:
        # 异常路径必须回滚事务，否则 BEGIN IMMEDIATE 写锁不释放，冻结数据库
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        # 无论成功/失败都关闭连接，防止资源泄漏
        conn.close()


def get_lifetime_sold_count() -> int:
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM pricing_config WHERE key = 'lifetime_sold'")
    row = c.fetchone()
    conn.close()
    return int(row["value"]) if row else 0


def get_current_lifetime_batch() -> int:
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM pricing_config WHERE key = 'lifetime_batch'")
    row = c.fetchone()
    conn.close()
    return int(row["value"]) if row else 1


def get_lifetime_current_price() -> float:
    base_price = MEMBERSHIP_PLANS["lifetime"]["price"]
    batch = get_current_lifetime_batch()
    increase_rate = MEMBERSHIP_PLANS["lifetime"].get("price_increase_rate", 0.1)
    return base_price * (1 + increase_rate * (batch - 1))


def get_lifetime_remaining() -> int:
    sold = get_lifetime_sold_count()
    limit = MEMBERSHIP_PLANS["lifetime"].get("total_limit", 500)
    return max(0, limit - sold)


def check_lifetime_price_increase():
    sold = get_lifetime_sold_count()
    batch = get_current_lifetime_batch()
    per_batch = 100

    new_batch = (sold // per_batch) + 1
    if new_batch > batch:
        conn = _get_db()
        c = conn.cursor()
        c.execute("UPDATE pricing_config SET value = ? WHERE key = 'lifetime_batch'", (str(new_batch),))
        conn.commit()
        conn.close()
        return True, new_batch
    return False, batch


# =============================================================================
# 交易记录
# =============================================================================
def get_transactions(user_id: str, limit: int = 50, offset: int = 0) -> List[CreditTransaction]:
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM credit_transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (user_id, limit, offset))
    rows = c.fetchall()
    conn.close()
    return [CreditTransaction(**dict(row)) for row in rows]


def get_usage_stats(user_id: str, days: int = 30) -> Dict:
    conn = _get_db()
    c = conn.cursor()
    since = time.time() - days * 24 * 3600

    c.execute("""
        SELECT
            COUNT(*) as total_calls,
            COALESCE(SUM(CASE WHEN type='consume' THEN amount ELSE 0 END), 0) as credits_used,
            COALESCE(SUM(CASE WHEN type='consume' THEN cost_price ELSE 0 END), 0) as total_cost,
            model
        FROM credit_transactions
        WHERE user_id = ? AND created_at > ? AND type = 'consume'
        GROUP BY model
        ORDER BY credits_used DESC
    """, (user_id, since))
    rows = c.fetchall()
    conn.close()

    total_credits = sum(row["credits_used"] for row in rows)
    total_cost = sum(row["total_cost"] or 0 for row in rows)

    return {
        "days": days,
        "total_calls": sum(row["total_calls"] for row in rows),
        "total_credits_used": total_credits,
        "total_cost": total_cost,
        "total_revenue": total_credits * CREDIT_VALUE,
        "total_profit": total_credits * CREDIT_VALUE - total_cost,
        "profit_margin": (total_credits * CREDIT_VALUE - total_cost) / (total_credits * CREDIT_VALUE) if total_credits > 0 else 0,
        "by_model": [dict(row) for row in rows],
    }


# =============================================================================
# 管理员功能
# =============================================================================
def get_all_plans() -> Dict:
    check_lifetime_price_increase()
    plans = {}
    for pid, p in MEMBERSHIP_PLANS.items():
        plans[pid] = dict(p)
        if pid == "lifetime":
            plans[pid]["current_price"] = get_lifetime_current_price()
            plans[pid]["sold_count"] = get_lifetime_sold_count()
            plans[pid]["remaining"] = get_lifetime_remaining()
            plans[pid]["batch"] = get_current_lifetime_batch()
    return plans


def get_credit_packages() -> List[Dict]:
    return [dict(p) for p in CREDIT_PACKAGES]


def admin_get_stats() -> Dict:
    conn = _get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as total_users FROM user_credits")
    total_users = c.fetchone()["total_users"]

    c.execute("SELECT COALESCE(SUM(credits), 0) as total_credits FROM user_credits")
    total_credits = c.fetchone()["total_credits"]

    c.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN type='consume' THEN amount ELSE 0 END), 0) as consumed,
            COALESCE(SUM(CASE WHEN type='recharge' THEN amount ELSE 0 END), 0) as recharged,
            COALESCE(SUM(CASE WHEN type='consume' THEN cost_price ELSE 0 END), 0) as total_cost
        FROM credit_transactions
    """)
    row = c.fetchone()

    c.execute("SELECT plan, COUNT(*) as count FROM user_credits GROUP BY plan")
    plan_distribution = {r["plan"]: r["count"] for r in c.fetchall()}

    conn.close()

    return {
        "total_users": total_users,
        "total_credits_in_circulation": total_credits,
        "total_credits_consumed": row["consumed"],
        "total_credits_recharged": row["recharged"],
        "total_cost": row["total_cost"] or 0,
        "total_revenue": row["consumed"] * CREDIT_VALUE,
        "total_profit": row["consumed"] * CREDIT_VALUE - (row["total_cost"] or 0),
        "profit_margin": (row["consumed"] * CREDIT_VALUE - (row["total_cost"] or 0)) / (row["consumed"] * CREDIT_VALUE) if row["consumed"] > 0 else 0,
        "plan_distribution": plan_distribution,
    }


init_db()
