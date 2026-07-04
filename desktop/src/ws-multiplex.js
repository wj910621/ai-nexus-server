/**
 * Y·NEX Desktop — WebSocket 多路复用
 * 单连接承载所有实时通信，替代多个 HTTP 请求
 */

const WebSocket = require('ws');
const { EventEmitter } = require('events');

class WebSocketMultiplexer extends EventEmitter {
  constructor() {
    super();
    this.ws = null;
    this.url = 'ws://127.0.0.1:7777/ws';
    this.subscriptions = new Map(); // channel -> Set<callback>
    this.pending = new Map();       // requestId -> { resolve, reject, timer }
    this.requestId = 0;
    this.connected = false;
    this.reconnectTimer = null;
    this.pingTimer = null;
  }

  /**
   * 连接 WebSocket 多路复用
   */
  async connect() {
    if (this.connected) return;
    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(this.url);
        this.ws.on('open', () => {
          this.connected = true;
          this._startPing();
          this.emit('connected');
          resolve(true);
        });
        this.ws.on('message', (data) => this._onMessage(data));
        this.ws.on('close', () => {
          this.connected = false;
          this._stopPing();
          this.emit('disconnected');
          this._scheduleReconnect();
        });
        this.ws.on('error', () => {
          this.connected = false;
          resolve(false);
        });
      } catch (e) {
        resolve(false);
      }
    });
  }

  /**
   * 通过 WebSocket 发送请求（替代 HTTP）
   */
  async request(method, path, body = null) {
    if (!this.connected) {
      await this.connect();
      if (!this.connected) {
        // 回退到 HTTP
        return this._fallbackHttp(method, path, body);
      }
    }

    const id = ++this.requestId;
    const frame = {
      type: 'request',
      id,
      method,
      path,
      body: body ? (typeof body === 'string' ? body : JSON.stringify(body)) : null,
      timestamp: Date.now(),
    };

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('请求超时'));
      }, 15000);

      this.pending.set(id, { resolve, reject, timer });
      try {
        this.ws.send(JSON.stringify(frame));
      } catch (e) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(e);
      }
    });
  }

  /**
   * 订阅频道（实时推送）
   */
  subscribe(channel, callback) {
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
      // 通知服务器订阅
      if (this.connected) {
        this.ws.send(JSON.stringify({ type: 'subscribe', channel }));
      }
    }
    this.subscriptions.get(channel).add(callback);
    return () => this.unsubscribe(channel, callback);
  }

  unsubscribe(channel, callback) {
    const subs = this.subscriptions.get(channel);
    if (!subs) return;
    subs.delete(callback);
    if (subs.size === 0) {
      this.subscriptions.delete(channel);
      if (this.connected) {
        this.ws.send(JSON.stringify({ type: 'unsubscribe', channel }));
      }
    }
  }

  _onMessage(data) {
    try {
      const frame = JSON.parse(data.toString());
      switch (frame.type) {
        case 'response':
          this._handleResponse(frame);
          break;
        case 'push':
          this._handlePush(frame);
          break;
        case 'pong':
          break;
        case 'error':
          this._handleResponse(frame);
          break;
      }
    } catch (e) {}
  }

  _handleResponse(frame) {
    const pending = this.pending.get(frame.id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pending.delete(frame.id);
    if (frame.error) {
      pending.reject(new Error(frame.error));
    } else {
      pending.resolve(frame.data);
    }
  }

  _handlePush(frame) {
    const subs = this.subscriptions.get(frame.channel);
    if (!subs) return;
    for (const cb of subs) {
      try { cb(frame.data); } catch (e) {}
    }
  }

  _startPing() {
    this.pingTimer = setInterval(() => {
      if (this.connected && this.ws) {
        try { this.ws.send(JSON.stringify({ type: 'ping' })); } catch (e) {}
      }
    }, 30000);
  }

  _stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 2000);
  }

  async _fallbackHttp(method, path, body) {
    const http = require('http');
    return new Promise((resolve, reject) => {
      const options = {
        hostname: '127.0.0.1',
        port: 7777,
        path,
        method,
        timeout: 10000,
      };
      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', d => data += d);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); } catch { resolve(data); }
        });
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('超时')); });
      if (body) {
        const d = typeof body === 'string' ? body : JSON.stringify(body);
        req.write(d);
      }
      req.end();
    });
  }

  /**
   * 多路复用：同时发送多个请求
   */
  async multiplex(requests) {
    return Promise.all(requests.map(r => this.request(r.method, r.path, r.body)));
  }

  stats() {
    return {
      connected: this.connected,
      subscriptions: this.subscriptions.size,
      pendingRequests: this.pending.size,
      multiplexed: this.requestId,
    };
  }

  shutdown() {
    this._stopPing();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    // 拒绝所有 pending
    for (const [id, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new Error('连接已关闭'));
    }
    this.pending.clear();
    this.subscriptions.clear();
    if (this.ws) {
      try { this.ws.close(); } catch (e) {}
      this.ws = null;
    }
    this.connected = false;
  }
}

module.exports = { WebSocketMultiplexer };