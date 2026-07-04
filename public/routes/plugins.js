const { db } = require('../server');

module.exports = function(app) {
  app.get('/api/plugins', (req, res) => {
    try {
      const plugins = db.prepare("SELECT id, name, version, description, author, enabled, config, created_at FROM plugins ORDER BY id").all();
      res.json({ ok: true, plugins: plugins.map(r => ({ id: r.id, name: r.name, version: r.version, description: r.description, author: r.author, enabled: r.enabled, config: r.config, createdAt: r.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/plugins/:id', (req, res) => {
    try {
      const r = db.prepare("SELECT * FROM plugins WHERE id=?").get(req.params.id);
      if (!r) return res.json({ ok: false, error: '插件不存在' });
      res.json({ ok: true, plugin: { id: r.id, name: r.name, version: r.version, description: r.description, author: r.author, enabled: r.enabled, config: r.config, createdAt: r.created_at } });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/plugins', (req, res) => {
    const { name, version, description, author, config } = req.body;
    if (!name) return res.json({ ok: false, error: '插件名称必填' });
    try {
      const result = db.prepare("INSERT INTO plugins (name, version, description, author, config) VALUES (?,?,?,?,?)").run(
        name, version || '1.0', description || '', author || '', config || '{}');
      res.json({ ok: true, id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/plugins/:id', (req, res) => {
    const { name, version, description, author, enabled, config } = req.body;
    try {
      if (name !== undefined) db.prepare("UPDATE plugins SET name=? WHERE id=?").run(name, req.params.id);
      if (version !== undefined) db.prepare("UPDATE plugins SET version=? WHERE id=?").run(version, req.params.id);
      if (description !== undefined) db.prepare("UPDATE plugins SET description=? WHERE id=?").run(description, req.params.id);
      if (author !== undefined) db.prepare("UPDATE plugins SET author=? WHERE id=?").run(author, req.params.id);
      if (enabled !== undefined) db.prepare("UPDATE plugins SET enabled=? WHERE id=?").run(enabled ? 1 : 0, req.params.id);
      if (config !== undefined) db.prepare("UPDATE plugins SET config=? WHERE id=?").run(config, req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/plugins/:id', (req, res) => {
    try {
      db.prepare("DELETE FROM plugins WHERE id=?").run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });
};
