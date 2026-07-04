/**
 * Y·NEX Desktop — AI 重构管理器
 * 支持：提取函数、简化逻辑、添加类型注解、重命名等
 */

const http = require('http');

class RefactorManager {
  constructor() {
    this.operations = {
      'extract-function': '将选中的代码块提取为独立函数，保持原有功能不变',
      'simplify-logic': '简化代码逻辑，消除冗余条件判断，使代码更易读',
      'add-types': '为代码添加类型注解（TypeScript/Python类型提示）',
      'rename': '对变量/函数进行语义化重命名',
      'add-docs': '为函数和类添加文档注释',
      'add-error-handling': '添加适当的错误处理（try-catch / 异常处理）',
      'optimize-performance': '优化性能，减少不必要的计算和内存分配',
      'convert-async': '将回调/Promise链转换为 async/await',
      'split-file': '将过大的文件拆分为多个模块',
      'fix-lint': '修复所有 lint 警告和错误',
    };
  }

  /**
   * 执行重构操作
   */
  async refactor({ code, filePath, language, operation, selection }) {
    if (!this.operations[operation]) {
      return { error: `未知重构操作: ${operation}。可用: ${Object.keys(this.operations).join(', ')}` };
    }

    const opDesc = this.operations[operation];
    const selectionInfo = selection
      ? `\n只重构以下选中代码片段（行 ${selection.startLine}-${selection.endLine}）:\n\`\`\`${language}\n${selection.text}\n\`\`\``
      : '';

    const prompt = `请对以下代码进行重构。重构类型: ${opDesc}

文件: ${filePath}
语言: ${language}
${selectionInfo}

完整代码:
\`\`\`${language}
${code}
\`\`\`

请直接输出重构后的完整代码，不要添加任何解释。如果需要添加导入语句，请包含在输出中。`;

    const result = await this._callYnexApi('/api/chat/stream', {
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 4096,
      temperature: 0.1
    });

    // 提取代码块
    const codeMatch = (typeof result === 'string' ? result : result?.content || '')
      .match(/```[\w]*\n?([\s\S]*?)\n?```/);
    const refactoredCode = codeMatch ? codeMatch[1] : (typeof result === 'string' ? result : result?.content || '');

    return {
      operation,
      originalCode: code,
      refactoredCode: refactoredCode.trim(),
      explanation: ''
    };
  }

  /**
   * 获取所有可用重构操作
   */
  getOperations() {
    return Object.entries(this.operations).map(([id, desc]) => ({ id, desc }));
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
        timeout: 30000
      }, (res) => {
        let response = '';
        res.on('data', d => response += d);
        res.on('end', () => {
          try { resolve(JSON.parse(response)); }
          catch { resolve({ content: response }); }
        });
      });
      req.on('error', (e) => resolve({ error: e.message }));
      req.on('timeout', () => { req.destroy(); resolve({ error: '超时' }); });
      req.write(data);
      req.end();
    });
  }
}

module.exports = { RefactorManager };