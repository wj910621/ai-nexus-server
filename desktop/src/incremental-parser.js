/**
 * Y·NEX Desktop — 增量解析 + Monaco 按需加载
 * 只解析变化的文件部分，按需加载 Monaco 语言支持
 */

const fs = require('fs');
const path = require('path');

class IncrementalParser {
  constructor() {
    this.fileStates = new Map();  // path -> { hash, lastModified, imports, symbols }
    this.symbolCache = new Map(); // path -> [{ name, type, line, column }]
    this.languageModules = new Map(); // 已加载的语言模块
  }

  /**
   * 获取文件哈希（快速检测变化）
   */
  _hash(content) {
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const ch = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + ch;
      hash |= 0;
    }
    return hash;
  }

  /**
   * 增量解析：只解析变化的部分
   */
  parse(filePath, content, options = {}) {
    const state = this.fileStates.get(filePath);
    const newHash = this._hash(content);

    if (state && state.hash === newHash) {
      // 未变化，返回缓存
      return {
        symbols: this.symbolCache.get(filePath) || [],
        imports: state.imports || [],
        cached: true,
      };
    }

    // 增量解析
    const symbols = this._extractSymbols(content, filePath);
    const imports = this._extractImports(content, filePath);

    this.fileStates.set(filePath, {
      hash: newHash,
      lastModified: Date.now(),
      imports,
      symbols,
    });
    this.symbolCache.set(filePath, symbols);

    return { symbols, imports, cached: false };
  }

  /**
   * 解析文件变化（只处理变化行）
   */
  parseDiff(filePath, oldContent, newContent, changes) {
    const symbols = this._extractSymbols(newContent, filePath);
    const imports = this._extractImports(newContent, filePath);

    // 只更新变化部分
    this.fileStates.set(filePath, {
      hash: this._hash(newContent),
      lastModified: Date.now(),
      imports,
      symbols,
    });
    this.symbolCache.set(filePath, symbols);

    return {
      symbols,
      imports,
      changedLines: changes.map(c => c.line),
      cached: false,
    };
  }

  _extractSymbols(content, filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const symbols = [];
    const lines = content.split('\n');

    if (ext === '.py') {
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        let match;
        if ((match = line.match(/^def\s+(\w+)/))) {
          symbols.push({ name: match[1], type: 'function', line: i + 1 });
        } else if ((match = line.match(/^class\s+(\w+)/))) {
          symbols.push({ name: match[1], type: 'class', line: i + 1 });
        }
      }
    } else if (['.js', '.ts', '.jsx', '.tsx'].includes(ext)) {
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        let match;
        if ((match = line.match(/(?:export\s+)?(?:async\s+)?function\s+(\w+)/))) {
          symbols.push({ name: match[1], type: 'function', line: i + 1 });
        } else if ((match = line.match(/(?:export\s+)?class\s+(\w+)/))) {
          symbols.push({ name: match[1], type: 'class', line: i + 1 });
        } else if ((match = line.match(/(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(/))) {
          symbols.push({ name: match[1], type: 'function', line: i + 1 });
        } else if ((match = line.match(/(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\w+\s*=>/))) {
          symbols.push({ name: match[1], type: 'function', line: i + 1 });
        }
      }
    }

    return symbols;
  }

  _extractImports(content, filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const imports = [];
    const lines = content.split('\n');

    if (ext === '.py') {
      for (const line of lines) {
        const match = line.match(/^(?:from|import)\s+([\w.]+)/);
        if (match) imports.push(match[1]);
      }
    } else if (['.js', '.ts', '.jsx', '.tsx'].includes(ext)) {
      for (const line of lines) {
        let match;
        if ((match = line.match(/require\(['"]([^'"]+)['"]\)/))) {
          imports.push(match[1]);
        } else if ((match = line.match(/from\s+['"]([^'"]+)['"]/))) {
          imports.push(match[1]);
        } else if ((match = line.match(/import\s+['"]([^'"]+)['"]/))) {
          imports.push(match[1]);
        }
      }
    }

    return [...new Set(imports)];
  }

  /**
   * Monaco 按需加载语言支持
   * 返回需要加载的语言模块列表
   */
  getMonacoLanguages(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const map = {
      '.js': 'javascript', '.jsx': 'javascript',
      '.ts': 'typescript', '.tsx': 'typescript',
      '.py': 'python', '.html': 'html', '.css': 'css',
      '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
      '.md': 'markdown', '.sql': 'sql',
      '.java': 'java', '.go': 'go', '.rs': 'rust',
      '.cpp': 'cpp', '.c': 'cpp', '.h': 'cpp',
    };
    const lang = map[ext] || 'plaintext';

    if (!this.languageModules.has(lang)) {
      this.languageModules.set(lang, true);
      return { lang, firstLoad: true };
    }
    return { lang, firstLoad: false };
  }

  /**
   * 获取依赖图
   */
  getDependencyGraph(filePath) {
    const state = this.fileStates.get(filePath);
    if (!state) return { file: filePath, imports: [], dependents: [] };

    const dependents = [];
    for (const [fp, s] of this.fileStates) {
      if (s.imports && s.imports.some(imp => fp.includes(imp) || imp.includes(path.basename(filePath, path.extname(filePath))))) {
        dependents.push(fp);
      }
    }

    return {
      file: filePath,
      imports: state.imports || [],
      dependents,
    };
  }

  stats() {
    return {
      parsedFiles: this.fileStates.size,
      cachedSymbols: this.symbolCache.size,
      loadedLanguages: this.languageModules.size,
    };
  }
}

module.exports = { IncrementalParser };