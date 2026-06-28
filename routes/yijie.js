/**
 * routes/yijie.js
 * 亿界本地AI 与 ai-nexus-server 云端融合路由
 *
 * 说明：
 * - 亿界服务运行在用户本机 localhost:7777
 * - dashboard 前端通过 CORS 直连本机服务
 * - 云端只负责会员权益、用量统计、远程指令队列
 */
const { db, authRequired } = require('../server');
const https = require('https');
const http = require('http');

const YIJIE_PORT = 7777;
const YIJIE_HOST = '127.0.0.1';

module.exports = function(app) {
  // ============================================================
  // 亿界会员/权益状态
  // ============================================================
  app.get('/api/yijie/membership', authRequired, (req, res) => {
    try {
      const user = db.prepare(
        "SELECT username, membership, membership_expires, credits, role FROM users WHERE username=?"
      ).get(req.user.username);
      if (!user) return res.status(404).json({ ok: false, error: '用户不存在' });

      const tiers = {
        free: { name: '免费版', local_llm: true, cloud_sync: false, remote_cmd: false, max_devices: 1 },
        silver: { name: '月度会员', local_llm: true, cloud_sync: true, remote_cmd: true, max_devices: 2 },
        gold: { name: '季度会员', local_llm: true, cloud_sync: true, remote_cmd: true, max_devices: 5 },
        platinum: { name: '年度会员', local_llm: true, cloud_sync: true, remote_cmd: true, max_devices: 10 },
      };

      let tier = tiers[user.membership || 'free'];
      if (user.membership && user.membership !== 'free' && user.membership_expires) {
        if (new Date(user.membership_expires) < new Date()) tier = tiers.free;
      }

      res.json({
        ok: true,
        username: user.username,
        membership: user.membership || 'free',
        expires: user.membership_expires || '',
        credits: user.credits || 0,
        tier: tier,
      });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // ============================================================
  // 上报本地亿界用量/状态（由桌面端或本地服务调用）
  // ============================================================
  app.post('/api/yijie/usage', authRequired, (req, res) => {
    try {
      const { requests, tokens, date } = req.body || {};
      db.exec(`CREATE TABLE IF NOT EXISTS yijie_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        requests INTEGER DEFAULT 0,
        tokens INTEGER DEFAULT 0,
        date TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )`);

      const today = date || new Date().toISOString().split('T')[0];
      const existing = db.prepare(
        "SELECT id FROM yijie_usage WHERE username=? AND date=?"
      ).get(req.user.username, today);

      if (existing) {
        db.prepare(
          "UPDATE yijie_usage SET requests=requests+?, tokens=tokens+?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        ).run(requests || 0, tokens || 0, existing.id);
      } else {
        db.prepare(
          "INSERT INTO yijie_usage (username, requests, tokens, date) VALUES (?,?,?,?)"
        ).run(req.user.username, requests || 0, tokens || 0, today);
      }

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // ============================================================
  // 获取当前用户用量统计
  // ============================================================
  app.get('/api/yijie/usage', authRequired, (req, res) => {
    try {
      db.exec(`CREATE TABLE IF NOT EXISTS yijie_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        requests INTEGER DEFAULT 0,
        tokens INTEGER DEFAULT 0,
        date TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )`);
      const rows = db.prepare(
        "SELECT date, SUM(requests) as requests, SUM(tokens) as tokens FROM yijie_usage WHERE username=? GROUP BY date ORDER BY date DESC LIMIT 30"
      ).all(req.user.username);
      res.json({ ok: true, usage: rows });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // ============================================================
  // 远程指令队列（用于网页端向本地设备下发任务）
  // ============================================================
  app.post('/api/yijie/commands', authRequired, (req, res) => {
    try {
      const { command, params = {} } = req.body || {};
      if (!command) return res.status(400).json({ ok: false, error: '缺少 command' });

      db.exec(`CREATE TABLE IF NOT EXISTS yijie_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        command TEXT NOT NULL,
        params TEXT,
        status TEXT DEFAULT 'pending',
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        executed_at TIMESTAMP
      )`);

      const info = db.prepare(
        "INSERT INTO yijie_commands (username, command, params) VALUES (?,?,?)"
      ).run(req.user.username, command, JSON.stringify(params));

      res.json({ ok: true, command_id: info.lastInsertRowid });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  app.get('/api/yijie/commands', authRequired, (req, res) => {
    try {
      db.exec(`CREATE TABLE IF NOT EXISTS yijie_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        command TEXT NOT NULL,
        params TEXT,
        status TEXT DEFAULT 'pending',
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        executed_at TIMESTAMP
      )`);
      const rows = db.prepare(
        "SELECT id, command, params, status, result, created_at, executed_at FROM yijie_commands WHERE username=? ORDER BY id DESC LIMIT 50"
      ).all(req.user.username);
      res.json({
        ok: true,
        commands: rows.map(r => ({ ...r, params: safeJsonParse(r.params), result: safeJsonParse(r.result) }))
      });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // 本地设备拉取待执行指令
  app.get('/api/yijie/commands/pending', authRequired, (req, res) => {
    try {
      db.exec(`CREATE TABLE IF NOT EXISTS yijie_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        command TEXT NOT NULL,
        params TEXT,
        status TEXT DEFAULT 'pending',
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        executed_at TIMESTAMP
      )`);
      const rows = db.prepare(
        "SELECT id, command, params, created_at FROM yijie_commands WHERE username=? AND status='pending' ORDER BY id ASC LIMIT 10"
      ).all(req.user.username);
      res.json({
        ok: true,
        commands: rows.map(r => ({ ...r, params: safeJsonParse(r.params) }))
      });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // 本地设备上报指令执行结果
  app.post('/api/yijie/commands/:id/result', authRequired, (req, res) => {
    try {
      const { result, status = 'done' } = req.body || {};
      db.prepare(
        "UPDATE yijie_commands SET status=?, result=?, executed_at=CURRENT_TIMESTAMP WHERE id=? AND username=?"
      ).run(status, JSON.stringify(result || {}), req.params.id, req.user.username);
      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // ============================================================
  // 服务端代理：把网页端请求转发到用户本机亿界服务
  // 注意：仅在本机访问时有效；服务器本身无法访问用户 localhost
  // ============================================================
  app.all('/api/yijie/proxy/*', authRequired, (req, res) => {
    const targetPath = req.params[0] || '';
    const query = req.url.split('?')[1] || '';
    const targetUrl = `http://${YIJIE_HOST}:${YIJIE_PORT}/${targetPath}${query ? '?' + query : ''}`;

    const client = targetUrl.startsWith('https') ? https : http;
    const options = {
      method: req.method,
      headers: { 'Content-Type': req.headers['content-type'] || 'application/json' },
      timeout: 30000,
    };

    const proxyReq = client.request(targetUrl, options, (proxyRes) => {
      res.status(proxyRes.statusCode);
      Object.keys(proxyRes.headers).forEach(k => res.setHeader(k, proxyRes.headers[k]));
      proxyRes.pipe(res);
    });

    proxyReq.on('error', (err) => {
      res.status(502).json({ ok: false, error: '无法连接到本机亿界服务', detail: err.message });
    });
    proxyReq.on('timeout', () => {
      proxyReq.destroy();
      res.status(504).json({ ok: false, error: '连接本机亿界服务超时' });
    });

    if (req.body) proxyReq.write(JSON.stringify(req.body));
    proxyReq.end();
  });

  // ============================================================
  // 管理后台统计
  // ============================================================
  app.get('/api/admin/yijie/stats', authRequired, (req, res) => {
    if (req.user.role !== 'admin') return res.status(403).json({ ok: false, error: '无权限' });
    try {
      const totalUsers = db.prepare("SELECT COUNT(DISTINCT username) as cnt FROM yijie_usage").get().cnt || 0;
      const today = new Date().toISOString().split('T')[0];
      const todayReqs = db.prepare("SELECT SUM(requests) as cnt FROM yijie_usage WHERE date=?").get(today).cnt || 0;
      res.json({ ok: true, totalUsers, todayRequests: todayReqs });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });
};

function safeJsonParse(s) {
  try { return JSON.parse(s); } catch (e) { return s; }
}
