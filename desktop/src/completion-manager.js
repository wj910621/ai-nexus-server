/**
 * Y·NEX Desktop — AI 内联代码补全管理器
 * 类似 Copilot 的幽灵文字 (ghost text) inline completion
 */

const { spawn } = require('child_process');
const http = require('http');

class CompletionManager {
  constructor() {
    this.cache = new Map();
    this.pending = new Map();
    this.debounceMs = 300;
  }

  /**
   * 获取代码补全建议
   * @param {string} code - 光标前的代码
   * @param {string} suffix - 光标后的代码
   * @param {string} language - 语言标识
   * @param {string} filePath - 文件路径
   */
  async getCompletion({ code, suffix, language, filePath, maxTokens = 64 }) {
    const cacheKey = `${filePath}:${code.slice(-200)}:${suffix.slice(0, 100)}`;
    if (this.cache.has(cacheKey)) return this.cache.get(cacheKey);

    // 防抖：相同文件的请求合并
    if (this.pending.has(filePath)) {
      return this.pending.get(filePath);
    }

    const promise = this._fetchCompletion({ code, suffix, language, filePath, maxTokens });
    this.pending.set(filePath, promise);

    try {
      const result = await promise;
      if (result) this.cache.set(cacheKey, result);
      return result;
    } finally {
      this.pending.delete(filePath);
    }
  }

  async _fetchCompletion({ code, suffix, language, filePath, maxTokens }) {
    try {
      const prompt = this._buildFimPrompt(code, suffix, language, filePath);
      const result = await this._callYnexApi('/api/code/completion', {
        prompt,
        max_tokens: maxTokens,
        temperature: 0.1,
        stop: ['\n\n\n', '\n\n\n\n']
      });
      return result?.text || '';
    } catch (e) {
      return '';
    }
  }

  _buildFimPrompt(code, suffix, language, filePath) {
    const filename = filePath ? filePath.split(/[\\/]/).pop() : 'code';
    return `你是一个代码补全助手。请根据上下文补全后续代码，只输出补全内容，不要重复已有代码。

文件: ${filename}
语言: ${language}

上下文:
\`\`\`${language}
${code.slice(-2000)}`;
  }

  async _callYnexApi(endpoint, body) {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify(body);
      const req = http.request({
        hostname: '127.0.0.1',
        port: 7777,
        path: endpoint,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        },
        timeout: 5000
      }, (res) => {
        let response = '';
        res.on('data', d => response += d);
        res.on('end', () => {
          try { resolve(JSON.parse(response)); }
          catch { resolve(null); }
        });
      });
      req.on('error', () => resolve(null));
      req.on('timeout', () => { req.destroy(); resolve(null); });
      req.write(data);
      req.end();
    });
  }

  clearCache() {
    this.cache.clear();
    this.pending.clear();
  }
}

module.exports = { CompletionManager };