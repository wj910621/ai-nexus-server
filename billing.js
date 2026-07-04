const crypto = require('crypto');
const jwt = require('jsonwebtoken');

// 安全：JWT_SECRET 必须由环境变量提供。若未设置，启动时输出显著警告，
// 并生成临时随机密钥（仅用于本地开发，重启后所有 token 失效）。
// 生产环境务必设置 JWT_SECRET，否则攻击者可伪造任意用户 token。
const JWT_SECRET = process.env.JWT_SECRET || (() => {
  const tmp = crypto.randomBytes(32).toString('hex');
  console.warn('\x1b[33m[安全警告] JWT_SECRET 未设置，使用临时随机密钥（仅限开发）！生产环境必须在 .env 中设置 JWT_SECRET，否则 token 可被伪造。\x1b[0m');
  return tmp;
})();

const PRODUCT_PRICING = {
  membership_pro_monthly: { price: 99, credits: 4000, type: 'membership', membership: 'pro', duration: 'monthly', durationDays: 30 },
  membership_pro_quarterly: { price: 269, credits: 13000, type: 'membership', membership: 'pro', duration: 'quarterly', durationDays: 90 },
  membership_pro_yearly: { price: 999, credits: 52000, type: 'membership', membership: 'pro', duration: 'yearly', durationDays: 365 },
  membership_ultimate_monthly: { price: 299, credits: 12000, type: 'membership', membership: 'ultimate', duration: 'monthly', durationDays: 30 },
  membership_ultimate_quarterly: { price: 799, credits: 40000, type: 'membership', membership: 'ultimate', duration: 'quarterly', durationDays: 90 },
  membership_ultimate_yearly: { price: 2999, credits: 160000, type: 'membership', membership: 'ultimate', duration: 'yearly', durationDays: 365 },
  membership_lifetime_standard: { price: 899, credits: 4000, type: 'membership', membership: 'lifetime_standard', duration: 'lifetime', monthlyCredits: 4000 },
  membership_lifetime_ultimate: { price: 2599, credits: 12000, type: 'membership', membership: 'lifetime_ultimate', duration: 'lifetime', monthlyCredits: 12000 },
  pack_100: { price: 9.9, credits: 100, type: 'pack' },
  pack_500: { price: 45, credits: 550, type: 'pack' },
  pack_1000: { price: 85, credits: 1150, type: 'pack' },
  pack_3000: { price: 240, credits: 3600, type: 'pack' },
  pack_10000: { price: 750, credits: 13000, type: 'pack' },
};

const ORDER_STATUS = {
  PENDING: 'pending',
  PAID: 'paid',
  DELIVERED: 'delivered',
  FAILED: 'failed',
  REFUNDED: 'refunded',
  CANCELLED: 'cancelled',
};

function generateOrderNo() {
  const random = crypto.randomBytes(4).toString('hex').toUpperCase();
  return 'YJ' + Date.now() + random;
}

function generateQRCodeSVG(orderNo, amount) {
  const size = 200;
  const modules = 25;
  const cellSize = size / modules;
  let rects = '';
  const seed = crypto.createHash('md5').update(orderNo).digest('hex');
  for (let y = 0; y < modules; y++) {
    for (let x = 0; x < modules; x++) {
      const idx = (y * modules + x) % seed.length;
      const charCode = seed.charCodeAt(idx);
      if (charCode % 2 === 0) {
        rects += `<rect x="${x * cellSize}" y="${y * cellSize}" width="${cellSize}" height="${cellSize}" fill="#000"/>`;
      }
    }
  }
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" fill="#fff"/>
  ${rects}
  <rect x="0" y="0" width="${cellSize * 7}" height="${cellSize * 7}" fill="#fff"/>
  <rect x="${cellSize}" y="${cellSize}" width="${cellSize * 5}" height="${cellSize * 5}" fill="#000"/>
  <rect x="${cellSize * 2}" y="${cellSize * 2}" width="${cellSize * 3}" height="${cellSize * 3}" fill="#fff"/>
  <rect x="${size - cellSize * 7}" y="0" width="${cellSize * 7}" height="${cellSize * 7}" fill="#fff"/>
  <rect x="${size - cellSize * 6}" y="${cellSize}" width="${cellSize * 5}" height="${cellSize * 5}" fill="#000"/>
  <rect x="${size - cellSize * 5}" y="${cellSize * 2}" width="${cellSize * 3}" height="${cellSize * 3}" fill="#fff"/>
  <rect x="0" y="${size - cellSize * 7}" width="${cellSize * 7}" height="${cellSize * 7}" fill="#fff"/>
  <rect x="${cellSize}" y="${size - cellSize * 6}" width="${cellSize * 5}" height="${cellSize * 5}" fill="#000"/>
  <rect x="${cellSize * 2}" y="${size - cellSize * 5}" width="${cellSize * 3}" height="${cellSize * 3}" fill="#fff"/>
  <text x="${size / 2}" y="${size / 2 + 4}" text-anchor="middle" font-size="12" fill="#07c160" font-weight="bold" background="#fff">¥${amount}</text>
</svg>`;
}

function verifyJWT(authHeader) {
  if (!authHeader) return null;
  const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : authHeader;
  try {
    const decoded = jwt.verify(token, JWT_SECRET, { algorithms: ['HS256'] });
    return decoded;
  } catch (e) {
    return null;
  }
}

function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;
  const decoded = verifyJWT(authHeader);
  if (!decoded) {
    return res.status(401).json({ ok: false, error: '请先登录' });
  }
  req.user = decoded;
  next();
}

function requireAdmin(req, res, next) {
  const authHeader = req.headers.authorization;
  const decoded = verifyJWT(authHeader);
  if (!decoded) {
    return res.status(401).json({ ok: false, error: '请先登录' });
  }
  if (decoded.role !== 'admin') {
    return res.status(403).json({ ok: false, error: '需要管理员权限' });
  }
  req.user = decoded;
  next();
}

function verifyWechatSignature(params, key) {
  const sign = params.sign;
  if (!sign) return false;
  const sorted = Object.keys(params)
    .filter(k => k !== 'sign' && params[k] !== '' && params[k] !== undefined && params[k] !== null)
    .sort()
    .map(k => `${k}=${params[k]}`)
    .join('&');
  const stringSignTemp = sorted + '&key=' + key;
  const calculated = crypto.createHash('md5').update(stringSignTemp).digest('hex').toUpperCase();
  return calculated === sign.toUpperCase();
}

function deliverOrderAtomic(db, order) {
  const product = PRODUCT_PRICING[order.product_id];
  if (!product) return { success: false, error: '产品不存在' };
  if (order.status === ORDER_STATUS.DELIVERED) {
    return { success: true, already: true, message: '已发货' };
  }
  if (order.status !== ORDER_STATUS.PAID && order.status !== ORDER_STATUS.PENDING) {
    return { success: false, error: '订单状态不正确: ' + order.status };
  }

  const now = new Date().toISOString();

  try {
    db.exec('BEGIN TRANSACTION');

    const updateResult = db.prepare(
      'UPDATE orders SET status=? WHERE order_no=? AND status IN (?,?)'
    ).run(ORDER_STATUS.PAID, order.order_no, ORDER_STATUS.PENDING, ORDER_STATUS.PAID);
    
    if (updateResult.changes === 0) {
      db.exec('ROLLBACK');
      const current = db.prepare('SELECT status FROM orders WHERE order_no=?').get(order.order_no);
      if (current && current.status === ORDER_STATUS.DELIVERED) {
        return { success: true, already: true, message: '已发货' };
      }
      return { success: false, error: '订单状态冲突' };
    }

    if (product.type === 'membership') {
      let newExpires;
      if (product.duration === 'lifetime') {
        newExpires = '2099-12-31T23:59:59.000Z';
      } else {
        const user = db.prepare('SELECT membership_expires FROM users WHERE username=?').get(order.username);
        let baseDate = new Date();
        if (user && user.membership_expires && new Date(user.membership_expires) > new Date()) {
          baseDate = new Date(user.membership_expires);
        }
        baseDate.setDate(baseDate.getDate() + product.durationDays);
        newExpires = baseDate.toISOString();
      }

      const existing = db.prepare('SELECT membership, membership_expires FROM users WHERE username=?').get(order.username);
      if (existing && existing.membership === product.membership &&
          existing.membership_expires && new Date(existing.membership_expires) > new Date()) {
        db.prepare('UPDATE users SET membership_expires=?, credits=credits+? WHERE username=?').run(
          newExpires, product.credits, order.username
        );
      } else {
        db.prepare('UPDATE users SET membership=?, membership_expires=?, credits=credits+? WHERE username=?').run(
          product.membership, newExpires, product.credits, order.username
        );
      }
      db.prepare('INSERT INTO credit_log (username, amount, reason, order_no) VALUES (?, ?, ?, ?)').run(
        order.username, product.credits, `${order.product_id} 购买赠送`, order.order_no
      );
    } else if (product.type === 'pack') {
      db.prepare('UPDATE users SET credits=credits+? WHERE username=?').run(product.credits, order.username);
      db.prepare('INSERT INTO credit_log (username, amount, reason, order_no) VALUES (?, ?, ?, ?)').run(
        order.username, product.credits, `积分包 ${order.product_id}`, order.order_no
      );
    }

    const paidAt = new Date().toISOString();
    db.prepare('UPDATE orders SET status=?, paid_at=? WHERE order_no=?').run(
      ORDER_STATUS.DELIVERED, paidAt, order.order_no
    );

    db.exec('COMMIT');
    return { success: true };
  } catch (e) {
    try { db.exec('ROLLBACK'); } catch (_) {}
    console.error('[billing] deliverOrderAtomic error:', e);
    return { success: false, error: e.message };
  }
}

module.exports = function(app, db) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      product_type TEXT,
      product_id TEXT NOT NULL,
      amount REAL NOT NULL,
      credits INTEGER DEFAULT 0,
      status TEXT DEFAULT 'pending',
      order_no TEXT UNIQUE NOT NULL,
      idempotency_key TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      paid_at TIMESTAMP,
      delivered_at TIMESTAMP
    )
  `);

  db.exec(`
    CREATE TABLE IF NOT EXISTS payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_no TEXT NOT NULL,
      method TEXT,
      transaction_id TEXT,
      amount REAL NOT NULL,
      status TEXT DEFAULT 'pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      callback_data TEXT
    )
  `);

  try {
    db.prepare('ALTER TABLE orders ADD COLUMN idempotency_key TEXT').run();
  } catch (_) {}
  try {
    db.prepare('ALTER TABLE orders ADD COLUMN delivered_at TIMESTAMP').run();
  } catch (_) {}
  try {
    db.prepare('ALTER TABLE credit_log ADD COLUMN order_no TEXT').run();
  } catch (_) {}

  db.prepare('CREATE INDEX IF NOT EXISTS idx_orders_username ON orders(username)');
  db.prepare('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)');
  db.prepare('CREATE INDEX IF NOT EXISTS idx_payments_order_no ON payments(order_no)');

  app.post('/api/payments/create', requireAuth, (req, res) => {
    try {
      const username = req.user.username;
      const { productId, method = 'wechat', idempotencyKey } = req.body;
      
      if (!productId) {
        return res.json({ ok: false, error: '参数不完整' });
      }

      const product = PRODUCT_PRICING[productId];
      if (!product) {
        return res.json({ ok: false, error: '产品不存在' });
      }

      if (idempotencyKey) {
        const existing = db.prepare('SELECT * FROM orders WHERE idempotency_key=? AND username=?').get(idempotencyKey, username);
        if (existing) {
          return res.json({
            ok: true,
            orderNo: existing.order_no,
            amount: existing.amount,
            credits: existing.credits,
            productId: existing.product_id,
            status: existing.status,
            idempotent: true
          });
        }
      }

      const orderNo = generateOrderNo();

      db.prepare('INSERT INTO orders (username, product_type, product_id, amount, credits, status, order_no, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)').run(
        username, product.type, productId, product.price, product.credits, ORDER_STATUS.PENDING, orderNo, idempotencyKey || null
      );

      db.prepare('INSERT INTO payments (order_no, method, amount, status) VALUES (?, ?, ?, ?)').run(
        orderNo, method, product.price, ORDER_STATUS.PENDING
      );

      res.json({
        ok: true,
        orderNo,
        amount: product.price,
        credits: product.credits,
        productId,
        method,
        status: ORDER_STATUS.PENDING
      });
    } catch (e) {
      console.error('[billing] create order error:', e);
      res.json({ ok: false, error: '创建订单失败' });
    }
  });

  app.get('/api/payments/qrcode', requireAuth, (req, res) => {
    try {
      const { orderNo } = req.query;
      const username = req.user.username;
      if (!orderNo) {
        return res.status(400).json({ error: '缺少订单号' });
      }

      const order = db.prepare('SELECT * FROM orders WHERE order_no=? AND username=?').get(orderNo, username);
      if (!order) {
        return res.status(404).json({ error: '订单不存在' });
      }

      const svg = generateQRCodeSVG(orderNo, order.amount);
      res.setHeader('Content-Type', 'image/svg+xml');
      res.send(svg);
    } catch (e) {
      console.error('[billing] qrcode error:', e);
      res.status(500).json({ error: '生成二维码失败' });
    }
  });

  app.post('/api/payments/confirm', requireAdmin, (req, res) => {
    try {
      const { orderNo } = req.body;
      if (!orderNo) {
        return res.json({ ok: false, error: '缺少订单号' });
      }

      const order = db.prepare('SELECT * FROM orders WHERE order_no=?').get(orderNo);
      if (!order) {
        return res.json({ ok: false, error: '订单不存在' });
      }

      if (order.status === ORDER_STATUS.DELIVERED) {
        return res.json({ ok: true, message: '订单已发货', order });
      }

      const transactionId = 'ADMIN_' + Date.now() + '_' + crypto.randomBytes(4).toString('hex');

      const result = deliverOrderAtomic(db, order);
      if (!result.success) {
        return res.json({ ok: false, error: result.error || '发货失败' });
      }

      db.prepare('UPDATE payments SET status=?, transaction_id=? WHERE order_no=?').run('success', transactionId, orderNo);

      const updatedOrder = db.prepare('SELECT * FROM orders WHERE order_no=?').get(orderNo);
      res.json({ ok: true, message: result.already ? '订单已发货' : '支付成功', order: updatedOrder });
    } catch (e) {
      console.error('[billing] confirm error:', e);
      res.json({ ok: false, error: '支付确认失败' });
    }
  });

  app.post('/api/payments/wechat-notify', (req, res) => {
    try {
      const callbackData = JSON.stringify(req.body);
      const { out_trade_no, transaction_id, result_code } = req.body;

      if (!out_trade_no) {
        return res.json({ return_code: 'FAIL', return_msg: '参数错误' });
      }

      const order = db.prepare('SELECT * FROM orders WHERE order_no=?').get(out_trade_no);
      if (!order) {
        return res.json({ return_code: 'FAIL', return_msg: '订单不存在' });
      }

      db.prepare('UPDATE payments SET callback_data=? WHERE order_no=?').run(callbackData, out_trade_no);

      // 安全：验签默认拒绝，防止伪造支付回调。
      // 必须配置 WECHAT_PAY_KEY 且签名校验通过才放行。
      // 开发环境可通过 PAYMENT_DEV_MODE=1 跳过（仅限 NODE_ENV=development）。
      const wechatKey = process.env.WECHAT_PAY_KEY;
      const isDevMode = process.env.NODE_ENV === 'development' && process.env.PAYMENT_DEV_MODE === '1';

      let signatureValid = false;
      if (isDevMode) {
        console.warn('[billing] 开发模式跳过微信支付验签，生产环境必须配置 WECHAT_PAY_KEY');
        signatureValid = true;
      } else if (!wechatKey) {
        console.error('[billing] 未配置 WECHAT_PAY_KEY，拒绝微信支付回调');
        return res.json({ return_code: 'FAIL', return_msg: '服务器未配置支付密钥' });
      } else if (!req.body.sign) {
        return res.json({ return_code: 'FAIL', return_msg: '缺少签名' });
      } else {
        signatureValid = verifyWechatSignature(req.body, wechatKey);
      }

      if (!signatureValid) {
        return res.json({ return_code: 'FAIL', return_msg: '签名校验失败' });
      }

      if (result_code === 'SUCCESS') {
        const result = deliverOrderAtomic(db, order);
        if (result.success) {
          db.prepare('UPDATE payments SET status=?, transaction_id=? WHERE order_no=?').run(
            'success', transaction_id || '', out_trade_no
          );
        }
      }

      res.json({ return_code: 'SUCCESS', return_msg: 'OK' });
    } catch (e) {
      console.error('Wechat notify error:', e);
      res.json({ return_code: 'FAIL', return_msg: '系统错误' });
    }
  });

  app.get('/api/payments/orders', requireAuth, (req, res) => {
    try {
      const username = req.user.username;
      const { page = 1, pageSize = 20 } = req.query;
      const p = Math.max(1, parseInt(page) || 1);
      const ps = Math.min(100, Math.max(1, parseInt(pageSize) || 20));
      const offset = (p - 1) * ps;

      const total = db.prepare('SELECT COUNT(*) as cnt FROM orders WHERE username=?').get(username).cnt;
      const orders = db.prepare('SELECT id, username, product_type, product_id, amount, credits, status, order_no, created_at, paid_at, delivered_at FROM orders WHERE username=? ORDER BY created_at DESC LIMIT ? OFFSET ?').all(username, ps, offset);
      
      res.json({ ok: true, orders, total, page: p, pageSize: ps });
    } catch (e) {
      console.error('[billing] orders list error:', e);
      res.json({ ok: false, error: '查询失败' });
    }
  });

  app.get('/api/payments/order', requireAuth, (req, res) => {
    try {
      const { orderNo } = req.query;
      const username = req.user.username;
      if (!orderNo) {
        return res.json({ ok: false, error: '缺少订单号' });
      }

      const order = db.prepare('SELECT id, username, product_type, product_id, amount, credits, status, order_no, created_at, paid_at, delivered_at FROM orders WHERE order_no=?').get(orderNo);
      if (!order) {
        return res.json({ ok: false, error: '订单不存在' });
      }

      if (order.username !== username && req.user.role !== 'admin') {
        return res.status(403).json({ ok: false, error: '无权查看' });
      }

      res.json({ ok: true, order });
    } catch (e) {
      console.error('[billing] order detail error:', e);
      res.json({ ok: false, error: '查询失败' });
    }
  });

  app.get('/api/payments/products', (req, res) => {
    const products = Object.entries(PRODUCT_PRICING).map(([id, p]) => ({
      id,
      type: p.type,
      price: p.price,
      credits: p.credits,
      membership: p.membership || null,
      duration: p.duration || null,
    }));
    res.json({ ok: true, products });
  });
};
