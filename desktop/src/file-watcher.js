/**
 * Y·NEX Desktop — 原生文件监听 + 增量索引
 * 使用 fs.watch 替代轮询，仅扫描变化目录
 */

const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

class NativeFileWatcher extends EventEmitter {
  constructor() {
    super();
    this.watchers = new Map();    // path -> FSWatcher
    this.watchQueue = new Set();   // 待处理的文件变化事件
    this.debounceMs = 100;
    this.debounceTimer = null;
    this.active = false;
  }

  /**
   * 开始监听工作区
   */
  watch(workspacePath) {
    this.unwatch();
    this.active = true;
    this._watchRecursive(workspacePath, 0);
    return { ok: true, watched: this.watchers.size };
  }

  _watchRecursive(dir, depth) {
    if (depth > 8 || !this.active) return;
    try {
      // 跳过不需要监听的目录
      const skip = ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build', '.next', '.cache'];
      const watcher = fs.watch(dir, { persistent: true, recursive: false }, (eventType, filename) => {
        if (!filename || skip.some(s => filename.includes(s))) return;
        this._onChange(eventType, path.join(dir, filename));
      });
      watcher.on('error', () => {});
      this.watchers.set(dir, watcher);

      // 递归监听子目录
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && !entry.name.startsWith('.') && !skip.includes(entry.name)) {
          this._watchRecursive(path.join(dir, entry.name), depth + 1);
        }
      }
    } catch (e) {}
  }

  _onChange(eventType, filePath) {
    this.watchQueue.add({ event: eventType, path: filePath, time: Date.now() });
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this._flush(), this.debounceMs);
  }

  _flush() {
    const events = [...this.watchQueue];
    this.watchQueue.clear();

    // 去重：同一文件的多次变化合并
    const deduped = new Map();
    for (const evt of events) {
      const key = evt.path;
      if (!deduped.has(key) || evt.time > deduped.get(key).time) {
        deduped.set(key, evt);
      }
    }

    // 分类事件
    const added = [];
    const changed = [];
    const deleted = [];

    for (const [fp, evt] of deduped) {
      try {
        if (!fs.existsSync(fp)) {
          deleted.push(fp);
        } else if (evt.event === 'rename') {
          // 检查是新增还是删除
          const stat = fs.statSync(fp);
          if (stat.isFile()) added.push(fp);
        } else {
          changed.push(fp);
        }
      } catch (e) {
        deleted.push(fp);
      }
    }

    if (added.length > 0) this.emit('add', added);
    if (changed.length > 0) this.emit('change', changed);
    if (deleted.length > 0) this.emit('delete', deleted);
    if (added.length + changed.length + deleted.length > 0) {
      this.emit('any', { added, changed, deleted });
    }
  }

  unwatch() {
    this.active = false;
    for (const [dir, watcher] of this.watchers) {
      try { watcher.close(); } catch (e) {}
    }
    this.watchers.clear();
    this.watchQueue.clear();
  }

  stats() {
    return {
      watchedDirs: this.watchers.size,
      pendingEvents: this.watchQueue.size,
      active: this.active,
    };
  }
}

module.exports = { NativeFileWatcher };