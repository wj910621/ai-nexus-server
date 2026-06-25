const { db, getApiKey, MODEL_CONFIG } = require('../server');

module.exports = function(app) {
  app.post('/v1/chat/completions', async (req, res) => {
    const authHeader = req.headers.authorization || '';
    const apiKey = authHeader.replace('Bearer ', '');
    if (!apiKey || apiKey.length < 10) return res.status(401).json({ error: { message: '缺少 API Key', type: 'auth_error' } });

    let username = null;
    let userCredits = 0;
    try {
      const keyResult = db.prepare(
        "SELECT a.username, a.active, u.credits FROM api_keys a JOIN users u ON a.username=u.username WHERE a.api_key=?"
      ).get(apiKey);
      if (!keyResult) return res.status(401).json({ error: { message: '无效的 API Key', type: 'auth_error' } });
      if (!keyResult.active) return res.status(403).json({ error: { message: 'API Key 已被禁用', type: 'auth_error' } });
      username = keyResult.username;
      userCredits = keyResult.credits || 0;
    } catch(e) { return res.status(401).json({ error: { message: '验证失败', type: 'auth_error' } }); }

    const { model, messages, stream } = req.body;
    if (!model || !messages) return res.status(400).json({ error: { message: '缺少 model 或 messages', type: 'invalid_request' } });
    const modelId = model;
    const creditCost = 1;
    if (userCredits < creditCost) return res.status(402).json({ error: { message: '积分不足', type: 'insufficient_credits' } });

    let config = MODEL_CONFIG[modelId];
    if (!config) {
      if (modelId.startsWith('or_')) {
        const key = process.env.OPENROUTER_API_KEY;
        if (key) config = { provider: 'openai', model: modelId.replace(/^or_/, ''), baseUrl: 'https://openrouter.ai/api/v1' };
      } else if (modelId.startsWith('sf_')) {
        const key = process.env.SILICONFLOW_API_KEY;
        if (key) config = { provider: 'openai', model: modelId.replace(/^sf_/, ''), baseUrl: 'https://api.siliconflow.cn/v1' };
      }
    }
    if (!config) return res.status(400).json({ error: { message: '不支持的模型', type: 'invalid_request' } });

    const providerApiKey = getApiKey(config.provider, modelId);
    if (!providerApiKey) return res.status(500).json({ error: { message: 'API Key 未配置', type: 'server_error' } });

    try {
      const url = `${config.baseUrl}/chat/completions`;
      const body = JSON.stringify({ model: config.model, messages, temperature: 0.7, max_tokens: 4096, stream: !!stream });
      const upstream = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${providerApiKey}` },
        body,
      });
      if (!upstream.ok) {
        const err = await upstream.text();
        return res.status(upstream.status).json({ error: { message: err, type: 'upstream_error' } });
      }
      if (stream) {
        res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        const reader = upstream.body.getReader();
        const decoder = new TextDecoder();
        let done = false;
        while (!done) {
          const { value, done: d } = await reader.read();
          done = d;
          if (value) res.write(decoder.decode(value, { stream: true }));
        }
        res.end();
      } else {
        const data = await upstream.json();
        res.json(data);
      }
      db.prepare("UPDATE users SET credits=credits-? WHERE username=?").run(creditCost, username);
      db.prepare("INSERT INTO credit_log (username, amount, reason) VALUES (?,?,?)").run(username, -creditCost, 'OpenAI API: ' + modelId);
      db.prepare("UPDATE api_keys SET used=used+? WHERE api_key=?").run(creditCost, apiKey);
    } catch (error) {
      res.status(502).json({ error: { message: error.message, type: 'upstream_error' } });
    }
  });

  app.get('/v1/models', (req, res) => {
    const models = Object.entries(MODEL_CONFIG).map(([id, cfg]) => ({
      id, object: 'model', created: 0, owned_by: cfg.provider,
    }));
    res.json({ object: 'list', data: models });
  });
};
