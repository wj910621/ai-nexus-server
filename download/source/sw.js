/* ========================================
   TriGenClaw - Service Worker
   v20260612 - 网络优先策略，解决缓存问�?   ======================================== */
var SW_VERSION = 'trigenclaw-v20260612';
var CACHE_NAME = SW_VERSION;

// 需要预缓存的文件列表（仅首次安装时使用�?var PRECACHE_FILES = [
  '.',
  'index.html',
  'css/style.css',
  'js/storage.js',
  'js/api.js',
  'js/models.js',
  'js/chat.js',
  'js/code.js',
  'js/agent.js',
  'js/skills.js',
  'js/plugin.js',
  'js/particles.js',
  'js/autonomous.js',
  'js/knowledge.js',
  'js/ui.js',
  'js/app.js',
  'manifest.json'
];

// Install: 预缓�?+ 立即激�?self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(c) { return c.addAll(PRECACHE_FILES); })
      .then(function() { return self.skipWaiting(); })
  );
});

// Activate: 删除旧缓�?+ 接管所有客户端
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
          .map(function(k) { return caches.delete(k); })
      );
    }).then(function() { return self.clients.claim(); })
  );
});

// Fetch: 网络优先策略 - 始终先请求服务端最新文�?self.addEventListener('fetch', function(e) {
  var r = e.request;
  var url = new URL(r.url);

  // 仅处理同源请�?  if (url.origin !== location.origin) return;

  // 导航请求（页面加载）- 网络优先，离线时回退到缓�?  if (r.mode === 'navigate') {
    e.respondWith(
      fetch(r).then(function(res) {
        // 缓存最新版�?        var clone = res.clone();
        caches.open(CACHE_NAME).then(function(ca) { ca.put(r, clone); });
        return res;
      }).catch(function() {
        return caches.match('index.html');
      })
    );
    return;
  }

  // JS/CSS/静态资�?- 网络优先（确保始终加载最新代码）
  e.respondWith(
    fetch(r).then(function(res) {
      // 缓存网络返回的最新版�?      if (res && res.ok) {
        var clone = res.clone();
        caches.open(CACHE_NAME).then(function(ca) { ca.put(r, clone); });
      }
      return res;
    }).catch(function() {
      // 离线时回退到缓�?      return caches.match(r).then(function(cached) {
        return cached || new Response('Offline', { status: 503 });
      });
    })
  );
});
