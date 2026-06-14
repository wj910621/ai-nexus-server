/* ========================================
   NexusStorage - IndexedDB 持久化存储层
   替换 localStorage，支持 50MB+，异步非阻塞
   自动迁移现有数据，向后兼容
   ======================================== */
var NexusStorage = (function() {
  'use strict';

  var DB_NAME = 'nexus_ai_studio';
  var DB_VERSION = 1;
  var STORE_NAME = 'data';
  var _db = null;
  var _ready = false;
  var _usingIDB = false;
  var _queue = [];

  /** 打开 IndexedDB 连接 */
  function open() {
    try {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function(e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };
      req.onsuccess = function(e) {
        _db = e.target.result;
        _usingIDB = true;
        _ready = true;
        migrateFromLocalStorage();
        processQueue();
        patchLocalStorage();
        console.log('NexusStorage: IndexedDB ready (' + getSize() + ' items)');
      };
      req.onerror = function() {
        _ready = true;
        processQueue();
        console.log('NexusStorage: falling back to localStorage');
      };
    } catch(e) {
      _ready = true;
      processQueue();
    }
  }

  /** 从 localStorage 迁移数据到 IndexedDB */
  function migrateFromLocalStorage() {
    if (!_db) return;
    var migrated = localStorage.getItem('nx_storage_migrated');
    if (migrated) return;

    var tx = _db.transaction(STORE_NAME, 'readwrite');
    var store = tx.objectStore(STORE_NAME);
    var count = 0;

    for (var i = 0; i < localStorage.length; i++) {
      var key = localStorage.key(i);
      if (key && key.indexOf('nx_') === 0) {
        try {
          var val = localStorage.getItem(key);
          if (val) {
            try { store.put(JSON.parse(val), key); } catch(e) { store.put(val, key); }
            count++;
          }
        } catch(e) {}
      }
    }

    localStorage.setItem('nx_storage_migrated', '1');
    console.log('NexusStorage: migrated ' + count + ' items');
  }

  /** 修补 localStorage 实现双写 */
  function patchLocalStorage() {
    if (!_db) return;
    var _orig = localStorage.setItem.bind(localStorage);
    var _self = this;

    localStorage.setItem = function(key, value) {
      _orig(key, value);
      if (key && key.indexOf('nx_') === 0) {
        NexusStorage.write(key, value);
      }
    };

    localStorage.removeItem = (function(orig) {
      return function(key) {
        orig.call(localStorage, key);
        NexusStorage.remove(key);
      };
    })(localStorage.removeItem.bind(localStorage));
  }

  /** 写入 IndexedDB */
  function write(key, value) {
    if (!_db) { _queue.push({ op: 'set', key: key, value: value }); return; }
    try {
      var tx = _db.transaction(STORE_NAME, 'readwrite');
      var store = tx.objectStore(STORE_NAME);
      var val;
      try { val = JSON.parse(value); } catch(e) { val = value; }
      store.put(val, key);
    } catch(e) {}
  }

  /** 从 IndexedDB 读取 */
  function read(key, callback) {
    if (!_db) { callback(null); return; }
    try {
      var tx = _db.transaction(STORE_NAME, 'readonly');
      var store = tx.objectStore(STORE_NAME);
      var req = store.get(key);
      req.onsuccess = function() { callback(req.result); };
      req.onerror = function() { callback(null); };
    } catch(e) { callback(null); }
  }

  /** 删除 */
  function remove(key) {
    if (!_db) { _queue.push({ op: 'remove', key: key }); return; }
    try {
      var tx = _db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).delete(key);
    } catch(e) {}
  }

  /** 清空 */
  function clearAll() {
    if (!_db) { _queue = []; return; }
    try {
      var tx = _db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).clear();
    } catch(e) {}
  }

  /** 获取大小 */
  function getSize() {
    if (!_db) return 0;
    try {
      var tx = _db.transaction(STORE_NAME, 'readonly');
      var req = tx.objectStore(STORE_NAME).count();
      return req.result || 0;
    } catch(e) { return 0; }
  }

  /** 处理队列 */
  function processQueue() {
    var q = _queue;
    _queue = [];
    for (var i = 0; i < q.length; i++) {
      var item = q[i];
      if (item.op === 'set') write(item.key, item.value);
      else if (item.op === 'remove') remove(item.key);
    }
  }

  /** 导出所有数据 */
  function exportAll(callback) {
    if (!_db) { callback(null); return; }
    try {
      var tx = _db.transaction(STORE_NAME, 'readonly');
      var store = tx.objectStore(STORE_NAME);
      var allReq = store.getAll();
      var keysReq = store.getAllKeys();
      var result = {};
      var done = 0;

      allReq.onsuccess = function() {
        keysReq.onsuccess = function() {
          var keys = keysReq.result;
          var vals = allReq.result;
          for (var i = 0; i < keys.length; i++) {
            result[keys[i]] = vals[i];
          }
          callback(result);
        };
      };
    } catch(e) { callback(null); }
  }

  // 开库
  open();

  return {
    ready: function() { return _ready; },
    usingIDB: function() { return _usingIDB; },
    write: write,
    read: read,
    remove: remove,
    clear: clearAll,
    getSize: getSize,
    exportAll: exportAll
  };
})();
