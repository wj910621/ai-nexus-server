/**
 * Y·NEX Desktop — 最小内置 Agent（回退方案）
 * 当外部 agent-engine-v2.js 不可用时使用
 */

class ToolRegistry {
  constructor() {
    this._tools = new Map();
    this._initBuiltins();
  }

  define(name, config) { this._tools.set(name, { name, ...config }); return this; }
  get(name) { return this._tools.get(name); }
  list() { return Array.from(this._tools.values()).map(t => ({ name: t.name, description: t.description })); }
  async execute(name, args, ctx) { const t = this._tools.get(name); if (!t) throw new Error('Tool not found: ' + name); return await t.handler(args, ctx); }

  _initBuiltins() {
    const fs = require('fs');
    const path = require('path');

    this.define('web_search', {
      description: '搜索网络信息',
      handler: async (a) => {
        try {
          const r = await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(a.query)}&format=json&no_html=1`);
          const d = await r.json();
          return { success: true, results: (d.RelatedTopics||[]).slice(0,a.count||5).map(x => ({ title:x.Text?.substring(0,80)||'', snippet:x.Text||'', url:x.FirstURL||'' })) };
        } catch(e) { return { success: false, error: e.message }; }
      }
    });

    this.define('file_read', {
      description: '读取文件',
      handler: async (a, ctx) => {
        const ws = ctx?.workspace || process.cwd();
        const fp = path.resolve(ws, a.path);
        if (!fp.startsWith(path.resolve(ws))) return { success: false, error: '权限拒绝' };
        try { const c = fs.readFileSync(fp,'utf-8'); return { success: true, content: c }; } catch(e) { return { success: false, error: e.message }; }
      }
    });

    this.define('file_write', {
      description: '写入文件',
      handler: async (a, ctx) => {
        const ws = ctx?.workspace || process.cwd();
        const fp = path.resolve(ws, a.path);
        if (!fp.startsWith(path.resolve(ws))) return { success: false, error: '权限拒绝' };
        try { fs.mkdirSync(path.dirname(fp),{recursive:true}); fs.writeFileSync(fp,a.content,'utf-8'); return { success: true }; } catch(e) { return { success: false, error: e.message }; }
      }
    });
  }
}

module.exports = { ToolRegistry };
