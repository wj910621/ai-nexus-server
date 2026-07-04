/**
 * Y·NEX Desktop — AI 代码审查管理器
 * 一键审查代码，按严重程度列出问题并给出修复建议
 */

const http = require('http');

class CodeReviewManager {
  constructor() {
    this.reviews = new Map();
  }

  /**
   * 审查单个文件
   * @param {string} code - 代码内容
   * @param {string} filePath - 文件路径
   * @param {string} language - 语言
   */
  async reviewFile({ code, filePath, language }) {
    const reviewId = `review_${Date.now()}`;
    const prompt = `请审查以下代码，按严重程度（🔴严重/🟡警告/🔵建议）列出问题，每个问题包含：位置、问题描述、修复建议。

文件: ${filePath}
语言: ${language}

\`\`\`${language}
${code}
\`\`\`

请按以下格式输出：
🔴 严重问题：
- [行号] 问题描述 → 修复建议

🟡 警告：
- [行号] 问题描述 → 修复建议

🔵 建议：
- [行号] 问题描述 → 修复建议

最后给出总体评分（1-10分）和总结。`;

    const result = await this._callYnexApi('/api/chat/stream', {
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 2048,
      temperature: 0.3
    });

    const review = {
      id: reviewId,
      filePath,
      timestamp: new Date().toISOString(),
      result
    };
    this.reviews.set(reviewId, review);
    return review;
  }

  /**
   * 审查整个项目（多个文件）
   */
  async reviewProject({ files, workspacePath }) {
    const results = [];
    for (const { path, content, language } of files.slice(0, 10)) {
      const review = await this.reviewFile({ code: content, filePath: path, language });
      results.push(review);
    }

    // 生成项目级总结
    const summary = await this._generateProjectSummary(results, workspacePath);
    return { files: results, summary };
  }

  async _generateProjectSummary(fileReviews, workspacePath) {
    const issues = fileReviews.map(r => `文件: ${r.filePath}\n${r.result}`).join('\n\n---\n\n');
    const prompt = `以下是多个文件的代码审查结果，请生成项目级总结：

${issues.slice(0, 6000)}

请输出：
1. 项目整体质量评分（1-10分）
2. 最需要优先修复的 3 个问题
3. 项目改进建议`;

    return this._callYnexApi('/api/chat/stream', {
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 1024,
      temperature: 0.3
    });
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
          catch { resolve(response); }
        });
      });
      req.on('error', (e) => resolve({ error: e.message }));
      req.on('timeout', () => { req.destroy(); resolve({ error: '超时' }); });
      req.write(data);
      req.end();
    });
  }

  getReview(id) {
    return this.reviews.get(id);
  }

  listReviews() {
    return Array.from(this.reviews.entries()).map(([id, r]) => ({
      id, filePath: r.filePath, timestamp: r.timestamp
    }));
  }
}

module.exports = { CodeReviewManager };