/* ============================================
   sw.js — Service Worker (PWA)
   ============================================ */

const CACHE_NAME = 'gnr-escala-v1';
const STATIC_ASSETS = [
    '/',
    '/static/css/app.css',
    '/static/js/api.js',
    '/static/js/router.js',
    '/static/js/components.js',
    '/static/js/app.js',
    '/static/js/pages/login.js',
    '/static/js/pages/minha_escala.js',
    '/static/js/pages/escala_geral.js',
    '/static/js/pages/trocas.js',
];

// Instalar — cachear assets estáticos
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Activar — limpar caches antigas
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// Fetch — cache-first para estáticos, network-first para API
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // API — sempre vai à rede
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() =>
                new Response(JSON.stringify({ error: 'Sem ligação' }), {
                    headers: { 'Content-Type': 'application/json' }
                })
            )
        );
        return;
    }

    // Estáticos — cache first
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            });
        })
    );
});
