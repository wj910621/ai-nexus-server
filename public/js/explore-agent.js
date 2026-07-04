/**
 * TriGen 代码探索 Agent
 * 基于 Claude Code Explore Agent 设计
 * 只读模式，快速定位代码
 */
'use strict';

// ============================================================
// 一、探索 Agent 配置
// ============================================================
const ExploreAgent = {
  // Agent 元数据
  metadata: {
    name: 'Explore',
    description: '只读代码搜索专家',
    model: 'haiku', // 使用轻量级模型
    readonly: true
  },

  // 搜索深度
  DEPTH: {
    QUICK: 'quick',       // 快速单次查找
    MEDIUM: 'medium',     // 中等探索
    THOROUGH: 'thorough'  // 全面搜索
  },

  // 工具白名单（只读操作）
  ALLOWED_TOOLS: ['Grep', 'Glob', 'Read', 'WebSearch', 'WebFetch'],

  // 禁止的工具（写操作）
  FORBIDDEN_TOOLS: ['Write', 'Edit', 'Bash', 'NotebookEdit', 'TodoWrite', 'Task']
};

// ============================================================
// 二、探索请求
// ============================================================
class ExploreRequest {
  constructor(query, options = {}) {
    this.id = `explore_${Date.now()}`;
    this.query = query;
    this.depth = options.depth || ExploreAgent.DEPTH.MEDIUM;
    this.filePatterns = options.filePatterns || ['**/*'];
    this.excludePatterns = options.excludePatterns || ['node_modules/**', '.git/**', 'dist/**'];
    this.includeTests = options.includeTests || false;
    this.createdAt = Date.now();
  }

  /**
   * 获取搜索策略
   */
  getSearchStrategy() {
    switch (this.depth) {
      case ExploreAgent.DEPTH.QUICK:
        return {
          maxFiles: 10,
          maxResults: 5,
          timeout: 30000,
          parallelCalls: 3
        };
      case ExploreAgent.DEPTH.MEDIUM:
        return {
          maxFiles: 30,
          maxResults: 15,
          timeout: 60000,
          parallelCalls: 5
        };
      case ExploreAgent.DEPTH.THOROUGH:
        return {
          maxFiles: 100,
          maxResults: 50,
          timeout: 120000,
          parallelCalls: 10
        };
      default:
        return {
          maxFiles: 30,
          maxResults: 15,
          timeout: 60000,
          parallelCalls: 5
        };
    }
  }
}

// ============================================================
// 三、探索结果
// ============================================================
class ExploreResult {
  constructor(request) {
    this.request = request;
    this.files = [];
    this.matches = [];
    this.summary = '';
    this.statistics = {
      filesScanned: 0,
      linesMatched: 0,
      searchTime: 0,
      startTime: Date.now()
    };
  }

  addFile(file) {
    this.files.push(file);
    this.statistics.filesScanned++;
  }

  addMatch(match) {
    this.matches.push(match);
    this.statistics.linesMatched++;
  }

  setSummary(summary) {
    this.summary = summary;
    this.statistics.searchTime = Date.now() - this.statistics.startTime;
  }

  /**
   * 生成报告
   */
  toReport() {
    let report = '';

    if (this.summary) {
      report += `## 搜索摘要\n${this.summary}\n\n`;
    }

    if (this.files.length > 0) {
      report += `## 相关文件 (${this.files.length}个)\n`;
      this.files.forEach(f => {
        report += `- \`${f.path}\` ${f.description || ''}\n`;
      });
      report += '\n';
    }

    if (this.matches.length > 0) {
      report += `## 匹配详情 (${this.matches.length}处)\n`;
      this.matches.slice(0, 20).forEach(m => {
        report += `### \`${m.file}\`:${m.line}\n`;
        report += '```\n' + m.content + '\n```\n';
        if (m.context) {
          report += `> 上下文: ${m.context}\n`;
        }
      });
    }

    report += `\n---\n*搜索耗时: ${this.statistics.searchTime}ms | 扫描文件: ${this.statistics.filesScanned} | 匹配行数: ${this.statistics.linesMatched}*`;

    return report;
  }
}

// ============================================================
// 四、探索服务
// ============================================================
const ExploreService = {
  /**
   * 执行代码探索
   * @param {string} query - 搜索查询
   * @param {object} options - 选项
   * @returns {Promise<ExploreResult>}
   */
  async explore(query, options = {}) {
    const request = new ExploreRequest(query, options);
    const result = new ExploreResult(request);
    const strategy = request.getSearchStrategy();

    try {
      // 1. 快速文件定位
      const files = await this.findFiles(request, strategy);
      files.forEach(f => result.addFile(f));

      // 2. 内容搜索
      const matches = await this.searchContent(request, strategy);
      matches.forEach(m => result.addMatch(m));

      // 3. 生成摘要
      result.setSummary(this.generateSummary(result, query));

      return result;
    } catch (error) {
      console.error('Explore error:', error);
      result.setSummary(`搜索出错: ${error.message}`);
      return result;
    }
  },

  /**
   * 查找相关文件
   */
  async findFiles(request, strategy) {
    const files = [];

    // 构建 glob 模式
    const patterns = request.filePatterns.flatMap(p =>
      request.excludePatterns.map(exc => `!${exc}`).concat(p)
    );

    // 使用 glob 搜索
    for (const pattern of patterns.slice(0, strategy.maxFiles)) {
      try {
        // 模拟 glob 结果（实际使用时调用工具）
        const globResults = await this.globFiles(pattern);
        globResults.forEach(f => {
          if (!files.find(existing => existing.path === f.path)) {
            files.push(f);
          }
        });
      } catch (e) {
        // 单个 pattern 失败不影响整体
      }
    }

    return files.slice(0, strategy.maxFiles);
  },

  /**
   * 搜索文件内容
   */
  async searchContent(request, strategy) {
    const matches = [];

    // 对每个文件进行 grep 搜索
    for (const file of request.relatedFiles || []) {
      if (matches.length >= strategy.maxResults) break;

      try {
        const grepResults = await this.grepFile(file.path, request.query);
        matches.push(...grepResults);
      } catch (e) {
        // 继续下一个文件
      }
    }

    return matches.slice(0, strategy.maxResults);
  },

  /**
   * 执行 glob 搜索
   */
  async globFiles(pattern) {
    // 实际实现时调用 Glob 工具
    // 这里返回空数组，由调用者填充
    return [];
  },

  /**
   * 执行 grep 搜索
   */
  async grepFile(filePath, query) {
    // 实际实现时调用 Grep 工具
    return [];
  },

  /**
   * 生成搜索摘要
   */
  generateSummary(result, query) {
    const fileCount = result.files.length;
    const matchCount = result.matches.length;

    if (fileCount === 0 && matchCount === 0) {
      return `未找到与「${query}」相关的代码`;
    }

    let summary = `找到 ${fileCount} 个相关文件`;

    if (matchCount > 0) {
      summary += `，${matchCount} 处匹配`;
    }

    // 添加关键词发现
    const keyFiles = result.files.slice(0, 3).map(f => `\`${f.path}\``).join(', ');
    if (keyFiles) {
      summary += `\n\n重点文件: ${keyFiles}`;
    }

    return summary;
  }
};

// ============================================================
// 五、快捷探索函数
// ============================================================
const QuickExplore = {
  /**
   * 快速查找文件定义
   */
  async findDefinition(symbol) {
    const result = await ExploreService.explore(
      `定义 ${symbol}`,
      { depth: ExploreAgent.DEPTH.QUICK }
    );

    return result.files.filter(f =>
      f.path.includes(symbol) ||
      result.matches.some(m => m.content.includes(`function ${symbol}`) || m.content.includes(`const ${symbol}`))
    );
  },

  /**
   * 查找符号引用
   */
  async findReferences(symbol) {
    const result = await ExploreService.explore(
      `引用 ${symbol}`,
      { depth: ExploreAgent.DEPTH.MEDIUM }
    );

    return result.matches;
  },

  /**
   * 理解文件结构
   */
  async understandFile(filePath) {
    const result = await ExploreService.explore(
      `分析 ${filePath} 的结构和依赖`,
      { depth: ExploreAgent.DEPTH.QUICK }
    );

    return result;
  },

  /**
   * 查找相似代码
   */
  async findSimilarCode(code) {
    const keywords = this.extractKeywords(code);
    const result = await ExploreService.explore(
      keywords.join(' '),
      { depth: ExploreAgent.DEPTH.THOROUGH }
    );

    return result.matches.filter(m =>
      this.calculateSimilarity(code, m.content) > 0.3
    );
  },

  /**
   * 提取关键词
   */
  extractKeywords(code) {
    const patterns = [
      /function\s+(\w+)/g,
      /class\s+(\w+)/g,
      /const\s+(\w+)/g,
      /import\s+.*?from\s+['"](.+?)['"]/g
    ];

    const keywords = [];
    patterns.forEach(p => {
      let match;
      while ((match = p.exec(code)) !== null) {
        if (match[1] && match[1].length > 3) {
          keywords.push(match[1]);
        }
      }
    });

    return [...new Set(keywords)].slice(0, 5);
  },

  /**
   * 计算相似度（简单实现）
   */
  calculateSimilarity(a, b) {
    const wordsA = new Set(a.split(/\s+/));
    const wordsB = new Set(b.split(/\s+/));
    const intersection = new Set([...wordsA].filter(x => wordsB.has(x)));
    return intersection.size / Math.max(wordsA.size, wordsB.size);
  }
};

// ============================================================
// 六、导出
// ============================================================
window.ExploreAgent = {
  Agent: ExploreAgent,
  Request: ExploreRequest,
  Result: ExploreResult,
  Service: ExploreService,
  Quick: QuickExplore
};
