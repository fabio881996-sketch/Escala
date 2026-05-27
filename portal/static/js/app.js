/* app.js v3 — com Web Push */

const App = {
    init() {
        setTimeout(() => {
            const s = document.getElementById('splash');
            if (s) { s.classList.add('hidden'); setTimeout(() => s.remove(), 400); }
        }, 700);
        Router.init();
    },

    initUI() {
        const user = API.getUser();
        if (!user) return;

        document.getElementById('app').innerHTML = `
            <div id="navbar">
                <div class="nav-left">
                    <span class="nav-logo">🛡️</span>
                    <div>
                        <div class="nav-title">Portal de Escalas</div>
                        <div class="nav-sub">Posto de Famalicão</div>
                    </div>
                </div>
                <div class="nav-right">
                    ${user.is_admin ? '<span class="nav-badge">⭐ ADMIN</span>' : ''}
                    <button class="nav-btn" onclick="App.logout()" title="Sair">🚪</button>
                </div>
            </div>
            <div id="content"></div>
            <div id="tabbar">
                <button class="tab-item" data-page="home" onclick="Router.go('home')">
                    <span class="tab-icon">📅</span>
                    <span>Minha Escala</span>
                </button>
                <button class="tab-item" data-page="escala-geral" onclick="Router.go('escala-geral')">
                    <span class="tab-icon">🔍</span>
                    <span>Escala Geral</span>
                </button>
                <button class="tab-item" data-page="ferias" onclick="Router.go('ferias')">
                    <span class="tab-icon">🏖️</span>
                    <span>Férias</span>
                </button>
                <button class="tab-item" data-page="trocas" onclick="Router.go('trocas')">
                    <div class="tab-badge-wrap">
                        <span class="tab-icon">🔄</span>
                        <span id="tab-dot-trocas" class="tab-dot" style="display:none"></span>
                    </div>
                    <span>Trocas</span>
                </button>
            </div>`;

        App.checkPendentes();
        App.initPush();

        // Ouvir mensagem do SW para navegar após clique na notificação
        navigator.serviceWorker?.addEventListener('message', e => {
            if (e.data?.type === 'NAVIGATE') Router.go(e.data.url.replace('/', '') || 'home');
        });
    },

    async checkPendentes() {
        try {
            const data = await API.trocas_pendentes();
            const n = data?.trocas?.length || 0;
            const dot = document.getElementById('tab-dot-trocas');
            if (dot) dot.style.display = n > 0 ? 'block' : 'none';
            // Badge no ícone
            if (navigator.setAppBadge) {
                n > 0 ? navigator.setAppBadge(n) : navigator.clearAppBadge();
            }
        } catch(e) {}
    },

    // ── Push ────────────────────────────────────────────────────
    async initPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

        try {
            const reg = await navigator.serviceWorker.ready;

            // Verificar se já está subscrito
            const existing = await reg.pushManager.getSubscription();
            if (existing) {
                // Já subscrito — garantir que o servidor tem a subscription actual
                await API.push_subscribe({ subscription: existing.toJSON() });
                return;
            }

            // Pedir permissão (só na primeira vez, sem popup intrusivo)
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') return;

            // Buscar chave pública VAPID
            const keyData = await API.vapid_public_key();
            if (!keyData?.public_key) return;

            const applicationServerKey = App._urlBase64ToUint8Array(keyData.public_key);
            const subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey,
            });

            await API.push_subscribe({ subscription: subscription.toJSON() });
        } catch (e) {
            console.warn('Push init falhou:', e);
        }
    },

    _urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = atob(base64);
        return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
    },

    logout() {
        if (confirm('Tens a certeza que queres sair?')) {
            // Remover subscription do servidor antes de sair
            API.push_unsubscribe?.().catch(() => {});
            if (navigator.clearAppBadge) navigator.clearAppBadge();
            API.clearToken(); API.clearCache(); location.reload();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
