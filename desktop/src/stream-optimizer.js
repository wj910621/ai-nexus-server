/**
 * Y·NEX Desktop — 流式响应优化器
 * 并行工具执行 / 流式分块 / 早期中止 / 自适应温度
 */

const http = require('http');

class StreamOptimizer {
  constructor() {
    this.activeStreams = new Map();
    this.maxConcurrent = 3;
  }

  /**
   * 流式调用 ynex API，支持分块返回和早期中止
   */
  async streamChat(messages, options = {}) {
    const { onToken, onDone, signal, temperature = 0.7, maxTokens = 4096 } = options;

    return new Promise((resolve, reject) => {
      const data = JSON.stringify({ messages, max_tokens: maxTokens, temperature });
      const req = http.request({
        hostname: '127.0.0.1',
        port: 7777,
        path: '/api/chat/stream',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        },
        timeout: 60000
      }, (res) => {
        let fullResponse = '';
        let buffer = '';

        res.on('data', (chunk) => {
          // 检查中止信号
          if (signal && signal.aborted) {
            req.destroy();
            resolve(fullResponse);
            return;
          }

          buffer += chunk.toString();
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const json = line.slice(6);
            if (json === '[DONE]') {
              if (onDone) onDone(fullResponse);
              resolve(fullResponse);
              return;
            }
            try {
              const parsed = JSON.parse(json);
              if (parsed.content) {
                fullResponse += parsed.content;
                if (onToken) onToken(parsed.content, parsed.source);
              }
              if (parsed.done) {
                if (onDone) onDone(fullResponse);
                resolve(fullResponse);
                return;
              }
            } catch (e) {}
          }
        });

        res.on('end', () => {
          if (onDone) onDone(fullResponse);
          resolve(fullResponse);
        });

        res.on('error', (e) => reject(e));
      });

      req.on('error', (e) => reject(e));
      req.on('timeout', () => { req.destroy(); resolve(''); });
      req.write(data);
      req.end();
    });
  }

  /**
   * 并行工具执行 - 同时调用多个独立工具
   */
  async parallelTools(toolCalls, maxConcurrent = this.maxConcurrent) {
    const results = [];
    const queue = [...toolCalls];

    const worker = async () => {
      while (queue.length > 0) {
        const call = queue.shift();
        if (!call) break;
        try {
          const result = await this._executeTool(call);
          results.push({ tool: call.name, result, ok: true });
        } catch (e) {
          results.push({ tool: call.name, error: e.message, ok: false });
        }
      }
    };

    const workers = Array(Math.min(maxConcurrent, toolCalls.length)).fill(null).map(() => worker());
    await Promise.all(workers);
    return results;
  }

  async _executeTool(call) {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify({ name: call.name, ...call.arguments });
      const req = http.request({
        hostname: '127.0.0.1',
        port: 7777,
        path: '/api/skills/run',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        },
        timeout: 15000
      }, (res) => {
        let response = '';
        res.on('data', d => response += d);
        res.on('end', () => {
          try { resolve(JSON.parse(response)); }
          catch { resolve(response); }
        });
      });
      req.on('error', (e) => reject(e));
      req.on('timeout', () => { req.destroy(); reject(new Error('超时')); });
      req.write(data);
      req.end();
    });
  }

  /**
   * 自适应温度：根据任务类型调整
   *   代码生成: 0.1-0.2
   *   对话: 0.7
   *   创意: 0.9
   *   分析: 0.3
   */
  adaptiveTemperature(taskType) {
    const map = {
      'code': 0.15,
      'chat': 0.7,
      'creative': 0.9,
      'analysis': 0.3,
      'refactor': 0.1,
      'review': 0.2,
      'completion': 0.1,
      'default': 0.5,
    };
    return map[taskType] || map['default'];
  }

  /**
   * 创建中止控制器
   */
  createAbortController() {
    const controller = { aborted: false };
    return {
      signal: controller,
      abort: () => { controller.aborted = true; },
    };
  }
}

module.exports = { StreamOptimizer };