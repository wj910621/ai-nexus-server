/**
 * Y·NEX Desktop — 智能上下文管理器
 * 动态判断相关文件，自动调整上下文窗口大小
 */

const fs = require('fs');
const path = require('path');

class ContextManager {
  constructor() {
    this.maxContextTokens = 8000;
    this.maxFiles = 15;
    this.fileRelevance = new Map();
    this.importGraph = new Map();
  }

  /**
   * 为给定任务收集相关文件上下文
   */
  async collectContext({ task, workspacePath, openFiles, currentFile }) {
    const context = {
      files: [],
      totalTokens: 0,
      summary: ''
    };

    // 1. 当前打开的文件优先级最高
    if (currentFile && openFiles) {
      for (const [fp, file] of openFiles) {
        if (file.modified) {
          context.files.push({
            path: fp,
            content: file.content,
            relevance: 'current',
            priority: 100
          });
        }
      }
    }

    // 2. 分析任务关键词，匹配相关文件
    if (workspacePath && task) {
      const keywords = this._extractKeywords(task);
      const relatedFiles = await this._findRelatedFiles(workspacePath, keywords);
      for (const rf of relatedFiles) {
        if (!context.files.find(f => f.path === rf.path)) {
          context.files.push({
            path: rf.path,
            content: rf.content,
            relevance: `keyword: ${rf.matchedKeyword}`,
            priority: 50
          });
        }
      }
    }

    // 3. 分析 import 依赖关系
    if (currentFile && workspacePath) {
      const imports = await this._analyzeImports(currentFile, workspacePath);
      for (const imp of imports) {
        if (!context.files.find(f => f.path === imp)) {
          try {
            const content = fs.readFileSync(imp, 'utf-8');
            context.files.push({
              path: imp,
              content: content.slice(0, 3000),
              relevance: 'import-dependency',
              priority: 30
            });
          } catch (e) {}
        }
      }
    }

    // 4. 按优先级排序，限制总 token 数
    context.files.sort((a, b) => b.priority - a.priority);

    let totalChars = 0;
    const maxChars = this.maxContextTokens * 3; // 粗略估计 1 token ≈ 3 chars
    const selected = [];

    for (const file of context.files) {
      const contentLen = file.content.length;
      if (totalChars + contentLen > maxChars) {
        // 截断文件内容
        const remaining = maxChars - totalChars;
        if (remaining > 500) {
          file.content = file.content.slice(0, remaining) + '\n... (内容已截断)';
          selected.push(file);
          totalChars += remaining;
        }
        break;
      }
      selected.push(file);
      totalChars += contentLen;
      if (selected.length >= this.maxFiles) break;
    }

    context.files = selected;
    context.totalTokens = Math.round(totalChars / 3);
    context.summary = `${selected.length} 个文件, ~${context.totalTokens} tokens`;

    return context;
  }

  /**
   * 构建上下文 prompt
   */
  buildContextPrompt(context) {
    if (!context.files.length) return '';
    const parts = context.files.map(f => {
      const lang = this._detectLanguage(f.path);
      return `\n文件: ${f.path} (${f.relevance})\n\`\`\`${lang}\n${f.content}\n\`\`\``;
    });
    return `\n\n=== 项目上下文 (${context.summary}) ===\n${parts.join('\n')}\n=== 上下文结束 ===\n`;
  }

  _extractKeywords(task) {
    // 简单提取：英文单词 + 中文词组
    const words = [];
    const enMatch = task.match(/[a-zA-Z_][a-zA-Z0-9_.]*/g);
    if (enMatch) words.push(...enMatch);
    const cnMatch = task.match(/[\u4e00-\u9fa5]{2,}/g);
    if (cnMatch) words.push(...cnMatch);
    return words.filter(w => w.length > 1).slice(0, 20);
  }

  async _findRelatedFiles(workspacePath, keywords) {
    const results = [];
    const files = this._listProjectFiles(workspacePath, 200);

    for (const fp of files) {
      try {
        const filename = path.basename(fp).toLowerCase();
        for (const kw of keywords) {
          if (filename.includes(kw.toLowerCase())) {
            const content = fs.readFileSync(fp, 'utf-8').slice(0, 3000);
            results.push({ path: fp, content, matchedKeyword: kw });
            break;
          }
        }
      } catch (e) {}
    }

    return results.slice(0, 10);
  }

  async _analyzeImports(filePath, workspacePath) {
    const resolved = [];
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const ext = path.extname(filePath);

      // Python imports
      if (ext === '.py') {
        const importRegex = /^(?:from|import)\s+([\w.]+)/gm;
        let match;
        while ((match = importRegex.exec(content)) !== null) {
          const modulePath = match[1].replace(/\./g, '/');
          const candidates = [
            path.join(workspacePath, modulePath + '.py'),
            path.join(workspacePath, modulePath, '__init__.py'),
            path.join(path.dirname(filePath), modulePath + '.py'),
          ];
          for (const c of candidates) {
            if (fs.existsSync(c)) { resolved.push(c); break; }
          }
        }
      }

      // JS/TS imports
      if (['.js', '.ts', '.jsx', '.tsx'].includes(ext)) {
        const requireRegex = /require\(['"]([^'"]+)['"]\)/g;
        const importRegex = /from\s+['"]([^'"]+)['"]/g;
        let match;
        const check = async (modPath) => {
          if (modPath.startsWith('.')) {
            const abs = path.resolve(path.dirname(filePath), modPath);
            for (const ext of ['', '.js', '.ts', '.jsx', '.tsx', '/index.js', '/index.ts']) {
              if (fs.existsSync(abs + ext)) { resolved.push(abs + ext); return; }
            }
          }
        };
        while ((match = requireRegex.exec(content)) !== null) await check(match[1]);
        while ((match = importRegex.exec(content)) !== null) await check(match[1]);
      }
    } catch (e) {}

    return resolved.slice(0, 10);
  }

  _listProjectFiles(workspacePath, maxFiles) {
    const files = [];
    const walk = (dir, depth) => {
      if (depth > 5 || files.length >= maxFiles) return;
      try {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const e of entries) {
          if (e.name.startsWith('.') || e.name === 'node_modules' || e.name === '__pycache__') continue;
          const full = path.join(dir, e.name);
          if (e.isDirectory()) {
            walk(full, depth + 1);
          } else if (e.isFile() && this._isCodeFile(e.name)) {
            files.push(full);
          }
        }
      } catch (e) {}
    };
    walk(workspacePath, 0);
    return files;
  }

  _isCodeFile(filename) {
    const exts = ['.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.html', '.css', '.json', '.yaml', '.yml', '.md'];
    return exts.includes(path.extname(filename).toLowerCase());
  }

  _detectLanguage(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const map = {
      '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
      '.py': 'python', '.java': 'java', '.go': 'go', '.rs': 'rust', '.cpp': 'cpp',
      '.c': 'c', '.h': 'cpp', '.html': 'html', '.css': 'css', '.json': 'json',
      '.yaml': 'yaml', '.yml': 'yaml', '.md': 'markdown'
    };
    return map[ext] || 'plaintext';
  }
}

module.exports = { ContextManager };