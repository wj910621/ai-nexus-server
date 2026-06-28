/**
 * Y·NEX AGENTS.md 项目级指令系统 v2.0
 * 基于 Codex AGENTS.md 设计
 * 支持项目级编码规范和指令
 */
'use strict';

// ============================================================
// 一、AGENTS.md 解析器
// ============================================================
const AgentsMdParser = {
  /**
   * 解析 AGENTS.md 内容
   */
  parse(content) {
    const sections = {
      global: [],
      fileScopes: new Map(),
      languageScopes: new Map()
    };

    const lines = content.split('\n');
    let currentScope = 'global';
    let currentFilePattern = null;
    let currentLangPattern = null;
    let currentContent = [];

    for (const line of lines) {
      // 检查作用域指令
      if (line.startsWith('# scope:')) {
        // 保存之前的内容
        this.saveContent(sections, currentScope, currentFilePattern, currentLangPattern, currentContent);

        // 解析新作用域
        const scopeDef = line.replace('# scope:', '').trim();

        if (scopeDef.startsWith('file:')) {
          currentScope = 'file';
          currentFilePattern = scopeDef.replace('file:', '').trim();
          currentLangPattern = null;
        } else if (scopeDef.startsWith('lang:')) {
          currentScope = 'language';
          currentLangPattern = scopeDef.replace('lang:', '').trim();
          currentFilePattern = null;
        } else {
          currentScope = 'global';
          currentFilePattern = null;
          currentLangPattern = null;
        }

        currentContent = [];
        continue;
      }

      // 跳过注释和空行
      if (line.trim() === '' || line.trim().startsWith('#') || line.trim().startsWith('//')) {
        continue;
      }

      currentContent.push(line);
    }

    // 保存最后的内容
    this.saveContent(sections, currentScope, currentFilePattern, currentLangPattern, currentContent);

    return sections;
  },

  /**
   * 保存内容到对应作用域
   */
  saveContent(sections, scope, filePattern, langPattern, content) {
    const text = content.join('\n').trim();
    if (!text) return;

    if (scope === 'global') {
      sections.global.push(text);
    } else if (scope === 'file' && filePattern) {
      if (!sections.fileScopes.has(filePattern)) {
        sections.fileScopes.set(filePattern, []);
      }
      sections.fileScopes.get(filePattern).push(text);
    } else if (scope === 'language' && langPattern) {
      if (!sections.languageScopes.has(langPattern)) {
        sections.languageScopes.set(langPattern, []);
      }
      sections.languageScopes.get(langPattern).push(text);
    }
  },

  /**
   * 获取适用于文件指令
   */
  getInstructionsForFile(filename, parsed) {
    const instructions = [];

    // 添加全局指令
    instructions.push(...parsed.global);

    // 添加语言特定指令
    const ext = filename.split('.').pop();
    if (ext && parsed.languageScopes.has(ext)) {
      instructions.push(...parsed.languageScopes.get(ext));
    }

    // 添加文件匹配指令
    for (const [pattern, rules] of parsed.fileScopes) {
      if (this.matchPattern(filename, pattern)) {
        instructions.push(...rules);
      }
    }

    return instructions.join('\n\n');
  },

  /**
   * 匹配文件模式
   */
  matchPattern(filename, pattern) {
    // 简单 glob 匹配
    const regex = new RegExp(
      pattern
        .replace(/\./g, '\\.')
        .replace(/\*/g, '.*')
        .replace(/\?/g, '.'),
      'i'
    );
    return regex.test(filename);
  }
};

// ============================================================
// 二、AGENTS.md 管理器
// ============================================================
const AgentsMdManager = {
  // 缓存的 AGENTS.md 内容
  cache: new Map(),

  // 当前项目的 AGENTS.md
  currentProject: null,

  /**
   * 加载项目的 AGENTS.md
   */
  async loadForProject(projectPath) {
    const agentsPath = `${projectPath}/AGENTS.md`;

    // 检查缓存
    if (this.cache.has(agentsPath)) {
      return this.cache.get(agentsPath);
    }

    try {
      // 尝试读取 AGENTS.md
      const response = await fetch(API_BASE + '/api/files/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: agentsPath })
      });

      if (!response.ok) {
        return null;
      }

      const result = await response.json();

      if (result.error) {
        return null;
      }

      // 解析内容
      const parsed = AgentsMdParser.parse(result.content);

      // 缓存
      this.cache.set(agentsPath, {
        raw: result.content,
        parsed,
        path: agentsPath,
        modified: Date.now()
      });

      this.currentProject = agentsPath;
      return parsed;
    } catch (e) {
      return null;
    }
  },

  /**
   * 获取文件的指令
   */
  getInstructionsForFile(filename) {
    if (!this.currentProject) return '';

    const cached = this.cache.get(this.currentProject);
    if (!cached) return '';

    return AgentsMdParser.getInstructionsForFile(filename, cached.parsed);
  },

  /**
   * 创建默认 AGENTS.md
   */
  createDefault(projectName, options = {}) {
    const { language = 'JavaScript', framework = '' } = options;

    const template = `# AGENTS.md - ${projectName}

# 全局指令

## 代码风格
- 使用 2 空格缩进
- 使用 \`const\` 和 \`let\`，避免 \`var\`
- 优先使用箭头函数
- 使用语义化命名

## 注释规范
- 文件顶部添加简短说明
- 复杂逻辑添加注释
- 不添加显而易见的注释

## Git 提交
- 使用 conventional commits 格式
- 提交前运行测试
- 保持提交粒度适中

# lang:${language}

## 类型
- 使用 JSDoc 标注类型
- 优先使用接口而非类型别名
- 导出类型显式声明

# scope:src/**/*.test.js

## 测试
- 每个函数至少一个测试
- 使用 describe/it 结构
- 包含边界情况测试

# scope:**/*.css

## 样式
- 使用 CSS 变量管理主题
- 优先使用 flexbox
- 避免使用 !important
`;

    return template;
  },

  /**
   * 清除缓存
   */
  clearCache() {
    this.cache.clear();
    this.currentProject = null;
  }
};

// ============================================================
// 三、代码片段库（可嵌入 AGENTS.md）
// ============================================================
const CodeSnippets = {
  snippets: {
    // 错误处理
    errorHandling: `
// 错误处理模式
try {
  // 异步操作
} catch (error) {
  console.error('操作失败:', error);
  throw error; // 或 return { error: error.message };
}
`,

    // 异步模式
    asyncPattern: `
// 异步函数模式
async function fetchData(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(\`HTTP error! status: \${response.status}\`);
    }
    return await response.json();
  } catch (error) {
    console.error('Fetch failed:', error);
    throw error;
  }
}
`,

    // 事件发射器
    eventEmitter: `
// 简单事件发射器
class EventEmitter {
  constructor() {
    this.events = {};
  }
  on(event, listener) {
    (this.events[event] = this.events[event] || []).push(listener);
    return this;
  }
  off(event, listener) {
    this.events[event] = (this.events[event] || []).filter(l => l !== listener);
    return this;
  }
  emit(event, ...args) {
    (this.events[event] || []).forEach(listener => listener(...args));
    return this;
  }
}
`,

    // 单例模式
    singleton: `
// 单例模式
class Singleton {
  constructor() {
    if (Singleton.instance) {
      return Singleton.instance;
    }
    Singleton.instance = this;
    this.init();
  }
  init() {
    // 初始化逻辑
  }
}
`,

    // 防抖
    debounce: `
// 防抖函数
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
`,

    // 节流
    throttle: `
// 节流函数
function throttle(func, limit) {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}
`,

    // 缓存
    memoize: `
// 记忆化函数
function memoize(fn) {
  const cache = new Map();
  return function memoized(...args) {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn.apply(this, args);
    cache.set(key, result);
    return result;
  };
}
`,

    // 深拷贝
    deepClone: `
// 深拷贝
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(item => deepClone(item));
  const cloned = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      cloned[key] = deepClone(obj[key]);
    }
  }
  return cloned;
}
`,

    // 观察者模式
    observer: `
// 观察者模式
class Observable {
  constructor() {
    this.observers = [];
  }
  subscribe(fn) {
    this.observers.push(fn);
    return () => this.observers = this.observers.filter(o => o !== fn);
  }
  notify(data) {
    this.observers.forEach(fn => fn(data));
  }
}
`
  },

  /**
   * 获取代码片段
   */
  get(name) {
    return this.snippets[name] || null;
  },

  /**
   * 添加代码片段
   */
  add(name, code) {
    this.snippets[name] = code;
  },

  /**
   * 获取所有片段名称
   */
  list() {
    return Object.keys(this.snippets);
  },

  /**
   * 生成片段文档
   */
  generateDocs() {
    let docs = '# 可用代码片段\n\n';

    for (const [name, code] of Object.entries(this.snippets)) {
      docs += `## ${name}\n\n`;
      docs += '```javascript\n' + code.trim() + '\n```\n\n';
    }

    return docs;
  }
};

// ============================================================
// 四、导出
// ============================================================
window.AgentsMdSystem = {
  Parser: AgentsMdParser,
  Manager: AgentsMdManager,
  Snippets: CodeSnippets,

  // 便捷方法
  load: (path) => AgentsMdManager.loadForProject(path),
  getInstructions: (filename) => AgentsMdManager.getInstructionsForFile(filename),
  createDefault: (name, opts) => AgentsMdManager.createDefault(name, opts),
  parse: (content) => AgentsMdParser.parse(content),
  getSnippet: (name) => CodeSnippets.get(name),
  addSnippet: (name, code) => CodeSnippets.add(name, code),
  listSnippets: () => CodeSnippets.list(),
  snippetsDocs: () => CodeSnippets.generateDocs()
};
