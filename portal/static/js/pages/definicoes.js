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
                <button id="notif-btn" class="btn btn-primary" style="width:100%" onclick="DefinicoesPage.toggleNotificacoes(event)">
                    🔔 Ativar Notificações
                </button>
            </div>

            <!-- Exportar -->
            <div class="card" style="margin-bottom:12px;padding:16px">
                <div style="font-size:.68rem;font-weight:800;color:var(--azul);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Exportar para Calendário</div>
                <div style="font-size:.78rem;color:#64748b;margin-bottom:12px">Exporta os teus serviços ou folgas para o calendário do telemóvel</div>
                <button class="btn btn-primary" style="width:100%;margin-bottom:8px" onclick="DefinicoesPage.escolherExportar('escala')">
                    📅 Exportar Escala
                </button>
                <button class="btn btn-primary" style="width:100%" onclick="DefinicoesPage.escolherExportar('folgas')">
                    😴 Exportar Folgas
                </button>
            </div>
            <!-- Modal escolha calendário -->
            <div id="modal-exportar" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;align-items:flex-end;justify-content:center">
                <div style="background:#fff;border-radius:16px 16px 0 0;padding:24px;width:100%;max-width:480px">
                    <div style="font-size:.9rem;font-weight:700;color:#1e293b;margin-bottom:16px">Exportar para...</div>
                    <button class="btn btn-primary" style="width:100%;margin-bottom:10px" onclick="DefinicoesPage.confirmarExportar('ics')">
                        📥 Descarregar ficheiro .ics
                    </button>
                    <button class="btn btn-primary" style="width:100%;margin-bottom:10px;background:#fff;color:#1e293b;border:1px solid #e2e8f0" onclick="DefinicoesPage.confirmarExportar('google')">
                        <img src="https://www.google.com/favicon.ico" style="width:14px;height:14px;vertical-align:middle;margin-right:6px">Google Calendar
                    </button>
                    <button class="btn" style="width:100%;background:#f1f5f9;color:#64748b" onclick="DefinicoesPage.fecharModal()">
                        Cancelar
                    </button>
                </div>
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

    async toggleNotificacoes(e) {
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
        const btnEl = document.getElementById('notif-btn');
        const statusEl = document.getElementById('notif-status');

        // iOS Safari: requestPermission tem de ser chamado sincronamente no gesto
        const perm = Notification.permission;
        if (!isCapacitor && perm === 'default' && 'Notification' in window) {
            const result = await Notification.requestPermission();
            if (result !== 'granted') {
                if (statusEl) statusEl.innerHTML = '❌ Permissão negada';
                return;
            }
        }

        try {
            if (isCapacitor) {
                const { PushNotifications } = window.Capacitor.Plugins;
                const perm = await PushNotifications.checkPermissions();
                if (perm.receive === 'granted') {
                    // Já tem permissão — remover token do servidor
                    await API.push_unsubscribe();
                    if (statusEl) statusEl.innerHTML = '❌ Notificações desactivadas';
                    if (btnEl) { btnEl.textContent = '🔔 Ativar Notificações'; btnEl.classList.replace('btn-secondary','btn-primary'); }
                } else {
                    await App._initPushCapacitor();
                }
                return;
            }
            const ativas = Notification.permission === 'granted';
            if (ativas) {
                if ('serviceWorker' in navigator && 'PushManager' in window) {
                    const reg = await navigator.serviceWorker.ready;
                    const existing = await reg.pushManager.getSubscription();
                    if (existing) {
                        // Tem subscription activa — desativar
                        await existing.unsubscribe();
                        await API.push_unsubscribe();
                        if (statusEl) statusEl.innerHTML = '❌ Notificações desactivadas';
                        if (btnEl) { btnEl.textContent = '🔔 Ativar Notificações'; btnEl.classList.replace('btn-secondary','btn-primary'); }
                    } else {
                        // Permissão mas subscription perdida (ex: SW reinstalado) — re-registar
                        await App._initPushWeb();
                        if (statusEl) statusEl.innerHTML = '✅ Notificações activas';
                    }
                }
            } else {
                await App._initPushWeb();
            }
        } catch(e) {
            if (statusEl) statusEl.innerHTML = '❌ Erro: ' + e.message;
        }

        setTimeout(() => this.verificarEstadoNotificacoes(), 500);
    },
    _tipoExportar: null,

    escolherExportar(tipo) {
        this._tipoExportar = tipo;
        const modal = document.getElementById('modal-exportar');
        if (modal) { modal.style.display = 'flex'; }
    },

    fecharModal() {
        const modal = document.getElementById('modal-exportar');
        if (modal) modal.style.display = 'none';
    },

    async confirmarExportar(destino) {
        this.fecharModal();
        const tipo = this._tipoExportar;
        if (destino === 'ics') {
            if (tipo === 'escala') await this._exportarICS('/api/ferias/escala-ics', `escala_${API.getUser()?.id || 'gnr'}.ics`);
            else await this._exportarICS('/api/ferias/folgas-ics', `folgas_${API.getUser()?.id || 'gnr'}.ics`);
        } else {
            if (tipo === 'escala') await GCal.exportarEscala();
            else await GCal.exportarFolgas();
        }
    },

    async exportarEscala() {
        await this._exportarICS('/api/ferias/escala-ics', `escala_${API.getUser()?.id || 'gnr'}.ics`);
    },

    async exportarFolgas() {
        await this._exportarICS('/api/ferias/folgas-ics', `folgas_${API.getUser()?.id || 'gnr'}.ics`);
    },

    async _exportarICS(endpoint, filename) {
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
        try {
            const res = await fetch(endpoint, { headers: API.headers() });
            if (!res.ok) throw new Error(await res.text());
            const text = await res.text();

            if (isCapacitor) {
                // APK Android — guardar e partilhar via Share
                const Filesystem = window.Capacitor.Plugins.Filesystem;
                const Share = window.Capacitor.Plugins.Share;
                await Filesystem.writeFile({
                    path: filename,
                    data: btoa(unescape(encodeURIComponent(text))),
                    directory: 'CACHE',
                    encoding: null,
                });
                const fileUri = await Filesystem.getUri({
                    path: filename,
                    directory: 'CACHE',
                });
                await Share.share({
                    title: filename,
                    url: fileUri.uri,
                    dialogTitle: 'Abrir com...',
                });
            } else {
                // Browser / iOS PWA
                const blob = new Blob([text], { type: 'text/calendar;charset=utf-8' });
                const objUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = objUrl;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(objUrl);
            }
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
        // Capacitor APK não suporta a.click() — usar window.open
        const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
        if (isCapacitor) {
            window.open(url, '_blank');
        } else {
            const a = document.createElement('a');
            a.href = url; a.download = filename; a.click();
            URL.revokeObjectURL(url);
        }
    },
};
