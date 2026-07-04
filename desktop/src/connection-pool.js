/**
 * Y·NEX Desktop — HTTP/2 连接池 + 请求去重合并
 * 复用 HTTP 连接，合并重复请求，避免重复调用
 */

const http = require('http');
const https = require('https');

class ConnectionPool {
  constructor() {
    this.pool = new Map();        // host:port -> { agent, requests, keepAlive }
    this.maxSockets = 10;
    this.maxFreeSockets = 5;
    this.keepAliveMs = 60000;
    this.pending = new Map();     // key -> Promise (请求去重)
    this.stats = { hits: 0, misses: 0, merges: 0, connections: 0 };
  }

  _getAgent(hostname, port, protocol = 'http:') {
    const key = `${hostname}:${port}`;
    if (!this.pool.has(key)) {
      const mod = protocol === 'https:' ? https : http;
      const agent = new mod.Agent({
        keepAlive: true,
        maxSockets: this.maxSockets,
        maxFreeSockets: this.maxFreeSockets,
        keepAliveMsecs: this.keepAliveMs,
        scheduling: 'fifo',
      });
      this.pool.set(key, { agent, connections: 0 });
      this.stats.connections++;
    }
    return this.pool.get(key).agent;
  }

  /**
   * 发送请求（带连接池 + 去重）
   */
  async request(options, body = null) {
    const { hostname, port = 7777, path, method = 'GET', headers = {}, timeout = 10000 } = options;
    const agent = this._getAgent(hostname, port);

    // 请求去重：相同 method + path + body 的并行请求合并
    const dedupKey = `${method}:${hostname}:${port}:${path}:${body ? JSON.stringify(body).slice(0, 200) : ''}`;
    if (method === 'GET' || method === undefined) {
      if (this.pending.has(dedupKey)) {
        this.stats.merges++;
        return this.pending.get(dedupKey);
      }
    }

    const promise = new Promise((resolve, reject) => {
      const req = http.request({
        hostname,
        port,
        path,
        method,
        headers: { ...headers, 'Connection': 'keep-alive' },
        agent,
        timeout,
      }, (res) => {
        let response = '';
        res.on('data', d => response += d);
        res.on('end', () => {
          try {
            resolve(JSON.parse(response));
          } catch {
            resolve(response);
          }
          this.pending.delete(dedupKey);
        });
      });

      req.on('error', (e) => {
        reject(e);
        this.pending.delete(dedupKey);
      });
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('请求超时'));
        this.pending.delete(dedupKey);
      });

      if (body) {
        const data = JSON.stringify(body);
        req.setHeader('Content-Length', Buffer.byteLength(data));
        req.write(data);
      }
      req.end();
    });

    if (method === 'GET' || method === undefined) {
      this.pending.set(dedupKey, promise);
    }

    this.stats.misses++;
    return promise;
  }

  /**
   * 并行请求（不等待响应就发送，减少延迟）
   */
  async parallelRequests(requests) {
    // 发送所有请求（不等待）
    const promises = requests.map(r => this.request(r.options, r.body));
    // 等待所有响应
    const results = await Promise.allSettled(promises);
    return results.map((r, i) => ({
      ok: r.status === 'fulfilled',
      result: r.value,
      error: r.reason?.message,
      request: requests[i].name,
    }));
  }

  /**
   * 批量请求（合并为一次）
   */
  async batchRequest(requests) {
    // 合并为单个 POST 请求
    const combined = {
      batch: requests.map(r => ({
        method: r.options?.method || 'GET',
        path: r.options?.path,
        body: r.body,
      })),
    };
    return this.request({
      hostname: '127.0.0.1',
      port: 7777,
      path: '/api/batch',
      method: 'POST',
    }, combined);
  }

  stats() {
    return {
      ...this.stats,
      poolSize: this.pool.size,
      pendingRequests: this.pending.size,
      hitRate: this.stats.hits + this.stats.misses > 0
        ? ((this.stats.merges / (this.stats.hits + this.stats.misses)) * 100).toFixed(1) + '%'
        : '0%',
    };
  }

  shutdown() {
    for (const [key, { agent }] of this.pool) {
      agent.destroy();
    }
    this.pool.clear();
    this.pending.clear();
  }
}

module.exports = { ConnectionPool };