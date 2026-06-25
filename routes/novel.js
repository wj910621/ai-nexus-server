const { db, authRequired } = require('../server');

module.exports = function(app) {
  app.get('/api/novels', authRequired, (req, res) => {
    try {
      const novels = db.prepare("SELECT id, username, title, type, outline, core, total_words, chapter_count, status, created_at, updated_at FROM novels WHERE username=? ORDER BY updated_at DESC").all(req.user.username);
      res.json({ ok: true, novels: novels.map(v => ({ id: v.id, title: v.title, type: v.type, total_words: v.total_words, chapter_count: v.chapter_count, status: v.status, updated_at: v.updated_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/novels', authRequired, (req, res) => {
    try {
      var { title, type, core } = req.body;
      const result = db.prepare("INSERT INTO novels (username, title, type, core) VALUES (?,?,?,?)").run(req.user.username, title || '未命名作品', type || '', core || '');
      res.json({ ok: true, novel_id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/novels/:id', authRequired, (req, res) => {
    try {
      const nv = db.prepare("SELECT * FROM novels WHERE id=? AND username=?").get(req.params.id, req.user.username);
      if (!nv) return res.json({ ok: false, error: '作品不存在' });
      const chars = db.prepare("SELECT * FROM novel_characters WHERE novel_id=?").all(req.params.id);
      const worlds = db.prepare("SELECT * FROM novel_worlds WHERE novel_id=?").all(req.params.id);
      res.json({ ok: true, novel: { id: nv.id, title: nv.title, type: nv.type, outline: nv.outline, core: nv.core, total_words: nv.total_words, chapter_count: nv.chapter_count, status: nv.status }, characters: chars.map(r => ({ id: r.id, name: r.name, gender: r.gender, age: r.age, appearance: r.appearance, personality: r.personality, background: r.background, goal: r.goal, arc: r.arc, notes: r.notes })), worlds: worlds.map(r => ({ id: r.id, category: r.category, key: r.key, value: r.value })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/novels/:id', authRequired, (req, res) => {
    try {
      var { title, type, outline, core } = req.body;
      if (title !== undefined) db.prepare("UPDATE novels SET title=? WHERE id=? AND username=?").run(title, req.params.id, req.user.username);
      if (type !== undefined) db.prepare("UPDATE novels SET type=? WHERE id=? AND username=?").run(type, req.params.id, req.user.username);
      if (outline !== undefined) db.prepare("UPDATE novels SET outline=? WHERE id=? AND username=?").run(outline, req.params.id, req.user.username);
      if (core !== undefined) db.prepare("UPDATE novels SET core=? WHERE id=? AND username=?").run(core, req.params.id, req.user.username);
      db.prepare("UPDATE novels SET updated_at=datetime('now','localtime') WHERE id=?").run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/novels/:id/characters', authRequired, (req, res) => {
    try {
      const chars = db.prepare("SELECT * FROM novel_characters WHERE novel_id=? ORDER BY id").all(req.params.id);
      res.json({ ok: true, characters: chars.map(r => ({ id: r.id, name: r.name, gender: r.gender, age: r.age, appearance: r.appearance, personality: r.personality, background: r.background, goal: r.goal, arc: r.arc, notes: r.notes })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/novels/:id/characters', authRequired, (req, res) => {
    try {
      var { name, gender, age, appearance, personality, background, goal, arc, notes } = req.body;
      const result = db.prepare("INSERT INTO novel_characters (username, novel_id, name, gender, age, appearance, personality, background, goal, arc, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)").run(req.user.username, req.params.id, name || '新角色', gender || '', age || '', appearance || '', personality || '', background || '', goal || '', arc || '', notes || '');
      res.json({ ok: true, character_id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/characters/:id', authRequired, (req, res) => {
    try {
      var fields = req.body;
      var ALLOWED_COLS = ['name','age','gender','personality','appearance','background','traits','role','status','description','goal','motivation','relationship','notes'];
      Object.keys(fields).forEach(function(k) {
        if(ALLOWED_COLS.indexOf(k)===-1)return;
        db.prepare("UPDATE novel_characters SET " + k + "=? WHERE id=?").run(fields[k], req.params.id);
      });
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/characters/:id', authRequired, (req, res) => {
    try { db.prepare("DELETE FROM novel_characters WHERE id=?").run(req.params.id); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/novels/:id/worlds', authRequired, (req, res) => {
    try {
      var { category, key, value } = req.body;
      const result = db.prepare("INSERT INTO novel_worlds (username, novel_id, category, key, value) VALUES (?,?,?,?,?)").run(req.user.username, req.params.id, category || 'general', key || '', value || '');
      res.json({ ok: true, world_id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/worlds/:id', authRequired, (req, res) => {
    try { db.prepare("DELETE FROM novel_worlds WHERE id=?").run(req.params.id); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/novels/:id/chapters', authRequired, (req, res) => {
    try {
      const chaps = db.prepare("SELECT * FROM novel_chapters WHERE novel_id=? ORDER BY chapter_index").all(req.params.id);
      res.json({ ok: true, chapters: chaps.map(r => ({ id: r.id, index: r.chapter_index, title: r.title, content: r.content, outline: r.outline, word_count: r.word_count })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/novels/:id/chapters', authRequired, (req, res) => {
    try {
      var { title, content, outline, chapter_index } = req.body;
      const result = db.prepare("INSERT INTO novel_chapters (username, novel_id, chapter_index, title, content, outline, word_count) VALUES (?,?,?,?,?,?,?)").run(req.user.username, req.params.id, chapter_index || 0, title || '', content || '', outline || '', (content || '').length);
      res.json({ ok: true, chapter_id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/chapters/:id', authRequired, (req, res) => {
    try {
      var { title, content, outline } = req.body;
      if (content !== undefined) {
        db.prepare("UPDATE novel_chapters SET content=?, word_count=? WHERE id=?").run(content, content.length, req.params.id);
        db.prepare("INSERT INTO novel_chapter_versions (chapter_id, username, version, content, summary) VALUES (?,(SELECT COALESCE(MAX(version),0)+1 FROM novel_chapter_versions WHERE chapter_id=?),?,?)").run(req.params.id, req.params.id, content, title || '');
      }
      if (title !== undefined) db.prepare("UPDATE novel_chapters SET title=? WHERE id=?").run(title, req.params.id);
      if (outline !== undefined) db.prepare("UPDATE novel_chapters SET outline=? WHERE id=?").run(outline, req.params.id);
      db.prepare("UPDATE novel_chapters SET updated_at=datetime('now','localtime') WHERE id=?").run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/chapters/:id/versions', authRequired, (req, res) => {
    try {
      const vers = db.prepare("SELECT * FROM novel_chapter_versions WHERE chapter_id=? ORDER BY version DESC").all(req.params.id);
      res.json({ ok: true, versions: vers.map(r => ({ id: r.id, version: r.version, content: r.content, summary: r.summary, created_at: r.created_at })) });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/chapters/:id', authRequired, (req, res) => {
    try { db.prepare("DELETE FROM novel_chapters WHERE id=?").run(req.params.id); db.prepare("DELETE FROM novel_chapter_versions WHERE chapter_id=?").run(req.params.id); res.json({ ok: true }); } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/novels/:id/export', authRequired, (req, res) => {
    try {
      const nv = db.prepare("SELECT * FROM novels WHERE id=? AND username=?").get(req.params.id, req.user.username);
      if (!nv) return res.status(404).json({ ok: false, error: '作品不存在' });
      const chaps = db.prepare("SELECT * FROM novel_chapters WHERE novel_id=? ORDER BY chapter_index").all(req.params.id);
      var text = '《' + nv.title + '》\n\n';
      if (chaps.length) { chaps.forEach(function(ch, i) { text += '第' + (i+1) + '章 ' + (ch.title||'') + '\n\n' + (ch.content||'') + '\n\n'; }); }
      res.setHeader('Content-Type', 'text/plain; charset=utf-8');
      res.setHeader('Content-Disposition', 'attachment; filename="' + nv.title + '.txt"');
      res.send(text);
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/novels/:id', authRequired, (req, res) => {
    try {
      var nid = req.params.id;
      db.prepare("DELETE FROM novels WHERE id=? AND username=?").run(nid, req.user.username);
      db.prepare("DELETE FROM novel_characters WHERE novel_id=?").run(nid);
      db.prepare("DELETE FROM novel_worlds WHERE novel_id=?").run(nid);
      const chs = db.prepare("SELECT id FROM novel_chapters WHERE novel_id=?").all(nid);
      if (chs.length) { chs.forEach(function(ch) { db.prepare("DELETE FROM novel_chapter_versions WHERE chapter_id=?").run(ch.id); }); }
      db.prepare("DELETE FROM novel_chapters WHERE novel_id=?").run(nid);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });
};
