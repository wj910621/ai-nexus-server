/**
 * Y·NEX Desktop — Service Worker 缓存
 * 缓存 CDN 资源（Monaco Editor、Mermaid 等），实现离线就绪
 */

const CACHE_NAME = 'ynex-desktop-v1';
const CDN_CACHE = 'ynex-cdn-v1';

const CDN_URLS = [
  // Monaco Editor
  'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs/loader.js',
  'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs/editor/editor.main.js',
  'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs/editor/editor.main.css',
  // Mermaid
  'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',
  // xterm
  'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js',
  'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css',
];

// 安装阶段：预缓存关键资源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll([
        '/',
        '/renderer/index.html',
        '/renderer/ide.js',
        '/renderer/ynex-client.js',
      ]);
    })
  );
  // 预缓存 CDN 资源
  event.waitUntil(
    caches.open(CDN_CACHE).then(cache => {
      return Promise.allSettled(
        CDN_URLS.map(url => cache.add(url).catch(() => {}))
      );
    })
  );
  self.skipWaiting();
});

// 激活阶段：清理旧缓存
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME && key !== CDN_CACHE)
          .map(key => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// 请求拦截：缓存优先策略
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // CDN 资源：缓存优先
  if (CDN_URLS.some(cdn => url.href.startsWith(cdn.split('/').slice(0, 5).join('/')))) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open(CDN_CACHE).then(cache => cache.put(event.request, clone));
          return response;
        });
      })
    );
    return;
  }

  // 本地资源：网络优先，失败回退缓存
  if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request);
      })
    );
    return;
  }

  // 其他资源：缓存优先
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request);
    })
  );
});

// 监听消息：清理缓存
self.addEventListener('message', (event) => {
  if (event.data === 'clear-cache') {
    caches.delete(CACHE_NAME);
    caches.delete(CDN_CACHE);
  }
  if (event.data === 'precache') {
    caches.open(CDN_CACHE).then(cache => {
      CDN_URLS.forEach(url => cache.add(url).catch(() => {}));
    });
  }
});