const CACHE_NAME = 'ag-scorer-shell-v1.3.0';
const APP_SHELL = [
  '/',
  '/manifest.webmanifest',
  '/assets/styles.css',
  '/assets/app.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache authenticated API calls or live match data.
  if (/^\/(auth|matches|teams|players|tournaments|ws|docs|openapi\.json)(\/|$)/.test(url.pathname)) return;

  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(
      caches.match(request).then(cached => cached || fetch(request).then(response => {
        if (response.ok) caches.open(CACHE_NAME).then(cache => cache.put(request, response.clone()));
        return response;
      }))
    );
    return;
  }

  if (request.mode === 'navigate' || url.pathname === '/') {
    event.respondWith(
      fetch(request).then(response => {
        if (response.ok) caches.open(CACHE_NAME).then(cache => cache.put('/', response.clone()));
        return response;
      }).catch(() => caches.match('/'))
    );
  }
});
