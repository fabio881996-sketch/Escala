/* ============================================
   pages/trocas.js — Trocas de Serviço v2
   ============================================ */

const TrocasPage = {
    activeTab: 'solicitar',

    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();
        const isAdmin = user?.is_admin || false;
        const validarTab = isAdmin
            ? `<button class="tab-btn" onclick="TrocasPage.setTab('validar', this)">⚖️ Validar</button>`
            : '';
        content.innerHTML = `
            <div class="section-header">🔄 Trocas de Serviço</div>
            <div class="tabs">
                <button class="tab-btn" onclick="TrocasPage.setTab('pendentes', this)">📥 Pendentes</button>
                <button class="tab-btn" onclick="TrocasPage.setTab('historico', this)">📋 Histórico</button>
                <button class="tab-btn active" onclick="TrocasPage.setTab('solicitar', this)">➕ Solicitar</button>
                ${validarTab}
            </div>
            <div id="trocas-content">${Components.loading()}</div>
        `;
        await this.renderSolicitar();
    },

    setTab(tab, btn) {
        this.activeTab = tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (tab === 'pendentes') this.loadPendentes();
        else if (tab === 'historico') this.loadHistorico();
        else if (tab === 'validar') this.loadValidar();
        else this.renderSolicitar();
    },

    // ── VALIDAR (ADMIN) ──────────────────────────────────────
    async loadValidar() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API._get('/api/trocas/pendentes-admin', false);
            const trocas = data?.trocas || [];
            if (!trocas.length) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">⚖️</div><p>Sem trocas para validar.</p></div>`;
                return;
            }

            const _horFim = (serv) => {
                const m = serv?.match(/\((\d{2})-(\d{2})\)/);
                return m ? parseInt(m[2]) : null;
            };
            const _horIni = (serv) => {
                const m = serv?.match(/\((\d{2})-(\d{2})\)/);
                return m ? parseInt(m[1]) : null;
            };
            const _consecutivo = (servFim, servIni) => {
                const fim = _horFim(servFim);
                const ini = _horIni(servIni);
                if (fim === null || ini === null) return false;
                return (fim === 0 && ini === 0) || (fim === 16 && ini === 0) || (fim === 8 && ini === 16);
            };

            el.innerHTML = trocas.map(t => {
                // Usar avisos do backend (mais precisos)
                const avisosList = t.avisos_consecutivos || [];
                let avisos = avisosList.map(a =>
                    `<div style="background:#fef3c7;border-left:3px solid #f59e0b;padding:6px 10px;border-radius:6px;margin-top:8px;font-size:.78rem">${a}</div>`
                ).join('');
                return `
                <div class="card card-amber">
                    <div class="card-label">⚖️ Aguarda validação • ${t.data}</div>
                    <div class="card-title">🔄 Troca de Serviço</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
                        <div style="background:var(--bg-secondary);padding:8px;border-radius:8px;font-size:.82rem">
                            <div style="font-weight:600;margin-bottom:4px">📤 ${t.nome_origem || t.id_origem}</div>
                            <div>${t.servico_origem}</div>
                        </div>
                        <div style="background:var(--bg-secondary);padding:8px;border-radius:8px;font-size:.82rem">
                            <div style="font-weight:600;margin-bottom:4px">📥 ${t.nome_destino || t.id_destino}</div>
                            <div>${t.servico_destino}</div>
                        </div>
                    </div>
                    ${avisos}
                    ${t.observacoes ? `<div class="card-subtitle" style="margin-top:6px">📝 ${t.observacoes}</div>` : ''}
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="btn btn-success btn-sm" onclick="TrocasPage.validar(${t.__row_index || t.id}, 'aprovar', this)">✅ Aprovar</button>
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.validar(${t.__row_index || t.id}, 'rejeitar', this)">🚫 Rejeitar</button>
                    </div>
                </div>`;
            }).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async validar(id, acao, btn) {
        const label = acao === 'aprovar' ? 'Aprovar' : 'Rejeitar';
        if (!confirm(`Tens a certeza que queres ${label.toLowerCase()} esta troca?`)) return;
        if (btn) { btn.disabled = true; btn.textContent = '⏳...'; }
        try {
            await API._post('/api/trocas/validar', { row_index: id, acao });
            await this.loadValidar();
            App.checkPendentes();
        } catch (e) {
            alert(`❌ Erro: ${e.message}`);
            if (btn) { btn.disabled = false; btn.textContent = acao === 'aprovar' ? '✅ Aprovar' : '🚫 Rejeitar'; }
        }
    },

    // ── PENDENTES ────────────────────────────────────────────
    async loadPendentes() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = Components.loading();
        try {
            const [dataPendentes, dataMinhas] = await Promise.all([
                API.trocas_pendentes(),
                API.minhas_trocas(),
            ]);
            const user = API.getUser();
            const pendentes = dataPendentes?.trocas || [];
            // Os meus pedidos ainda por responder
            const meusAtivos = (dataMinhas?.trocas || []).filter(t =>
                String(t.id_origem) === String(user?.id) &&
                (t.status === 'Pendente_Militar' || t.status === 'Pendente_Admin')
            );

            if (!pendentes.length && !meusAtivos.length) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><p>Sem pedidos pendentes.</p></div>`;
                return;
            }

            const htmlPendentes = pendentes.map((t, i) => `
                <div class="card card-amber">
                    <div class="card-label">📥 Pedido recebido • ${t.data}</div>
                    <div class="card-title">🔄 ${t.servico_origem}</div>
                    <div class="card-subtitle">De: ${t.nome_origem || t.id_origem}</div>
                    ${t.observacoes ? `<div class="card-subtitle" style="margin-top:4px">📝 ${t.observacoes}</div>` : ''}
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="btn btn-success btn-sm" onclick="TrocasPage.responder(${t.__row_index}, 'aceitar', this)">✅ Aceitar</button>
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.responder(${t.__row_index}, 'rejeitar', this)">❌ Recusar</button>
                    </div>
                </div>`).join('');

            const htmlMeus = meusAtivos.map(t => {
                const statusLabel = t.status === 'Pendente_Admin' ? '⏳ Aguarda admin' : '⏳ Aguarda resposta';
                return `
                <div class="card" style="border-left:4px solid #64748b">
                    <div class="card-label">📤 Pedido enviado • ${t.data} • ${statusLabel}</div>
                    <div class="card-title">🔄 ${t.servico_origem}</div>
                    <div class="card-subtitle">Para: ${t.nome_destino || t.id_destino}</div>
                    ${t.observacoes ? `<div class="card-subtitle" style="margin-top:4px">📝 ${t.observacoes}</div>` : ''}
                    ${t.status === 'Pendente_Militar' ? `
                    <div style="margin-top:12px">
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.cancelar(${t.__row_index}, this)">🗑️ Cancelar pedido</button>
                    </div>` : ''}
                </div>`;
            }).join('');

            el.innerHTML = htmlPendentes + htmlMeus;
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async cancelar(rowIndex, btn) {
        if (!confirm('Tens a certeza que queres cancelar este pedido?')) return;
        if (btn) { btn.disabled = true; btn.textContent = '⏳...'; }
        try {
            await API._post('/api/trocas/cancelar', { row_index: rowIndex });
            await this.loadPendentes();
            App.checkPendentes();
        } catch (e) {
            alert('❌ Erro: ' + e.message);
            if (btn) { btn.disabled = false; btn.textContent = '🗑️ Cancelar pedido'; }
        }
    },

    async responder(rowIndex, acao, btn) {
        const label = acao === 'aceitar' ? 'Aceitar' : 'Recusar';
        if (!confirm(`Tens a certeza que queres ${label.toLowerCase()} esta troca?`)) return;
        if (btn) { btn.disabled = true; btn.textContent = '⏳...'; }
        try {
            await API.responder_troca({ row_index: rowIndex, acao });
            await this.loadPendentes();
            App.checkPendentes();
        } catch (e) {
            alert(`❌ Erro: ${e.message}`);
            if (btn) { btn.disabled = false; btn.textContent = acao === 'aceitar' ? '✅ Aceitar' : '❌ Recusar'; }
        }
    },

    // ── HISTÓRICO ────────────────────────────────────────────
    async loadHistorico() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API.minhas_trocas();
            const trocas = (data?.trocas || []).slice(0, 30);
            if (!trocas.length) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">📋</div><p>Sem histórico de trocas.</p></div>`;
                return;
            }
            el.innerHTML = trocas.map(t => {
                const user = API.getUser();
                const souOrigem = String(t.id_origem) === String(user?.id);
                const cor = t.status === 'Aprovada' ? 'verde' : t.status === 'Rejeitada' ? 'vermelho' : 'amber';
                const contraparte = souOrigem
                    ? (t.nome_destino || t.id_destino)
                    : (t.nome_origem || t.id_origem);
                const direcao = souOrigem ? '→' : '←';
                return `
                    <div class="card card-${cor}">
                        <div class="card-label">${t.data} • ${
                            t.status === 'Aprovada' ? '✅ Aprovada' :
                            t.status === 'Rejeitada' ? '❌ Rejeitada' :
                            t.status === 'Pendente_Admin' ? '⏳ Aguarda admin' :
                            t.status === 'Cancelada' ? '🚫 Cancelada' : '⏳ Pendente'
                        }</div>
                        <div class="card-title">🔄 ${t.servico_origem}</div>
                        <div class="card-subtitle">${direcao} ${contraparte}</div>
                        ${t.observacoes ? `<div class="card-subtitle" style="margin-top:2px">📝 ${t.observacoes}</div>` : ''}
                    </div>`;
            }).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    // ── SOLICITAR ────────────────────────────────────────────
    renderSolicitar() {
        const hoje = new Date().toISOString().slice(0, 10);
        const el = document.getElementById('trocas-content');
        el.innerHTML = `
            <div class="alert alert-info">ℹ️ Seleciona o dia e o militar para solicitar uma troca.</div>

            <div class="form-group">
                <label class="form-label">📅 Data</label>
                <input type="date" id="troca-data" class="form-input" value="${hoje}">
            </div>

            <div class="form-group">
                <label class="form-label">🔄 Tipo de troca</label>
                <select id="troca-tipo" class="form-input form-select">
                    <option value="simples">🔄 Troca Simples</option>
                    <option value="folga">📅 Troca de Folga</option>
                    <option value="dar_remunerado">💶 Dar Remunerado</option>
                    <option value="fazer_remunerado">💶 Fazer Remunerado</option>
                </select>
            </div>

            <button class="btn btn-primary" style="width:100%" onclick="TrocasPage.carregarDia()">🔍 Ver escala do dia</button>
            <div id="troca-resultado" style="margin-top:16px"></div>
        `;
    },

    async carregarDia() {
        const dataInput = document.getElementById('troca-data');
        const tipoInput = document.getElementById('troca-tipo');
        if (!dataInput || !tipoInput) return;

        const dt = new Date(dataInput.value + 'T00:00:00');
        const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`;
        const tipo = tipoInput.value;
        const el = document.getElementById('troca-resultado');
        el.innerHTML = Components.loading();

        try {
            const data = await API.trocas_disponiveis(aba, tipo);
            const { meu_servico, meu_horario, disponiveis } = data;

            // Mensagem se não tenho serviço relevante para este tipo
            let alertaMeuServico = '';
            if (tipo === 'simples' && !meu_servico) {
                alertaMeuServico = `<div class="alert alert-warning">⚠️ Não tens serviço escalado neste dia.</div>`;
            } else if (tipo === 'folga' && meu_servico && !meu_servico.toLowerCase().includes('folga')) {
                alertaMeuServico = `<div class="alert alert-warning">⚠️ Não tens folga neste dia (tens: ${meu_servico}).</div>`;
            } else if ((tipo === 'dar_remunerado') && meu_servico && !/(remun|gratif)/i.test(meu_servico)) {
                alertaMeuServico = `<div class="alert alert-warning">⚠️ Não tens remunerado neste dia.</div>`;
            }

            const meuServicoHTML = meu_servico
                ? `<div class="card" style="margin-bottom:12px;background:var(--bg-card)">
                       <div class="card-label">O teu serviço</div>
                       <div class="card-title">📋 ${meu_servico}</div>
                       ${meu_horario ? `<div class="card-subtitle">🕐 ${meu_horario}</div>` : ''}
                   </div>`
                : `<div class="alert alert-warning">⚠️ Não tens serviço escalado neste dia.</div>`;

            if (!disponiveis.length) {
                el.innerHTML = meuServicoHTML + alertaMeuServico +
                    `<div class="alert alert-warning">⚠️ Sem militares disponíveis para este tipo de troca.</div>`;
                return;
            }

            const opcoesHTML = disponiveis.map(d =>
                `<option value="${d.id}" data-servico="${d.servico}" data-horario="${d.horario}">
                    ${d.nome} — ${d.servico} ${d.horario ? `(${d.horario})` : ''}
                </option>`
            ).join('');

            el.innerHTML = `
                ${meuServicoHTML}
                ${alertaMeuServico}
                <div class="form-group">
                    <label class="form-label">👤 Trocar com</label>
                    <select id="troca-mil" class="form-input form-select">
                        ${opcoesHTML}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">📝 Observações (opcional)</label>
                    <input type="text" id="troca-obs" class="form-input" placeholder="ex: problema pessoal">
                </div>
                <button class="btn btn-primary" style="width:100%"
                    onclick="TrocasPage.enviar('${dataInput.value}', '${aba}', '${tipo}', '${meu_servico || ''}', '${meu_horario || ''}')">
                    📨 Enviar Pedido
                </button>
            `;
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async enviar(dataStr, aba, tipo, meuServico, meuHorario) {
        const milSel = document.getElementById('troca-mil');
        const obsEl = document.getElementById('troca-obs');
        if (!milSel) return;

        const opt = milSel.options[milSel.selectedIndex];
        const servicoDestino = opt.dataset.servico || '';
        const horarioDestino = opt.dataset.horario || '';
        const idDestino = milSel.value;
        const obs = obsEl?.value || '';

        // Formatar data DD/MM/YYYY
        const dt = new Date(dataStr + 'T00:00:00');
        const dataFmt = `${String(dt.getDate()).padStart(2,'0')}/${String(dt.getMonth()+1).padStart(2,'0')}/${dt.getFullYear()}`;

        // Serviço origem: para dar_remunerado usar marcador especial
        let servicoOrigem = meuServico || 'auto';
        if (tipo === 'dar_remunerado') servicoOrigem = 'MATAR_REMUNERADO';

        const el = document.getElementById('troca-resultado');
        try {
            await API.solicitar_troca({
                tipo,
                data: dataFmt,
                id_destino: idDestino,
                servico_origem: servicoOrigem,
                servico_destino: servicoDestino,
                observacoes: obs,
            });
            el.innerHTML = `<div class="alert alert-success">✅ Pedido enviado com sucesso!</div>`;
            setTimeout(() => this.render(), 2000);
        } catch (e) {
            el.innerHTML += `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },
};
