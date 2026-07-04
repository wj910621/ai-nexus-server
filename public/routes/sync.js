const { db, authRequired } = require('../server');

module.exports = function(app) {
  app.get('/api/sync/history', authRequired, (req, res) => {
    try {
      const history = db.prepare("SELECT * FROM sync_history WHERE username=? ORDER BY created_at DESC LIMIT 50").all(req.user.username);
      res.json({ ok: true, history: history.map(r => ({ id: r.id, data: r.data, createdAt: r.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/sync/history', authRequired, (req, res) => {
    try {
      const { data } = req.body;
      db.prepare("INSERT INTO sync_history (username, data) VALUES (?,?)").run(req.user.username, JSON.stringify(data));
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/sync/history/:id', authRequired, (req, res) => {
    try {
      const r = db.prepare("SELECT * FROM sync_history WHERE id=? AND username=?").get(req.params.id, req.user.username);
      if (!r) return res.json({ ok: false, error: '记录不存在' });
      res.json({ ok: true, data: JSON.parse(r.data) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/sync/history/:id', authRequired, (req, res) => {
    try {
      db.prepare("DELETE FROM sync_history WHERE id=? AND username=?").run(req.params.id, req.user.username);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });
};
