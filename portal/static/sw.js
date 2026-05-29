/* ============================================
   sw.js — Service Worker (PWA) v2
   ============================================ */

const CACHE_NAME = 'gnr-escala-v3';
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

// ── Instalar ──────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// ── Activar ───────────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // API — sempre rede
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

    // JS — network first (garante versão mais recente)
    if (url.pathname.startsWith('/static/js/')) {
        event.respondWith(
            fetch(event.request).then(response => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => caches.match(event.request))
        );
        return;
    }

    // CSS e outros estáticos — cache first
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

// ── Push ──────────────────────────────────────────────────────
self.addEventListener('push', event => {
    let data = { title: '🛡️ Portal GNR', body: 'Nova notificação', url: '/' };
    try {
        if (event.data) data = { ...data, ...JSON.parse(event.data.text()) };
    } catch (e) {}

    const options = {
        body: data.body,
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/badge-72.png',
        vibrate: [200, 100, 200],
        data: { url: data.url },
        actions: [
            { action: 'open', title: 'Abrir' },
            { action: 'close', title: 'Fechar' },
        ],
        requireInteraction: false,
        tag: data.tag || 'gnr-notif',   // agrupa notificações do mesmo tipo
        renotify: true,
    };

    event.waitUntil(
        Promise.all([
            self.registration.showNotification(data.title, options),
            // Badge no ícone (Android PWA)
            navigator.setAppBadge
                ? navigator.setAppBadge(1).catch(() => {})
                : Promise.resolve(),
        ])
    );
});

// ── Clique na notificação ─────────────────────────────────────
self.addEventListener('notificationclick', event => {
    event.notification.close();

    if (event.action === 'close') return;

    const targetUrl = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
            // Se já há janela aberta, focar e navegar
            for (const client of clientList) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.focus();
                    client.postMessage({ type: 'NAVIGATE', url: targetUrl });
                    return;
                }
            }
            // Senão abrir nova janela
            if (clients.openWindow) return clients.openWindow(targetUrl);
        })
    );
});

// ── Push subscription change ──────────────────────────────────
self.addEventListener('pushsubscriptionchange', event => {
    // Re-subscrever automaticamente se a subscription expirar
    event.waitUntil(
        self.registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: self._vapidPublicKey,
        }).then(subscription => {
            return fetch('/api/notificacoes/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription: subscription.toJSON() }),
            });
        }).catch(() => {})
    );
});
