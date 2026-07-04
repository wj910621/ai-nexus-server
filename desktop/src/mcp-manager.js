/**
 * Y·NEX Desktop — MCP Server Manager
 * 真正启动和管理 MCP 服务器（filesystem、browser、sqlite 等）
 * 通过 stdio + JSON-RPC 与 MCP 服务器通信
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class McpManager {
  constructor() {
    this.servers = new Map();   // name -> { proc, tools, pending, buffer, root }
    this._sequence = 0;
  }

  /**
   * 添加并启动 MCP 服务器
   */
  async addServer(name, command, rootPath) {
    if (this.servers.has(name)) {
      return { ok: true, message: `服务器 ${name} 已在运行` };
    }

    const parts = command.split(/\s+/);
    const cmd = parts[0];
    const args = parts.slice(1);

    const ALLOWED_MCP_COMMANDS = ['npx', 'node', 'python', 'python3', 'uv', 'uvx', 'java', 'dotnet'];
    const baseCmd = path.basename(cmd).replace(/\.(exe|cmd|bat)$/i, '');
    if (!ALLOWED_MCP_COMMANDS.includes(baseCmd.toLowerCase())) {
      throw new Error(`安全限制：命令 "${baseCmd}" 不在白名单中`);
    }

    const proc = spawn(cmd, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: rootPath || process.cwd(),
      windowsHide: true,
      env: { ...process.env, PATH: process.env.PATH }
    });

    const server = {
      proc,
      tools: [],
      pending: new Map(),
      buffer: '',
      root: rootPath,
      ready: false,
      error: null,
    };

    proc.stdout.on('data', (data) => {
      server.buffer += data.toString();
      this._parseMessages(name, server);
    });

    proc.stderr.on('data', (data) => {
      console.log(`[MCP ${name}] stderr:`, data.toString().trim());
    });

    proc.on('close', (code) => {
      console.log(`[MCP ${name}] 退出, 码: ${code}`);
      this.servers.delete(name);
    });

    proc.on('error', (err) => {
      console.error(`[MCP ${name}] 启动失败:`, err.message);
      server.error = err.message;
      this.servers.delete(name);
    });

    this.servers.set(name, server);

    // 发送 initialize
    try {
      const initResult = await this._sendRequest(name, 'initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {
          roots: { listChanged: true },
          sampling: {}
        },
        clientInfo: {
          name: 'ynex-desktop',
          version: '2.0.0'
        }
      });

      server.ready = true;
      console.log(`[MCP ${name}] 初始化成功, 协议: ${initResult?.protocolVersion || 'unknown'}`);

      // 发送 initialized 通知
      this._sendNotification(name, 'notifications/initialized', {});

      // 发现工具
      await this._discoverTools(name);
      return { ok: true, message: `服务器 ${name} 已连接`, tools: server.tools };
    } catch (e) {
      proc.kill();
      this.servers.delete(name);
      return { ok: false, error: `初始化失败: ${e.message}` };
    }
  }

  /**
   * 移除 MCP 服务器
   */
  removeServer(name) {
    const server = this.servers.get(name);
    if (!server) return { ok: false, error: '服务器未运行' };
    try {
      server.proc.stdin.end();
      server.proc.kill();
    } catch (e) {}
    this.servers.delete(name);
    return { ok: true };
  }

  /**
   * 调用 MCP 工具
   */
  async callTool(serverName, toolName, args) {
    const server = this.servers.get(serverName);
    if (!server) return { ok: false, error: '服务器未运行' };

    try {
      const result = await this._sendRequest(serverName, 'tools/call', {
        name: toolName,
        arguments: args || {}
      });
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 列出所有服务器和工具
   */
  listAll() {
    const result = [];
    for (const [name, server] of this.servers.entries()) {
      result.push({
        name,
        ready: server.ready,
        tools: server.tools.map(t => t.name),
        error: server.error,
      });
    }
    return result;
  }

  /**
   * 发现工具
   */
  async _discoverTools(name) {
    const server = this.servers.get(name);
    if (!server) return;

    try {
      const result = await this._sendRequest(name, 'tools/list', {});
      server.tools = (result?.tools || []).map(t => ({
        name: t.name,
        description: t.description || '',
        inputSchema: t.inputSchema || {},
      }));
      console.log(`[MCP ${name}] 发现 ${server.tools.length} 个工具:`, server.tools.map(t => t.name).join(', '));
    } catch (e) {
      console.warn(`[MCP ${name}] 工具发现失败:`, e.message);
    }
  }

  /**
   * 列出资源
   */
  async listResources(serverName) {
    try {
      const result = await this._sendRequest(serverName, 'resources/list', {});
      return { ok: true, resources: result?.resources || [] };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * 读取资源
   */
  async readResource(serverName, uri) {
    try {
      const result = await this._sendRequest(serverName, 'resources/read', { uri });
      return { ok: true, contents: result?.contents || [] };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  // ============================================================
  // JSON-RPC 通信
  // ============================================================

  _nextId() {
    return ++this._sequence;
  }

  _sendNotification(serverName, method, params) {
    const server = this.servers.get(serverName);
    if (!server) return;
    const msg = JSON.stringify({ jsonrpc: '2.0', method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg, 'utf-8')}\r\n\r\n`;
    server.proc.stdin.write(header + msg);
  }

  _sendRequest(serverName, method, params) {
    const server = this.servers.get(serverName);
    if (!server) return Promise.reject(new Error(`Server ${serverName} not running`));

    const id = this._nextId();
    const msg = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg, 'utf-8')}\r\n\r\n`;
    server.proc.stdin.write(header + msg);

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        server.pending.delete(id);
        reject(new Error(`${method} 超时`));
      }, 15000);

      server.pending.set(id, { resolve, reject, timeout });
    });
  }

  _parseMessages(serverName, server) {
    while (server.buffer.includes('Content-Length:')) {
      const headerEnd = server.buffer.indexOf('\r\n\r\n');
      if (headerEnd === -1) break;

      const header = server.buffer.substring(0, headerEnd);
      const match = header.match(/Content-Length: (\d+)/);
      if (!match) { server.buffer = ''; break; }

      const contentLength = parseInt(match[1], 10);
      const contentStart = headerEnd + 4;
      const contentEnd = contentStart + contentLength;

      if (server.buffer.length < contentEnd) break;

      const content = server.buffer.substring(contentStart, contentEnd);
      server.buffer = server.buffer.substring(contentEnd);

      try {
        const msg = JSON.parse(content);
        if (msg.id && server.pending.has(msg.id)) {
          const { resolve, reject, timeout } = server.pending.get(msg.id);
          clearTimeout(timeout);
          server.pending.delete(msg.id);
          if (msg.error) reject(new Error(msg.error.message || 'MCP error'));
          else resolve(msg.result);
        }
      } catch (e) {
        console.warn(`[MCP ${serverName}] 解析消息失败:`, e.message);
      }
    }
  }

  /**
   * 清理所有服务器
   */
  shutdown() {
    for (const [name, server] of this.servers.entries()) {
      try {
        server.proc.stdin.end();
        server.proc.kill();
      } catch (e) {}
    }
    this.servers.clear();
  }
}

module.exports = { McpManager };