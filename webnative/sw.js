// Minimal service worker — offline support
const CACHE = 'kev-substrate-v1';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.open(CACHE).then(cache =>
      cache.match(e.request).then(cached => {
        const networked = fetch(e.request)
          .then(response => {
            if (response.ok) cache.put(e.request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || networked;
      })
    )
  );
});
