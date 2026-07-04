/**
 * Y·NEX Desktop — Arena 内存分配器 + 弱引用缓存淘汰
 * 预分配内存池，减少 GC 压力；WeakRef 自动淘汰缓存
 */

class ArenaAllocator {
  constructor(chunkSize = 64 * 1024) {
    this.chunkSize = chunkSize;
    this.chunks = [];
    this.offset = 0;
    this.totalAllocated = 0;
    this.totalReleased = 0;
  }

  /**
   * 分配内存（返回 ArrayBuffer 视图）
   */
  alloc(size) {
    if (size > this.chunkSize) {
      // 超大分配：直接 new
      this.totalAllocated += size;
      return new ArrayBuffer(size);
    }

    // 获取或创建 chunk
    if (this.chunks.length === 0 || this.offset + size > this.chunkSize) {
      this.chunks.push(new ArrayBuffer(this.chunkSize));
      this.offset = 0;
    }

    const chunk = this.chunks[this.chunks.length - 1];
    const view = new Uint8Array(chunk, this.offset, size);
    this.offset += size;
    this.totalAllocated += size;
    return view;
  }

  /**
   * 分配字符串
   */
  allocString(str) {
    const encoded = new TextEncoder().encode(str);
    const buf = this.alloc(encoded.length);
    new Uint8Array(buf).set(encoded);
    return new TextDecoder().decode(buf);
  }

  /**
   * 重置（释放所有内存）
   */
  reset() {
    this.chunks = [];
    this.offset = 0;
    this.totalReleased += this.totalAllocated;
    this.totalAllocated = 0;
  }

  stats() {
    return {
      chunks: this.chunks.length,
      allocatedMB: (this.totalAllocated / 1024 / 1024).toFixed(2),
      releasedMB: (this.totalReleased / 1024 / 1024).toFixed(2),
      chunkSizeKB: (this.chunkSize / 1024).toFixed(0),
    };
  }
}

/**
 * 弱引用缓存：使用 WeakRef + FinalizationRegistry 自动淘汰
 */
class WeakRefCache {
  constructor(maxSize = 1000) {
    this.map = new Map();          // key -> WeakRef
    this.registry = new FinalizationRegistry((key) => {
      this.map.delete(key);
    });
    this.maxSize = maxSize;
    this._hits = 0;
    this._misses = 0;
  }

  get(key) {
    const ref = this.map.get(key);
    if (!ref) {
      this._misses++;
      return undefined;
    }
    const value = ref.deref();
    if (value === undefined) {
      this.map.delete(key);
      this._misses++;
      return undefined;
    }
    this._hits++;
    return value;
  }

  set(key, value) {
    // 容量控制
    if (this.map.size >= this.maxSize) {
      const first = this.map.keys().next().value;
      this.map.delete(first);
    }

    const ref = new WeakRef(value);
    this.registry.register(value, key, ref);
    this.map.set(key, ref);
  }

  delete(key) {
    this.map.delete(key);
  }

  clear() {
    this.map.clear();
  }

  stats() {
    return {
      size: this.map.size,
      hits: this._hits,
      misses: this._misses,
      hitRate: this._hits + this._misses > 0
        ? ((this._hits / (this._hits + this._misses)) * 100).toFixed(1) + '%'
        : '0%',
    };
  }
}

module.exports = { ArenaAllocator, WeakRefCache };