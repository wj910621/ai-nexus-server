const { db, signToken, verifyToken, authRequired, authLimiter } = require('../server');
const bcrypt = require('bcryptjs');

function btoaPwd(pwd) { return Buffer.from(pwd).toString('base64'); }
function isBcryptHash(hash) { return typeof hash === 'string' && (hash.startsWith('$2a$') || hash.startsWith('$2b$')); }
function hashPasswordSync(pwd) { return bcrypt.hashSync(pwd, 10); }
function verifyPasswordSync(pwd, storedHash) {
  if (isBcryptHash(storedHash)) return bcrypt.compareSync(pwd, storedHash);
  return storedHash === btoaPwd(pwd);
}
function upgradePasswordToBcrypt(username, plainPwd) {
  const newHash = hashPasswordSync(plainPwd);
  db.prepare("UPDATE users SET password=? WHERE username=?").run(newHash, username);
}

function requireAdmin(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ ok: false, error: '未登录' });
  }
  try {
    const token = auth.slice(7);
    const payload = verifyToken(token);
    if (!payload || payload.role !== 'admin') {
      return res.status(403).json({ ok: false, error: '无管理员权限' });
    }
    req.adminUser = payload.username;
    next();
  } catch(e) {
    return res.status(401).json({ ok: false, error: 'Token无效' });
  }
}

module.exports = function(app) {
  app.post('/api/auth/register', authLimiter, (req, res) => {
    const { username, email, password, refCode, deviceFp } = req.body;
    if (!username || !password) return res.json({ ok: false, error: '请填写用户名和密码' });
    const phone = (req.body.phone || '').trim();
    if (!phone || !/^1[3-9]\d{9}$/.test(phone)) return res.json({ ok: false, error: '请填写正确的手机号' });
    if (!/^[a-zA-Z0-9]{2,20}$/.test(username)) return res.json({ ok: false, error: '用户名格式不正确（2-20位字母或数字）' });
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return res.json({ ok: false, error: '邮箱格式不正确' });
    if (password.length < 6) return res.json({ ok: false, error: '密码至少6位' });
    const securityQ = (req.body.securityQuestion || '').trim();
    const securityA = (req.body.securityA || '').trim();
    if (!securityQ || !securityA) return res.json({ ok: false, error: '请设置密保问题和答案' });
    const clientIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
    const ipRow = db.prepare("SELECT COUNT(*) as cnt FROM users WHERE register_ip=?").get(clientIP);
    const currentCount = ipRow ? ipRow.cnt : 0;
    if (currentCount >= 2) return res.json({ ok: false, error: '本网络已注册过 2 个账号，已达到上限' });
    if (deviceFp && deviceFp.length >= 8) {
      const fpRow = db.prepare("SELECT COUNT(*) as cnt FROM users WHERE device_fp=?").get(deviceFp);
      const currentFpCount = fpRow ? fpRow.cnt : 0;
      if (currentFpCount >= 1) return res.json({ ok: false, error: '该设备已注册过账号，每个设备限注册一个账号' });
    }
    try {
      const existing = db.prepare("SELECT id FROM users WHERE username=? " + (email ? "OR email=?" : "") + " OR phone=?").get(
        email ? [username, email, phone] : [username, phone]
      );
      if (existing) return res.json({ ok: false, error: '用户名、邮箱或手机号已被注册' });
      const refCodeGen = 'J3' + username.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6) + Math.random().toString(36).slice(2, 5).toUpperCase();
      const userEmail = email || ('noemail_' + username + '@nexus-hub.local');
      let bonus = 30;
      let referrer = null;
      if (refCode) {
        const refUser = db.prepare("SELECT username FROM users WHERE ref_code=? OR username=?").get(refCode, refCode);
        if (refUser) {
          bonus += 30;
          referrer = refUser.username;
          db.prepare("UPDATE users SET credits=credits+30 WHERE username=?").run(referrer);
          db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?, ?, ?)").run(referrer, 30, '推荐奖励');
        }
      }
      db.prepare("INSERT INTO users (username, email, password, credits, ref_code, referrer, register_ip, phone, device_fp, security_q, security_a) VALUES (?,?,?,?,?,?,?,?,?,?,?)").run(
        username, userEmail, hashPasswordSync(password), bonus, refCodeGen, referrer, clientIP, phone||'', deviceFp||'', securityQ, hashPasswordSync(securityA));
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, bonus, '注册赠送');
      const apiKey = 'nexus-' + username.substring(0,4).toLowerCase() + '-' + require('crypto').randomBytes(6).toString('hex');
      db.prepare("INSERT INTO api_keys (username, key_name, api_key, quota) VALUES (?,?,?,?)").run(username, '默认Key', apiKey, 0);
      const token = signToken({ username, role: 'user', ts: Date.now() });
      res.json({ ok: true, token, apiKey, user: { username, email, credits: bonus, refCode: refCodeGen }, bonus, referrerBonus: refCode ? 30 : 0 });
    } catch(e) { res.json({ ok: false, error: '注册失败: ' + e.message }); }
  });

  app.post('/api/auth/login', authLimiter, (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) return res.json({ ok: false, error: '请输入用户名和密码' });
    try {
      const user = db.prepare("SELECT username, email, password, credits, role, ref_code FROM users WHERE username=? OR email=? OR phone=?").get(username, username, username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      if (!verifyPasswordSync(password, user.password)) return res.json({ ok: false, error: '密码错误' });
      if (!isBcryptHash(user.password)) upgradePasswordToBcrypt(user.username, password);
      const token = signToken({ username: user.username, role: user.role, ts: Date.now() });
      const apiKeyRow = db.prepare("SELECT api_key FROM api_keys WHERE username=? ORDER BY id LIMIT 1").get(user.username);
      const apiKey = apiKeyRow ? apiKeyRow.api_key : null;
      res.json({ ok: true, token, apiKey, user: { username: user.username, email: user.email, credits: user.credits, role: user.role, refCode: user.ref_code } });
    } catch(e) { res.json({ ok: false, error: '登录失败: ' + e.message }); }
  });

  app.post('/api/user/spend', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    const { amount } = req.body;
    if (!amount || amount <= 0) return res.json({ ok: false, error: '金额无效' });
    try {
      const payload = verifyToken(token);
      const username = payload.username;
      const user = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      const current = user.credits;
      if (current < amount) return res.json({ ok: false, error: '积分不足' });
      db.prepare("UPDATE users SET credits=credits-? WHERE username=?").run(amount, username);
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, -amount, '消费');
      const newCredits = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      res.json({ ok: true, credits: newCredits.credits });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/user/credits', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const user = db.prepare("SELECT credits FROM users WHERE username=?").get(payload.username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      res.json({ ok: true, credits: user.credits });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/user/checkin', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const username = payload.username;
      const today = new Date().toISOString().slice(0, 10);
      const existing = db.prepare("SELECT checkin_date, checkin_streak FROM users WHERE username=?").get(username);
      let lastCheckin = existing && existing.checkin_date ? existing.checkin_date : '';
      if (lastCheckin === today) return res.json({ ok: false, error: '今天已经签到过了', already: true });
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      let streak = existing && existing.checkin_streak ? existing.checkin_streak : 0;
      if (lastCheckin === yesterday) streak += 1; else streak = 1;
      let bonus = 5;
      if (streak % 7 === 0) bonus += 5;
      if (streak % 30 === 0) bonus += 20;
      db.prepare("UPDATE users SET credits=credits+?, checkin_date=?, checkin_streak=? WHERE username=?").run(bonus, today, streak, username);
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, bonus, '每日签到');
      const newCredits = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      res.json({ ok: true, bonus, streak, credits: newCredits.credits });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/user/checkin-status', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const today = new Date().toISOString().slice(0, 10);
      const result = db.prepare("SELECT checkin_date, checkin_streak FROM users WHERE username=?").get(payload.username);
      if (result) {
        const lastDate = result.checkin_date || '';
        const streak = result.checkin_streak || 0;
        res.json({ ok: true, checkedIn: lastDate === today, streak: streak || 0, lastDate });
      } else {
        res.json({ ok: true, checkedIn: false, streak: 0, lastDate: '' });
      }
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/user/refund', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    const { amount } = req.body;
    if (!amount || amount <= 0) return res.json({ ok: false, error: '金额无效' });
    try {
      const payload = verifyToken(token);
      const username = payload.username;
      db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(amount, username);
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, amount, '退款-API失败');
      const newCredits = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      res.json({ ok: true, credits: newCredits.credits });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/admin/login', (req, res) => {
    const { password } = req.body;
    try {
      const admin = db.prepare("SELECT username, password FROM users WHERE role='admin' AND username='admin'").get();
      if (!admin) return res.json({ ok: false, error: '管理员账号不存在' });
      if (!verifyPasswordSync(password, admin.password)) return res.json({ ok: false, error: '密码错误' });
      if (!isBcryptHash(admin.password)) upgradePasswordToBcrypt('admin', password);
      const token = signToken({ username: 'admin', role: 'admin', ts: Date.now() });
      res.json({ ok: true, token });
    } catch(e) { res.json({ ok: false, error: '登录失败: ' + e.message }); }
  });

  app.post('/api/admin/change-pwd', requireAdmin, (req, res) => {
    const { oldPwd, newPwd } = req.body;
    if (!newPwd || newPwd.length < 6) return res.json({ ok: false, error: '新密码至少6位' });
    try {
      const admin = db.prepare("SELECT password FROM users WHERE username='admin'").get();
      if (!admin) return res.json({ ok: false, error: '管理员账号不存在' });
      if (!verifyPasswordSync(oldPwd, admin.password)) return res.json({ ok: false, error: '原密码错误' });
      db.prepare("UPDATE users SET password=? WHERE username=?").run(hashPasswordSync(newPwd), 'admin');
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: '修改失败: ' + e.message }); }
  });

  app.get('/api/admin/users', requireAdmin, (req, res) => {
    try {
      const users = db.prepare("SELECT username, email, credits, role, ref_code, created_at FROM users ORDER BY created_at DESC").all();
      const total = users.length;
      const totalCredits = users.reduce((s, u) => s + u.credits, 0);
      res.json({ ok: true, users: users.map(u => ({ username: u.username, email: u.email, credits: u.credits, role: u.role, refCode: u.ref_code, createdAt: u.created_at })), total, totalCredits });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/admin/recharge', requireAdmin, (req, res) => {
    const { username, amount, reason } = req.body;
    if (!username || !amount || amount <= 0) return res.json({ ok: false, error: '请填写正确的用户名和金额' });
    try {
      const user = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      db.prepare("UPDATE users SET credits=credits+? WHERE username=?").run(amount, username);
      db.prepare("INSERT INTO credit_log (username, amount, reason, admin) VALUES (?,?,?,?)").run(username, amount, reason || '手动充值', req.adminUser);
      const newCredits = db.prepare("SELECT credits FROM users WHERE username=?").get(username);
      res.json({ ok: true, username, added: amount, credits: newCredits.credits });
    } catch(e) { res.json({ ok: false, error: '充值失败: ' + e.message }); }
  });

  app.get('/api/admin/recharge-log', requireAdmin, (req, res) => {
    try {
      const logs = db.prepare("SELECT username, amount, reason, admin, created_at FROM credit_log ORDER BY created_at DESC LIMIT 200").all();
      res.json({ ok: true, logs: logs.map(r => ({ username: r.username, amount: r.amount, reason: r.reason, admin: r.admin, createdAt: r.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/user/data', (req, res) => {
    const auth = req.headers.authorization;
    if (!auth || !auth.startsWith('Bearer ')) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = JSON.parse(Buffer.from(auth.slice(7), 'base64').toString());
      const user = db.prepare("SELECT username, email, credits, role, ref_code FROM users WHERE username=?").get(payload.username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      res.json({ ok: true, data: { username: user.username, email: user.email, credits: user.credits, role: user.role, refCode: user.ref_code } });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/admin/keys', requireAdmin, (req, res) => {
    try {
      const keys = db.prepare("SELECT id, platform, prefix, models, manage_url, notes FROM key_config ORDER BY id").all();
      res.json({ ok: true, keys: keys.map(r => ({ id: r.id, platform: r.platform, prefix: r.prefix, models: JSON.parse(r.models || '[]'), manageUrl: r.manage_url, notes: r.notes })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/admin/keys', requireAdmin, (req, res) => {
    const { platform, prefix, models, manageUrl, notes } = req.body;
    if (!platform || !prefix) return res.json({ ok: false, error: '平台名称和Key前缀必填' });
    try {
      db.prepare("INSERT INTO key_config (platform, prefix, models, manage_url, notes) VALUES (?,?,?,?,?)").run(platform, prefix, JSON.stringify(models || []), manageUrl || '', notes || '');
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/admin/keys/:id', requireAdmin, (req, res) => {
    try {
      db.prepare("DELETE FROM key_config WHERE id=?").run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/keys/create', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const username = payload.username;
      const keyName = (req.body.name || '').trim() || '默认 Key';
      const apiKey = 'ai-' + username.substring(0, 3) + '-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 8);
      db.prepare("INSERT INTO api_keys (username, key_name, api_key, quota) VALUES (?,?,?,?)").run(username, keyName, apiKey, 0);
      res.json({ ok: true, apiKey, name: keyName });
    } catch(e) { res.json({ ok: false, error: '创建失败: ' + e.message }); }
  });

  app.get('/api/keys', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const keys = db.prepare("SELECT id, key_name, api_key, quota, used, active, created_at FROM api_keys WHERE username=? ORDER BY id DESC").all(payload.username);
      res.json({ ok: true, keys: keys.map(v => ({ id: v.id, name: v.key_name, key: v.api_key, quota: v.quota, used: v.used, active: v.active, created: v.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/keys/:id', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      db.prepare("DELETE FROM api_keys WHERE id=? AND username=?").run(req.params.id, payload.username);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/auth/forgot-password', authLimiter, (req, res) => {
    const { input, securityAnswer, newPassword } = req.body;
    if (!input || !securityAnswer || !newPassword) return res.json({ ok: false, error: '请填写完整信息' });
    if (newPassword.length < 6) return res.json({ ok: false, error: '新密码至少6位' });
    try {
      const user = db.prepare("SELECT username, security_q, security_a FROM users WHERE username=? OR email=? OR phone=?").get(input, input, input);
      if (!user) return res.json({ ok: false, error: '未找到该邮箱或用户名对应的账号' });
      const storedAnswer = user.security_a;
      if (!storedAnswer) return res.json({ ok: false, error: '该账号未设置密保，无法找回' });
      if (!verifyPasswordSync(securityAnswer, storedAnswer)) return res.json({ ok: false, error: '密保答案错误' });
      db.prepare("UPDATE users SET password=? WHERE username=?").run(hashPasswordSync(newPassword), user.username);
      res.json({ ok: true, message: '密码已重置，请使用新密码登录', username: user.username });
    } catch(e) { res.json({ ok: false, error: '重置失败: ' + e.message }); }
  });

  app.post('/api/auth/forgot-password-query', authLimiter, (req, res) => {
    const { input } = req.body;
    if (!input) return res.json({ ok: false, error: '请输入用户名、邮箱或手机号' });
    try {
      const user = db.prepare("SELECT username, email, security_q FROM users WHERE username=? OR email=? OR phone=?").get(input, input, input);
      if (!user) return res.json({ ok: false, error: '未找到该邮箱或用户名对应的账号' });
      if (!user.security_q) return res.json({ ok: false, error: '该账号未设置密保，无法找回' });
      res.json({ ok: true, username: user.username, email: user.email, securityQ: user.security_q });
    } catch(e) { res.json({ ok: false, error: '查询失败: ' + e.message }); }
  });

  app.post('/api/user/update-profile', (req, res) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return res.json({ ok: false, error: '未登录' });
    try {
      const payload = verifyToken(token);
      const { email, oldPassword, newPassword } = req.body;
      const user = db.prepare("SELECT password FROM users WHERE username=?").get(payload.username);
      if (!user) return res.json({ ok: false, error: '用户不存在' });
      if (!verifyPasswordSync(oldPassword, user.password)) return res.json({ ok: false, error: '当前密码错误' });
      if (email) db.prepare("UPDATE users SET email=? WHERE username=?").run(email, payload.username);
      if (newPassword) db.prepare("UPDATE users SET password=? WHERE username=?").run(hashPasswordSync(newPassword), payload.username);
      res.json({ ok: true, message: '已保存' });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/admin/balances', async (req, res) => {
    const results = {};
    const check = async (name, url, headers, parseFn) => {
      try {
        const r = await fetch(url, { headers, signal: AbortSignal.timeout(10000) });
        if (!r.ok) return { balance: 0, unit: '元', status: 'down', error: `HTTP ${r.status}` };
        const d = await r.json();
        return parseFn ? parseFn(d) : { balance: 0, unit: '元', status: 'ok' };
      } catch(e) { return { balance: 0, unit: '元', status: 'down', error: e.message }; }
    };
    if (process.env.DEEPSEEK_API_KEY) {
      results.deepseek = await check('DeepSeek', 'https://api.deepseek.com/user/balance', { Authorization: `Bearer ${process.env.DEEPSEEK_API_KEY}` }, d => { const bal = (d.balance_infos || []).reduce((s, b) => s + parseFloat(b.total_balance || 0), 0); return { balance: bal.toFixed(2), unit: '元', status: bal > 1 ? 'ok' : 'low' }; });
    }
    if (process.env.SILICONFLOW_API_KEY) {
      results.siliconflow = await check('SiliconFlow', 'https://api.siliconflow.cn/v1/user/info', { Authorization: `Bearer ${process.env.SILICONFLOW_API_KEY}` }, d => { const bal = d.data?.balance || d.balance || 0; return { balance: parseFloat(bal).toFixed(2), unit: '元', status: bal > 5 ? 'ok' : 'low' }; });
    }
    if (process.env.OPENROUTER_API_KEY) {
      results.openrouter = await check('OpenRouter', 'https://openrouter.ai/api/v1/auth/key', { Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}` }, d => { const bal = d.data?.credits || 0; return { balance: parseFloat(bal).toFixed(2), unit: '$', status: bal > 0.5 ? 'ok' : 'low' }; });
    }
    res.json({ ok: true, balances: results, updated: new Date().toISOString() });
  });

  app.post('/api/admin/auth', authLimiter, (req, res) => {
    const { password } = req.body || {};
    if (password === process.env.ADMIN_PASSWORD) {
      res.json({ ok: true, token: Buffer.from(password + ':' + Date.now()).toString('base64') });
    } else {
      res.json({ ok: false, error: '密码错误' });
    }
  });
};
