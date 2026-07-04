/**
 * TriGen 会话持久化系统 v2.0
 * 基于 Codex Thread 模型设计
 * SQLite 持久化，支持会话恢复和分叉
 */
'use strict';

// ============================================================
// 一、数据结构定义
// ============================================================

/**
 * 消息项
 */
class MessageItem {
  constructor(role, content, metadata = {}) {
    this.id = this.generateId();
    this.role = role; // 'user' | 'assistant' | 'system' | 'tool'
    this.content = content;
    this.metadata = {
      timestamp: Date.now(),
      model: metadata.model || null,
      tokens: metadata.tokens || 0,
      cost: metadata.cost || 0,
      toolCalls: metadata.toolCalls || [],
      attachments: metadata.attachments || [],
      ...metadata
    };
  }

  generateId() {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  toJSON() {
    return {
      id: this.id,
      role: this.role,
      content: this.content,
      metadata: this.metadata
    };
  }
}

/**
 * 会话 Turn（一次对话往返）
 */
class Turn {
  constructor() {
    this.id = `turn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    this.items = [];
    this.status = 'active'; // active | completed | failed
    this.startTime = Date.now();
    this.endTime = null;
    this.summary = '';
  }

  addItem(item) {
    this.items.push(item instanceof MessageItem ? item.toJSON() : item);
  }

  complete(summary = '') {
    this.status = 'completed';
    this.endTime = Date.now();
    this.summary = summary;
  }

  fail(error) {
    this.status = 'failed';
    this.endTime = Date.now();
    this.summary = error;
  }

  toJSON() {
    return {
      id: this.id,
      items: this.items,
      status: this.status,
      startTime: this.startTime,
      endTime: this.endTime,
      duration: this.endTime ? this.endTime - this.startTime : null,
      summary: this.summary
    };
  }
}

/**
 * 会话 Thread
 */
class Thread {
  constructor(title = '新会话', metadata = {}) {
    this.id = this.generateId();
    this.title = title;
    this.turns = [];
    this.currentTurn = null;
    this.metadata = {
      created: Date.now(),
      updated: Date.now(),
      model: metadata.model || 'deepseekv3',
      tags: metadata.tags || [],
      pinned: false,
      archived: false,
      ...metadata
    };
  }

  generateId() {
    return `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  newTurn() {
    if (this.currentTurn && this.currentTurn.items.length === 0) {
      return this.currentTurn;
    }
    this.currentTurn = new Turn();
    return this.currentTurn;
  }

  addMessage(role, content, metadata = {}) {
    if (!this.currentTurn) {
      this.newTurn();
    }
    const item = new MessageItem(role, content, metadata);
    this.currentTurn.addItem(item);
    this.metadata.updated = Date.now();
    return item;
  }

  completeTurn(summary = '') {
    if (this.currentTurn) {
      this.currentTurn.complete(summary);
      this.turns.push(this.currentTurn.toJSON());
      this.currentTurn = null;
    }
  }

  toJSON() {
    return {
      id: this.id,
      title: this.title,
      turns: this.turns,
      currentTurn: this.currentTurn ? this.currentTurn.toJSON() : null,
      metadata: this.metadata
    };
  }

  /**
   * 分叉会话（创建副本）
   */
  fork(newTitle) {
    const forked = new Thread(newTitle || `${this.title} (副本)`, {
      ...this.metadata,
      forkedFrom: this.id,
      forkedAt: Date.now()
    });

    // 复制所有 turns
    this.turns.forEach(turn => {
      forked.turns.push({ ...turn });
    });

    return forked;
  }
}

// ============================================================
// 二、会话存储（IndexedDB 实现）
// ============================================================
const SessionStore = {
  DB_NAME: 'TrigenSessions',
  DB_VERSION: 1,
  STORE_NAME: 'threads',
  db: null,

  /**
   * 初始化数据库
   */
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

      request.onerror = () => reject(request.error);

      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // 创建 threads 存储
        if (!db.objectStoreNames.contains(this.STORE_NAME)) {
          const store = db.createObjectStore(this.STORE_NAME, { keyPath: 'id' });

          // 索引
          store.createIndex('updated', 'metadata.updated', { unique: false });
          store.createIndex('pinned', 'metadata.pinned', { unique: false });
          store.createIndex('archived', 'metadata.archived', { unique: false });
          store.createIndex('tags', 'metadata.tags', { unique: false, multiEntry: true });
        }
      };
    });
  },

  /**
   * 保存会话
   */
  async save(thread) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
      const store = transaction.objectStore(this.STORE_NAME);
      const data = thread instanceof Thread ? thread.toJSON() : thread;
      data.metadata.updated = Date.now();

      const request = store.put(data);
      request.onsuccess = () => resolve(data.id);
      request.onerror = () => reject(request.error);
    });
  },

  /**
   * 获取会话
   */
  async get(threadId) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.STORE_NAME], 'readonly');
      const store = transaction.objectStore(this.STORE_NAME);
      const request = store.get(threadId);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  /**
   * 删除会话
   */
  async delete(threadId) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
      const store = transaction.objectStore(this.STORE_NAME);
      const request = store.delete(threadId);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  },

  /**
   * 列出所有会话
   */
  async list(options = {}) {
    if (!this.db) await this.init();

    const {
      limit = 50,
      offset = 0,
      archived = false,
      pinned = null,
      tag = null,
      search = null
    } = options;

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.STORE_NAME], 'readonly');
      const store = transaction.objectStore(this.STORE_NAME);
      const results = [];
      let skipped = 0;
      let count = 0;

      const request = store.openCursor();

      request.onsuccess = (event) => {
        const cursor = event.target.result;

        if (cursor && count < limit) {
          const thread = cursor.value;

          // 过滤条件
          if (thread.metadata.archived === archived) {
            if (pinned === null || thread.metadata.pinned === pinned) {
              if (!tag || thread.metadata.tags.includes(tag)) {
                if (!search || thread.title.toLowerCase().includes(search.toLowerCase())) {
                  if (skipped >= offset) {
                    results.push({
                      id: thread.id,
                      title: thread.title,
                      turnCount: thread.turns.length,
                      metadata: thread.metadata
                    });
                    count++;
                  } else {
                    skipped++;
                  }
                }
              }
            }
          }
          cursor.continue();
        } else {
          resolve(results);
        }
      };

      request.onerror = () => reject(request.error);
    });
  },

  /**
   * 清空归档会话
   */
  async clearArchived() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([this.STORE_NAME], 'readwrite');
      const store = transaction.objectStore(this.STORE_NAME);
      const request = store.openCursor();

      let deleted = 0;

      request.onsuccess = (event) => {
        const cursor = event.target.result;

        if (cursor) {
          if (cursor.value.metadata.archived) {
            cursor.delete();
            deleted++;
          }
          cursor.continue();
        } else {
          resolve(deleted);
        }
      };

      request.onerror = () => reject(request.error);
    });
  },

  /**
   * 导出会话数据
   */
  async export(threadId) {
    const thread = await this.get(threadId);
    if (!thread) return null;

    return JSON.stringify(thread, null, 2);
  },

  /**
   * 导入会话数据
   */
  async import(jsonString) {
    try {
      const data = JSON.parse(jsonString);

      // 生成新 ID
      data.id = `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      data.metadata.imported = Date.now();

      await this.save(data);
      return data.id;
    } catch (e) {
      throw new Error(`导入失败: ${e.message}`);
    }
  }
};

// ============================================================
// 三、会话管理器
// ============================================================
const SessionManager = {
  // 当前会话
  currentThread: null,

  // 会话列表缓存
  threadList: [],

  // 事件监听器
  listeners: {
    onThreadChange: [],
    onMessageAdd: [],
    onTurnComplete: []
  },

  /**
   * 初始化
   */
  async init() {
    await SessionStore.init();
    await this.refreshList();
  },

  /**
   * 创建新会话
   */
  create(title, metadata = {}) {
    this.currentThread = new Thread(title, metadata);
    SessionStore.save(this.currentThread);
    this.refreshList();
    this.emit('onThreadChange', this.currentThread);
    return this.currentThread;
  },

  /**
   * 加载会话
   */
  async load(threadId) {
    const data = await SessionStore.get(threadId);
    if (!data) return null;

    // 重建对象
    this.currentThread = new Thread(data.title, data.metadata);
    this.currentThread.id = data.id;
    this.currentThread.turns = data.turns || [];
    if (data.currentTurn) {
      this.currentTurn = new Turn();
      this.currentThread.currentTurn = data.currentTurn;
    }

    this.emit('onThreadChange', this.currentThread);
    return this.currentThread;
  },

  /**
   * 保存当前会话
   */
  async save() {
    if (this.currentThread) {
      await SessionStore.save(this.currentThread);
      await this.refreshList();
    }
  },

  /**
   * 添加消息
   */
  addMessage(role, content, metadata = {}) {
    if (!this.currentThread) {
      this.create('新会话');
    }

    const item = this.currentThread.addMessage(role, content, metadata);
    this.emit('onMessageAdd', item);
    return item;
  },

  /**
   * 完成当前 Turn
   */
  completeTurn(summary = '') {
    if (this.currentThread) {
      this.currentThread.completeTurn(summary);
      this.emit('onTurnComplete', this.currentThread.currentTurn);
      this.save();
    }
  },

  /**
   * 分叉会话
   */
  async fork(newTitle) {
    if (!this.currentThread) return null;

    const forked = this.currentThread.fork(newTitle);
    await SessionStore.save(forked);
    await this.refreshList();

    return forked;
  },

  /**
   * 归档会话
   */
  async archive() {
    if (!this.currentThread) return;

    this.currentThread.metadata.archived = true;
    await this.save();
  },

  /**
   * 删除会话
   */
  async delete(threadId) {
    await SessionStore.delete(threadId);
    await this.refreshList();

    if (this.currentThread && this.currentThread.id === threadId) {
      this.currentThread = null;
    }
  },

  /**
   * 刷新会话列表
   */
  async refreshList() {
    this.threadList = await SessionStore.list({ limit: 100 });
  },

  /**
   * 搜索会话
   */
  async search(query) {
    return await SessionStore.list({ search: query });
  },

  /**
   * 导出当前会话
   */
  async export() {
    if (!this.currentThread) return null;
    return await SessionStore.export(this.currentThread.id);
  },

  /**
   * 导入会话
   */
  async import(jsonString) {
    const id = await SessionStore.import(jsonString);
    await this.refreshList();
    return id;
  },

  /**
   * 获取当前会话的消息历史
   */
  getHistory() {
    if (!this.currentThread) return [];

    const messages = [];

    // 添加系统消息
    messages.push({ role: 'system', content: PLATFORM_SYSTEM_PROMPT });

    // 添加所有 turns
    for (const turn of this.currentThread.turns) {
      for (const item of turn.items) {
        messages.push({ role: item.role, content: item.content });
      }
    }

    return messages;
  },

  // 事件系统
  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].push(callback);
    }
  },

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }
  },

  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(cb => cb(data));
    }
  }
};

// ============================================================
// 四、轨迹记录器
// ============================================================
const TrajectoryRecorder = {
  recordings: [],

  /**
   * 记录一步操作
   */
  record(action, data = {}) {
    this.recordings.push({
      timestamp: Date.now(),
      action,
      data
    });

    // 持久化到 localStorage
    this.save();
  },

  /**
   * 保存到 localStorage
   */
  save() {
    try {
      const data = JSON.stringify(this.recordings.slice(-1000)); // 保留最近 1000 条
      localStorage.setItem('trigen_trajectory', data);
    } catch (e) {
      // 存储满时清理旧数据
      this.recordings = this.recordings.slice(-500);
      this.save();
    }
  },

  /**
   * 加载
   */
  load() {
    try {
      const data = localStorage.getItem('trigen_trajectory');
      if (data) {
        this.recordings = JSON.parse(data);
      }
    } catch (e) {
      this.recordings = [];
    }
  },

  /**
   * 清空
   */
  clear() {
    this.recordings = [];
    localStorage.removeItem('trigen_trajectory');
  },

  /**
   * 获取最近的轨迹
   */
  getRecent(limit = 50) {
    return this.recordings.slice(-limit);
  }
};

// 初始化加载
TrajectoryRecorder.load();

// ============================================================
// 五、导出
// ============================================================
window.SessionSystem = {
  Thread,
  Turn,
  MessageItem,
  Store: SessionStore,
  Manager: SessionManager,
  Trajectory: TrajectoryRecorder,

  // 便捷方法
  init: () => SessionManager.init(),
  create: (title, meta) => SessionManager.create(title, meta),
  load: (id) => SessionManager.load(id),
  save: () => SessionManager.save(),
  addMessage: (role, content, meta) => SessionManager.addMessage(role, content, meta),
  getHistory: () => SessionManager.getHistory(),
  fork: (title) => SessionManager.fork(title),
  archive: () => SessionManager.archive(),
  delete: (id) => SessionManager.delete(id),
  list: () => SessionManager.threadList,
  export: () => SessionManager.export(),
  import: (json) => SessionManager.import(json)
};
