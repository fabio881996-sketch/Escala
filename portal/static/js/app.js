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
                    <img src="/static/icons/icon-192.png" alt="GNR" style="width:32px;height:32px;border-radius:6px;object-fit:cover">
                    <div>
                        <div class="nav-title">Portal de Escalas</div>
                        <div class="nav-sub">Posto de Famalicão</div>
                    </div>
                </div>
                <div class="nav-right">
                    ${user.is_admin ? '<span class="nav-badge">⭐ ADMIN</span>' : ''}

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
                <button class="tab-item" data-page="definicoes" onclick="Router.go('definicoes')">
                    <span class="tab-icon">⚙️</span>
                    <span>Definições</span>
                </button>
            </div>`;

        App.checkPendentes();
        App.initPush();
        App.verificarNavPendente();
        GCal.verificarCallbackPendente();

        // Ouvir mensagem do SW para navegar após clique na notificação
        navigator.serviceWorker?.addEventListener('message', e => {
            if (e.data?.type === 'NAVIGATE') { const pg = e.data.url.replace(/^\//, '') || 'home'; Router.go(pg === 'trocas' ? 'trocas' : pg === 'home' ? 'home' : pg); }
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
        // Detectar se está no APK Capacitor
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);

        if (isCapacitor) {
            await App._initPushCapacitor();
        } else {
            await App._initPushWeb();
        }
    },

    async _initPushCapacitor() {
        try {
            const { PushNotifications } = window.Capacitor.Plugins;
            if (!PushNotifications) return;

            // Pedir permissão
            const result = await PushNotifications.requestPermissions();
            if (result.receive !== 'granted') return;

            // Registar para receber token FCM
            await PushNotifications.register();

            // Token recebido — enviar ao servidor
            PushNotifications.addListener('registration', async (token) => {
                try {
                    await API.push_subscribe({ fcm_token: token.value });
                } catch (e) {
                    console.warn('FCM subscribe falhou:', e);
                }
            });

            // Notificação recebida em foreground
            PushNotifications.addListener('pushNotificationReceived', (notification) => {
                console.log('Push recebida:', notification);
                App.checkPendentes();
            });

            // Clique na notificação
            PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
                const url = action.notification.data?.url;
                if (url) Router.go(url.replace('/', '') || 'home');
            });

        } catch (e) {
            console.warn('Capacitor push init falhou:', e);
        }
    },

    async _initPushWeb() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

        try {
            // Usar getRegistrations para evitar pending quando SW não é controller
            const regs = await navigator.serviceWorker.getRegistrations();
            const reg = regs[0] || await navigator.serviceWorker.ready;

            // Verificar se já está subscrito
            const existing = await reg.pushManager.getSubscription();
            if (existing) {
                await API.push_subscribe({ subscription: existing.toJSON() });
                return;
            }

            // Pedir permissão
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
            console.warn('Web push init falhou:', e);
        }
    },

    _urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = atob(base64);
        return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
    },

    verificarNavPendente() {
        const params = new URLSearchParams(window.location.search);
        const nav = params.get('nav');
        if (!nav) return;
        const url = new URL(window.location.href);
        url.searchParams.delete('nav');
        window.history.replaceState({}, '', url.toString());
        setTimeout(() => Router.go(nav), 300);
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
