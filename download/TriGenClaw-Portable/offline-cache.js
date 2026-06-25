/**
 * 离线缓存管理模块
 * 用于 Electron 本地缓存和离线支持
 */

const fs = require('fs');
const path = require('path');

class OfflineCache {
  constructor(cacheDir) {
    this.cacheDir = cacheDir;
    this.cacheFile = path.join(cacheDir, 'offline-cache.json');
    this.init();
  }

  init() {
    try {
      if (!fs.existsSync(this.cacheDir)) {
        fs.mkdirSync(this.cacheDir, { recursive: true });
      }
      // 确保缓存文件存在
      if (!fs.existsSync(this.cacheFile)) {
        fs.writeFileSync(this.cacheFile, '{}', 'utf8');
      }
    } catch (e) {
      console.error('OfflineCache 初始化失败:', e);
    }
  }

  get(key) {
    try {
      const data = this._readData();
      return data[key] || null;
    } catch (e) {
      console.error('OfflineCache.get 错误:', e);
      return null;
    }
  }

  set(key, value, ttl = 86400000) {
    try {
      const data = this._readData();
      data[key] = {
        value: value,
        expiry: Date.now() + ttl,
        created: Date.now()
      };
      this._writeData(data);
      return true;
    } catch (e) {
      console.error('OfflineCache.set 错误:', e);
      return false;
    }
  }

  delete(key) {
    try {
      const data = this._readData();
      if (data[key]) {
        delete data[key];
        this._writeData(data);
        return true;
      }
      return false;
    } catch (e) {
      console.error('OfflineCache.delete 错误:', e);
      return false;
    }
  }

  isExpired(key) {
    try {
      const item = this.get(key);
      if (!item) return true;
      return Date.now() > item.expiry;
    } catch (e) {
      return true;
    }
  }

  clear() {
    try {
      this._writeData({});
      return true;
    } catch (e) {
      console.error('OfflineCache.clear 错误:', e);
      return false;
    }
  }

  cleanup() {
    try {
      const data = this._readData();
      const now = Date.now();
      let cleaned = 0;
      const newData = {};

      for (const key in data) {
        if (data[key] && data[key].expiry > now) {
          newData[key] = data[key];
        } else {
          cleaned++;
        }
      }

      this._writeData(newData);
      console.log(`OfflineCache 清理完成: 删除了 ${cleaned} 个过期项`);
      return cleaned;
    } catch (e) {
      console.error('OfflineCache.cleanup 错误:', e);
      return 0;
    }
  }

  keys() {
    try {
      const data = this._readData();
      return Object.keys(data);
    } catch (e) {
      return [];
    }
  }

  size() {
    try {
      const data = this._readData();
      return Object.keys(data).length;
    } catch (e) {
      return 0;
    }
  }

  getStats() {
    try {
      const data = this._readData();
      const now = Date.now();
      let active = 0;
      let expired = 0;
      let totalSize = 0;

      for (const key in data) {
        if (data[key]) {
          if (data[key].expiry > now) {
            active++;
          } else {
            expired++;
          }
          totalSize += JSON.stringify(data[key]).length;
        }
      }

      return {
        total: Object.keys(data).length,
        active: active,
        expired: expired,
        sizeBytes: totalSize,
        sizeKB: (totalSize / 1024).toFixed(2)
      };
    } catch (e) {
      return null;
    }
  }

  _readData() {
    try {
      const content = fs.readFileSync(this.cacheFile, 'utf8');
      return JSON.parse(content) || {};
    } catch (e) {
      return {};
    }
  }

  _writeData(data) {
    try {
      fs.writeFileSync(this.cacheFile, JSON.stringify(data, null, 2), 'utf8');
    } catch (e) {
      console.error('OfflineCache _writeData 错误:', e);
    }
  }
}

module.exports = OfflineCache;
