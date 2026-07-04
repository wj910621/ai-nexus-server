/**
 * Y·NEX 移动端 PWA Service Worker
 * 提供离线缓存：App Shell、SDK、图标
 */

const CACHE_NAME = 'ynex-mobile-v1';
const ASSETS = [
  './mobile.html',
  './mobile-manifest.json',
  './ynex-client.js',
  './icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // 仅缓存同域静态资源；API 请求走网络
  const { request } = event;
  if (request.method !== 'GET') return;
  if (!request.url.startsWith(self.location.origin)) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        // 只缓存静态文件
        const isStatic = ASSETS.some((a) => request.url.endsWith(a.replace('./', '')));
        if (isStatic && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      }).catch(() => cached);
    })
  );
});
