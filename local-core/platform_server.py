"""
Y·NEX - 在线服务平台 v2.0
完整的 SaaS 平台：
  - 用户注册/登录/管理
  - AI对话（本地LLM + API混合）
  - 在线充值（支付宝沙箱/微信）
  - 订阅套餐管理
  - 分销佣金系统
  - API Key 管理
  - 插件市场
  - 管理后台
  - 流式对话界面

启动方式：
  python platform_server.py    # 默认端口 7789
"""

import os
import sys
import json
import time
import functools
import threading
import html
from datetime import datetime
from pathlib import Path

# 加载 .env 配置（必须在其他导入之前，确保环境变量可用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (Flask, request, jsonify, g, render_template_string,
                   redirect, url_for, session, Response, stream_with_context)

app = Flask(__name__)
# 安全要求：必须在 .env 中设置 FLASK_SECRET_KEY，否则启动时给出警告并使用临时密钥
_secret_key = os.environ.get("FLASK_SECRET_KEY") or ""
if not _secret_key:
    import warnings as _warnings
    _warnings.warn(
        "FLASK_SECRET_KEY 未设置，正在使用临时随机密钥。"
        "重启后所有用户 session 将失效。请在 .env 中设置固定值（不少于 32 字节）。",
        RuntimeWarning,
        stacklevel=2,
    )
    _secret_key = os.urandom(32).hex()
app.secret_key = _secret_key
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "16")) * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# HTTPS 环境下启用 Secure cookie（生产部署在反向代理后应取消注释或设置 ENV）
if os.environ.get("FLASK_COOKIE_SECURE") == "1":
    app.config["SESSION_COOKIE_SECURE"] = True


# 安全响应头：CSP / X-Frame-Options / HSTS / X-Content-Type-Options 等
@app.after_request
def _set_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # CSP：允许内联脚本/样式（render_template_string 需要）、同源资源
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    # HSTS：仅 HTTPS 请求时设置（避免 HTTP 环境误锁）
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

# 简单的登录限流（IP 维度，防止暴力破解）
_login_attempts: dict = {}
_LOGIN_WINDOW = 60  # 60 秒窗口
_LOGIN_MAX_ATTEMPTS = 10  # 每窗口最多 10 次尝试


def _check_login_rate(ip: str) -> bool:
    """检查登录速率，返回 True 表示允许"""
    import time as _time
    now = _time.time()
    attempts = _login_attempts.get(ip, [])
    # 清理过期记录
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        _login_attempts[ip] = attempts
        return False
    attempts.append(now)
    _login_attempts[ip] = attempts
    return True

from billing import (
    init_db, register_user, login_user, verify_api_key,
    get_user_info, recharge_balance, subscribe_tier,
    get_user_usage, check_quota, calculate_charge, record_usage,
    regenerate_api_key, list_users, admin_update_user,
    create_agent_account, get_referral_link, get_agent_stats,
    TIERS, _get_db
)

from payment_system import (
    process_payment, confirm_payment, mock_payment_callback,
    list_user_orders, get_order, get_agent_settings, update_agent_settings,
    get_agent_commissions, get_agent_commission_summary, settle_commission,
    init_payment_db, PaymentMethod, PaymentStatus
)
# 注意：payment_orders 表位于 payments.db（payment_system 管理），
# 不能用 billing 的 _get_db()（连接 users.db）查询，否则抛 OperationalError。
from payment_system import _get_db as _get_payment_db

from logger import logger


# =============================================================================
# 安全辅助：获取客户端真实 IP（防 XFF 欺骗）
# =============================================================================
def _get_client_ip() -> str:
    """获取客户端 IP。
    仅在显式配置 TRUSTED_PROXY=1 时才信任 X-Forwarded-For，
    否则使用 request.remote_addr 防止 XFF 欺骗。"""
    if os.environ.get("TRUSTED_PROXY") == "1":
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


# =============================================================================
# 装饰器
# =============================================================================

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if request.path.startswith("/api/"):
                return jsonify({"error": "请先登录"}), 401
            return redirect("/login")
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect("/login")
        user = get_user_info(user_id)
        if not user or user.get("role") != "admin":
            return jsonify({"error": "需要管理员权限"}), 403
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # 仅允许从 Header 读取 API Key，禁止 URL/表单传参以避免日志泄露
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not api_key:
            api_key = request.headers.get("X-API-Key", "")

        valid, user, err = verify_api_key(api_key)
        if not valid:
            return jsonify({"error": err}), 401
        g.user = user
        g.api_key = api_key
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# 页面 - 登录注册
# =============================================================================

LOGIN_PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Y·NEX - 登录</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#0a0a1a,#1a1a3a);color:#e0e0ff;min-height:100vh;display:flex;align-items:center;justify-content:center}
.bg-particles{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0}
.particle{position:absolute;width:4px;height:4px;background:#00ffff;border-radius:50%;opacity:.3;animation:float 15s infinite}
@keyframes float{0%,100%{transform:translateY(0) translateX(0);opacity:.3}50%{transform:translateY(-100px) translateX(50px);opacity:.6}}
.box{position:relative;z-index:1;background:rgba(0,30,50,.6);border:1px solid rgba(0,255,255,.2);border-radius:20px;padding:48px 40px;width:420px;backdrop-filter:blur(20px);box-shadow:0 20px 60px rgba(0,255,255,.1)}
.logo{text-align:center;margin-bottom:32px}
.logo-icon{width:64px;height:64px;margin:0 auto 16px;background:linear-gradient(135deg,#00ffff,#0088ff);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:28px;box-shadow:0 0 30px rgba(0,255,255,.4)}
.logo h1{font-size:28px;letter-spacing:12px;background:linear-gradient(90deg,#00ffff,#00aaff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-left:12px}
.logo p{color:#6688aa;font-size:13px;margin-top:6px;letter-spacing:4px}
h2{text-align:center;margin-bottom:28px;font-size:20px;font-weight:400;letter-spacing:4px;color:#88ccff}
.form-group{margin-bottom:18px}
label{display:block;font-size:13px;color:#88aacc;margin-bottom:8px;letter-spacing:1px}
input{width:100%;padding:14px 16px;background:rgba(0,40,70,.5);border:1px solid rgba(0,255,255,.2);border-radius:10px;color:#e0f0ff;font-size:15px;transition:all .3s}
input:focus{outline:none;border-color:#00ffff;box-shadow:0 0 0 3px rgba(0,255,255,.1);background:rgba(0,50,90,.6)}
button{width:100%;padding:14px;margin-top:12px;background:linear-gradient(135deg,#006688,#00aacc,#00ffff);border:none;border-radius:10px;color:#fff;font-size:16px;cursor:pointer;letter-spacing:6px;font-weight:300;transition:all .3s}
button:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,255,255,.3)}
.links{display:flex;justify-content:space-between;margin-top:20px;font-size:13px}
.links a{color:#00aacc;text-decoration:none;transition:color .2s}
.links a:hover{color:#00ffff}
.msg{padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:14px;text-align:center}
.msg.error{background:rgba(255,68,68,.1);border:1px solid rgba(255,68,68,.3);color:#ff8888}
.msg.success{background:rgba(0,255,136,.1);border:1px solid rgba(0,255,136,.3);color:#66ffaa}
.features{margin-top:32px;padding-top:24px;border-top:1px solid rgba(0,255,255,.1);display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center}
.feature{font-size:11px;color:#6688aa}
.feature .icon{font-size:20px;margin-bottom:4px}
</style></head><body>
<div class="bg-particles">
<div class="particle" style="top:10%;left:10%;animation-delay:0s"></div>
<div class="particle" style="top:20%;left:80%;animation-delay:2s"></div>
<div class="particle" style="top:60%;left:30%;animation-delay:4s"></div>
<div class="particle" style="top:80%;left:70%;animation-delay:6s"></div>
<div class="particle" style="top:40%;left:90%;animation-delay:8s"></div>
</div>
<div class="box"><div class="logo">
<div class="logo-icon">🌌</div>
<h1>Y·NEX</h1>
<p>亿界互联 · 无界未来</p>
</div>
<h2>登 录</h2>
{% if msg %}<div class="msg {% if ok %}success{% else %}error{% endif %}">{{ msg }}</div>{% endif %}
<form method="post">
<div class="form-group">
<label>用户名</label>
<input name="username" placeholder="请输入用户名" required>
</div>
<div class="form-group">
<label>密码</label>
<input name="password" type="password" placeholder="请输入密码" required>
</div>
<button type="submit">登 录</button>
</form>
<div class="links">
<a href="/register">注册账户</a>
<a href="#" onclick="alert('请联系管理员重置密码');return false;">忘记密码</a>
</div>
<div class="features">
<div class="feature"><div class="icon">🧠</div>AI对话</div>
<div class="feature"><div class="icon">⚡</div>本地推理</div>
<div class="feature"><div class="icon">🔌</div>插件扩展</div>
</div>
</div></body></html>
"""

REGISTER_PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Y·NEX - 注册</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#0a0a1a,#1a1a3a);color:#e0e0ff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.box{background:rgba(0,30,50,.6);border:1px solid rgba(0,255,255,.2);border-radius:20px;padding:40px;width:420px;backdrop-filter:blur(20px);box-shadow:0 20px 60px rgba(0,255,255,.1)}
.logo{text-align:center;margin-bottom:24px}
.logo h1{font-size:24px;letter-spacing:12px;background:linear-gradient(90deg,#00ffff,#00aaff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.form-group{margin-bottom:14px}
label{display:block;font-size:13px;color:#88aacc;margin-bottom:6px}
input{width:100%;padding:12px 14px;background:rgba(0,40,70,.5);border:1px solid rgba(0,255,255,.2);border-radius:8px;color:#e0f0ff;font-size:14px}
input:focus{outline:none;border-color:#00ffff}
button{width:100%;padding:12px;margin-top:10px;background:linear-gradient(135deg,#006688,#00aacc);border:none;border-radius:8px;color:#fff;font-size:15px;cursor:pointer;letter-spacing:4px}
button:hover{box-shadow:0 0 20px rgba(0,255,255,.3)}
a{color:#00aacc;text-decoration:none;font-size:13px;display:block;text-align:center;margin-top:16px}
.msg{padding:10px;border-radius:8px;margin-bottom:16px;font-size:13px;text-align:center}
.msg.error{background:rgba(255,68,68,.1);border:1px solid #ff444444;color:#ff8888}
.msg.success{background:rgba(0,255,136,.1);border:1px solid #00ff8844;color:#66ffaa}
</style></head><body>
<div class="box">
<div class="logo"><h1>Y·NEX · 注册</h1></div>
{% if msg %}<div class="msg {% if ok %}success{% else %}error{% endif %}">{{ msg }}</div>{% endif %}
<form method="post">
<div class="form-group"><label>用户名</label>
<input name="username" placeholder="3-20位字符" required minlength="3" maxlength="20"></div>
<div class="form-group"><label>邮箱</label>
<input name="email" type="email" placeholder="your@email.com" required></div>
<div class="form-group"><label>密码</label>
<input name="password" type="password" placeholder="至少6位" required minlength="6"></div>
<div class="form-group"><label>推荐码（可选）</label>
<input name="referral" placeholder="推荐人ID" value="{{ referral }}"></div>
<button type="submit">注 册 账 户</button>
</form>
<a href="/login">已有账户？去登录</a>
</div></body></html>
"""


# =============================================================================
# 页面 - 仪表盘
# =============================================================================

DASHBOARD_PAGE = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Y·NEX - 控制台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Microsoft YaHei',sans-serif;background:#0a0a1a;color:#e0e0ff;min-height:100vh}
.sidebar{position:fixed;left:0;top:0;width:220px;height:100vh;background:#0d1525;border-right:1px solid #00ffff22;padding:20px 0}
.sidebar .logo{padding:0 20px 20px;border-bottom:1px solid #00ffff11;margin-bottom:10px}
.sidebar .logo h2{font-size:18px;letter-spacing:6px;color:#00ffff}
.nav-item{padding:12px 20px;cursor:pointer;color:#88aacc;font-size:14px;transition:all .2s;border-left:3px solid transparent}
.nav-item:hover,.nav-item.active{background:#00ffff0a;color:#00ffff;border-left-color:#00ffff}
.nav-item .icon{margin-right:10px}
.main{margin-left:220px;padding:24px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #00ffff11}
.header h1{font-size:22px;font-weight:400;letter-spacing:4px}
.user-info{display:flex;align-items:center;gap:12px}
.user-info .avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#00ffff,#0088ff);display:flex;align-items:center;justify-content:center;font-weight:bold}
.user-info a{color:#88aacc;text-decoration:none;font-size:13px;margin-left:8px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.stat-card{background:#0d1525;border:1px solid #00ffff11;border-radius:12px;padding:20px;position:relative;overflow:hidden}
.stat-card::before{content:'';position:absolute;top:0;left:0;width:4px;height:100%;background:linear-gradient(180deg,#00ffff,transparent)}
.stat-card .label{font-size:12px;color:#6688aa;margin-bottom:8px;letter-spacing:1px}
.stat-card .value{font-size:28px;font-weight:300;color:#00ffff}
.stat-card .sub{font-size:11px;color:#557799;margin-top:6px}
.section{background:#0d1525;border:1px solid #00ffff11;border-radius:12px;padding:24px;margin-bottom:20px}
.section h3{font-size:15px;font-weight:500;color:#88ccff;margin-bottom:16px;letter-spacing:2px;padding-bottom:10px;border-bottom:1px solid #00ffff11}
.api-key-box{background:#000;padding:14px;border-radius:8px;font-family:monospace;font-size:13px;color:#00ff88;word-break:break-all;border:1px solid #00ffff22;margin-bottom:10px}
.btn{display:inline-block;padding:8px 18px;background:linear-gradient(135deg,#004466,#0088aa);border-radius:6px;color:#fff;text-decoration:none;font-size:13px;border:none;cursor:pointer;transition:all .2s}
.btn:hover{box-shadow:0 0 15px #00ffff44;transform:translateY(-1px)}
.btn-outline{background:transparent;border:1px solid #00ffff55;color:#00aacc}
.btn-success{background:linear-gradient(135deg,#006644,#00aa77)}
.btn-danger{background:linear-gradient(135deg,#660000,#aa3333)}
.btn-sm{padding:6px 12px;font-size:12px}
.usage-bar{height:10px;background:#001a26;border-radius:5px;margin-top:10px;overflow:hidden}
.usage-bar .fill{height:100%;border-radius:5px;background:linear-gradient(90deg,#004466,#00ffff);transition:width .5s}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:12px 8px;text-align:left;border-bottom:1px solid #00ffff0a}
th{color:#00aacc;font-weight:500;font-size:12px;letter-spacing:1px}
tr:hover{background:#00ffff05}
.tab-nav{display:flex;gap:0;margin-bottom:20px;border-bottom:1px solid #00ffff11}
.tab-btn{padding:10px 20px;cursor:pointer;color:#6688aa;border-bottom:2px solid transparent;transition:all .2s;font-size:14px}
.tab-btn.active{color:#00ffff;border-bottom-color:#00ffff}
.chat-container{display:grid;grid-template-columns:1fr 300px;gap:20px;height:500px}
.chat-box{background:#0a0a12;border:1px solid #00ffff11;border-radius:12px;display:flex;flex-direction:column;overflow:hidden}
.chat-messages{flex:1;padding:20px;overflow-y:auto}
.msg-item{margin-bottom:16px;max-width:80%}
.msg-item.user{margin-left:auto;text-align:right}
.msg-item .bubble{display:inline-block;padding:12px 16px;border-radius:16px;font-size:14px;line-height:1.6}
.msg-item.assistant .bubble{background:#0d1525;border:1px solid #00ffff22;color:#d0e0ff}
.msg-item.user .bubble{background:linear-gradient(135deg,#006688,#0088aa);color:#fff}
.msg-item .time{font-size:11px;color:#557799;margin-top:4px}
.chat-input{padding:16px;border-top:1px solid #00ffff11;display:flex;gap:10px}
.chat-input textarea{flex:1;padding:12px;background:#0a0a12;border:1px solid #00ffff22;border-radius:8px;color:#e0f0ff;font-size:14px;resize:none;max-height:80px}
.chat-input textarea:focus{outline:none;border-color:#00ffff}
.chat-input button{padding:0 24px;background:linear-gradient(135deg,#006688,#00aacc);border:none;border-radius:8px;color:#fff;cursor:pointer;font-size:14px}
.side-panel{background:#0d1525;border:1px solid #00ffff11;border-radius:12px;padding:16px;overflow-y:auto}
.side-panel h4{font-size:13px;color:#88ccff;margin-bottom:12px;letter-spacing:1px}
.tool-tag{display:inline-block;padding:4px 10px;background:#00ffff10;border:1px solid #00ffff33;border-radius:12px;font-size:11px;color:#00aacc;margin:3px}
.payment-form{max-width:400px}
.amount-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.amount-card{padding:16px;border:2px solid #00ffff22;border-radius:10px;text-align:center;cursor:pointer;transition:all .2s}
.amount-card:hover,.amount-card.selected{border-color:#00ffff;background:#00ffff08}
.amount-card .num{font-size:22px;color:#00ffff;font-weight:300}
.amount-card .desc{font-size:11px;color:#6688aa;margin-top:4px}
.pay-methods{display:flex;gap:10px;margin-bottom:16px}
.pay-method{flex:1;padding:14px;border:2px solid #00ffff22;border-radius:10px;text-align:center;cursor:pointer;transition:all .2s}
.pay-method:hover,.pay-method.selected{border-color:#00ffff;background:#00ffff08}
.qr-box{text-align:center;padding:30px;background:#fff;border-radius:12px;color:#333}
.qr-placeholder{width:180px;height:180px;background:#f0f0f0;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;border-radius:8px;font-size:14px;color:#999}
.empty{text-align:center;padding:40px;color:#557799;font-size:13px}
</style></head><body>

<div class="sidebar">
<div class="logo"><h2>Y·NEX</h2></div>
<div class="nav-item active" onclick="switchTab('overview')"><span class="icon">📊</span>概览</div>
<div class="nav-item" onclick="switchTab('chat')"><span class="icon">💬</span>AI对话</div>
<div class="nav-item" onclick="switchTab('recharge')"><span class="icon">💰</span>充值中心</div>
<div class="nav-item" onclick="switchTab('subscribe')"><span class="icon">⭐</span>订阅套餐</div>
<div class="nav-item" onclick="switchTab('apikeys')"><span class="icon">🔑</span>API Key</div>
<div class="nav-item" onclick="switchTab('agent')"><span class="icon">🤝</span>分销中心</div>
<div class="nav-item" onclick="switchTab('plugins')"><span class="icon">🔌</span>插件市场</div>
<div class="nav-item" onclick="switchTab('history')"><span class="icon">📜</span>使用记录</div>
</div>

<div class="main">
<div class="header">
<h1>控制台</h1>
<div class="user-info">
<div class="avatar">{{ user.username[0].upper() }}</div>
<div>
<div style="font-size:14px">{{ user.username }}</div>
<div style="font-size:11px;color:#6688aa">{{ user.role }}</div>
</div>
<a href="/logout">退出</a>
</div>
</div>

<div id="tab-overview" class="tab-content">
<div class="stats-grid">
<div class="stat-card">
<div class="label">账户余额</div>
<div class="value">{{ "%.2f"|format(user.balance / 100) }}<span style="font-size:14px">元</span></div>
<div class="sub">可用于API调用抵扣</div>
</div>
<div class="stat-card">
<div class="label">本月用量</div>
<div class="value">{{ user.quota_used // 1000 }}K<span style="font-size:14px"> tokens</span></div>
<div class="sub">额度: {{ user.quota_limit // 1000 }}K</div>
</div>
<div class="stat-card">
<div class="label">API Key</div>
<div class="value" style="font-size:16px;margin-top:4px">{{ user.api_key_prefix or '未设置' }}...</div>
<div class="sub">点击API Key管理查看/重新生成</div>
</div>
<div class="stat-card">
<div class="label">已用天数</div>
<div class="value">{{ ((user.quota_used / (user.quota_limit or 1)) * 100)|round(1) }}<span style="font-size:14px">%</span></div>
<div class="usage-bar"><div class="fill" style="width:{{ [user.quota_used / (user.quota_limit or 1) * 100, 100]|min }}%"></div></div>
</div>
</div>

<div class="section">
<h3>🚀 快速开始</h3>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">
<div style="padding:20px;border:1px solid #00ffff11;border-radius:10px;text-align:center">
<div style="font-size:32px;margin-bottom:8px">💬</div>
<div style="font-size:14px;color:#00aacc;margin-bottom:4px">在线对话</div>
<div style="font-size:12px;color:#6688aa">直接与AI聊天，体验所有功能</div>
</div>
<div style="padding:20px;border:1px solid #00ffff11;border-radius:10px;text-align:center">
<div style="font-size:32px;margin-bottom:8px">🔌</div>
<div style="font-size:14px;color:#00aacc;margin-bottom:4px">API接入</div>
<div style="font-size:12px;color:#6688aa">用API Key集成到你自己的项目</div>
</div>
<div style="padding:20px;border:1px solid #00ffff11;border-radius:10px;text-align:center">
<div style="font-size:32px;margin-bottom:8px">📦</div>
<div style="font-size:14px;color:#00aacc;margin-bottom:4px">下载客户端</div>
<div style="font-size:12px;color:#6688aa">下载桌面版，体验3D粒子界面</div>
</div>
</div>
</div>

<div class="section">
<h3>📋 最近使用记录</h3>
<table>
<thead><tr><th>日期</th><th>调用次数</th><th>Tokens</th><th>费用</th><th>状态</th></tr></thead>
<tbody>
{% for row in usage[:10] %}
<tr>
<td>{{ row.date }}</td>
<td>{{ row.calls or 0 }}</td>
<td>{{ (row.total_tokens or 0) // 1000 }}K</td>
<td>{{ "%.2f"|format((row.total_charged or 0) / 100) }} 元</td>
<td style="color:#00ff88">成功</td>
</tr>
{% else %}
<tr><td colspan="5" class="empty">暂无使用记录</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</div>

<div id="tab-chat" class="tab-content" style="display:none">
<div class="chat-container">
<div class="chat-box">
<div class="chat-messages" id="chatMessages">
<div class="msg-item assistant">
<div class="bubble">你好！我是Y·NEX助手，有什么可以帮你的吗？<br>你可以问我天气、时间、设置提醒、搜索文件，或者让我帮你写代码。</div>
<div class="time">刚刚</div>
</div>
</div>
<div class="chat-input">
<textarea id="chatInput" placeholder="输入消息... (Ctrl+Enter发送)" rows="2"></textarea>
<button onclick="sendMessage()">发送</button>
</div>
</div>
<div class="side-panel">
<h4>可用技能</h4>
<div>
<span class="tool-tag">🌤️ 天气查询</span>
<span class="tool-tag">⏰ 时间查询</span>
<span class="tool-tag">📁 文件搜索</span>
<span class="tool-tag">🔔 提醒设置</span>
<span class="tool-tag">💻 系统信息</span>
<span class="tool-tag">📝 记事功能</span>
<span class="tool-tag">😂 讲笑话</span>
<span class="tool-tag">🤖 多智能体</span>
<span class="tool-tag">🏠 智能家居</span>
<span class="tool-tag">🌐 浏览器控制</span>
<span class="tool-tag">📧 邮件日历</span>
</div>
<h4 style="margin-top:20px">使用提示</h4>
<div style="font-size:12px;color:#6688aa;line-height:1.8">
• 直接说"北京天气怎么样"<br>
• "明天下午3点提醒我开会"<br>
• "搜索一下合同文件"<br>
• "帮我写一个Python爬虫"<br>
• "打开客厅的灯"（需配置智能家居）
</div>
</div>
</div>
</div>

<div id="tab-recharge" class="tab-content" style="display:none">
<div class="section">
<h3>💰 账户充值</h3>
<div class="payment-form">
<div style="margin-bottom:12px;font-size:13px;color:#88aacc">选择充值金额</div>
<div class="amount-grid">
<div class="amount-card selected" onclick="selectAmount(10,this)"><div class="num">¥10</div><div class="desc">体验套餐</div></div>
<div class="amount-card" onclick="selectAmount(50,this)"><div class="num">¥50</div><div class="desc">常用套餐</div></div>
<div class="amount-card" onclick="selectAmount(100,this)"><div class="num">¥100</div><div class="desc">推荐</div></div>
<div class="amount-card" onclick="selectAmount(500,this)"><div class="num">¥500</div><div class="desc">超值套餐</div></div>
</div>
<div style="margin-bottom:12px;font-size:13px;color:#88aacc">或自定义金额</div>
<div style="margin-bottom:16px"><input type="number" id="customAmount" placeholder="自定义金额" style="width:100%;padding:12px;background:#0a0a12;border:1px solid #00ffff22;border-radius:8px;color:#e0f0ff" oninput="clearAmountSelection()"></div>

<div style="margin-bottom:12px;font-size:13px;color:#88aacc">选择支付方式</div>
<div class="pay-methods">
<div class="pay-method selected" onclick="selectMethod('alipay',this)"><div style="font-size:24px">🅰️</div><div style="font-size:12px;margin-top:4px">支付宝</div></div>
<div class="pay-method" onclick="selectMethod('wechat',this)"><div style="font-size:24px">💚</div><div style="font-size:12px;margin-top:4px">微信支付</div></div>
</div>

<button class="btn" style="width:100%;padding:14px;font-size:15px" onclick="doRecharge()">立即充值</button>
<div style="margin-top:12px;font-size:11px;color:#557799;text-align:center">* 当前为沙箱环境，支付为模拟测试</div>
</div>
</div>

<div class="section">
<h3>📋 充值记录</h3>
<table>
<thead><tr><th>订单号</th><th>金额</th><th>方式</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
<tbody>
{% for order in orders %}
<tr>
<td style="font-family:monospace;font-size:12px">{{ order.id }}</td>
<td>{{ "%.2f"|format(order.amount) }} 元</td>
<td>{{ order.method }}</td>
<td style="color:{{ '#00ff88' if order.status=='success' else '#ffaa00' if order.status=='pending' else '#ff6666' }}">
{{ '成功' if order.status=='success' else '待支付' if order.status=='pending' else '失败' }}
</td>
<td>{{ datetime.fromtimestamp(order.created_at).strftime('%m-%d %H:%M') }}</td>
<td>
{% if order.status == 'pending' %}
<button class="btn btn-sm" onclick="mockPay('{{ order.id }}')">模拟支付</button>
{% endif %}
</td>
</tr>
{% else %}
<tr><td colspan="6" class="empty">暂无充值记录</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</div>

<div id="tab-subscribe" class="tab-content" style="display:none">
<div class="section">
<h3>⭐ 订阅套餐</h3>
<p style="color:#6688aa;font-size:13px;margin-bottom:20px">当前套餐：<strong>{{ user.role }}</strong> | 月额度：{{ user.quota_limit // 1000 }}K tokens</p>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px">
{% for key, tier in tiers.items() %}
<div style="border:2px solid {{ '#00ffff' if user.role==key else '#00ffff22' }};border-radius:14px;padding:28px;background:{{ '#00ffff08' if user.role==key else 'transparent' }};position:relative">
{% if user.role==key %}<div style="position:absolute;top:12px;right:12px;background:#00ffff;color:#000;padding:4px 10px;border-radius:12px;font-size:11px">当前</div>{% endif %}
<h4 style="font-size:20px;margin-bottom:8px;color:#00ffff">{{ tier.name }}</h4>
<div style="font-size:32px;font-weight:300;margin-bottom:20px">¥{{ tier.monthly }}<span style="font-size:14px;color:#6688aa">/月</span></div>
<div style="font-size:13px;color:#88aacc;line-height:2">
✓ {{ tier.quota // 1000 }}K tokens/月<br>
✓ {{ '无限量使用' if key=='unlimited' else '标准响应速度' }}<br>
✓ 全部技能可用<br>
✓ API 访问权限<br>
{% if key in ['pro','unlimited'] %}✓ 优先客服支持<br>{% endif %}
{% if key == 'unlimited' %}✓ 专属模型定制<br>{% endif %}
</div>
<button class="btn" style="width:100%;margin-top:20px" onclick="subscribe('{{ key }}')" {% if user.role==key %}disabled{% endif %}>
{{ '当前套餐' if user.role==key else '立即订阅' }}
</button>
</div>
{% endfor %}
</div>
</div>
</div>

<div id="tab-apikeys" class="tab-content" style="display:none">
<div class="section">
<h3>🔑 API Key 管理</h3>
<div style="margin-bottom:16px;font-size:13px;color:#88aacc">你的主API Key（仅重新生成后显示一次）</div>
<div class="api-key-box" id="mainApiKey">{{ user.api_key_prefix or '未设置' }}... <span style="color:#6688aa">（出于安全，完整 Key 不在页面展示）</span></div>
<div style="display:flex;gap:10px;margin-bottom:24px">
<button class="btn btn-sm btn-outline" onclick="regenerateApiKey()">重新生成 Key</button>
</div>

<h3 style="margin-top:24px">管理多个Key</h3>
<button class="btn btn-sm" style="margin-bottom:16px">+ 创建新Key</button>
<table>
<thead><tr><th>Key</th><th>名称</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
<tbody>
<tr><td colspan="5" class="empty">暂无更多Key，使用主Key即可</td></tr>
</tbody>
</table>

<div style="margin-top:24px;padding:16px;background:#00ffff08;border-radius:8px;border:1px solid #00ffff22">
<h4 style="color:#00aacc;margin-bottom:10px">📘 API 使用说明</h4>
<div style="font-size:12px;color:#88aacc;line-height:1.8;font-family:monospace;background:#000;padding:12px;border-radius:6px;overflow-x:auto">
curl -X POST {{ request.host_url }}api/chat<br>
&nbsp;&nbsp;-H "Authorization: Bearer &lt;你的 API Key&gt;"<br>
&nbsp;&nbsp;-H "Content-Type: application/json"<br>
&nbsp;&nbsp;-d '{"message":"你好"}'
</div>
</div>
</div>
</div>

<div id="tab-agent" class="tab-content" style="display:none">
<div class="section">
<h3>🤝 分销中心</h3>
{% if user.role == 'agent' or user.role == 'admin' %}
<div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
<div class="stat-card">
<div class="label">累计推荐</div>
<div class="value">{{ stats.total_referrals or 0 }}<span style="font-size:14px">人</span></div>
</div>
<div class="stat-card">
<div class="label">待结算佣金</div>
<div class="value">{{ "%.2f"|format(commission_summary.total_pending or 0) }}<span style="font-size:14px">元</span></div>
</div>
<div class="stat-card">
<div class="label">已结算佣金</div>
<div class="value">{{ "%.2f"|format(commission_summary.total_settled or 0) }}<span style="font-size:14px">元</span></div>
</div>
</div>

<div style="margin:24px 0">
<div style="font-size:13px;color:#88aacc;margin-bottom:8px">你的推荐链接</div>
<div class="api-key-box" id="referralLink">{{ referral_link }}</div>
<button class="btn btn-sm" onclick="copyText('referralLink')">复制链接</button>
</div>

<h4 style="font-size:14px;color:#88ccff;margin-bottom:12px">佣金记录</h4>
<table>
<thead><tr><th>订单号</th><th>用户</th><th>金额</th><th>佣金</th><th>比例</th><th>状态</th></tr></thead>
<tbody>
{% for c in commissions[:10] %}
<tr>
<td style="font-size:12px;font-family:monospace">{{ c.order_id }}</td>
<td>{{ c.user_id[:8] }}...</td>
<td>{{ "%.2f"|format(c.amount / (c.rate or 0.2)) }} 元</td>
<td style="color:#00ff88">{{ "%.2f"|format(c.amount) }} 元</td>
<td>{{ (c.rate * 100)|round(0) }}%</td>
<td>{{ '已结算' if c.status=='settled' else '待结算' }}</td>
</tr>
{% else %}
<tr><td colspan="6" class="empty">暂无佣金记录，分享推荐链接开始赚钱吧！</td></tr>
{% endfor %}
</tbody>
</table>
{% else %}
<div style="text-align:center;padding:40px">
<div style="font-size:48px;margin-bottom:16px">🎁</div>
<h3 style="color:#00aacc;margin-bottom:12px">成为分销商，轻松赚钱</h3>
<p style="color:#6688aa;margin-bottom:24px;line-height:1.8">
分享你的专属推荐链接，好友注册充值后你可获得最高20%佣金<br>
无需成本，轻松躺赚，多推多得
</p>
<button class="btn btn-success" onclick="becomeAgent()" style="padding:14px 40px;font-size:16px">立即成为分销商</button>
</div>
{% endif %}
</div>
</div>

<div id="tab-plugins" class="tab-content" style="display:none">
<div class="section">
<h3>🔌 插件市场</h3>
<p style="color:#6688aa;font-size:13px;margin-bottom:20px">安装插件，扩展Y·NEX的能力边界</p>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">
<div style="border:1px solid #00ffff22;border-radius:12px;padding:20px;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor='#00ffff'" onmouseout="this.style.borderColor='#00ffff22'">
<div style="font-size:32px;margin-bottom:10px">📊</div>
<h4 style="color:#00aacc;margin-bottom:6px">数据分析助手</h4>
<p style="font-size:12px;color:#6688aa;margin-bottom:12px;line-height:1.6">自动分析Excel/CSV数据，生成报表和图表</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="font-size:11px;color:#557799">官方 · v1.0</span>
<button class="btn btn-sm">安装</button>
</div>
</div>
<div style="border:1px solid #00ffff22;border-radius:12px;padding:20px;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor='#00ffff'" onmouseout="this.style.borderColor='#00ffff22'">
<div style="font-size:32px;margin-bottom:10px">🎨</div>
<h4 style="color:#00aacc;margin-bottom:6px">AI绘图</h4>
<p style="font-size:12px;color:#6688aa;margin-bottom:12px;line-height:1.6">文字描述生成图片，支持多种风格</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="font-size:11px;color:#557799">官方 · v1.0</span>
<button class="btn btn-sm">安装</button>
</div>
</div>
<div style="border:1px solid #00ffff22;border-radius:12px;padding:20px;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor='#00ffff'" onmouseout="this.style.borderColor='#00ffff22'">
<div style="font-size:32px;margin-bottom:10px">📧</div>
<h4 style="color:#00aacc;margin-bottom:6px">邮件助手</h4>
<p style="font-size:12px;color:#6688aa;margin-bottom:12px;line-height:1.6">智能撰写、分类、回复邮件</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="font-size:11px;color:#557799">官方 · v1.0</span>
<button class="btn btn-sm">安装</button>
</div>
</div>
<div style="border:1px solid #00ffff22;border-radius:12px;padding:20px;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor='#00ffff'" onmouseout="this.style.borderColor='#00ffff22'">
<div style="font-size:32px;margin-bottom:10px">💻</div>
<h4 style="color:#00aacc;margin-bottom:6px">代码审查</h4>
<p style="font-size:12px;color:#6688aa;margin-bottom:12px;line-height:1.6">自动审查代码，发现Bug和优化建议</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="font-size:11px;color:#557799">社区 · v0.8</span>
<button class="btn btn-sm">安装</button>
</div>
</div>
<div style="border:1px solid #00ffff22;border-radius:12px;padding:20px;transition:all .2s;cursor:pointer" onmouseover="this.style.borderColor='#00ffff'" onmouseout="this.style.borderColor='#00ffff22'">
<div style="font-size:32px;margin-bottom:10px">📚</div>
<h4 style="color:#00aacc;margin-bottom:6px">知识库</h4>
<p style="font-size:12px;color:#6688aa;margin-bottom:12px;line-height:1.6">上传文档，构建个人知识库问答</p>
<div style="display:flex;justify-content:space-between;align-items:center">
<span style="font-size:11px;color:#557799">官方 · v1.2</span>
<button class="btn btn-sm">安装</button>
</div>
</div>
<div style="border:1px dashed #00ffff44;border-radius:12px;padding:20px;text-align:center;display:flex;flex-direction:column;justify-content:center;min-height:160px;cursor:pointer" onclick="alert('开发者文档即将上线')">
<div style="font-size:32px;margin-bottom:10px">➕</div>
<h4 style="color:#6688aa;margin-bottom:6px">开发你的插件</h4>
<p style="font-size:12px;color:#557799">查看开发者文档</p>
</div>
</div>
</div>
</div>

<div id="tab-history" class="tab-content" style="display:none">
<div class="section">
<h3>📜 使用记录</h3>
<table>
<thead><tr><th>日期</th><th>调用次数</th><th>输入Tokens</th><th>输出Tokens</th><th>费用</th></tr></thead>
<tbody>
{% for row in usage[:30] %}
<tr>
<td>{{ row.date }}</td>
<td>{{ row.calls or 0 }}</td>
<td>{{ (row.total_tokens or 0) // 1000 }}K</td>
<td>{{ (row.total_tokens or 0) // 1000 }}K</td>
<td>{{ "%.2f"|format((row.total_charged or 0) / 100) }} 元</td>
</tr>
{% else %}
<tr><td colspan="5" class="empty">暂无使用记录</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</div>

</div>
</div>

<script>
let currentTab = 'overview';
let selectedAmount = 10;
let selectedMethod = 'alipay';

function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('tab-' + tab).style.display = 'block';
    event.target.closest('.nav-item').classList.add('active');
    currentTab = tab;
}

function selectAmount(amount, el) {
    selectedAmount = amount;
    document.getElementById('customAmount').value = '';
    document.querySelectorAll('.amount-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
}

function clearAmountSelection() {
    document.querySelectorAll('.amount-card').forEach(c => c.classList.remove('selected'));
}

function selectMethod(method, el) {
    selectedMethod = method;
    document.querySelectorAll('.pay-method').forEach(m => m.classList.remove('selected'));
    el.classList.add('selected');
}

function doRecharge() {
    const custom = parseFloat(document.getElementById('customAmount').value);
    const amount = custom > 0 ? custom : selectedAmount;
    if (!amount || amount <= 0) { alert('请输入有效金额'); return; }

    fetch('/recharge/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({amount, method: selectedMethod})
    }).then(r => r.json()).then(d => {
        if (d.success) {
            alert('订单创建成功！\\n订单号：' + d.order_id + '\\n金额：' + d.amount + '元\\n\\n沙箱环境：点击订单列表中的"模拟支付"按钮完成支付');
            location.reload();
        } else {
            alert('充值失败：' + d.error);
        }
    });
}

function mockPay(orderId) {
    if (!confirm('确认模拟支付成功？（沙箱测试用）')) return;
    fetch('/recharge/mock/' + orderId, {method: 'POST'})
    .then(r => r.json()).then(d => {
        if (d.success) { alert('支付成功！'); location.reload(); }
        else { alert('失败：' + d.error); }
    });
}

function subscribe(tier) {
    if (!confirm('确认订阅 ' + tier + ' 套餐？费用从余额扣除。')) return;
    fetch('/subscribe/' + tier, {method: 'POST'})
    .then(r => r.json()).then(d => {
        alert(d.message || d.error);
        if (d.success) location.reload();
    });
}

function becomeAgent() {
    if (!confirm('确认成为分销商？免费加入，推广赚钱！')) return;
    fetch('/agent/become', {method: 'POST'})
    .then(r => r.json()).then(d => {
        alert(d.message || d.error);
        if (d.success) location.reload();
    });
}

function copyApiKey() { copyText('mainApiKey'); }

function copyText(id) {
    const text = document.getElementById(id).textContent;
    navigator.clipboard.writeText(text).then(() => alert('已复制到剪贴板'));
}

function regenerateApiKey() {
    if (!confirm('重新生成 API Key 后，旧 Key 将立即失效。是否继续？')) return;
    fetch('/api/regenerate-key', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
        .then(r => r.json())
        .then(d => {
            if (d.api_key) {
                document.getElementById('mainApiKey').textContent = d.api_key;
                navigator.clipboard.writeText(d.api_key).then(() => alert('新的 API Key 已生成并复制到剪贴板，请妥善保存（仅此一次显示）'));
            } else {
                alert(d.error || '生成失败');
            }
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sendMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    const messagesDiv = document.getElementById('chatMessages');
    messagesDiv.innerHTML += `<div class="msg-item user"><div class="bubble">${escapeHtml(msg)}</div><div class="time">刚刚</div></div>`;
    input.value = '';
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    const respDiv = document.createElement('div');
    respDiv.className = 'msg-item assistant';
    respDiv.innerHTML = `<div class="bubble" id="respContent">思考中...</div><div class="time">刚刚</div>`;
    messagesDiv.appendChild(respDiv);

    fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg})
    }).then(r => {
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let content = '';
        document.getElementById('respContent').textContent = '';
        function read() {
            reader.read().then(({done, value}) => {
                if (done) return;
                const text = decoder.decode(value);
                const lines = text.split('\\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') return;
                        try {
                            const obj = JSON.parse(data);
                            if (obj.content) {
                                content += obj.content;
                                document.getElementById('respContent').textContent = content;
                                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                            }
                        } catch(e) {}
                    }
                }
                read();
            });
        }
        read();
    }).catch(err => {
        document.getElementById('respContent').textContent = '错误：' + err.message;
    });
}

document.getElementById('chatInput').addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'Enter') { sendMessage(); }
});
</script>
</body></html>
"""


# =============================================================================
# 路由 - 页面
# =============================================================================

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    ok = False
    if request.method == "POST":
        # 登录限流检查（安全：使用 _get_client_ip 防 XFF 欺骗）
        client_ip = _get_client_ip()
        if not _check_login_rate(client_ip):
            return render_template_string(LOGIN_PAGE, msg="登录尝试过于频繁，请稍后再试", ok=False)
        ok, msg, user = login_user(request.form["username"], request.form["password"])
        if ok:
            # 防 session fixation：登录成功后先清除旧 session 再设置新标识
            session.clear()
            session["user_id"] = user["id"]
            return redirect("/dashboard")
    return render_template_string(LOGIN_PAGE, msg=msg, ok=ok)


@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    ok = False
    referral = request.args.get("ref", "")
    if request.method == "POST":
        ok, msg = register_user(
            request.form["username"],
            request.form["password"],
            request.form["email"],
            request.form.get("referral") or None
        )
        if ok:
            return redirect("/login?registered=1")
    return render_template_string(REGISTER_PAGE, msg=msg, ok=ok, referral=referral)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/dashboard")
@require_auth
def dashboard():
    user = get_user_info(g.user_id)
    usage = get_user_usage(g.user_id)
    stats = get_agent_stats(g.user_id) if user.get("role") in ["agent", "admin"] else {}
    referral_link = get_referral_link(g.user_id) if user.get("role") in ["agent", "admin"] else ""
    orders = list_user_orders(g.user_id, 20)

    commission_summary = {}
    commissions = []
    if user.get("role") in ["agent", "admin"]:
        commission_summary = get_agent_commission_summary(g.user_id)
        commissions = get_agent_commissions(g.user_id)

    return render_template_string(
        DASHBOARD_PAGE,
        user=user,
        usage=usage,
        stats=stats,
        referral_link=referral_link,
        orders=orders,
        tiers=TIERS,
        commission_summary=commission_summary,
        commissions=commissions,
        datetime=datetime,
    )


# =============================================================================
# 路由 - 充值支付
# =============================================================================

@app.route("/recharge/create", methods=["POST"])
@require_auth
def recharge_create():
    data = request.json or {}
    amount = float(data.get("amount", 0))
    method = data.get("method", "alipay")

    result = process_payment(
        g.user_id, amount, method,
        product_type="recharge",
        return_url=request.host_url + "dashboard",
        notify_url=request.host_url + "api/payment/callback"
    )
    return jsonify(result)


@app.route("/recharge/mock/<order_id>", methods=["POST"])
@require_admin
def recharge_mock(order_id):
    # 安全：模拟支付仅限管理员调用，且仅在开发/测试环境可用。
    # 普通用户调用此接口可绕过支付直接发货，造成资金损失。
    if os.environ.get("FLASK_ENV") == "production" and os.environ.get("ALLOW_MOCK_PAY") != "1":
        return jsonify({"success": False, "error": "生产环境禁止模拟支付"})

    order = get_order(order_id)
    if not order:
        return jsonify({"success": False, "error": "订单不存在"})

    ok, msg = mock_payment_callback(order_id)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/payment/callback/alipay", methods=["POST", "GET"])
def payment_callback_alipay():
    from payment_system import get_alipay
    alipay = get_alipay()
    params = request.form.to_dict() if request.method == "POST" else request.args.to_dict()

    if alipay.verify_callback(params):
        order_id = params.get("out_trade_no", "")
        trade_no = params.get("trade_no", "")
        try:
            verified_amount = float(params.get("total_amount", 0))
        except (ValueError, TypeError):
            verified_amount = None
        ok, msg = confirm_payment(order_id, trade_no, params, verified_amount=verified_amount)
        return "success" if ok else "fail"
    return "fail"


# =============================================================================
# 路由 - 订阅
# =============================================================================

@app.route("/subscribe/<tier_id>", methods=["POST"])
@require_auth
def do_subscribe(tier_id):
    ok, msg = subscribe_tier(g.user_id, tier_id)
    return jsonify({"success": ok, "message": msg})


# =============================================================================
# 路由 - 分销
# =============================================================================

@app.route("/agent/become", methods=["POST"])
@require_auth
def become_agent():
    ok, msg = create_agent_account(g.user_id)
    return jsonify({"success": ok, "message": msg})


@app.route("/agent/settings", methods=["GET", "POST"])
@require_auth
def agent_settings():
    if request.method == "POST":
        data = request.json or {}
        ok = update_agent_settings(
            g.user_id,
            commission_rate=data.get("commission_rate"),
            custom_price_multiplier=data.get("custom_price_multiplier"),
            bank_info=data.get("bank_info")
        )
        return jsonify({"success": ok})
    return jsonify(get_agent_settings(g.user_id))


@app.route("/agent/commissions")
@require_auth
def agent_commissions():
    status = request.args.get("status")
    return jsonify({
        "commissions": get_agent_commissions(g.user_id, status),
        "summary": get_agent_commission_summary(g.user_id)
    })


# =============================================================================
# 路由 - AI对话 API
# =============================================================================

@app.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    user = g.user
    message = request.form.get("message") or (request.json or {}).get("message", "")

    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    allowed, reason = check_quota(user.id)
    if not allowed:
        return jsonify({"error": reason}), 402

    try:
        from brain import get_ai_response
        reply = get_ai_response(message, use_mock=False)
        tokens_used = len(message) + len(reply)
        # record_usage 期望 cost 单位为分；0.1元/1M tokens 估算 ×100 转分
        cost = tokens_used * 0.1 / 1000000 * 100
        charged = calculate_charge(tokens_used, user.role)
        record_usage(g.api_key, tokens_used, cost, charged, "/api/chat")
        return jsonify({
            "reply": reply,
            "tokens": tokens_used,
            "charged": round(charged / 100, 4),
            "source": "api"
        })
    except Exception as e:
        # 安全：不向客户端泄露内部异常细节（路径/数据库结构等），仅记录服务端日志
        from logger import logger
        logger.error(f"[api_chat] 内部错误: {e}")
        return jsonify({"error": "内部错误，请稍后重试"}), 500


@app.route("/api/chat/stream", methods=["POST"])
@require_auth
def api_chat_stream():
    user = get_user_info(g.user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 401
    message = (request.json or {}).get("message", "")
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    # 流式接口也必须检查额度
    allowed, reason = check_quota(user["id"])
    if not allowed:
        return jsonify({"error": reason}), 402

    def generate():
        try:
            from brain import get_ai_response
            reply = get_ai_response(message, use_mock=False)
            for char in reply:
                yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                time.sleep(0.01)
            # 流式结束后记录用量（按字符估算 token）
            tokens_used = len(message) + len(reply)
            # record_usage 期望 cost 单位为分；0.1元/1M tokens 估算 ×100 转分
            cost = tokens_used * 0.1 / 1000000 * 100
            charged = calculate_charge(tokens_used, user["role"])
            record_usage(None, tokens_used, cost, charged, "/api/chat/stream", user_id=user["id"])
            yield f"data: {json.dumps({'content': '', 'done': True, 'tokens': tokens_used, 'charged': round(charged / 100, 4)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            # 安全：不向客户端泄露内部异常细节
            from logger import logger
            logger.error(f"[api_chat_stream] 内部错误: {e}")
            yield f"data: {json.dumps({'error': '内部错误，请稍后重试'}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# =============================================================================
# 路由 - API Key 管理
# =============================================================================

@app.route("/api/regenerate-key", methods=["POST"])
@require_auth
def api_regenerate_key():
    ok, raw_key = regenerate_api_key(g.user_id)
    if not ok:
        return jsonify({"error": raw_key}), 400
    return jsonify({"api_key": raw_key, "hint": "仅此一次显示，请妥善保存"})


# =============================================================================
# 路由 - 用量查询
# =============================================================================

@app.route("/api/usage")
@require_api_key
def api_usage():
    usage = get_user_usage(g.user.id)
    return jsonify({
        "usage": usage,
        "quota_used": g.user.quota_used,
        "quota_limit": g.user.quota_limit,
        "balance": g.user.balance
    })


# =============================================================================
# 路由 - 管理后台
# =============================================================================

@app.route("/admin")
@require_admin
def admin():
    users = list_users(limit=100)

    # users.db 查询：用户数、总余额（balance 单位为分，/100 转元）
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = c.fetchone()["cnt"]
    c.execute("SELECT COALESCE(SUM(balance),0) as bal FROM users")
    total_balance = c.fetchone()["bal"] / 100
    conn.close()

    # payments.db 查询：订单数、总收入（amount 单位为元）
    # 不能用 billing 的 _get_db()，因为 payment_orders 表在 payments.db
    pconn = _get_payment_db()
    pc = pconn.cursor()
    pc.execute("SELECT COUNT(*) as cnt FROM payment_orders WHERE status = 'success'")
    total_orders = pc.fetchone()["cnt"]
    pc.execute("SELECT COALESCE(SUM(amount),0) as amt FROM payment_orders WHERE status = 'success'")
    total_revenue = pc.fetchone()["amt"]
    pconn.close()

    rows_html = "".join(
        f'<tr style="border-bottom:1px solid #ffffff11">'
        f'<td>{html.escape(str(u["username"]))}</td>'
        f'<td>{html.escape(str(u["email"]))}</td>'
        f'<td>{html.escape(str(u["role"]))}</td>'
        f'<td>{u["balance"]/100:.2f}元</td>'
        f'<td>{u["quota_used"]//1000}K</td>'
        f'<td><a href="/admin/user/{html.escape(str(u["id"]))}" style="color:#00ffff">详情</a></td>'
        f'</tr>'
        for u in users
    )

    return f"""
    <html><body style="background:#0a0a1a;color:#00ffff;padding:20px;font-family:sans-serif">
    <h2>管理后台</h2>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0">
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">总用户数</div>
            <div style="font-size:28px;color:#00ffff">{total_users}</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">总余额</div>
            <div style="font-size:28px;color:#00ffff">{total_balance:.2f}元</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">总订单</div>
            <div style="font-size:28px;color:#00ff88">{total_orders}</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">总收入</div>
            <div style="font-size:28px;color:#00ff88">{total_revenue:.2f}元</div>
        </div>
    </div>
    <h3>用户列表</h3>
    <table style="width:100%;border-collapse:collapse">
    <tr style="text-align:left;color:#00aacc">
        <th>用户</th><th>邮箱</th><th>角色</th><th>余额</th><th>用量</th><th>操作</th>
    </tr>
    {rows_html}
    </table>
    <a href="/dashboard" style="color:#00aacc">返回控制台</a>
    </body></html>
    """


@app.route("/admin/user/<user_id>")
@require_admin
def admin_user_detail(user_id):
    user = get_user_info(user_id)
    if not user:
        return "用户不存在", 404
    usage = get_user_usage(user_id)
    orders = list_user_orders(user_id, 20)
    rows_usage = "".join(
        f'<tr style="border-bottom:1px solid #ffffff11">'
        f'<td>{html.escape(str(u.get("date", "")))}</td>'
        f'<td>{u.get("calls", 0)}</td>'
        f'<td>{(u.get("total_tokens", 0) or 0) // 1000}K</td>'
        f'<td>{((u.get("total_charged", 0) or 0) / 100):.2f}元</td>'
        f'</tr>' for u in usage[:20]
    )
    rows_orders = "".join(
        f'<tr style="border-bottom:1px solid #ffffff11">'
        f'<td>{html.escape(str(o["id"]))}</td>'
        f'<td>{o["amount"]:.2f}元</td>'
        f'<td>{o["method"]}</td>'
        f'<td>{o["status"]}</td>'
        f'<td>{datetime.fromtimestamp(o["created_at"]).strftime("%m-%d %H:%M")}</td>'
        f'</tr>' for o in orders
    )
    return f"""
    <html><body style="background:#0a0a1a;color:#00ffff;padding:20px;font-family:sans-serif">
    <h2>用户详情：{html.escape(str(user["username"]))}</h2>
    <div style="margin:20px 0;display:grid;grid-template-columns:repeat(4,1fr);gap:16px">
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">角色</div><div style="font-size:20px">{html.escape(str(user["role"]))}</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">余额</div><div style="font-size:20px">{user["balance"]/100:.2f}元</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">用量</div><div style="font-size:20px">{user["quota_used"]//1000}K / {user["quota_limit"]//1000}K</div>
        </div>
        <div style="padding:20px;background:#0d1525;border-radius:10px;border:1px solid #00ffff22">
            <div style="font-size:12px;color:#6688aa">API Key</div><div style="font-size:16px">{html.escape(str(user.get("api_key_prefix", "未设置")))}...</div>
        </div>
    </div>
    <h3>最近使用记录</h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
        <tr style="text-align:left;color:#00aacc"><th>日期</th><th>调用</th><th>Tokens</th><th>费用</th></tr>
        {rows_usage or '<tr><td colspan="4" style="text-align:center;color:#557799;padding:20px">暂无记录</td></tr>'}
    </table>
    <h3>最近订单</h3>
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
        <tr style="text-align:left;color:#00aacc"><th>订单号</th><th>金额</th><th>方式</th><th>状态</th><th>时间</th></tr>
        {rows_orders or '<tr><td colspan="5" style="text-align:center;color:#557799;padding:20px">暂无订单</td></tr>'}
    </table>
    <a href="/admin" style="color:#00aacc">返回管理后台</a>
    </body></html>
    """


# =============================================================================
# 启动
# =============================================================================

def run_platform(port: int = 7789):
    init_db()
    init_payment_db()
    print("=" * 60)
    print("  Y·NEX AI 在线服务平台 v2.0")
    print("=" * 60)
    print(f"  访问地址: http://localhost:{port}")
    print("  功能列表:")
    print("    ✓ 用户注册/登录")
    print("    ✓ AI在线对话（流式）")
    print("    ✓ 支付宝/微信支付（沙箱）")
    print("    ✓ 订阅套餐管理")
    print("    ✓ API Key 管理")
    print("    ✓ 分销佣金系统")
    print("    ✓ 插件市场")
    print("    ✓ 管理后台")
    print("=" * 60)
    # 默认仅监听本地回环，由 Nginx 反向代理处理外部访问。
    # 如需局域网访问，请通过环境变量 YNEX_HOST=0.0.0.0 显式开启并配合防火墙。
    import os as _os
    host = _os.environ.get("YNEX_HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_platform()
