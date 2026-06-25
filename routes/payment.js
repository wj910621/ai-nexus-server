const { db, authRequired } = require('../server');

const FREE_ALWAYS = ['dmx_qwen35_2b_free', 'dmx_qwen3_17b_free', 'dmx_spark_lite_free', 'ark_dbs2_mini', 'ark_dbp15l', 'sf_deepseek_v3_free', 'sf_glm47', 'sf_qwen3_8b'];
const MEMBERSHIP_TIERS = {
  free:  { name: '免费用户', dailyFreeCalls: 30, discount: 0, price: 0, creditsPerMonth: 0, desc: '基础体验' },
  silver:{ name: '月度会员', dailyFreeCalls: 999, discount: 0.2, price: 49, creditsPerMonth: 1000, desc: '高端模型8折' },
  gold:  { name: '季度会员', dailyFreeCalls: 999, discount: 0.3, price: 119, creditsPerMonth: 3500, desc: '高端模型7折+返利5%' },
  platinum:{name: '年度会员', dailyFreeCalls: 999, discount: 0.5, price: 369, creditsPerMonth: 15000, desc: '高端模型5折+返利10%+3D五折' },
};
function getMembership(user) {
  if (!user) return MEMBERSHIP_TIERS.free;
  const tier = user.membership || 'free';
  const expires = user.membership_expires || '';
  if (tier !== 'free' && expires && new Date(expires) < new Date()) return MEMBERSHIP_TIERS.free;
  return MEMBERSHIP_TIERS[tier] || MEMBERSHIP_TIERS.free;
}

const PAYMENT_PRODUCTS = {
  credits_starter: { name: '体验包', type: 'credits', credits: 150, price: 9.9, desc: '150积分' },
  credits_standard: { name: '标准包', type: 'credits', credits: 700, price: 39, desc: '700积分' },
  credits_premium: { name: '进阶包', type: 'credits', credits: 1500, price: 69, desc: '1500积分' },
  credits_pro: { name: '专业包', type: 'credits', credits: 2500, price: 99, desc: '2500积分' },
  credits_ultimate: { name: '旗舰包', type: 'credits', credits: 6000, price: 199, desc: '6000积分' },
  membership_silver: { name: '月度会员', type: 'membership', tier: 'silver', creditsPerMonth: 1000, price: 49, months: 1, desc: '月度会员' },
  membership_gold: { name: '季度会员', type: 'membership', tier: 'gold', creditsPerMonth: 3500, price: 119, months: 3, desc: '季度会员' },
  membership_platinum: { name: '年度会员', type: 'membership', tier: 'platinum', creditsPerMonth: 15000, price: 369, months: 12, desc: '年度会员' }
};

module.exports = function(app) {
  app.get('/api/membership/status', authRequired, (req, res) => {
    const user = db.prepare("SELECT membership, membership_expires, daily_free_usage, daily_free_date, credits FROM users WHERE username=?").get(req.user.username);
    if (!user) return res.json({ ok: false, error: '用户不存在' });
    const tier = getMembership({ membership: user.membership, membership_expires: user.membership_expires });
    res.json({
      ok: true, membership: user.membership, expires: user.membership_expires || '', tierName: tier.name,
      dailyFreeCalls: tier.dailyFreeCalls, discount: tier.discount,
      dailyFreeUsed: user.daily_free_usage || 0, dailyFreeDate: user.daily_free_date || '', credits: user.credits || 0,
    });
  });

  app.post('/api/membership/subscribe', authRequired, (req, res) => {
    const { tier, months } = req.body;
    if (!MEMBERSHIP_TIERS[tier]) return res.json({ ok: false, error: '无效的会员等级' });
    if (tier === 'free') return res.json({ ok: false, error: '已经是免费用户' });
    const m = MEMBERSHIP_TIERS[tier];
    const now = new Date();
    const current = db.prepare("SELECT membership_expires FROM users WHERE username=?").get(req.user.username);
    let baseDate = now;
    if (current && current.membership_expires) {
      const existing = new Date(current.membership_expires);
      if (existing > now) baseDate = existing;
    }
    const expireDate = new Date(baseDate);
    expireDate.setMonth(expireDate.getMonth() + (months || 1));
    const totalPrice = m.price * (months || 1);
    db.prepare("UPDATE users SET membership=?, membership_expires=?, credits=credits+? WHERE username=?").run(
      tier, expireDate.toISOString(), m.creditsPerMonth * (months || 1), req.user.username);
    res.json({ ok: true, tier, expires: expireDate.toISOString(), creditsAdded: m.creditsPerMonth * (months || 1), price: totalPrice });
  });

  app.post('/api/payments/create-order', authRequired, (req, res) => {
    try {
      const { productId } = req.body;
      if (!productId || !PAYMENT_PRODUCTS[productId]) return res.json({ ok: false, error: '无效的商品ID' });
      const product = PAYMENT_PRODUCTS[productId];
      const orderId = 'ORD' + Date.now() + Math.random().toString(36).substring(2, 6).toUpperCase();
      db.exec(`CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY, username TEXT, product_id TEXT, product_name TEXT,
        amount REAL, credits INTEGER, status TEXT DEFAULT 'pending', created_at TEXT, paid_at TEXT
      )`);
      const existing = db.prepare("SELECT order_id FROM orders WHERE username=? AND status='pending' AND product_id=?").get(req.user.username, productId);
      if (existing) {
        return res.json({ ok: true, orderId: existing.order_id, product, status: 'pending', existing: true });
      }
      const credits = product.credits || 0;
      db.prepare("INSERT INTO orders (order_id, username, product_id, product_name, amount, credits, status, created_at) VALUES (?,?,?,?,?,?,'pending',?)").run(
        orderId, req.user.username, productId, product.name, product.price, credits, new Date().toISOString());
      res.json({ ok: true, orderId, product, status: 'pending' });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/payments/confirm', authRequired, (req, res) => {
    try {
      const { orderId } = req.body;
      if (!orderId) return res.json({ ok: false, error: '缺少订单ID' });
      const order = db.prepare("SELECT * FROM orders WHERE order_id=? AND username=?").get(orderId, req.user.username);
      if (!order) return res.json({ ok: false, error: '订单不存在' });
      if (order.status !== 'pending') return res.json({ ok: false, error: '订单状态异常', status: order.status });
      const product = PAYMENT_PRODUCTS[order.product_id];
      db.prepare("UPDATE orders SET status='completed', paid_at=? WHERE order_id=?").run(new Date().toISOString(), orderId);
      if (product.type === 'credits') {
        const credits = product.credits;
        db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(credits, req.user.username);
        db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(req.user.username, credits, '购买积分包: ' + product.name);
      } else if (product.type === 'membership') {
        const now = new Date();
        const current = db.prepare("SELECT membership_expires FROM users WHERE username=?").get(req.user.username);
        let baseDate = now;
        if (current && current.membership_expires) {
          const existing = new Date(current.membership_expires);
          if (existing > now) baseDate = existing;
        }
        const expireDate = new Date(baseDate);
        expireDate.setMonth(expireDate.getMonth() + (product.months || 1));
        db.prepare("UPDATE users SET membership=?, membership_expires=?, credits=credits+? WHERE username=?").run(
          product.tier, expireDate.toISOString(), product.creditsPerMonth || 0, req.user.username);
      }
      res.json({ ok: true, status: 'completed', message: '支付成功' });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/payments/orders', authRequired, (req, res) => {
    try {
      const orders = db.prepare("SELECT * FROM orders WHERE username=? ORDER BY created_at DESC LIMIT 20").all(req.user.username);
      res.json({ ok: true, orders });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  let wxpay = null;
  try { wxpay = require('../wechat-pay'); } catch (e) { console.log('[WX Pay] 模块加载失败:', e.message); }

  app.post('/api/payments/wechat-create', authRequired, async (req, res) => {
    try {
      const { productId } = req.body;
      if (!wxpay) return res.json({ ok: false, error: '微信支付模块未加载' });
      if (!productId || !PAYMENT_PRODUCTS[productId]) return res.json({ ok: false, error: '无效的商品ID' });
      const product = PAYMENT_PRODUCTS[productId];
      const orderId = 'ORD' + Date.now() + Math.random().toString(36).substring(2, 6).toUpperCase();
      const amount = Math.round(product.price * 100);
      const credits = product.credits || 0;
      db.exec(`CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY, username TEXT, product_id TEXT, product_name TEXT,
        amount REAL, credits INTEGER, status TEXT DEFAULT 'pending', created_at TEXT, paid_at TEXT
      )`);
      db.prepare("INSERT INTO orders (order_id, username, product_id, product_name, amount, credits, status, created_at) VALUES (?,?,?,?,?,?,'pending',?)").run(
        orderId, req.user.username, productId, product.name, product.price, credits, new Date().toISOString());
      const wxResult = await wxpay.createNativeOrder({
        description: `TriGen - ${product.name}`,
        outTradeNo: orderId, amount,
        attach: JSON.stringify({ username: req.user.username, productId }),
      });
      res.json({ ok: true, orderId, product, codeUrl: wxResult.code_url });
    } catch (e) { res.json({ ok: false, error: '创建支付失败: ' + e.message }); }
  });

  app.post('/api/payments/wechat-notify', (req, res) => {
    try {
      if (!wxpay) return res.status(500).json({ code: 'FAIL', message: '模块未加载' });
      const headers = req.headers;
      const body = JSON.stringify(req.body);
      const ver = wxpay.verifyNotify(headers, body);
      if (!ver.ok) {
        console.error('[WX Pay] 回调签名验证失败:', ver.error);
        return res.status(401).json({ code: 'FAIL', message: '签名验证失败' });
      }
      const resource = req.body.resource;
      if (!resource) return res.status(400).json({ code: 'FAIL', message: '缺少resource' });
      const decrypted = wxpay.decryptResource(resource);
      const { out_trade_no, trade_state } = decrypted;
      if (trade_state === 'SUCCESS') {
        const order = db.prepare("SELECT username, product_id, credits, status FROM orders WHERE order_id=?").get(out_trade_no);
        if (order && order.status === 'pending') {
          const username = order.username;
          const creditsToAdd = order.credits;
          db.prepare("UPDATE orders SET status='paid', paid_at=? WHERE order_id=?").run(new Date().toISOString(), out_trade_no);
          db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(creditsToAdd, username);
          console.log(`[WX Pay] 支付成功: ${out_trade_no}, 用户: ${username}, 积分: +${creditsToAdd}`);
        }
      }
      res.json({ code: 'SUCCESS', message: '成功' });
    } catch (e) {
      console.error('[WX Pay] 回调处理异常:', e.message);
      res.json({ code: 'FAIL', message: e.message });
    }
  });

  app.get('/api/payments/wechat-query/:orderId', authRequired, async (req, res) => {
    try {
      if (!wxpay) return res.json({ ok: false, error: '微信支付模块未加载' });
      const { orderId } = req.params;
      const order = db.prepare("SELECT status, credits FROM orders WHERE order_id=? AND username=?").get(orderId, req.user.username);
      if (!order) return res.json({ ok: false, error: '订单不存在' });
      if (order.status === 'paid') return res.json({ ok: true, paid: true });
      const wxResult = await wxpay.queryOrder(orderId);
      if (wxResult.trade_state === 'SUCCESS') {
        db.prepare("UPDATE orders SET status='paid', paid_at=? WHERE order_id=?").run(new Date().toISOString(), orderId);
        db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(order.credits, req.user.username);
        return res.json({ ok: true, paid: true });
      }
      res.json({ ok: true, paid: false, tradeState: wxResult.trade_state });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });
};
