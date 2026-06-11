/* ============================================
   pages/trocas.js — Trocas de Serviço v2
   ============================================ */

const TrocasPage = {
    activeTab: 'solicitar',

    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();
        const tabValidar = user?.is_admin
            ? `<button class="tab-btn" onclick="TrocasPage.setTab('validar', this)">⚖️ Validar</button>`
            : '';
        content.innerHTML = `
            <div class="section-header">🔄 Trocas de Serviço</div>
            <div class="tabs">
                <button class="tab-btn" onclick="TrocasPage.setTab('pendentes', this)">📥 Pendentes</button>
                <button class="tab-btn" onclick="TrocasPage.setTab('historico', this)">📋 Histórico</button>
                <button class="tab-btn active" onclick="TrocasPage.setTab('solicitar', this)">➕ Solicitar</button>
                ${tabValidar}
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
                        <button class="btn btn-success btn-sm" onclick="TrocasPage.responder(${t.__row_index || i}, 'aceitar', this)">✅ Aceitar</button>
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.responder(${t.__row_index || i}, 'rejeitar', this)">❌ Recusar</button>
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
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.cancelar(${t.__row_index || 0}, this)">🗑️ Cancelar pedido</button>
                    </div>` : ''}
                </div>`;
            }).join('');

            el.innerHTML = htmlPendentes + htmlMeus;
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async cancelarAprovada(rowIndex, btn) {
        if (!confirm('Tens a certeza que queres cancelar esta troca aprovada? Os militares serão notificados.')) return;
        if (btn) { btn.disabled = true; btn.textContent = '⏳...'; }
        try {
            await API._post('/api/trocas/cancelar-aprovada', { row_index: rowIndex });
            await this.loadHistorico();
            App.checkPendentes();
        } catch (e) {
            alert('❌ Erro: ' + e.message);
            if (btn) { btn.disabled = false; btn.textContent = '🚫 Cancelar Troca'; }
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
            const hoje = new Date(); hoje.setHours(0,0,0,0);
            el.innerHTML = trocas.map(t => {
                const user = API.getUser();
                const souOrigem = String(t.id_origem) === String(user?.id);
                const cor = t.status === 'Aprovada' ? 'verde' : t.status === 'Rejeitada' ? 'vermelho' : t.status === 'Cancelada' ? 'vermelho' : 'amber';
                const contraparte = souOrigem
                    ? (t.nome_destino || t.id_destino)
                    : (t.nome_origem || t.id_origem);
                const direcao = souOrigem ? '→' : '←';
                // Verificar se o dia da troca ainda não passou
                let podeCancelar = false;
                if (t.status === 'Aprovada' && souOrigem) {
                    try {
                        const parts = t.data.split('/');
                        const dataTroca = new Date(parseInt(parts[2]), parseInt(parts[1])-1, parseInt(parts[0]));
                        podeCancelar = dataTroca >= hoje;
                    } catch(e) {}
                }
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
                        ${podeCancelar ? `
                        <div style="margin-top:10px">
                            <button class="btn btn-danger btn-sm" onclick="TrocasPage.cancelarAprovada(${t.__row_index}, this)">🚫 Cancelar Troca</button>
                        </div>` : ''}
                    </div>`;
            }).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    // ── VALIDAR (admin) ──────────────────────────────────────
    _horFim(serv) {
        const m = serv?.match(/\((\d{2})-(\d{2})\)/);
        return m ? parseInt(m[2]) : null;
    },
    _horIni(serv) {
        const m = serv?.match(/\((\d{2})-(\d{2})\)/);
        return m ? parseInt(m[1]) : null;
    },
    _consecutivoAviso(nomeA, servA, nomeB, servB) {
        // A vai fazer servA, B vai fazer servB
        // Consecutivo: servA termina a 24 e servB começa a 00
        const avisos = [];
        if (this._horFim(servA) === 24 && this._horIni(servB) === 0)
            avisos.push(`⚠️ ${nomeA} ficará com serviços consecutivos: <b>${servA}</b> seguido de <b>${servB}</b>`);
        if (this._horFim(servB) === 24 && this._horIni(servA) === 0)
            avisos.push(`⚠️ ${nomeB} ficará com serviços consecutivos: <b>${servB}</b> seguido de <b>${servA}</b>`);
        return avisos;
    },

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
            el.innerHTML = trocas.map(t => {
                const nomeOrig = t.nome_origem || t.id_origem;
                const nomeDest = t.nome_destino || t.id_destino;
                const isMatar = t.servico_origem === 'MATAR_REMUNERADO' || t.servico_origem === 'FAZER_REMUNERADO';
                const avisos = isMatar ? [] : this._consecutivoAviso(nomeOrig, t.servico_destino, nomeDest, t.servico_origem);
                const avisosHtml = avisos.length
                    ? `<div style="background:#FFFBEB;border:1px solid #f59e0b;border-radius:6px;padding:8px 10px;margin-top:8px;font-size:.78rem;color:#b45309;font-weight:600">
                        ${avisos.join('<br>')}
                       </div>` : '';

                const cardBody = isMatar ? `
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0">
                        <div style="background:#fefce8;border-radius:8px;padding:10px">
                            <div style="font-size:.65rem;font-weight:800;color:#854d0e;text-transform:uppercase;margin-bottom:4px">💶 Cede Remunerado</div>
                            <div style="font-size:.82rem;font-weight:700;color:#1e293b">${nomeDest}</div>
                            <div style="font-size:.75rem;color:#64748b;margin-top:2px">Serviço: <b>${t.servico_destino}</b></div>
                            <div style="font-size:.75rem;color:#94a3b8;margin-top:2px">Mantém o seu serviço</div>
                        </div>
                        <div style="background:#f0fdf4;border-radius:8px;padding:10px">
                            <div style="font-size:.65rem;font-weight:800;color:#16a34a;text-transform:uppercase;margin-bottom:4px">💶 Faz Remunerado</div>
                            <div style="font-size:.82rem;font-weight:700;color:#1e293b">${nomeOrig}</div>
                            <div style="font-size:.75rem;color:#64748b;margin-top:2px">Fica com: <b>${t.servico_destino}</b></div>
                            <div style="font-size:.75rem;color:#94a3b8;margin-top:2px">Adicional ao seu serviço</div>
                        </div>
                    </div>` : `
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0">
                        <div style="background:#eff6ff;border-radius:8px;padding:10px">
                            <div style="font-size:.65rem;font-weight:800;color:#2563eb;text-transform:uppercase;margin-bottom:4px">📤 Solicita</div>
                            <div style="font-size:.82rem;font-weight:700;color:#1e293b">${nomeOrig}</div>
                            <div style="font-size:.75rem;color:#64748b;margin-top:2px">Cede: <b>${t.servico_origem}</b></div>
                            <div style="font-size:.75rem;color:#16a34a;margin-top:2px">Fica com: <b>${t.servico_destino}</b></div>
                        </div>
                        <div style="background:#f0fdf4;border-radius:8px;padding:10px">
                            <div style="font-size:.65rem;font-weight:800;color:#16a34a;text-transform:uppercase;margin-bottom:4px">📥 Aceita</div>
                            <div style="font-size:.82rem;font-weight:700;color:#1e293b">${nomeDest}</div>
                            <div style="font-size:.75rem;color:#64748b;margin-top:2px">Cede: <b>${t.servico_destino}</b></div>
                            <div style="font-size:.75rem;color:#16a34a;margin-top:2px">Fica com: <b>${t.servico_origem}</b></div>
                        </div>
                    </div>`;

                return `
                <div class="card card-amber">
                    <div class="card-label">${isMatar ? '💶 Cedência de Remunerado' : '⚖️ Aguarda validação'} • ${t.data}</div>
                    ${cardBody}
                    ${avisosHtml}
                    ${t.observacoes ? `<div class="card-subtitle" style="margin-top:4px">📝 ${t.observacoes}</div>` : ''}
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="btn btn-success btn-sm" style="flex:1" onclick="TrocasPage.validar(${t.__row_index}, 'aceitar', this)">✅ Aprovar</button>
                        <button class="btn btn-danger btn-sm" style="flex:1" onclick="TrocasPage.validar(${t.__row_index}, 'rejeitar', this)">🚫 Rejeitar</button>
                    </div>
                </div>`;
            }).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async validar(rowIndex, acao, btn) {
        const label = acao === 'aceitar' ? 'Aprovar' : 'Rejeitar';
        if (!confirm(`Tens a certeza que queres ${label.toLowerCase()} esta troca?`)) return;
        if (btn) { btn.disabled = true; btn.textContent = '⏳...'; }
        try {
            await API._post('/api/trocas/validar', { row_index: rowIndex, acao });
            await this.loadValidar();
            App.checkPendentes();
        } catch (e) {
            alert(`❌ Erro: ${e.message}`);
            if (btn) { btn.disabled = false; btn.textContent = acao === 'aceitar' ? '✅ Aprovar' : '🚫 Rejeitar'; }
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

    onMilitarChange(sel, euTenhoRem = false, meuServico = '', meuHorario = '') {
        const opt = sel.options[sel.selectedIndex];
        const temRem = opt.dataset.temRemunerado === 'true';
        const wrap = document.getElementById('rem-checkbox-wrap');
        const label = document.getElementById('rem-label');
        if (!wrap) return;

        const linhas = [];
        if (temRem && opt.dataset.remServico) {
            const remServ = opt.dataset.remServico;
            const remHor = opt.dataset.remHorario;
            linhas.push(`💶 Remunerado do militar de destino: ${remServ}${remHor ? ` (${remHor})` : ''}`);
        }
        if (euTenhoRem && meuServico) {
            linhas.push(`💶 O teu remunerado: ${meuServico}${meuHorario ? ` (${meuHorario})` : ''}`);
        }

        if (linhas.length > 0) {
            label.innerHTML = linhas.join('<br>');
            wrap.style.display = 'block';
        } else {
            wrap.style.display = 'none';
            const cb = document.getElementById('incluir-rem');
            if (cb) cb.checked = false;
        }
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

            // Verificar se EU tenho remunerado neste dia
            const _meuServ = (meu_servico || '').toLowerCase();
            const euTenhoRem = /remun|gratif/.test(_meuServ);

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
                `<option value="${d.id}"
                    data-servico="${d.servico}"
                    data-horario="${d.horario}"
                    data-tem-remunerado="${d.tem_remunerado || false}"
                    data-rem-servico="${d.remunerado_servico || ''}"
                    data-rem-horario="${d.remunerado_horario || ''}">
                    ${d.nome} — ${d.servico} ${d.horario ? `(${d.horario})` : ''}${d.tem_remunerado ? ' 💶' : ''}
                </option>`
            ).join('');

            el.innerHTML = `
                ${meuServicoHTML}
                ${alertaMeuServico}
                <div class="form-group">
                    <label class="form-label">👤 Trocar com</label>
                    <select id="troca-mil" class="form-input form-select" onchange="TrocasPage.onMilitarChange(this, ${euTenhoRem}, '${meu_servico || ''}', '${meu_horario || ''}')">
                        ${opcoesHTML}
                    </select>
                </div>
                <div id="rem-checkbox-wrap" style="display:none;margin-bottom:12px">
                    <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:.88rem">
                        <input type="checkbox" id="incluir-rem" style="width:16px;height:16px">
                        <span id="rem-label">💶 Incluir transferência do remunerado</span>
                    </label>
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
            // Verificar militar seleccionado por defeito
            const milSel = document.getElementById('troca-mil');
            if (milSel) TrocasPage.onMilitarChange(milSel, euTenhoRem, meu_servico, meu_horario);
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async enviar(dataStr, aba, tipo, meuServico, meuHorario) {
        const milSel = document.getElementById('troca-mil');
        const obsEl = document.getElementById('troca-obs');
        if (!milSel) return;

        const opt = milSel.options[milSel.selectedIndex];
        const _srvBase = opt.dataset.servico || '';
        const horarioDestino = opt.dataset.horario || '';
        const servicoDestino = horarioDestino ? `${_srvBase} (${horarioDestino})` : _srvBase;
        const idDestino = milSel.value;
        const obs = obsEl?.value || '';

        // Formatar data DD/MM/YYYY
        const dt = new Date(dataStr + 'T00:00:00');
        const dataFmt = `${String(dt.getDate()).padStart(2,'0')}/${String(dt.getMonth()+1).padStart(2,'0')}/${dt.getFullYear()}`;

        // Serviço origem: para dar_remunerado usar marcador especial
        // Incluir horário no serviço origem
        let servicoOrigem = (meuServico && meuHorario) ? `${meuServico} (${meuHorario})` : (meuServico || 'auto');
        if (tipo === 'dar_remunerado') servicoOrigem = 'MATAR_REMUNERADO';
        if (tipo === 'fazer_remunerado') servicoOrigem = 'FAZER_REMUNERADO';

        const incluirRem = document.getElementById('incluir-rem')?.checked || false;
        const el = document.getElementById('troca-resultado');
        try {
            await API.solicitar_troca({
                tipo,
                data: dataFmt,
                id_destino: idDestino,
                servico_origem: servicoOrigem,
                servico_destino: servicoDestino,
                observacoes: obs,
                incluir_remunerado: incluirRem,
            });
            el.innerHTML = `<div class="alert alert-success">✅ Pedido enviado com sucesso!</div>`;
            setTimeout(() => this.render(), 2000);
        } catch (e) {
            el.innerHTML += `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },
};
