/**
 * Y·NEX Desktop — Trie 即时模糊搜索
 * 毫秒级文件搜索，支持前缀匹配、模糊匹配、正则匹配
 */

const fs = require('fs');
const path = require('path');

class TrieNode {
  constructor() {
    this.children = {};
    this.isEnd = false;
    this.files = [];
  }
}

class CodeIndex {
  constructor() {
    this.root = new TrieNode();
    this.fileList = [];
    this.fileContents = new Map(); // path -> content cache
    this.maxContentCache = 50 * 1024 * 1024; // 50MB
    this.contentCacheSize = 0;
    this.indexed = false;
  }

  /**
   * 构建项目索引
   */
  indexWorkspace(workspacePath) {
    this.root = new TrieNode();
    this.fileList = [];
    this.fileContents.clear();
    this.contentCacheSize = 0;
    const start = Date.now();

    this._walk(workspacePath, workspacePath, 0);

    this.indexed = true;
    const elapsed = Date.now() - start;
    return { files: this.fileList.length, elapsedMs: elapsed };
  }

  _walk(dir, basePath, depth) {
    if (depth > 10) return;
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === '__pycache__') continue;
        const fullPath = path.join(dir, entry.name);
        const relativePath = path.relative(basePath, fullPath).replace(/\\/g, '/');

        if (entry.isDirectory()) {
          this._walk(fullPath, basePath, depth + 1);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          const codeExts = ['.js', '.ts', '.jsx', '.tsx', '.py', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.html', '.css', '.json', '.yaml', '.yml', '.md', '.sql', '.sh', '.bat', '.ps1', '.php', '.rb', '.txt', '.xml', '.toml', '.ini', '.cfg', '.env'];
          if (codeExts.includes(ext) || ext === '') {
            this.fileList.push(relativePath);
            // 插入到 trie
            this._insert(relativePath.toLowerCase(), relativePath);
          }
        }
      }
    } catch (e) {}
  }

  _insert(word, filePath) {
    let node = this.root;
    for (const ch of word) {
      if (!node.children[ch]) {
        node.children[ch] = new TrieNode();
      }
      node = node.children[ch];
    }
    node.isEnd = true;
    if (!node.files.includes(filePath)) {
      node.files.push(filePath);
    }
  }

  /**
   * 前缀搜索 - O(n) where n = query length
   */
  prefixSearch(query) {
    if (!this.indexed) return { results: [], query, count: 0 };
    const q = query.toLowerCase();
    let node = this.root;
    for (const ch of q) {
      if (!node.children[ch]) return { results: [], query, count: 0 };
      node = node.children[ch];
    }
    const results = this._collectAll(node);
    // 精确匹配排前面
    results.sort((a, b) => {
      const aExact = a.toLowerCase().includes(q);
      const bExact = b.toLowerCase().includes(q);
      if (aExact && !bExact) return -1;
      if (!aExact && bExact) return 1;
      return a.length - b.length;
    });
    return { results: results.slice(0, 50), query, count: results.length };
  }

  /**
   * 模糊搜索 - 使用编辑距离
   */
  fuzzySearch(query, maxResults = 20) {
    if (!this.indexed) return { results: [], query, count: 0 };
    const q = query.toLowerCase();
    const results = [];

    for (const file of this.fileList) {
      const score = this._fuzzyScore(file.toLowerCase(), q);
      if (score > 0) {
        results.push({ file, score, matched: this._highlightMatch(file, q) });
      }
    }

    results.sort((a, b) => b.score - a.score);
    const top = results.slice(0, maxResults);
    return { results: top, query, count: results.length };
  }

  /**
   * 内容搜索 - 在文件内容中搜索
   */
  contentSearch(query, maxResults = 20) {
    if (!this.indexed) return { results: [], query, count: 0 };
    const q = query.toLowerCase();
    const results = [];

    for (const file of this.fileList) {
      // 先检查文件名
      if (file.toLowerCase().includes(q)) {
        results.push({ file, line: 0, snippet: `文件名匹配: ${file}`, score: 100 });
        continue;
      }
      // 再检查内容
      const content = this._getCachedContent(file);
      if (content) {
        const lines = content.split('\n');
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].toLowerCase().includes(q)) {
            results.push({ file, line: i + 1, snippet: lines[i].trim().slice(0, 120), score: 50 });
            if (results.length >= maxResults * 3) break;
          }
        }
      }
      if (results.length >= maxResults * 3) break;
    }

    results.sort((a, b) => b.score - a.score);
    return { results: results.slice(0, maxResults), query, count: results.length };
  }

  _getCachedContent(file) {
    if (this.fileContents.has(file)) return this.fileContents.get(file);
    // 懒加载文件内容
    if (this.contentCacheSize > this.maxContentCache) return null;
    try {
      const content = fs.readFileSync(file, 'utf-8');
      this.contentCacheSize += content.length;
      this.fileContents.set(file, content);
      return content;
    } catch (e) {
      return null;
    }
  }

  _collectAll(node) {
    const results = [];
    const stack = [[node, '']];
    while (stack.length > 0 && results.length < 100) {
      const [n, prefix] = stack.pop();
      if (n.isEnd) {
        results.push(...n.files.slice(0, 10));
      }
      for (const [ch, child] of Object.entries(n.children)) {
        stack.push([child, prefix + ch]);
      }
    }
    return results;
  }

  _fuzzyScore(str, query) {
    let score = 0;
    let qi = 0;
    let consecutive = 0;
    let lastMatchPos = -1;

    for (let i = 0; i < str.length && qi < query.length; i++) {
      if (str[i] === query[qi]) {
        score += 10;
        if (lastMatchPos === i - 1) {
          consecutive++;
          score += consecutive * 5;
        } else {
          consecutive = 0;
        }
        lastMatchPos = i;
        qi++;
      } else {
        consecutive = 0;
      }
    }

    // 完全匹配加分
    if (qi === query.length) {
      score += 50;
      // 路径分隔符后的匹配加分
      if (str.includes('/' + query) || str.includes('\\' + query)) {
        score += 30;
      }
      // 完全文件名匹配
      const basename = path.basename(str).toLowerCase();
      if (basename === query) score += 100;
      if (basename.startsWith(query)) score += 50;
    } else {
      score = 0; // 不完全匹配
    }

    return score;
  }

  _highlightMatch(file, query) {
    const idx = file.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return file;
    return file.slice(0, idx) + '<b>' + file.slice(idx, idx + query.length) + '</b>' + file.slice(idx + query.length);
  }

  /**
   * 监听文件变化，增量更新索引
   */
  onFileChange(event, filePath) {
    const relativePath = filePath.replace(/\\/g, '/');
    if (event === 'add' || event === 'change') {
      if (!this.fileList.includes(relativePath)) {
        this.fileList.push(relativePath);
        this._insert(relativePath.toLowerCase(), relativePath);
      }
      this.fileContents.delete(relativePath);
    } else if (event === 'delete') {
      this.fileList = this.fileList.filter(f => f !== relativePath);
      this.fileContents.delete(relativePath);
    }
  }

  stats() {
    let nodeCount = 0;
    const count = (node) => { nodeCount++; Object.values(node.children).forEach(count); };
    count(this.root);
    return {
      files: this.fileList.length,
      trieNodes: nodeCount,
      contentCacheSize: (this.contentCacheSize / 1024 / 1024).toFixed(1) + 'MB',
      indexed: this.indexed,
    };
  }
}

module.exports = { CodeIndex };