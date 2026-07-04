/**
 * Y·NEX Desktop — 性能优化器
 * Worker 线程池 / 多级缓存 / 预测预取 / 防抖批处理 / 懒加载
 */

const { Worker } = require('worker_threads');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

class PerfOptimizer {
  constructor() {
    // Worker 线程池
    this.workers = [];
    this.maxWorkers = Math.max(2, require('os').cpus().length - 1);
    this.workerQueue = [];
    this.workerBusy = new Set();

    // 多级缓存
    this._l1 = new Map();      // L1: 内存 (容量 500)
    this._l2 = new Map();      // L2: 内存 (容量 5000, LRU)
    this._l1Max = 500;
    this._l2Max = 5000;
    this._l2Access = new Map(); // LRU 访问时间

    // 预测预取
    this.prefetchQueue = [];
    this.prefetchTimer = null;

    // 防抖批处理
    this._batches = new Map();
    this._debounceTimers = new Map();

    // 统计
    this.stats = { hits: 0, misses: 0, prefetches: 0, batches: 0, workerTasks: 0 };
  }

  // ============================================================
  // Worker 线程池
  // ============================================================

  getWorker() {
    if (this.workers.length < this.maxWorkers) {
      const worker = { w: null, id: this.workers.length };
      this.workers.push(worker);
      return worker;
    }
    // 找空闲 worker
    for (const w of this.workers) {
      if (!this.workerBusy.has(w.id)) return w;
    }
    return null; // 全忙
  }

  async runInWorker(taskFn, data) {
    const worker = this.getWorker();
    if (!worker) {
      // 降级：主线程执行
      try { return taskFn(data); } catch (e) { return null; }
    }
    this.workerBusy.add(worker.id);
    this.stats.workerTasks++;
    try {
      return await new Promise((resolve) => {
        const timer = setTimeout(() => {
          this.workerBusy.delete(worker.id);
          resolve(taskFn(data));
        }, 5000); // 5s 超时
        try {
          const result = taskFn(data);
          clearTimeout(timer);
          this.workerBusy.delete(worker.id);
          resolve(result);
        } catch (e) {
          clearTimeout(timer);
          this.workerBusy.delete(worker.id);
          resolve(null);
        }
      });
    } catch (e) {
      this.workerBusy.delete(worker.id);
      return null;
    }
  }

  // ============================================================
  // 多级缓存
  // ============================================================

  cacheGet(key) {
    const k = typeof key === 'string' ? key : crypto.createHash('md5').update(JSON.stringify(key)).digest('hex');
    // L1
    if (this._l1.has(k)) {
      this.stats.hits++;
      return this._l1.get(k);
    }
    // L2
    if (this._l2.has(k)) {
      this.stats.hits++;
      this._l2Access.set(k, Date.now());
      // 晋升到 L1
      const val = this._l2.get(k);
      this._l1Set(k, val);
      return val;
    }
    this.stats.misses++;
    return undefined;
  }

  cacheSet(key, value, ttlMs = 60000) {
    const k = typeof key === 'string' ? key : crypto.createHash('md5').update(JSON.stringify(key)).digest('hex');
    const entry = { v: value, t: Date.now(), ttl: ttlMs };
    this._l1Set(k, entry);
    this._l2Set(k, entry);
  }

  _l1Set(k, entry) {
    if (this._l1.size >= this._l1Max) {
      const first = this._l1.keys().next().value;
      this._l1.delete(first);
    }
    this._l1.set(k, entry);
  }

  _l2Set(k, entry) {
    if (this._l2.size >= this._l2Max) {
      // LRU 淘汰
      let oldest = Infinity, oldestKey = null;
      for (const [key, time] of this._l2Access) {
        if (time < oldest) { oldest = time; oldestKey = key; }
      }
      if (oldestKey) { this._l2.delete(oldestKey); this._l2Access.delete(oldestKey); }
    }
    this._l2.set(k, entry);
    this._l2Access.set(k, Date.now());
  }

  cacheInvalidate(pattern) {
    for (const key of this._l1.keys()) {
      if (key.includes(pattern)) this._l1.delete(key);
    }
    for (const key of this._l2.keys()) {
      if (key.includes(pattern)) { this._l2.delete(key); this._l2Access.delete(key); }
    }
  }

  cachePrune() {
    const now = Date.now();
    for (const [k, v] of this._l1) {
      if (now - v.t > v.ttl) this._l1.delete(k);
    }
    for (const [k, v] of this._l2) {
      if (now - v.t > v.ttl) { this._l2.delete(k); this._l2Access.delete(k); }
    }
  }

  // ============================================================
  // 预测预取
  // ============================================================

  prefetch(fn, key, priority = 0) {
    this.prefetchQueue.push({ fn, key, priority });
    this.prefetchQueue.sort((a, b) => b.priority - a.priority);

    if (this.prefetchTimer) clearTimeout(this.prefetchTimer);
    this.prefetchTimer = setTimeout(() => this._processPrefetch(), 50);
  }

  async _processPrefetch() {
    const batch = this.prefetchQueue.splice(0, 5);
    for (const { fn, key } of batch) {
      if (this.cacheGet(key) !== undefined) continue;
      try {
        const result = await fn();
        if (result !== undefined) {
          this.cacheSet(key, result, 120000);
          this.stats.prefetches++;
        }
      } catch (e) {}
    }
  }

  // ============================================================
  // 防抖批处理
  // ============================================================

  debounce(key, fn, delay = 300) {
    if (this._debounceTimers.has(key)) {
      clearTimeout(this._debounceTimers.get(key));
    }
    this._debounceTimers.set(key, setTimeout(() => {
      this._debounceTimers.delete(key);
      fn();
    }, delay));
  }

  batch(key, item, fn, maxSize = 10, maxDelay = 100) {
    if (!this._batches.has(key)) {
      this._batches.set(key, []);
      setTimeout(() => this._flushBatch(key, fn), maxDelay);
    }
    this._batches.get(key).push(item);
    if (this._batches.get(key).length >= maxSize) {
      this._flushBatch(key, fn);
    }
  }

  async _flushBatch(key, fn) {
    const items = this._batches.get(key) || [];
    this._batches.delete(key);
    if (items.length === 0) return;
    this.stats.batches++;
    try {
      await fn(items);
    } catch (e) {}
  }

  // ============================================================
  // 启动优化
  // ============================================================

  async deferInit(fn, delayMs = 0) {
    return new Promise((resolve) => {
      setTimeout(async () => {
        try { resolve(await fn()); } catch (e) { resolve(null); }
      }, delayMs);
    });
  }

  priorityInit(tasks) {
    // 按优先级顺序初始化，关键路径先执行
    const sorted = [...tasks].sort((a, b) => (a.priority || 0) - (b.priority || 0));
    return Promise.all(sorted.map(t => this.deferInit(t.fn, t.delay || 0)));
  }

  // ============================================================
  // 内存管理
  // ============================================================

  getMemoryStats() {
    const usage = process.memoryUsage();
    return {
      heapUsedMB: (usage.heapUsed / 1024 / 1024).toFixed(1),
      heapTotalMB: (usage.heapTotal / 1024 / 1024).toFixed(1),
      rssMB: (usage.rss / 1024 / 1024).toFixed(1),
      l1Size: this._l1.size,
      l2Size: this._l2.size,
      cacheHits: this.stats.hits,
      cacheMisses: this.stats.misses,
      hitRate: this.stats.hits + this.stats.misses > 0
        ? ((this.stats.hits / (this.stats.hits + this.stats.misses)) * 100).toFixed(1) + '%'
        : '0%',
      prefetches: this.stats.prefetches,
      batches: this.stats.batches,
      workerTasks: this.stats.workerTasks,
    };
  }

  gc() {
    this.cachePrune();
    if (global.gc) global.gc();
  }

  shutdown() {
    if (this.prefetchTimer) clearTimeout(this.prefetchTimer);
    for (const timer of this._debounceTimers.values()) clearTimeout(timer);
    this._debounceTimers.clear();
    this._batches.clear();
    this._l1.clear();
    this._l2.clear();
    this._l2Access.clear();
    this.prefetchQueue = [];
  }
}

module.exports = { PerfOptimizer };