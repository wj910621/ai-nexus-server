/**
 * TriGen MCP Server v1.0
 * Model Context Protocol 标准服务器
 * 将 Agent 引擎的 6 个工具通过 MCP 协议暴露
 * 
 * 启动: node mcp-server.js [--port 3100] [--stdio]
 * 
 * 两种模式:
 *   默认 → HTTP 服务 (端口 3100), 支持 JSON-RPC + SSE
 *   --stdio → stdio 模式, 适合本地 MCP Client 集成
 */

const { ToolRegistry } = require('./agent-engine');

// ============================================================
// MCP 协议消息处理
// ============================================================

class MCPServer {
  constructor(options = {}) {
    this.tools = options.tools || new ToolRegistry();
    this.serverInfo = {
      name: 'trigen-mcp',
      version: '1.0.0'
    };
    this.capabilities = {
      tools: {},
      resources: {},
      prompts: {}
    };
  }

  /**
   * 处理 MCP JSON-RPC 请求
   */
  async handleRequest(request) {
    if (!request || !request.jsonrpc || request.jsonrpc !== '2.0' || !request.method) {
      return this._error(null, -32600, 'Invalid Request: expected jsonrpc 2.0 with method');
    }

    const { id, method, params = {} } = request;

    try {
      switch (method) {
        // ========== 初始化 ==========
        case 'initialize':
          return this._result(id, {
            protocolVersion: '2024-11-05',
            capabilities: this.capabilities,
            serverInfo: this.serverInfo
          });

        // ========== 工具 ==========
        case 'tools/list':
          return this._result(id, {
            tools: this._formatTools()
          });

        case 'tools/call':
          return await this._callTool(id, params);

        // ========== 资源 ==========
        case 'resources/list':
          return this._result(id, { resources: [] });

        // ========== 提示词 ==========
        case 'prompts/list':
          return this._result(id, { prompts: [] });

        // ========== Ping ==========
        case 'ping':
          return this._result(id, {});

        default:
          return this._error(id, -32601, `Method not found: ${method}`);
      }
    } catch (e) {
      return this._error(id, -32603, `Internal error: ${e.message}`);
    }
  }

  /**
   * 格式化工具列表 => MCP 标准格式
   */
  _formatTools() {
    return this.tools.list().map(t => ({
      name: t.name,
      description: t.description,
      inputSchema: t.parameters || {
        type: 'object',
        properties: {},
        required: []
      }
    }));
  }

  /**
   * 调用工具
   */
  async _callTool(id, params) {
    const { name, arguments: args } = params;
    if (!name) {
      return this._error(id, -32602, 'Missing tool name');
    }

    const tool = this.tools.get(name);
    if (!tool) {
      return this._error(id, -32602, `Tool not found: ${name}`);
    }

    try {
      const result = await this.tools.execute(name, args || {}, { workspace: process.cwd() });
      
      // 格式化结果为 MCP 标准 content 数组
      const content = [];
      
      if (typeof result === 'string') {
        content.push({ type: 'text', text: result });
      } else {
        const text = JSON.stringify(result, null, 2);
        content.push({ type: 'text', text });
        
        // 如果有结构化数据，也添加
        if (result.results && Array.isArray(result.results)) {
          content.push({ 
            type: 'text', 
            text: result.results.map((r, i) => 
              `${i+1}. ${r.title || r.name || ''}: ${r.snippet || r.description || ''}`
            ).join('\n')
          });
        }
      }

      return this._result(id, {
        content,
        isError: !result.success
      });
    } catch (e) {
      return this._result(id, {
        content: [{ type: 'text', text: `Error: ${e.message}` }],
        isError: true
      });
    }
  }

  _result(id, result) {
    return { jsonrpc: '2.0', id, result };
  }

  _error(id, code, message) {
    return { jsonrpc: '2.0', id, error: { code, message } };
  }
}

// ============================================================
// HTTP 传输
// ============================================================

function startHTTPServer(port = 3100) {
  const http = require('http');
  const url = require('url');
  const server = new MCPServer();

  const app = http.createServer(async (req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    const parsedUrl = url.parse(req.url, true);
    const pathname = parsedUrl.pathname;

    // GET /health
    if (req.method === 'GET' && pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ 
        status: 'ok', 
        server: 'trigen-mcp',
        tools: server.tools.list().length,
        toolsList: server.tools.list().map(t => t.name)
      }));
      return;
    }

    // GET /tools (for desktop client)
    if (req.method === 'GET' && pathname === '/tools') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        tools: server.tools.list().map(t => ({
          name: t.name,
          description: t.description,
          parameters: t.parameters
        }))
      }));
      return;
    }

    // POST /mcp (MCP JSON-RPC)
    if (req.method === 'POST' && (pathname === '/mcp' || pathname === '/')) {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', async () => {
        try {
          const request = JSON.parse(body);
          const response = await server.handleRequest(request);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(response));
        } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ 
            jsonrpc: '2.0', 
            id: null, 
            error: { code: -32700, message: 'Parse error: ' + e.message } 
          }));
        }
      });
      return;
    }

    // GET / (info)
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      name: 'TriGen MCP Server',
      version: '1.0.0',
      tools: server.tools.list().length,
      endpoints: {
        'POST /mcp': 'MCP JSON-RPC endpoint',
        'GET /tools': 'List available tools',
        'GET /health': 'Health check'
      }
    }));
  });

  app.listen(port, () => {
    console.log(`\n🔌 TriGen MCP Server 已启动`);
    console.log(`   HTTP 模式: http://localhost:${port}`);
    console.log(`   MCP 端点: POST http://localhost:${port}/mcp`);
    console.log(`   工具列表: GET  http://localhost:${port}/tools`);
    console.log(`   可用工具: ${server.tools.list().length} 个`);
    server.tools.list().forEach(t => console.log(`     ◉ ${t.name}: ${t.description.substring(0, 60)}`));
  });

  return app;
}

// ============================================================
// stdio 传输
// ============================================================

function startStdioServer() {
  const server = new MCPServer();
  const readline = require('readline');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  console.error('[MCP] TriGen MCP Server (stdio mode)');
  console.error('[MCP] Tools:', server.tools.list().map(t => t.name).join(', '));

  rl.on('line', async (line) => {
    try {
      const request = JSON.parse(line);
      const response = await server.handleRequest(request);
      console.log(JSON.stringify(response));
    } catch (e) {
      console.error('[MCP] Error:', e.message);
    }
  });

  rl.on('close', () => {
    console.error('[MCP] stdio closed');
    process.exit(0);
  });
}

// ============================================================
// 入口
// ============================================================

if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.includes('--stdio')) {
    startStdioServer();
  } else {
    let port = 3100;
    const portIdx = args.indexOf('--port');
    if (portIdx >= 0 && portIdx < args.length - 1) {
      port = parseInt(args[portIdx + 1]) || 3100;
    }
    startHTTPServer(port);
  }
}

module.exports = { MCPServer, startHTTPServer, startStdioServer };
