/**
 * TriGenClaw 桌面端会话系统 v2.0
 * 基于 Codex Thread 模型，适配 Electron 环境
 */
'use strict';

// ============================================================
// 一、桌面端会话管理
// ============================================================
const DesktopSession = {
  // 当前会话
  currentThread: null,
  threadList: [],

  /**
   * 初始化
   */
  async init() {
    // 加载上次会话
    await this.loadLastSession();
  },

  /**
   * 加载上次会话
   */
  async loadLastSession() {
    try {
      const lastId = localStorage.getItem('trigen_last_session');
      if (lastId) {
        const data = localStorage.getItem(`trigen_session_${lastId}`);
        if (data) {
          this.currentThread = JSON.parse(data);
        }
      }
    } catch (e) {
      console.error('加载会话失败:', e);
    }
  },

  /**
   * 创建新会话
   */
  create(title, metadata = {}) {
    this.currentThread = {
      id: `thread_${Date.now()}`,
      title: title || '新会话',
      messages: [],
      metadata: {
        created: Date.now(),
        updated: Date.now(),
        model: metadata.model || 'deepseekv3',
        ...metadata
      }
    };

    this.save();
    return this.currentThread;
  },

  /**
   * 添加消息
   */
  addMessage(role, content, metadata = {}) {
    if (!this.currentThread) {
      this.create();
    }

    const msg = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      role,
      content,
      timestamp: Date.now(),
      ...metadata
    };

    this.currentThread.messages.push(msg);
    this.currentThread.metadata.updated = Date.now();
    this.save();

    return msg;
  },

  /**
   * 保存到 localStorage
   */
  save() {
    if (!this.currentThread) return;

    try {
      // 保存当前会话
      localStorage.setItem(
        `trigen_session_${this.currentThread.id}`,
        JSON.stringify(this.currentThread)
      );

      // 更新会话列表
      this.updateThreadList();

      // 记录最后会话 ID
      localStorage.setItem('trigen_last_session', this.currentThread.id);
    } catch (e) {
      console.error('保存会话失败:', e);
      // 清理旧数据
      this.cleanup();
      this.save();
    }
  },

  /**
   * 更新会话列表
   */
  updateThreadList() {
    const threads = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('trigen_session_')) {
        try {
          const data = JSON.parse(localStorage.getItem(key));
          if (data && data.metadata) {
            threads.push({
              id: data.id,
              title: data.title,
              messageCount: data.messages ? data.messages.length : 0,
              updated: data.metadata.updated
            });
          }
        } catch (e) {
          // 忽略损坏的数据
        }
      }
    }

    threads.sort((a, b) => b.updated - a.updated);
    this.threadList = threads.slice(0, 50);
  },

  /**
   * 清理旧数据
   */
  cleanup() {
    const threads = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('trigen_session_')) {
        threads.push({
          key,
          data: JSON.parse(localStorage.getItem(key) || '{}')
        });
      }
    }

    // 按更新时间排序，保留最近 20 个
    threads.sort((a, b) => (b.data.metadata?.updated || 0) - (a.data.metadata?.updated || 0));

    threads.slice(20).forEach(t => {
      localStorage.removeItem(t.key);
    });
  },

  /**
   * 删除会话
   */
  delete(threadId) {
    localStorage.removeItem(`trigen_session_${threadId}`);
    this.updateThreadList();

    if (this.currentThread && this.currentThread.id === threadId) {
      this.currentThread = null;
    }
  },

  /**
   * 获取消息历史（用于 API 调用）
   */
  getHistory() {
    if (!this.currentThread) return [];

    const messages = [];

    // 添加系统消息
    messages.push({ role: 'system', content: PLATFORM_SYSTEM_PROMPT });

    // 添加历史消息
    for (const msg of this.currentThread.messages) {
      messages.push({ role: msg.role, content: msg.content });
    }

    return messages;
  },

  /**
   * 分叉会话
   */
  fork() {
    if (!this.currentThread) return null;

    const forked = this.create(`${this.currentThread.title} (副本)`, {
      forkedFrom: this.currentThread.id
    });

    // 复制消息
    forked.messages = [...this.currentThread.messages];

    this.save();
    return forked;
  },

  /**
   * 导出当前会话
   */
  export() {
    if (!this.currentThread) return null;
    return JSON.stringify(this.currentThread, null, 2);
  },

  /**
   * 导入会话
   */
  import(jsonString) {
    try {
      const data = JSON.parse(jsonString);
      data.id = `thread_${Date.now()}`;
      data.metadata.imported = Date.now();
      localStorage.setItem(`trigen_session_${data.id}`, JSON.stringify(data));
      this.updateThreadList();
      return data.id;
    } catch (e) {
      throw new Error(`导入失败: ${e.message}`);
    }
  }
};

// ============================================================
// 二、桌面端轨迹记录
// ============================================================
const DesktopTrajectory = {
  recordings: [],

  /**
   * 记录操作
   */
  record(action, data = {}) {
    this.recordings.push({
      timestamp: Date.now(),
      action,
      data
    });

    // 保留最近 500 条
    if (this.recordings.length > 500) {
      this.recordings = this.recordings.slice(-500);
    }

    this.save();
  },

  /**
   * 保存
   */
  save() {
    try {
      localStorage.setItem(
        'trigen_trajectory',
        JSON.stringify(this.recordings)
      );
    } catch (e) {
      // 存储满时清理
      this.recordings = this.recordings.slice(-200);
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
   * 获取最近轨迹
   */
  getRecent(limit = 50) {
    return this.recordings.slice(-limit);
  }
};

// 初始化
DesktopTrajectory.load();

// ============================================================
// 三、导出
// ============================================================
window.DesktopSession = {
  Session: DesktopSession,
  Trajectory: DesktopTrajectory,

  // 便捷方法
  init: () => DesktopSession.init(),
  create: (title, meta) => DesktopSession.create(title, meta),
  addMessage: (role, content, meta) => DesktopSession.addMessage(role, content, meta),
  getHistory: () => DesktopSession.getHistory(),
  save: () => DesktopSession.save(),
  fork: () => DesktopSession.fork(),
  delete: (id) => DesktopSession.delete(id),
  export: () => DesktopSession.export(),
  import: (json) => DesktopSession.import(json),
  list: () => DesktopSession.threadList,
  record: (action, data) => DesktopTrajectory.record(action, data),
  getTrajectory: () => DesktopTrajectory.getRecent()
};
