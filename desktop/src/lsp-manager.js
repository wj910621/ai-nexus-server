/**
 * Y·NEX Desktop — LSP Language Server Manager
 * 为 IDE 提供真实的语言服务器支持：
 *   - pyright (Python)    → 跳转定义、诊断、悬停
 *   - typescript-language-server (JS/TS) → 同上
 *   - 自动检测 npm 全局安装的语言服务器
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class LspManager {
  constructor() {
    this.servers = new Map();   // fileExt -> { process, pending, capabilities }
    this.diagnostics = new Map(); // filePath -> diagnostics[]
    this._serverCache = new Map(); // serverName -> path
    this._sequence = 0;
    this._detectDone = false;
  }

  /**
   * 检测可用的语言服务器
   */
  autoDetect() {
    if (this._detectDone) return;
    this._detectDone = true;

    // 检测 pyright
    if (this._findCommand('pyright-langserver')) {
      this._serverCache.set('pyright', 'pyright-langserver --stdio');
    } else if (this._findCommand('pyright')) {
      this._serverCache.set('pyright', 'pyright --stdio');
    }

    // 检测 typescript-language-server
    if (this._findCommand('typescript-language-server')) {
      this._serverCache.set('ts-ls', 'typescript-language-server --stdio');
    } else if (this._findCommand('npx')) {
      this._serverCache.set('ts-ls', 'npx -y typescript-language-server --stdio');
    }

    console.log('[LSP] 检测到的服务器:', Array.from(this._serverCache.entries()).map(([k,v]) => `${k}: ${v}`).join(', '));
  }

  _findCommand(cmd) {
    try {
      const result = spawn(process.platform === 'win32' ? 'where' : 'which', [cmd], { shell: true });
      return true;
    } catch (e) {
      return false;
    }
  }

  _findServerPath(cmd) {
    try {
      const result = spawn(process.platform === 'win32' ? 'where' : 'which', [cmd.split(' ')[0]], { shell: true });
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * 根据文件扩展名获取对应的 LSP 服务器 key
   */
  getServerForFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    if (ext === '.py') return 'pyright';
    if (['.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs'].includes(ext)) return 'ts-ls';
    return null;
  }

  /**
   * 启动 LSP 服务器
   */
  async startServer(serverKey, rootPath) {
    if (this.servers.has(serverKey)) return this.servers.get(serverKey);

    const cmdStr = this._serverCache.get(serverKey);
    if (!cmdStr) return null;

    const parts = cmdStr.split(' ');
    const cmd = parts[0];
    const args = parts.slice(1);

    const proc = spawn(cmd, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: rootPath || process.cwd(),
      windowsHide: true
    });

    const server = {
      proc,
      pending: new Map(),
      capabilities: {},
      ready: false,
      buffer: '',
    };

    proc.stdout.on('data', (data) => {
      server.buffer += data.toString();
      this._parseMessages(server);
    });

    proc.stderr.on('data', (data) => {
      console.log(`[LSP ${serverKey}] stderr:`, data.toString().trim());
    });

    proc.on('close', (code) => {
      console.log(`[LSP ${serverKey}] 退出, 码: ${code}`);
      this.servers.delete(serverKey);
    });

    proc.on('error', (err) => {
      console.error(`[LSP ${serverKey}] 启动失败:`, err.message);
      this.servers.delete(serverKey);
    });

    this.servers.set(serverKey, server);

    // 发送 initialize
    const initResult = await this._sendRequest(serverKey, 'initialize', {
      processId: process.pid,
      rootUri: rootPath ? `file:///${rootPath.replace(/\\/g, '/')}` : null,
      workspaceFolders: rootPath ? [{ uri: `file:///${rootPath.replace(/\\/g, '/')}`, name: path.basename(rootPath) }] : null,
      capabilities: {
        textDocument: {
          hover: { contentFormat: ['markdown', 'plaintext'] },
          definition: { linkSupport: true },
          references: {},
          documentSymbol: {},
          completion: { completionItem: { snippetSupport: true } },
          publishDiagnostics: { relatedInformation: true },
        },
        workspace: {
          workspaceFolders: true,
          configuration: true,
        }
      }
    });

    server.capabilities = initResult?.capabilities || {};
    server.ready = true;

    // 发送 initialized
    this._sendNotification(serverKey, 'initialized', {});

    console.log(`[LSP ${serverKey}] 已就绪, 能力:`, Object.keys(server.capabilities).join(','));
    return server;
  }

  /**
   * 请求跳转定义
   */
  async goToDefinition(filePath, line, col, rootPath) {
    const serverKey = this.getServerForFile(filePath);
    if (!serverKey) return { ok: false, error: '不支持该文件类型' };

    const server = this.servers.get(serverKey) || await this.startServer(serverKey, rootPath);
    if (!server) return { ok: false, error: `无法启动 ${serverKey}` };

    // 先同步文件内容
    this._syncDocument(serverKey, filePath);

    const result = await this._sendRequest(serverKey, 'textDocument/definition', {
      textDocument: { uri: this._toUri(filePath) },
      position: { line: line - 1, character: col - 1 }
    });

    if (!result || (Array.isArray(result) && result.length === 0)) {
      return { ok: false, error: '未找到定义' };
    }

    const locations = Array.isArray(result) ? result : [result];
    return {
      ok: true,
      locations: locations.map(loc => ({
        uri: loc.uri,
        path: this._toFilePath(loc.uri),
        line: (loc.range?.start?.line ?? 0) + 1,
        col: (loc.range?.start?.character ?? 0) + 1,
      }))
    };
  }

  /**
   * 请求诊断
   */
  async getDiagnostics(filePath, rootPath) {
    const serverKey = this.getServerForFile(filePath);
    if (!serverKey) return { ok: true, diagnostics: [] };

    const server = this.servers.get(serverKey) || await this.startServer(serverKey, rootPath);
    if (!server) return { ok: true, diagnostics: [] };

    // 同步和打开文件
    this._syncDocument(serverKey, filePath);

    // 等待诊断推送
    return new Promise((resolve) => {
      const diags = this.diagnostics.get(filePath) || [];
      // 如果已有缓存，直接返回
      if (diags.length > 0) {
        resolve({ ok: true, diagnostics: diags });
        return;
      }
      // 等待最多 1 秒
      const start = Date.now();
      const check = () => {
        const d = this.diagnostics.get(filePath) || [];
        if (d.length > 0 || Date.now() - start > 1000) {
          resolve({ ok: true, diagnostics: d });
        } else {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }

  /**
   * 请求悬停
   */
  async hover(filePath, line, col, rootPath) {
    const serverKey = this.getServerForFile(filePath);
    if (!serverKey) return { ok: false, error: '不支持该文件类型' };

    const server = this.servers.get(serverKey) || await this.startServer(serverKey, rootPath);
    if (!server) return { ok: false, error: `无法启动 ${serverKey}` };

    this._syncDocument(serverKey, filePath);

    const result = await this._sendRequest(serverKey, 'textDocument/hover', {
      textDocument: { uri: this._toUri(filePath) },
      position: { line: line - 1, character: col - 1 }
    });

    if (!result) return { ok: false, error: '无悬停信息' };

    const content = result.contents?.value || result.contents?.toString() || '';
    return { ok: true, content };
  }

  /**
   * 请求文档符号
   */
  async documentSymbols(filePath, rootPath) {
    const serverKey = this.getServerForFile(filePath);
    if (!serverKey) return { ok: true, symbols: [] };

    const server = this.servers.get(serverKey) || await this.startServer(serverKey, rootPath);
    if (!server) return { ok: true, symbols: [] };

    this._syncDocument(serverKey, filePath);

    const result = await this._sendRequest(serverKey, 'textDocument/documentSymbol', {
      textDocument: { uri: this._toUri(filePath) }
    });

    return { ok: true, symbols: result || [] };
  }

  /**
   * 同步文档内容到 LSP
   */
  _syncDocument(serverKey, filePath) {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      this._sendNotification(serverKey, 'textDocument/didOpen', {
        textDocument: {
          uri: this._toUri(filePath),
          languageId: this._getLanguageId(filePath),
          version: 1,
          text: content,
        }
      });
    } catch (e) {
      console.warn(`[LSP] 同步文件失败: ${filePath}`, e.message);
    }
  }

  _getLanguageId(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const map = { '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.jsx': 'javascriptreact', '.tsx': 'typescriptreact' };
    return map[ext] || 'plaintext';
  }

  _toUri(filePath) {
    return `file:///${filePath.replace(/\\/g, '/').replace(/^\/+/, '')}`;
  }

  _toFilePath(uri) {
    const filePath = uri.replace(/^file:\/\/\//, '');
    return process.platform === 'win32' ? filePath.replace(/\//g, '\\') : '/' + filePath;
  }

  // ============================================================
  // JSON-RPC 通信
  // ============================================================

  _nextId() {
    return ++this._sequence;
  }

  _sendNotification(serverKey, method, params) {
    const server = this.servers.get(serverKey);
    if (!server) return;
    const msg = JSON.stringify({ jsonrpc: '2.0', method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg, 'utf-8')}\r\n\r\n`;
    server.proc.stdin.write(header + msg);
  }

  _sendRequest(serverKey, method, params) {
    const server = this.servers.get(serverKey);
    if (!server) return Promise.reject(new Error('Server not running'));

    const id = this._nextId();
    const msg = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const header = `Content-Length: ${Buffer.byteLength(msg, 'utf-8')}\r\n\r\n`;
    server.proc.stdin.write(header + msg);

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        server.pending.delete(id);
        reject(new Error(`${method} 超时`));
      }, 10000);

      server.pending.set(id, { resolve, reject, timeout });
    });
  }

  _parseMessages(server) {
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
        this._handleMessage(server, msg);
      } catch (e) {
        console.warn('[LSP] 解析消息失败:', e.message);
      }
    }
  }

  _handleMessage(server, msg) {
    // 响应
    if (msg.id && server.pending.has(msg.id)) {
      const { resolve, reject, timeout } = server.pending.get(msg.id);
      clearTimeout(timeout);
      server.pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message || 'LSP error'));
      else resolve(msg.result);
      return;
    }

    // 通知
    if (msg.method === 'textDocument/publishDiagnostics') {
      const uri = msg.params?.uri;
      if (uri) {
        const filePath = this._toFilePath(uri);
        this.diagnostics.set(filePath, msg.params.diagnostics || []);
      }
    }
  }

  /**
   * 清理所有服务器
   */
  shutdown() {
    for (const [key, server] of this.servers.entries()) {
      try {
        server.proc.stdin.end();
        server.proc.kill();
      } catch (e) {}
    }
    this.servers.clear();
    this.diagnostics.clear();
  }
}

module.exports = { LspManager };