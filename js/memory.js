/**
 * TriGen 记忆系统 v2.0
 * 基于 Claude Code CLAUDE.md 设计理念
 * 三层记忆架构：用户级、项目级、会话级
 */
'use strict';

// ============================================================
// 一、记忆存储配置
// ============================================================
const MemoryConfig = {
  // 存储键名
  STORAGE_KEYS: {
    USER: 'trigen_user_memory',      // 用户级记忆
    PROJECT: 'trigen_project_memory', // 项目级记忆
    SESSION: 'trigen_session_memory', // 会话级记忆
    CONTEXT_INDEX: 'trigen_context_index' // 上下文索引
  },

  // 最大存储条目
  MAX_ITEMS: {
    USER: 100,
    PROJECT: 50,
    SESSION: 30
  },

  // 过期时间（毫秒），0 表示永不过期
  EXPIRY: {
    USER: 0,           // 永不过期
    PROJECT: 30 * 24 * 60 * 60 * 1000, // 30天
    SESSION: 24 * 60 * 60 * 1000       // 24小时
  },

  // 自动清理阈值
  CLEANUP_THRESHOLD: 0.9 // 当存储达到90%容量时自动清理
};

// ============================================================
// 二、记忆数据结构
// ============================================================
class MemoryItem {
  constructor(type, key, content, metadata = {}) {
    this.id = this.generateId();
    this.type = type;
    this.key = key;
    this.content = content;
    this.metadata = {
      created: Date.now(),
      updated: Date.now(),
      accessed: Date.now(),
      accessCount: 0,
      tags: metadata.tags || [],
      source: metadata.source || 'user',
      ...metadata
    };
  }

  generateId() {
    return `mem_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  touch() {
    this.metadata.accessed = Date.now();
    this.metadata.accessCount++;
  }

  update(content) {
    this.content = content;
    this.metadata.updated = Date.now();
  }

  toJSON() {
    return {
      id: this.id,
      type: this.type,
      key: this.key,
      content: this.content,
      metadata: this.metadata
    };
  }
}

// ============================================================
// 三、记忆管理器
// ============================================================
const MemoryStore = {
  // 内存缓存
  cache: {
    user: new Map(),
    project: new Map(),
    session: new Map()
  },

  // 初始化
  init() {
    this.loadFromStorage('user');
    this.loadFromStorage('project');
    this.loadFromStorage('session');
  },

  // 从 localStorage 加载
  loadFromStorage(type) {
    try {
      const key = MemoryConfig.STORAGE_KEYS[type.toUpperCase()];
      const data = localStorage.getItem(key);
      if (data) {
        const items = JSON.parse(data);
        this.cache[type] = new Map(items.map(item => [item.key, new MemoryItem(item.type, item.key, item.content, item.metadata)]));
      }
    } catch (e) {
      console.error(`Failed to load ${type} memory:`, e);
      this.cache[type] = new Map();
    }
  },

  // 保存到 localStorage
  saveToStorage(type) {
    try {
      const key = MemoryConfig.STORAGE_KEYS[type.toUpperCase()];
      const items = Array.from(this.cache[type].values()).map(item => item.toJSON());
      localStorage.setItem(key, JSON.stringify(items));
    } catch (e) {
      console.error(`Failed to save ${type} memory:`, e);
      this.cleanup(type);
      this.saveToStorage(type);
    }
  },

  // 添加记忆
  add(type, key, content, metadata = {}) {
    const item = new MemoryItem(type, key, content, metadata);
    this.cache[type].set(key, item);
    this.saveToStorage(type);
    return item;
  },

  // 获取记忆
  get(type, key) {
    const item = this.cache[type].get(key);
    if (item) {
      item.touch();
      this.saveToStorage(type);
    }
    return item ? item.content : null;
  },

  // 检查是否存在
  has(type, key) {
    return this.cache[type].has(key);
  },

  // 删除记忆
  delete(type, key) {
    const result = this.cache[type].delete(key);
    if (result) this.saveToStorage(type);
    return result;
  },

  // 清空类型记忆
  clear(type) {
    this.cache[type].clear();
    this.saveToStorage(type);
  },

  // 搜索记忆
  search(type, query, limit = 10) {
    const results = [];
    const lowerQuery = query.toLowerCase();

    for (const [key, item] of this.cache[type]) {
      if (key.toLowerCase().includes(lowerQuery) ||
          item.content.toLowerCase().includes(lowerQuery) ||
          item.metadata.tags.some(tag => tag.toLowerCase().includes(lowerQuery))) {
        results.push(item);
      }
    }

    return results
      .sort((a, b) => b.metadata.accessCount - a.metadata.accessCount)
      .slice(0, limit)
      .map(item => item.toJSON());
  },

  // 获取所有记忆
  getAll(type) {
    return Array.from(this.cache[type].values())
      .map(item => item.toJSON())
      .sort((a, b) => b.metadata.updated - a.metadata.updated);
  },

  // 清理过期和低价值记忆
  cleanup(type) {
    const maxItems = MemoryConfig.MAX_ITEMS[type.toUpperCase()];
    const items = Array.from(this.cache[type].values());

    // 移除过期的
    const expiry = MemoryConfig.EXPIRY[type.toUpperCase()];
    const validItems = expiry > 0
      ? items.filter(item => Date.now() - item.metadata.created < expiry)
      : items;

    // 如果超量，移除最少访问的
    if (validItems.length > maxItems) {
      validItems.sort((a, b) => {
        // 优先保留最近更新的
        const aScore = a.metadata.accessCount * 0.3 + (Date.now() - a.metadata.accessed) * -0.0001;
        const bScore = b.metadata.accessCount * 0.3 + (Date.now() - b.metadata.accessed) * -0.0001;
        return bScore - aScore;
      });
      validItems.splice(maxItems);
    }

    this.cache[type] = new Map(validItems.map(item => [item.key, item]));
  }
};

// ============================================================
// 四、上下文构建器
// ============================================================
const ContextBuilder = {
  /**
   * 构建完整的上下文提示
   */
  build(options = {}) {
    const {
      includeUser = true,
      includeProject = true,
      includeSession = true,
      maxLength = 4000
    } = options;

    const parts = [];

    if (includeUser) {
      const userMemory = this.buildUserContext();
      if (userMemory) parts.push(userMemory);
    }

    if (includeProject) {
      const projectMemory = this.buildProjectContext();
      if (projectMemory) parts.push(projectMemory);
    }

    if (includeSession) {
      const sessionMemory = this.buildSessionContext();
      if (sessionMemory) parts.push(sessionMemory);
    }

    let context = parts.join('\n\n');

    // 截断到最大长度
    if (context.length > maxLength) {
      context = context.substring(0, maxLength) + '\n\n[上下文过长，已截断]';
    }

    return context;
  },

  /**
   * 构建用户级上下文
   */
  buildUserContext() {
    const items = MemoryStore.getAll('user');
    if (items.length === 0) return null;

    const preferences = items.filter(i => i.metadata.source === 'preference');
    const patterns = items.filter(i => i.metadata.source === 'pattern');

    let context = '【用户偏好】';
    if (preferences.length > 0) {
      context += '\n' + preferences.map(p => `- ${p.content}`).join('\n');
    }
    if (patterns.length > 0) {
      context += '\n\n【常见模式】';
      context += '\n' + patterns.map(p => `- ${p.content}`).join('\n');
    }

    return context;
  },

  /**
   * 构建项目级上下文（从 CLAUDE.md 或项目记忆）
   */
  buildProjectContext() {
    const items = MemoryStore.getAll('project');
    if (items.length === 0) return null;

    let context = '【项目上下文】';
    context += '\n' + items.map(item => `- ${item.content}`).join('\n');

    return context;
  },

  /**
   * 构建会话级上下文
   */
  buildSessionContext() {
    const items = MemoryStore.getAll('session');
    if (items.length === 0) return null;

    // 只取最近的任务和决策
    const recent = items.slice(0, 5);
    let context = '【当前会话】';
    context += '\n' + recent.map(item => `- ${item.content}`).join('\n');

    return context;
  }
};

// ============================================================
// 五、快速记忆操作
// ============================================================
const QuickMemory = {
  /**
   * 保存用户偏好
   */
  savePreference(key, value) {
    MemoryStore.add('user', `pref_${key}`, value, {
      source: 'preference',
      tags: ['preference', key]
    });
  },

  /**
   * 获取用户偏好
   */
  getPreference(key) {
    return MemoryStore.get('user', `pref_${key}`);
  },

  /**
   * 记录模式（用户习惯）
   */
  recordPattern(description) {
    MemoryStore.add('user', `pattern_${Date.now()}`, description, {
      source: 'pattern',
      tags: ['pattern']
    });
  },

  /**
   * 保存项目约定
   */
  saveProjectConvention(key, value) {
    MemoryStore.add('project', key, value, {
      source: 'convention',
      tags: ['convention', key]
    });
  },

  /**
   * 获取项目约定
   */
  getProjectConvention(key) {
    return MemoryStore.get('project', key);
  },

  /**
   * 保存会话任务
   */
  saveTask(description) {
    MemoryStore.add('session', `task_${Date.now()}`, description, {
      source: 'task',
      tags: ['task']
    });
  },

  /**
   * 保存决策
   */
  saveDecision(decision, reason) {
    MemoryStore.add('session', `decision_${Date.now()}`, `${decision}（原因：${reason}）`, {
      source: 'decision',
      tags: ['decision']
    });
  }
};

// ============================================================
// 六、导出
// ============================================================
window.MemorySystem = {
  Config: MemoryConfig,
  Store: MemoryStore,
  ContextBuilder,
  Quick: QuickMemory,

  // 便捷方法
  init: () => MemoryStore.init(),
  save: (type, key, content, meta) => MemoryStore.add(type, key, content, meta),
  get: (type, key) => MemoryStore.get(type, key),
  search: (type, query, limit) => MemoryStore.search(type, query, limit),
  clear: (type) => MemoryStore.clear(type),
  buildContext: (options) => ContextBuilder.build(options)
};
