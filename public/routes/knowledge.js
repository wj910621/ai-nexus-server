const { db } = require('../server');

module.exports = function(app) {
  app.get('/api/knowledge', (req, res) => {
    try {
      const category = req.query.category || '';
      let sql = 'SELECT id, title, content, category, tags, source, created_at, updated_at FROM knowledge_base';
      let params = [];
      if (category) { sql += ' WHERE category=?'; params.push(category); }
      sql += ' ORDER BY updated_at DESC';
      const items = db.prepare(sql).all(...params);
      const categories = db.prepare('SELECT DISTINCT category FROM knowledge_base ORDER BY category').all().map(r => r.category);
      res.json({ ok: true, items: items.map(r => ({
        id: r.id, title: r.title, content: r.content, category: r.category, tags: r.tags, source: r.source,
        createdAt: r.created_at, updatedAt: r.updated_at
      })), categories, total: items.length });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/knowledge/:id', (req, res) => {
    try {
      const r = db.prepare('SELECT id, title, content, category, tags, source, created_at, updated_at FROM knowledge_base WHERE id=?').get(req.params.id);
      if (!r) return res.json({ ok: false, error: '不存在' });
      res.json({ ok: true, item: { id: r.id, title: r.title, content: r.content, category: r.category, tags: r.tags, source: r.source, createdAt: r.created_at, updatedAt: r.updated_at } });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/knowledge', (req, res) => {
    const { title, content, category, tags, source } = req.body;
    if (!title || !content) return res.json({ ok: false, error: '标题和内容必填' });
    try {
      const result = db.prepare('INSERT INTO knowledge_base (title, content, category, tags, source) VALUES (?,?,?,?,?)').run(
        title, content, category || 'general', tags || '', source || '');
      res.json({ ok: true, id: result.lastInsertRowid });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.put('/api/knowledge/:id', (req, res) => {
    const { title, content, category, tags, source } = req.body;
    try {
      db.prepare(`UPDATE knowledge_base SET title=?, content=?, category=?, tags=?, source=?, updated_at=datetime('now','localtime') WHERE id=?`).run(
        title, content, category || 'general', tags || '', source || '', req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.delete('/api/knowledge/:id', (req, res) => {
    try {
      db.prepare('DELETE FROM knowledge_base WHERE id=?').run(req.params.id);
      res.json({ ok: true });
    } catch(e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/knowledge/search', (req, res) => {
    const { query, topK } = req.body;
    if (!query) return res.json({ ok: false, error: '缺少 query', results: [] });
    const k = Math.min(topK || 5, 10);
    try {
      const items = db.prepare('SELECT id, title, content, category, tags FROM knowledge_base').all();
      if (!items.length) {
        return res.json({ ok: true, results: [], query });
      }
      function tokenize(text) {
        const tokens = [];
        const enWords = text.toLowerCase().match(/[a-zA-Z0-9_]+/g) || [];
        tokens.push(...enWords);
        const cnChars = text.replace(/[a-zA-Z0-9_\s]+/g, '');
        for (let i = 0; i < cnChars.length; i++) {
          tokens.push(cnChars[i]);
          if (i < cnChars.length - 1) tokens.push(cnChars[i] + cnChars[i + 1]);
        }
        return tokens;
      }
      const totalDocs = items.length;
      const queryTokens = tokenize(query);
      const queryTokenSet = new Set(queryTokens);
      const scored = items.map(item => {
        const docText = `${item.title} ${item.tags} ${item.content}`;
        const docTokens = tokenize(docText);
        const docTokenSet = new Set(docTokens);
        let score = 0;
        for (const qt of queryTokenSet) {
          const queryTF = queryTokens.filter(t => t === qt).length;
          if (docTokenSet.has(qt)) {
            const docsWithTerm = items.filter(i => {
              const t = `${i.title} ${i.tags} ${i.content}`;
              return tokenize(t).includes(qt);
            }).length;
            const idf = Math.log((totalDocs + 1) / (docsWithTerm + 1)) + 1;
            const docTF = docTokens.filter(t => t === qt).length;
            score += queryTF * docTF * idf;
          }
        }
        const titleLower = item.title.toLowerCase();
        for (const qt of queryTokenSet) {
          if (titleLower.includes(qt)) score *= 2.5;
        }
        return { ...item, score };
      });
      const results = scored
        .filter(s => s.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, k)
        .map(s => ({
          id: s.id, title: s.title, content: s.content, category: s.category,
          score: Math.round(s.score * 100) / 100
        }));
      res.json({ ok: true, results, query, total: items.length, matched: results.length });
    } catch(e) {
      res.json({ ok: false, error: e.message, results: [] });
    }
  });
};
