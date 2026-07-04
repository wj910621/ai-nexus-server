/**
 * Y·NEX Desktop — SQLite 持久化缓存
 * 跨重启缓存复用，用 better-sqlite3 或回退到 JSON 文件
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

class PersistentCache {
  constructor() {
    this.db = null;
    this.sqlite = null;
    this.dbPath = path.join(os.homedir(), '.ynex', 'cache.db');
    this.useSqlite = false;
    this._initDb();
  }

  _initDb() {
    try {
      this.sqlite = require('better-sqlite3');
      const dir = path.dirname(this.dbPath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      this.db = new this.sqlite(this.dbPath);
      this.db.pragma('journal_mode = WAL');
      this.db.pragma('synchronous = NORMAL');
      this.db.pragma('cache_size = -8000');
      this.db.pragma('mmap_size = 268435456');
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS cache (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          ttl INTEGER NOT NULL,
          created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cache_ttl ON cache(ttl);
        CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);
      `);
      this.useSqlite = true;
    } catch (e) {
      // 回退到 JSON 文件
      this.jsonPath = path.join(os.homedir(), '.ynex', 'cache.json');
      this._loadJson();
    }
  }

  _loadJson() {
    try {
      if (fs.existsSync(this.jsonPath)) {
        this._jsonCache = JSON.parse(fs.readFileSync(this.jsonPath, 'utf-8'));
      } else {
        this._jsonCache = {};
      }
    } catch (e) {
      this._jsonCache = {};
    }
  }

  _saveJson() {
    if (this._jsonCache) {
      try {
        const dir = path.dirname(this.jsonPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(this.jsonPath, JSON.stringify(this._jsonCache), 'utf-8');
      } catch (e) {}
    }
  }

  get(key) {
    if (this.useSqlite) {
      try {
        const row = this.db.prepare('SELECT value, ttl, created_at FROM cache WHERE key = ?').get(key);
        if (!row) return undefined;
        if (Date.now() - row.created_at > row.ttl * 1000) {
          this.db.prepare('DELETE FROM cache WHERE key = ?').run(key);
          return undefined;
        }
        // 自动续期 TTL
        this.db.prepare('UPDATE cache SET created_at = ? WHERE key = ?').run(Date.now(), key);
        return JSON.parse(row.value);
      } catch (e) {
        return undefined;
      }
    }
    // JSON fallback
    const entry = this._jsonCache[key];
    if (!entry) return undefined;
    if (Date.now() - entry.t > entry.ttl * 1000) {
      delete this._jsonCache[key];
      return undefined;
    }
    entry.t = Date.now();
    return entry.v;
  }

  set(key, value, ttl = 300) {
    if (this.useSqlite) {
      try {
        const val = JSON.stringify(value);
        this.db.prepare('INSERT OR REPLACE INTO cache (key, value, ttl, created_at) VALUES (?, ?, ?, ?)')
          .run(key, val, ttl, Date.now());
      } catch (e) {}
      return;
    }
    this._jsonCache[key] = { v: value, ttl, t: Date.now() };
    // 延迟保存（防抖）
    if (!this._saveTimer) {
      this._saveTimer = setTimeout(() => {
        this._saveJson();
        this._saveTimer = null;
      }, 5000);
    }
  }

  delete(key) {
    if (this.useSqlite) {
      this.db.prepare('DELETE FROM cache WHERE key = ?').run(key);
      return;
    }
    delete this._jsonCache[key];
  }

  clear() {
    if (this.useSqlite) {
      this.db.prepare('DELETE FROM cache').run();
      return;
    }
    this._jsonCache = {};
    this._saveJson();
  }

  prune() {
    if (this.useSqlite) {
      this.db.prepare("DELETE FROM cache WHERE created_at + ttl * 1000 < ?").run(Date.now());
      return;
    }
    const now = Date.now();
    let changed = false;
    for (const [k, v] of Object.entries(this._jsonCache)) {
      if (now - v.t > v.ttl * 1000) {
        delete this._jsonCache[k];
        changed = true;
      }
    }
    if (changed) this._saveJson();
  }

  stats() {
    if (this.useSqlite) {
      const count = this.db.prepare('SELECT COUNT(*) as c FROM cache').get();
      const size = fs.existsSync(this.dbPath) ? (fs.statSync(this.dbPath).size / 1024).toFixed(1) : 0;
      return { count: count.c, sizeKB: size, backend: 'sqlite' };
    }
    return { count: Object.keys(this._jsonCache).length, sizeKB: 0, backend: 'json' };
  }

  shutdown() {
    if (this.useSqlite) {
      this.db.pragma('optimize');
      this.db.close();
    }
    if (this._saveTimer) {
      clearTimeout(this._saveTimer);
      this._saveJson();
    }
  }
}

module.exports = { PersistentCache };