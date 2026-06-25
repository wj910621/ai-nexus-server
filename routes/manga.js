const { db } = require('../server');

module.exports = function(app) {
  app.get('/api/manga', (req, res) => {
    try {
      const manga = db.prepare("SELECT id, title, author, description, cover, status, created_at FROM manga ORDER BY created_at DESC").all();
      res.json({ ok: true, manga: manga.map(r => ({ id: r.id, title: r.title, author: r.author, description: r.description, cover: r.cover, status: r.status, createdAt: r.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/manga/:id', (req, res) => {
    try {
      const r = db.prepare("SELECT * FROM manga WHERE id=?").get(req.params.id);
      if (!r) return res.json({ ok: false, error: '漫画不存在' });
      res.json({ ok: true, manga: { id: r.id, title: r.title, author: r.author, description: r.description, cover: r.cover, status: r.status, createdAt: r.created_at } });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/manga', (req, res) => {
    const { title, author, description, cover, status } = req.body;
    if (!title) return res.json({ ok: false, error: '漫画标题必填' });
    try {
      const result = db.prepare("INSERT INTO manga (title, author, description, cover, status) VALUES (?,?,?,?,?)").run(
        title, author || '', description || '', cover || '', status || 'ongoing');
      res.json({ ok: true, id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/manga/:id', (req, res) => {
    const { title, author, description, cover, status } = req.body;
    try {
      if (title !== undefined) db.prepare("UPDATE manga SET title=? WHERE id=?").run(title, req.params.id);
      if (author !== undefined) db.prepare("UPDATE manga SET author=? WHERE id=?").run(author, req.params.id);
      if (description !== undefined) db.prepare("UPDATE manga SET description=? WHERE id=?").run(description, req.params.id);
      if (cover !== undefined) db.prepare("UPDATE manga SET cover=? WHERE id=?").run(cover, req.params.id);
      if (status !== undefined) db.prepare("UPDATE manga SET status=? WHERE id=?").run(status, req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/manga/:id', (req, res) => {
    try {
      db.prepare("DELETE FROM manga WHERE id=?").run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });
};
