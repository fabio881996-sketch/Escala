/* ============================================
   pages/definicoes.js — Definições
   ============================================ */

const DefinicoesPage = {
    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();

        content.innerHTML = `
            <div class="section-header">⚙️ Definições</div>

            <!-- Perfil -->
            <div class="card" style="margin-bottom:12px;padding:16px">
                <div style="font-size:.68rem;font-weight:800;color:var(--azul);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Perfil</div>
                <div style="font-size:.9rem;font-weight:700;color:#1e293b">${user?.nome || '—'}</div>
                <div style="font-size:.78rem;color:#64748b">ID: ${user?.id || '—'}</div>
                ${user?.is_admin ? '<div style="font-size:.72rem;color:var(--azul);font-weight:700;margin-top:4px">⭐ Administrador</div>' : ''}
            </div>

            <!-- Notificações -->
            <div class="card" style="margin-bottom:12px;padding:16px">
                <div style="font-size:.68rem;font-weight:800;color:var(--azul);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Notificações</div>
                <div id="notif-status" style="font-size:.78rem;color:#64748b;margin-bottom:12px">A verificar...</div>
                <button id="notif-btn" class="btn btn-primary" style="width:100%" onclick="DefinicoesPage.toggleNotificacoes()">
                    🔔 Ativar Notificações
                </button>
            </div>

            <!-- Sair -->
            <div class="card" style="padding:16px">
                <button class="btn btn-danger" style="width:100%" onclick="App.logout()">
                    🚪 Sair
                </button>
            </div>
        `;

        this.verificarEstadoNotificacoes();
    },

    async verificarEstadoNotificacoes() {
        const statusEl = document.getElementById('notif-status');
        const btnEl = document.getElementById('notif-btn');
        if (!statusEl || !btnEl) return;

        // Capacitor (APK Android)
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
        if (isCapacitor) {
            try {
                const { PushNotifications } = window.Capacitor.Plugins;
                const perm = await PushNotifications.checkPermissions();
                if (perm.receive === 'granted') {
                    statusEl.innerHTML = '✅ Notificações activas';
                    btnEl.textContent = '🔕 Desativar Notificações';
                    btnEl.classList.replace('btn-primary', 'btn-secondary');
                } else {
                    statusEl.innerHTML = '❌ Notificações inactivas';
                    btnEl.textContent = '🔔 Ativar Notificações';
                }
            } catch(e) {
                statusEl.innerHTML = '⚠️ Não suportado neste dispositivo';
                btnEl.style.display = 'none';
            }
            return;
        }

        // Web Push (PWA)
        if (!('Notification' in window)) {
            statusEl.innerHTML = '⚠️ Notificações não suportadas neste browser';
            btnEl.style.display = 'none';
            return;
        }

        const perm = Notification.permission;
        if (perm === 'granted') {
            statusEl.innerHTML = '✅ Notificações activas';
            btnEl.textContent = '🔕 Desativar Notificações';
            btnEl.classList.replace('btn-primary', 'btn-secondary');
        } else if (perm === 'denied') {
            statusEl.innerHTML = '❌ Notificações bloqueadas — activa nas definições do browser';
            btnEl.style.display = 'none';
        } else {
            statusEl.innerHTML = '🔔 Notificações não activadas';
            btnEl.textContent = '🔔 Ativar Notificações';
        }
    },

    async toggleNotificacoes() {
        try {
            alert('Notification: ' + ('Notification' in window) + ' | SW: ' + ('serviceWorker' in navigator) + ' | PushManager: ' + ('PushManager' in window));
            const perm = await Notification.requestPermission();
            alert('Permissão: ' + perm);
        } catch(e) {
            alert('Erro: ' + e.message);
        }
        setTimeout(() => this.verificarEstadoNotificacoes(), 500);
    },
};
