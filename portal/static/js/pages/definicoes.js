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
                <button id="notif-btn" class="btn btn-primary" style="width:100%" onclick="Notification.requestPermission().then(p => { if(p==='granted') App._initPushWeb().then(() => DefinicoesPage.verificarEstadoNotificacoes()); else DefinicoesPage.verificarEstadoNotificacoes(); })">
                    🔔 Ativar Notificações
                </button>
            </div>

            <!-- Exportar -->
            <div class="card" style="margin-bottom:12px;padding:16px">
                <div style="font-size:.68rem;font-weight:800;color:var(--azul);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Exportar para Calendário</div>
                <div style="font-size:.78rem;color:#64748b;margin-bottom:12px">Exporta os teus serviços ou folgas para o calendário do telemóvel (.ics)</div>
                <button class="btn btn-primary" style="width:100%;margin-bottom:8px" onclick="DefinicoesPage.exportarEscala()">
                    📅 Exportar Escala
                </button>
                <button class="btn btn-primary" style="width:100%" onclick="DefinicoesPage.exportarFolgas()">
                    😴 Exportar Folgas
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
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
        const btnEl = document.getElementById('notif-btn');
        const statusEl = document.getElementById('notif-status');
        if (btnEl) btnEl.disabled = true;

        try {
            const ativas = Notification.permission === 'granted';
            if (isCapacitor) {
                await App._initPushCapacitor();
            } else if (ativas) {
                // Permissão já concedida — verificar se tem subscription activa
                if ('serviceWorker' in navigator && 'PushManager' in window) {
                    const reg = await navigator.serviceWorker.ready;
                    const existing = await reg.pushManager.getSubscription();
                    if (existing) {
                        // Tem subscription — desativar
                        await existing.unsubscribe();
                        await API.push_unsubscribe();
                        if (statusEl) statusEl.innerHTML = '❌ Notificações desactivadas';
                    } else {
                        // Permissão mas sem subscription — registar
                        await App._initPushWeb();
                        if (statusEl) statusEl.innerHTML = '✅ Notificações activas';
                    }
                }
            } else {
                // Sem permissão — pedir
                await App._initPushWeb();
            }
        } catch(e) {
            if (statusEl) statusEl.innerHTML = '❌ Erro: ' + e.message;
        }

        if (btnEl) btnEl.disabled = false;
        setTimeout(() => this.verificarEstadoNotificacoes(), 500);
    },
    async exportarEscala() {
        try {
            const data = await API.minha_escala();
            const servicos = (data?.servicos || []).filter(s => {
                const l = s.servico.toLowerCase();
                return !l.includes('folga') && !l.includes('férias') && !l.includes('ferias')
                    && !l.includes('licen') && !l.includes('doente') && !l.includes('conval');
            });
            if (!servicos.length) { alert('Sem serviços para exportar.'); return; }
            const user = API.getUser();
            this._downloadICS(servicos, `escala_${user?.id || 'gnr'}.ics`, false);
        } catch(e) { alert('❌ Erro: ' + e.message); }
    },

    async exportarFolgas() {
        try {
            const data = await API.minha_escala();
            const folgas = (data?.servicos || []).filter(s =>
                /folga|férias|ferias/i.test(s.servico)
            );
            if (!folgas.length) { alert('Sem folgas para exportar.'); return; }
            const user = API.getUser();
            this._downloadICS(folgas, `folgas_${user?.id || 'gnr'}.ics`, true);
        } catch(e) { alert('❌ Erro: ' + e.message); }
    },

    _downloadICS(servicos, filename, isDia) {
        const user = API.getUser();
        const linhas = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//GNR Famalicão//Escala//PT',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'X-WR-CALNAME:Escala GNR Famalicão',
        ];

        for (const s of servicos) {
            const [d, m, y] = s.data.split('/');
            const dt = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));

            if (isDia || !s.horario) {
                // Evento de dia inteiro
                const dtStr = `${y}${m}${d}`;
                const dtEnd = new Date(dt); dtEnd.setDate(dtEnd.getDate() + 1);
                const dtEndStr = `${dtEnd.getFullYear()}${String(dtEnd.getMonth()+1).padStart(2,'0')}${String(dtEnd.getDate()).padStart(2,'0')}`;
                linhas.push(
                    'BEGIN:VEVENT',
                    `UID:gnr-${user?.id}-${dtStr}@gnr`,
                    `DTSTART;VALUE=DATE:${dtStr}`,
                    `DTEND;VALUE=DATE:${dtEndStr}`,
                    `SUMMARY:${s.servico}`,
                    'END:VEVENT'
                );
            } else {
                // Evento com horário
                const partes = s.horario.split('-').map(h => h.trim());
                const hIniH = parseInt((partes[0] || '00').substring(0,2));
                const hFimH = parseInt((partes[1] || '00').substring(0,2));
                const hFimM = parseInt((partes[1] || '00').substring(2) || '0');

                const dtIni = new Date(dt);
                dtIni.setHours(hIniH, 0, 0);
                const dtFim = new Date(dt);
                dtFim.setHours(hFimH, hFimM, 0);
                if (dtFim <= dtIni) dtFim.setDate(dtFim.getDate() + 1);

                const fmt = d => d.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z/,'');
                linhas.push(
                    'BEGIN:VEVENT',
                    `UID:gnr-${user?.id}-${fmt(dtIni)}@gnr`,
                    `DTSTART:${fmt(dtIni)}`,
                    `DTEND:${fmt(dtFim)}`,
                    `SUMMARY:${s.servico}`,
                    'END:VEVENT'
                );
            }
        }
        linhas.push('END:VCALENDAR');

        const blob = new Blob([linhas.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.click();
        URL.revokeObjectURL(url);
    },
};
