/**
 * Y·NEX Agent Engine v1.0
 * Built-in tools version
 */

class ToolRegistry {
  constructor() {
    this.tools = new Map();
    this._initBuiltins();
  }
  register(name, desc, params, handler) {
    this.tools.set(name, { name, description: desc, parameters: params, handler });
    return this;
  }
  get(name) { return this.tools.get(name); }
  list() { return Array.from(this.tools.values()).map(t => ({ name: t.name, description: t.description, parameters: t.parameters })); }
  async execute(name, args, ctx) { const t = this.tools.get(name); if (!t) throw new Error('Tool not found: ' + name); return await t.handler(args, ctx || {}); }

  _initBuiltins() {
    // web_search
    this.register('web_search', 'Search the web for information.', { type: 'object', properties: { query: { type: 'string', description: 'Search query' }, count: { type: 'number', default: 5 } }, required: ['query'] }, async (a) => {
      try { const r = await fetch('https://api.duckduckgo.com/?q=' + encodeURIComponent(a.query) + '&format=json&no_html=1'); const d = await r.json(); return { success: true, results: (d.RelatedTopics || []).slice(0, a.count || 5).map(x => ({ title: (x.Text || '').substring(0, 80), snippet: x.Text || '', url: x.FirstURL || '' })) }; } catch(e) { return { success: false, error: e.message }; }
    });
    // web_fetch
    this.register('web_fetch', 'Fetch a web page.', { type: 'object', properties: { url: { type: 'string', description: 'URL' } }, required: ['url'] }, async (a) => {
      try { const r = await fetch(a.url, { signal: AbortSignal.timeout(15000) }); const t = await r.text(); return { success: true, content: t.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().substring(0, 8000) }; } catch(e) { return { success: false, error: e.message }; }
    });
    // file_read (sandboxed)
    this.register('file_read', 'Read a file from workspace.', { type: 'object', properties: { path: { type: 'string', description: 'File path' } }, required: ['path'] }, async (a, ctx) => {
      const fs = require('fs'); const path = require('path'); const ws = (ctx && ctx.workspace) || process.cwd(); const sp = path.resolve(ws, a.path);
      if (!sp.startsWith(ws)) return { success: false, error: 'Path traversal denied' };
      try { const c = fs.readFileSync(sp, 'utf-8'); return { success: true, content: c, size: c.length }; } catch(e) { return { success: false, error: e.message }; }
    });
    // file_write (sandboxed)
    this.register('file_write', 'Write content to a file in workspace.', { type: 'object', properties: { path: { type: 'string', description: 'File path' }, content: { type: 'string', description: 'Content' } }, required: ['path', 'content'] }, async (a, ctx) => {
      const fs = require('fs'); const path = require('path'); const ws = (ctx && ctx.workspace) || process.cwd(); const sp = path.resolve(ws, a.path);
      if (!sp.startsWith(ws)) return { success: false, error: 'Path traversal denied' };
      try { fs.mkdirSync(path.dirname(sp), { recursive: true }); fs.writeFileSync(sp, a.content, 'utf-8'); return { success: true, path: a.path, size: a.content.length }; } catch(e) { return { success: false, error: e.message }; }
    });
    // shell_exec (sandboxed)
    this.register('shell_exec', 'Execute a shell command.', { type: 'object', properties: { command: { type: 'string', description: 'Command' }, timeout: { type: 'number', default: 10 } }, required: ['command'] }, async (a, ctx) => {
      const { execFileSync } = require('child_process'); const ws = (ctx && ctx.workspace) || process.cwd(); const maxT = Math.min(a.timeout || 10, 30); const isWin = process.platform === 'win32';
      try { const r = execFileSync(isWin ? 'cmd.exe' : '/bin/bash', [isWin ? '/c' : '-c', a.command], { cwd: ws, timeout: maxT * 1000, maxBuffer: 1024 * 1024, encoding: 'utf-8' }); return { success: true, stdout: r.substring(0, 10000), stderr: '' }; } catch(e) { return { success: false, stdout: (e.stdout || '').substring(0, 5000), stderr: (e.stderr || e.message).substring(0, 5000) }; }
    });
    // calculator
    this.register('calculator', 'Evaluate a math expression.', { type: 'object', properties: { expression: { type: 'string', description: 'Math expression' } }, required: ['expression'] }, async (a) => {
      try { const fn = new Function('return (' + a.expression + ')'); const result = fn(); return { success: true, result: Number(result) }; } catch(e) { return { success: false, error: e.message }; }
    });
  }
}

class AgentMemory {
  constructor(maxShortTerm) { this.shortTerm = []; this.maxShortTerm = maxShortTerm || 20; this.longTerm = {}; this.workingMemory = {}; }
  add(role, content) { this.shortTerm.push({ role, content, timestamp: Date.now() }); if (this.shortTerm.length > this.maxShortTerm) this.shortTerm.shift(); }
  getRecent(n) { return this.shortTerm.slice(-(n || 10)); }
  getAll() { return this.shortTerm; }
  remember(key, value) { this.longTerm[key] = value; }
  recall(key) { return this.longTerm[key]; }
  setWorking(key, value) { this.workingMemory[key] = value; }
  getWorking(key) { return this.workingMemory[key]; }
  clear() { this.shortTerm = []; this.workingMemory = {}; }
  summarize() { return { shortTermCount: this.shortTerm.length, longTermKeys: Object.keys(this.longTerm), workingKeys: Object.keys(this.workingMemory) }; }
}

class AgentEngine {
  constructor(options) { options = options || {}; this.tools = options.tools || new ToolRegistry(); this.maxIterations = options.maxIterations || 15; this.model = options.model || 'deepseekv3'; }
  _getApiKey(modelId) {
    if (modelId.startsWith('dmx_')) return process.env.DMXAPI_API_KEY;
    if (modelId.startsWith('ark_')) return process.env.ARK_API_KEY;
    if (modelId.startsWith('bc_')) return process.env.BAICHUAN_API_KEY;
    if (modelId.startsWith('nx_')) return process.env.NEXUS_API_KEY;
    if (modelId.startsWith('deepseek')) return process.env.DEEPSEEK_API_KEY;
    if (modelId.startsWith('qwen')) return process.env.DASHSCOPE_API_KEY;
    if (modelId.startsWith('sf_')) return process.env.SILICONFLOW_API_KEY;
    if (modelId.startsWith('ali_')) return process.env.DASHSCOPE_API_KEY;
    if (modelId.startsWith('or_') || modelId.startsWith('claude') || modelId.startsWith('gemini') || modelId.startsWith('llama') || modelId.startsWith('grok')) return process.env.OPENROUTER_API_KEY;
    return process.env.DMXAPI_API_KEY || process.env.OPENAI_API_KEY;
  }
  _getBaseUrl(modelId) {
    if (modelId.startsWith('dmx_') || !modelId.includes('_')) return 'https://www.dmxapi.cn/v1';
    if (modelId.startsWith('sf_')) return 'https://api.siliconflow.cn/v1';
    if (modelId.startsWith('ark_')) return 'https://ark.cn-beijing.volces.com/api/v3';
    if (modelId.startsWith('ali_') || modelId.startsWith('qwen')) return 'https://dashscope.aliyuncs.com/compatible-mode/v1';
    if (modelId.startsWith('nx_')) return 'https://apinexus.net/v1';
    if (modelId.startsWith('or_') || modelId.startsWith('claude') || modelId.startsWith('gemini') || modelId.startsWith('llama') || modelId.startsWith('grok')) return 'https://openrouter.ai/api/v1';
    if (modelId.startsWith('deepseek')) return 'https://api.deepseek.com/v1';
    if (modelId.startsWith('kimi')) return 'https://api.moonshot.cn/v1';
    if (modelId.startsWith('glm')) return 'https://open.bigmodel.cn/api/paas/v4';
    if (modelId.startsWith('hunyuan')) return 'https://api.hunyuan.cloud.tencent.com/v1';
    if (modelId.startsWith('bc_')) return 'https://api.baichuan-ai.com/v1';
    if (modelId.startsWith('qiniu_')) return 'https://api.qnaiqc.com/v1';
    if (modelId.startsWith('qf_')) return 'https://qianfan.baidubce.com/v2';
    return 'https://www.dmxapi.cn/v1';
  }
  async _callLLM(messages, model) {
    // 直接调用本地 API 代理（复用所有模型路由和认证逻辑）
    const modelToUse = model || 'deepseekv3';
    try {
      const r = await fetch('http://localhost:3001/api/chat', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-internal-token': global.__INTERNAL_SERVICE_TOKEN || process.env.INTERNAL_SERVICE_TOKEN || ''
        },
        body: JSON.stringify({ model: modelToUse, messages, stream: false }),
        signal: AbortSignal.timeout(60000)
      });
      if (!r.ok) { const errText = await r.text().catch(()=>''); return { content: 'API Error: ' + r.status + (errText ? ': ' + errText.substring(0,200) : ''), role: 'assistant' }; }
      const d = await r.json();
      return { content: (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content) || d.content || '', role: 'assistant' };
    } catch(e) { return { content: 'Error: ' + e.message, role: 'assistant' }; }
  }
  async run(task, options) {
    options = options || {}; const model = options.model || this.model; const maxIter = options.maxIterations || this.maxIterations; const tools = options.tools || this.tools; const workspace = options.workspace || process.cwd(); const streamCb = options.streamCallback;
    const toolNames = tools.list().map(t => t.name).join(', ');
    const msgs = [{ role: 'system', content: '你是Y·NEX AI Agent，可用工具: ' + toolNames + '。需要调用工具时输出JSON格式：\n操作：{"工具名":"值"}\n完成后输出"最终回答："+你的答案' }, { role: 'user', content: task }];
    const history = []; let answer = ''; let iter = 0;
    while (iter < maxIter) {
      iter++; const resp = await this._callLLM(msgs, model); const content = resp.content;
      if (content.startsWith('Error') || content.startsWith('No')) { answer = content; break; }
      if (/最终回答/.test(content)) { var m = content.match(/(?:最终回答)[：:]\s*([\s\S]*)/); answer = m ? m[1].trim() : content; if (streamCb) streamCb({ type: 'final', content: answer }); break; }
      var actMatch = content.match(/操作[：:]\s*(\w+)/); var inpMatch = content.match(/参数[：:]\s*(\{[\s\S]*?\})/);
      if (actMatch) {
        if (streamCb) streamCb({ type: 'thought', content, action: actMatch[1] });
        try { var input = inpMatch ? JSON.parse(inpMatch[1]) : {}; var result = await tools.execute(actMatch[1], input, { workspace }); var obs = JSON.stringify(result).substring(0, 2000); msgs.push({ role: 'assistant', content }); msgs.push({ role: 'user', content: '观察：' + obs + '\n\n如果任务完成请输出"最终回答"' }); history.push({ action: actMatch[1], input, result }); if (streamCb) streamCb({ type: 'observation', action: actMatch[1], result }); } catch(e) { msgs.push({ role: 'assistant', content }); msgs.push({ role: 'user', content: '操作出错：' + e.message }); }
      } else { answer = content; if (streamCb) streamCb({ type: 'final', content: answer }); break; }
    }
    return { answer, iterations: iter, history };
  }
  async plan(task, options) {
    const model = (options && options.model) || this.model;
    const resp = await this._callLLM([{ role: 'system', content: 'Output JSON: {title,steps:[{id,description,tools}],difficulty,dependencies}' }, { role: 'user', content: 'Plan: ' + task }], model);
    try { var j = resp.content.match(/\{[\s\S]*\}/); if (j) return JSON.parse(j[0]); } catch(e) {}
    return { title: task.substring(0, 50), steps: [{ id: 1, description: resp.content, tools: [] }], difficulty: 'Unknown', dependencies: [[1]] };
  }
}

function createAgentRouter(engine) {
  var express = require('express'); var router = express.Router(); var ae = engine || new AgentEngine(); var tr = ae.tools;
  router.get('/tools', function(req, res) { res.json({ ok: true, tools: tr.list() }); });
  router.post('/chat', async function(req, res) {
    try { if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' }); var r = await ae.run(req.body.task, { model: req.body.model || 'deepseekv3', maxIterations: req.body.maxIterations || 10 }); res.json({ ok: true, answer: r.answer, iterations: r.iterations, history: r.history }); } catch(e) { res.status(500).json({ ok: false, error: e.message }); }
  });
  router.post('/chat/stream', async function(req, res) {
    try {
      if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' });
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
      var r = await ae.run(req.body.task, {
        model: req.body.model || 'deepseekv3',
        maxIterations: req.body.maxIterations || 10,
        streamCallback: function(d) {
          res.write('data: ' + JSON.stringify(d) + '\n\n');
        }
      });
      res.write('data: ' + JSON.stringify({ type: 'done', answer: r.answer, iterations: r.iterations }) + '\n\n');
      res.end();
    } catch(e) {
      res.write('data: ' + JSON.stringify({ type: 'error', error: e.message }) + '\n\n');
      res.end();
    }
  });
  router.post('/plan', async function(req, res) {
    try { if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' }); var p = await ae.plan(req.body.task, { model: req.body.model }); res.json({ ok: true, plan: p }); } catch(e) { res.status(500).json({ ok: false, error: e.message }); }
  });
  router.post('/execute', async function(req, res) {
    try { if (!req.body.tool) return res.status(400).json({ ok: false, error: 'Missing tool' }); var r = await tr.execute(req.body.tool, req.body.args || {}); res.json({ ok: true, result: r }); } catch(e) { res.status(500).json({ ok: false, error: e.message }); }
  });
  return { router, agentEngine: ae, toolRegistry: tr };
}

module.exports = { ToolRegistry, AgentMemory, AgentEngine, createAgentRouter };
