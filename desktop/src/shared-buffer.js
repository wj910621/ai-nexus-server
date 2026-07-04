/**
 * Y·NEX Desktop — SharedArrayBuffer 零拷贝 IPC + WebWorker 渲染
 * 主进程/渲染进程直接共享内存，零拷贝传输大文件
 */

const { contextBridge } = require('electron');

class SharedBufferIPC {
  constructor() {
    this.buffers = new Map();   // id -> SharedArrayBuffer
    this.meta = new Map();      // id -> { type, size, timestamp }
    this.maxBufferSize = 256 * 1024 * 1024; // 256MB
    this.totalAllocated = 0;
  }

  /**
   * 分配共享内存缓冲区
   */
  allocate(id, size) {
    if (this.totalAllocated + size > this.maxBufferSize) {
      this.gc();
    }
    const sab = new SharedArrayBuffer(size);
    this.buffers.set(id, sab);
    this.meta.set(id, { type: 'buffer', size, timestamp: Date.now() });
    this.totalAllocated += size;
    return sab;
  }

  /**
   * 写入数据到共享缓冲区
   */
  write(id, data, offset = 0) {
    const sab = this.buffers.get(id);
    if (!sab) return false;
    if (typeof data === 'string') {
      new Uint8Array(sab, offset).set(new TextEncoder().encode(data));
    } else if (data instanceof ArrayBuffer || data instanceof SharedArrayBuffer) {
      new Uint8Array(sab, offset).set(new Uint8Array(data));
    } else if (ArrayBuffer.isView(data)) {
      new Uint8Array(sab, offset).set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength));
    }
    return true;
  }

  /**
   * 从共享缓冲区读取
   */
  read(id, offset = 0, length) {
    const sab = this.buffers.get(id);
    if (!sab) return null;
    const view = new Uint8Array(sab, offset, length || sab.byteLength - offset);
    return view;
  }

  /**
   * 读取为字符串
   */
  readString(id, offset = 0, length) {
    const view = this.read(id, offset, length);
    if (!view) return null;
    return new TextDecoder().decode(view);
  }

  /**
   * 释放缓冲区
   */
  release(id) {
    const meta = this.meta.get(id);
    if (meta) {
      this.totalAllocated -= meta.size;
    }
    this.buffers.delete(id);
    this.meta.delete(id);
  }

  /**
   * 垃圾回收：释放过期缓冲区
   */
  gc(ttl = 60000) {
    const now = Date.now();
    for (const [id, meta] of this.meta) {
      if (now - meta.timestamp > ttl) {
        this.release(id);
      }
    }
  }

  /**
   * 获取引用给渲染进程
   */
  getRef(id) {
    return this.buffers.get(id);
  }

  stats() {
    return {
      buffers: this.buffers.size,
      totalAllocatedMB: (this.totalAllocated / 1024 / 1024).toFixed(1),
      maxBufferMB: (this.maxBufferSize / 1024 / 1024).toFixed(0),
    };
  }

  shutdown() {
    this.buffers.clear();
    this.meta.clear();
    this.totalAllocated = 0;
  }
}

/**
 * WebWorker 渲染调度器
 * 将 Monaco 语法高亮等计算密集型任务转移到 Worker
 */
class RenderWorker {
  constructor() {
    this.workers = [];
    this.maxWorkers = 2;
    this.taskQueue = [];
    this.busy = new Set();
  }

  async execute(taskFn, data) {
    // 在 Worker 中执行（简化版：使用主线程异步）
    return new Promise((resolve) => {
      setImmediate(() => {
        try {
          resolve(taskFn(data));
        } catch (e) {
          resolve(null);
        }
      });
    });
  }

  /**
   * 批量渲染：合并多个 DOM 更新到单帧
   */
  scheduleBatch(fn) {
    if (!this._rafId) {
      this._rafId = setImmediate(() => {
        this._rafId = null;
        fn();
      });
    }
  }
}

module.exports = { SharedBufferIPC, RenderWorker };