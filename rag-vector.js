/**
 * Agentic RAG v2: 向量语义检索 + Chunk切分
 * 作为 server.js 的扩展加载
 * require('./rag-vector');
 */

const EMBEDDING_MODEL = 'text-embedding-3-small';
const CHUNK_MAX_LEN = 500;
const CHUNK_OVERLAP = 100;

// ============================================================
// Embedding API
// ============================================================
async function getEmbedding(text) {
  const apiKey = process.env.DMXAPI_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) return null;
  try {
    const r = await fetch('https://www.dmxapi.cn/v1/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey },
      body: JSON.stringify({ model: EMBEDDING_MODEL, input: text }),
      signal: AbortSignal.timeout(10000)
    });
    if (!r.ok) return null;
    const d = await r.json();
    return d.data && d.data[0] && d.data[0].embedding;
  } catch(e) {
    return null;
  }
}

// ============================================================
// 余弦相似度
// ============================================================
function cosineSimilarity(a, b) {
  if (!a || !b || a.length !== b.length || a.length === 0) return 0;
  var dot = 0, nA = 0, nB = 0;
  for (var i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    nA += a[i] * a[i];
    nB += b[i] * b[i];
  }
  var denom = Math.sqrt(nA) * Math.sqrt(nB);
  return denom === 0 ? 0 : dot / denom;
}

// ============================================================
// 滑动窗口切分
// ============================================================
function chunkText(text, maxLen, overlap) {
  maxLen = maxLen || CHUNK_MAX_LEN;
  overlap = overlap || CHUNK_OVERLAP;
  var chunks = [];
  if (!text || text.length <= maxLen) {
    if (text) chunks.push(text);
    return chunks;
  }
  var start = 0;
  while (start < text.length) {
    var end = Math.min(start + maxLen, text.length);
    if (end < text.length) {
      var nextPeriod = text.indexOf(String.fromCharCode(12290), end - 50); // Chinese period
      if (nextPeriod > 0 && nextPeriod < end + 50) {
        end = nextPeriod + 1;
      } else {
        var nextNewline = text.indexOf('\n', end - 30);
        if (nextNewline > 0 && nextNewline < end + 30) {
          end = nextNewline + 1;
        }
      }
    }
    var chunk = text.substring(start, end).trim();
    if (chunk.length > 10) chunks.push(chunk);
    start = end - overlap;
    if (start >= text.length - overlap) break;
  }
  return chunks;
}

// ============================================================
// 向量化指定知识条目
// ============================================================
async function reindexKnowledge(km, id) {
  if (!km || !km.exec) return;
  try {
    var r = km.exec('SELECT id, title, content FROM knowledge_base WHERE id=?', [id]);
    if (!r.length || !r[0].values || !r[0].values.length) return;
    var row = r[0].values[0];
    var fullText = (row[1] || '') + '\n' + (row[2] || '');
    var chunks = chunkText(fullText);
    km.run('DELETE FROM knowledge_chunks WHERE knowledge_id=?', [id]);
    for (var i = 0; i < chunks.length; i++) {
      var emb = await getEmbedding(chunks[i]);
      var embStr = emb ? JSON.stringify(emb) : '';
      km.run('INSERT INTO knowledge_chunks (knowledge_id, chunk_text, chunk_order, embedding) VALUES (?,?,?,?)',
        [id, chunks[i], i, embStr]);
    }
    console.log('[RAG] Reindexed knowledge #' + id + ': ' + chunks.length + ' chunks');
  } catch(e) {
    console.error('[RAG] Reindex error:', e.message);
  }
}

// 向量搜索路由（注册到 Express app，早于 404 处理器）
// db 在请求时通过 global.__rag_db 延迟获取
function registerRoutes(app) {
  if (!app) return;
  // Only reindex endpoint - search is handled by server.js delegator
  app.post('/api/knowledge/reindex', function(req, res) {
    res.json({ ok: true, message: 'Reindex started in background' });
    var localDB = global.__rag_db;
    if (!localDB) return;
    // Run async reindex
    setTimeout(function() {
      try {
        var r = localDB.exec('SELECT id FROM knowledge_base');
        if (r.length && r[0].values) {
          for (var i = 0; i < r[0].values.length; i++) {
            reindexKnowledge(localDB, r[0].values[i][0]);
          }
          console.log('[RAG] Full reindex complete: ' + r[0].values.length + ' items');
        }
      } catch(e) {
        console.error('[RAG] Full reindex error:', e.message);
      }
    }, 100);
  });

  console.log('[RAG] Vector search routes registered');
}

// ============================================================
// 关键词搜索后备方案
// ============================================================

// ============================================================
// 关键词搜索后备方案
// ============================================================
function doKeywordSearch(db, query, topK, res) {
  try {
    var result = db.exec('SELECT id, title, content, category, tags FROM knowledge_base');
    if (!result.length || !result[0].values || !result[0].values.length) {
      return res.json({ ok: true, results: [], query: query, mode: 'keyword' });
    }
    var items = result[0].values.map(function(r) {
      return { id: r[0], title: r[1], content: r[2], category: r[3], tags: r[4] };
    });

    // Simple TF-IDF keyword scoring
    function tokenize(t) {
      var tokens = [];
      var en = (t || '').toLowerCase().match(/[a-zA-Z0-9_]+/g) || [];
      for (var i = 0; i < en.length; i++) tokens.push(en[i]);
      var cn = (t || '').replace(/[a-zA-Z0-9_\s]+/g, '');
      for (var j = 0; j < cn.length; j++) {
        tokens.push(cn[j]);
        if (j < cn.length - 1) tokens.push(cn[j] + cn[j + 1]);
      }
      return tokens;
    }

    var qt = new Set(tokenize(query));
    var scored = items.map(function(item) {
      var docText = item.title + ' ' + item.tags + ' ' + item.content;
      var dt = new Set(tokenize(docText));
      var score = 0;
      qt.forEach(function(t) {
        if (dt.has(t)) score++;
      });
      if (item.title.toLowerCase().indexOf(query.toLowerCase()) >= 0) score += 3;
      if ((item.tags || '').indexOf(query) >= 0) score += 2;
      return { item: item, score: score };
    });

    scored.sort(function(a, b) { return b.score - a.score; });
    var results = scored.slice(0, topK).filter(function(s) { return s.score > 0; }).map(function(s) {
      return { id: s.item.id, title: s.item.title, content: (s.item.content || '').substring(0, 800), category: s.item.category, tags: s.item.tags, score: s.score, from: 'keyword' };
    });
    res.json({ ok: true, results: results, query: query, mode: results.length > 0 ? 'keyword' : 'none' });
  } catch(e) {
    res.json({ ok: false, error: e.message, results: [] });
  }
}

// ============================================================
// 初始化：挂载到知识新增端点
// ============================================================
function initRAGHooks(app, db) {
  setupRAGVectorSearch(app, db);

  // Patch knowledge add to auto-index
  var originalPost = null;
  if (app._router && app._router.stack) {
    for (var i = 0; i < app._router.stack.length; i++) {
      var layer = app._router.stack[i];
      if (layer.route && layer.route.path === '/api/knowledge' && layer.route.methods.post) {
        var handleFn = layer.route.stack[0].handle;
        originalPost = handleFn;
        // Wrap the handler to also vectorize
        layer.route.stack[0].handle = function(req, res) {
          // Call original
          var jsonSend = res.json.bind(res);
          res.json = function(body) {
            if (body && body.ok && body.id) {
              setImmediate(function() {
                reindexKnowledge(db, body.id).catch(function(e) {});
              });
            }
            jsonSend(body);
          };
          handleFn(req, res);
        };
        console.log('[RAG] Knowledge add auto-index hook installed');
        break;
      }
    }
  }
}

module.exports = { getEmbedding, cosineSimilarity, chunkText, reindexKnowledge, registerRoutes };
