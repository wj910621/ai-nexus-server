/**
 * Y·NEX Desktop — 内容寻址存储 + 文件去重
 * 相同内容的文件只存储一份，节省内存和磁盘
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

class ContentAddressableStorage {
  constructor() {
    this.store = new Map();       // hash -> { content, refs: Set<path> }
    this.maxStoreSize = 100 * 1024 * 1024; // 100MB
    this.storeSize = 0;
    this.dedupSavings = 0;
  }

  /**
   * 存储文件内容（去重）
   */
  put(filePath, content) {
    const hash = this._hash(content);
    const existing = this.store.get(hash);

    if (existing) {
      // 内容已存在，只增加引用
      existing.refs.add(filePath);
      this.dedupSavings += content.length;
      return { hash, deduplicated: true, refs: existing.refs.size };
    }

    // 新内容
    if (this.storeSize + content.length > this.maxStoreSize) {
      this.evict();
    }

    this.store.set(hash, {
      content,
      refs: new Set([filePath]),
      size: content.length,
      timestamp: Date.now(),
    });
    this.storeSize += content.length;
    return { hash, deduplicated: false, refs: 1 };
  }

  /**
   * 获取文件内容
   */
  get(filePath) {
    for (const [hash, entry] of this.store) {
      if (entry.refs.has(filePath)) {
        return entry.content;
      }
    }
    return null;
  }

  /**
   * 删除文件引用
   */
  remove(filePath) {
    for (const [hash, entry] of this.store) {
      if (entry.refs.has(filePath)) {
        entry.refs.delete(filePath);
        if (entry.refs.size === 0) {
          this.storeSize -= entry.size;
          this.store.delete(hash);
        }
        return true;
      }
    }
    return false;
  }

  /**
   * 淘汰最久未使用的条目
   */
  evict(count = 10) {
    const entries = [...this.store.entries()]
      .sort((a, b) => a[1].timestamp - b[1].timestamp);

    for (let i = 0; i < Math.min(count, entries.length); i++) {
      const [hash, entry] = entries[i];
      this.storeSize -= entry.size;
      this.store.delete(hash);
    }
  }

  _hash(content) {
    return crypto.createHash('sha256').update(content).digest('hex').slice(0, 16);
  }

  stats() {
    let totalRefs = 0;
    for (const entry of this.store.values()) {
      totalRefs += entry.refs.size;
    }
    return {
      uniqueContents: this.store.size,
      totalRefs,
      storeSizeMB: (this.storeSize / 1024 / 1024).toFixed(1),
      dedupSavingsMB: (this.dedupSavings / 1024 / 1024).toFixed(1),
      dedupRatio: this.storeSize + this.dedupSavings > 0
        ? ((this.dedupSavings / (this.storeSize + this.dedupSavings)) * 100).toFixed(1) + '%'
        : '0%',
    };
  }

  shutdown() {
    this.store.clear();
    this.storeSize = 0;
    this.dedupSavings = 0;
  }
}

/**
 * 懒加载模块注册表
 * 延迟加载非关键模块，减少启动时间
 */
class LazyModuleRegistry {
  constructor() {
    this.modules = new Map();    // name -> { factory, instance, loaded }
    this.loadOrder = [];
  }

  register(name, factory, priority = 100) {
    this.modules.set(name, { factory, instance: null, loaded: false, priority });
    this.loadOrder.push({ name, priority });
    this.loadOrder.sort((a, b) => a.priority - b.priority);
  }

  get(name) {
    const mod = this.modules.get(name);
    if (!mod) return undefined;
    if (!mod.loaded) {
      mod.instance = mod.factory();
      mod.loaded = true;
    }
    return mod.instance;
  }

  /**
   * 按优先级批量加载
   */
  async loadAll() {
    const results = [];
    for (const { name } of this.loadOrder) {
      try {
        const instance = this.get(name);
        results.push({ name, ok: true });
      } catch (e) {
        results.push({ name, ok: false, error: e.message });
      }
      // 每 5 个让出事件循环
      if (results.length % 5 === 0) {
        await new Promise(r => setImmediate(r));
      }
    }
    return results;
  }

  /**
   * 空闲时加载低优先级模块
   */
  loadIdle() {
    const idle = this.loadOrder.filter(({ name }) => {
      const mod = this.modules.get(name);
      return mod && !mod.loaded && mod.priority > 50;
    });
    for (const { name } of idle) {
      setImmediate(() => this.get(name));
    }
  }

  stats() {
    let loaded = 0;
    for (const mod of this.modules.values()) {
      if (mod.loaded) loaded++;
    }
    return { total: this.modules.size, loaded, pending: this.modules.size - loaded };
  }
}

module.exports = { ContentAddressableStorage, LazyModuleRegistry };