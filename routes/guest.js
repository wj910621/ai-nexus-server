const { db } = require('../server');

module.exports = function(app) {
  app.post('/api/guest/sync', (req, res) => {
    try {
      const { username, password, deviceFp } = req.body;
      if (!username || !password) return res.json({ ok: false, error: '请提供用户名和密码' });
      const user = db.prepare("SELECT username, password, credits, role, ref_code FROM users WHERE username=? OR email=?").get(username, username);
      if (user) {
        const bcrypt = require('bcryptjs');
        const isBcryptHash = (h) => typeof h === 'string' && (h.startsWith('$2a$') || h.startsWith('$2b$'));
        const btoaPwd = (p) => Buffer.from(p).toString('base64');
        const verifyPasswordSync = (p, s) => isBcryptHash(s) ? bcrypt.compareSync(p, s) : s === btoaPwd(p);
        if (!verifyPasswordSync(password, user.password)) return res.json({ ok: false, error: '密码错误' });
        return res.json({ ok: true, exists: true, user: { username: user.username, credits: user.credits, role: user.role, refCode: user.ref_code } });
      }
      const clientIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
      const ipRow = db.prepare("SELECT COUNT(*) as cnt FROM users WHERE register_ip=?").get(clientIP);
      const currentCount = ipRow ? ipRow.cnt : 0;
      if (currentCount >= 2) return res.json({ ok: false, error: '本网络已注册过 2 个账号，已达到上限' });
      if (deviceFp && deviceFp.length >= 8) {
        const fpRow = db.prepare("SELECT COUNT(*) as cnt FROM users WHERE device_fp=?").get(deviceFp);
        const currentFpCount = fpRow ? fpRow.cnt : 0;
        if (currentFpCount >= 1) return res.json({ ok: false, error: '该设备已注册过账号，每个设备限注册一个账号' });
      }
      const refCodeGen = 'J3' + username.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6) + Math.random().toString(36).slice(2, 5).toUpperCase();
      const email = 'noemail_' + username + '@nexus-hub.local';
      db.prepare("INSERT INTO users (username, email, password, credits, ref_code, register_ip, device_fp) VALUES (?,?,?,?,?,?,?)").run(
        username, email, require('bcryptjs').hashSync(password, 10), 30, refCodeGen, clientIP, deviceFp || '');
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, 30, '注册赠送');
      const apiKey = 'nexus-' + username.substring(0,4).toLowerCase() + '-' + require('crypto').randomBytes(6).toString('hex');
      db.prepare("INSERT INTO api_keys (username, key_name, api_key, quota) VALUES (?,?,?,?)").run(username, '默认Key', apiKey, 0);
      res.json({ ok: true, exists: false, user: { username, credits: 30, role: 'user', refCode: refCodeGen }, apiKey });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/guest/spend', (req, res) => {
    const { username, amount } = req.body;
    if (!username || !amount || amount <= 0) return res.json({ ok: false, error: '参数无效' });
    try {
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
};
