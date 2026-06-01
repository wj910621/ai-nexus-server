const CACHE='ai-nexus-v2';
const STATIC_ASSETS=[
  '/',
  '/manifest.json',
  '/?pwa=1',
];

// Install: cache static assets, skip waiting
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches, claim clients
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API requests - network only, no cache
  if (url.pathname.startsWith('/api/')) {
    // Don't cache API responses - always go to network
    return;
  }

  // Same-origin static assets - cache-first
  if (url.origin === location.origin) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        return cached || fetch(e.request).then(res => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // Cross-origin - network with offline fallback
  e.respondWith(
    caches.match(e.request).then(cached => {
      return cached || fetch(e.request).catch(() => {
        return new Response('离线模式', { status: 503 });
      });
    })
  );
});

// Handle messages from client (e.g., skipWaiting request)
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
