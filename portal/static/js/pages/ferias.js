/* ============================================
   pages/ferias.js — Plano de Férias
   ============================================ */

const FeriasPage = {
    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="section-header">🏖️ Plano de Férias</div>
            <div id="ferias-content">${Components.loading()}</div>
        `;
        await this.carregar();
    },

    async carregar() {
        const el = document.getElementById('ferias-content');
        try {
            const data = await API.minhas_ferias();
            this.render_ferias(data, el);
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    render_ferias(data, el) {
        const { ano, periodos, total_dias_uteis } = data;

        if (!periodos || !periodos.length) {
            el.innerHTML = `<div class="empty-state"><div class="empty-icon">🏖️</div><p>Sem plano de férias registado para ${ano}.</p></div>`;
            return;
        }

        const hoje = new Date();

        const periodosHTML = periodos.map(p => {
            const ini = this._parseData(p.inicio);
            const fim = this._parseData(p.fim);
            const passado = fim && fim < hoje;
            const ativo = ini && fim && ini <= hoje && hoje <= fim;
            const futuro = ini && ini > hoje;

            let badge = '';
            if (ativo)   badge = `<span style="background:#16a34a;color:#fff;font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">EM CURSO</span>`;
            if (passado) badge = `<span style="background:#94a3b8;color:#fff;font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">CONCLUÍDO</span>`;

            const corBorda = ativo ? '#16a34a' : passado ? '#cbd5e1' : 'var(--azul)';

            return `
                <div class="card" style="border-left:4px solid ${corBorda};margin-bottom:10px;padding:14px 16px">
                    <div style="display:flex;align-items:center;margin-bottom:6px">
                        <span style="font-size:.68rem;font-weight:800;color:var(--azul);text-transform:uppercase;letter-spacing:.06em">Período ${p.numero}</span>
                        ${badge}
                    </div>
                    <div style="font-size:1rem;font-weight:700;color:#1e293b;margin-bottom:2px">
                        📅 ${this._formatarData(p.inicio)}
                    </div>
                    <div style="font-size:.82rem;color:#475569;margin-bottom:10px">
                        até ${this._formatarData(p.fim)}
                    </div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        <span style="background:#eff6ff;color:var(--azul);font-size:.75rem;font-weight:600;padding:4px 10px;border-radius:6px">
                            📆 ${p.dias_corridos} dias corridos
                        </span>
                        <span style="background:#f0fdf4;color:#16a34a;font-size:.75rem;font-weight:600;padding:4px 10px;border-radius:6px">
                            💼 ${p.dias_uteis} dias úteis
                        </span>
                    </div>
                </div>`;
        }).join('');

        // Barra de progresso dos dias úteis (assumindo 22 dias de direito)
        const DIREITO = 22;
        const pct = Math.min(100, Math.round((total_dias_uteis / DIREITO) * 100));
        const corBarra = pct >= 100 ? '#16a34a' : pct >= 50 ? 'var(--azul)' : '#f59e0b';

        el.innerHTML = `
            <!-- Cabeçalho resumo -->
            <div class="card" style="background:linear-gradient(135deg,var(--azul) 0%,#1e40af 100%);color:#fff;margin-bottom:12px;padding:18px">
                <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;opacity:.8;margin-bottom:4px">Plano de Férias ${ano}</div>
                <div style="font-size:2rem;font-weight:800;line-height:1">${total_dias_uteis}</div>
                <div style="font-size:.82rem;opacity:.85;margin-bottom:12px">dias úteis marcados</div>
                <div style="background:rgba(255,255,255,.2);border-radius:99px;height:8px;overflow:hidden">
                    <div style="background:#fff;width:${pct}%;height:100%;border-radius:99px;transition:width .4s"></div>
                </div>
                <div style="font-size:.72rem;opacity:.75;margin-top:4px">${total_dias_uteis} de ${DIREITO} dias (${pct}%)</div>
            </div>

            <!-- Botão exportar .ics -->
            <button class="btn btn-primary" style="width:100%;margin-bottom:12px" onclick="FeriasPage.exportarICS()">
                📥 Exportar para Calendário (.ics)
            </button>

            <!-- Períodos -->
            ${periodosHTML}
        `;
    },

    async exportarICS() {
        // Buscar dados já carregados e gerar .ics no browser
        try {
            const data = await API.minhas_ferias();
            const { ano, periodos } = data;
            const user = API.getUser();
            const linhas = [
                'BEGIN:VCALENDAR',
                'VERSION:2.0',
                'PRODID:-//GNR Famalicão//Ferias//PT',
                'CALSCALE:GREGORIAN',
                'METHOD:PUBLISH',
                'X-WR-CALNAME:Férias GNR Famalicão',
            ];

            for (const p of periodos) {
                const ini = this._parseData(p.inicio);
                const fim = this._parseData(p.fim);
                if (!ini || !fim) continue;

                const dtStart = this._toICSDate(ini);
                // DTEND é exclusivo no formato DATE — dia seguinte
                const fimMais1 = new Date(fim);
                fimMais1.setDate(fimMais1.getDate() + 1);
                const dtEnd = this._toICSDate(fimMais1);

                linhas.push(
                    'BEGIN:VEVENT',
                    `UID:ferias-${user?.id}-${p.numero}-${dtStart}@gnr`,
                    `DTSTART;VALUE=DATE:${dtStart}`,
                    `DTEND;VALUE=DATE:${dtEnd}`,
                    `SUMMARY:🏖️ Férias P${p.numero} (${p.dias_uteis} dias úteis)`,
                    'END:VEVENT',
                );
            }
            linhas.push('END:VCALENDAR');

            const isCapacitor = !!(window.Capacitor?.isNativePlatform?.() || window.Capacitor?.platform);
            const filename = `ferias_${user?.id || 'gnr'}_${ano}.ics`;
            const text = linhas.join('\r\n');

            if (isCapacitor) {
                const { Filesystem, Directory, Share } = window.Capacitor.Plugins;
                await Filesystem.writeFile({
                    path: filename,
                    data: btoa(unescape(encodeURIComponent(text))),
                    directory: Directory.Cache,
                    encoding: null,
                });
                const fileUri = await Filesystem.getUri({ path: filename, directory: Directory.Cache });
                await Share.share({ title: filename, url: fileUri.uri, dialogTitle: 'Abrir com...' });
            } else {
                const blob = new Blob([text], { type: 'text/calendar;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
            }
        } catch(e) { alert('❌ Erro ao exportar: ' + e.message); }
    },

    _parseData(str) {
        if (!str) return null;
        const [d, m, y] = str.split('/');
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
    },

    _formatarData(str) {
        if (!str) return '—';
        const meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
        const [d, m, y] = str.split('/');
        return `${parseInt(d)} de ${meses[parseInt(m) - 1]} de ${y}`;
    },

    _toICSDate(dt) {
        const y = dt.getFullYear();
        const m = String(dt.getMonth() + 1).padStart(2, '0');
        const d = String(dt.getDate()).padStart(2, '0');
        return `${y}${m}${d}`;
    },
};
