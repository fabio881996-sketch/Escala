/* ============================================
   pages/trocas.js — Trocas
   ============================================ */

const TrocasPage = {
    activeTab: 'pendentes',

    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="section-header">🔄 Trocas de Serviço</div>
            <div class="tabs">
                <button class="tab-btn active" onclick="TrocasPage.setTab('pendentes', this)">📥 Pendentes</button>
                <button class="tab-btn" onclick="TrocasPage.setTab('historico', this)">📋 Histórico</button>
                <button class="tab-btn" onclick="TrocasPage.setTab('solicitar', this)">➕ Solicitar</button>
            </div>
            <div id="trocas-content">${Components.loading()}</div>
        `;
        await this.loadPendentes();
    },

    setTab(tab, btn) {
        this.activeTab = tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (tab === 'pendentes') this.loadPendentes();
        else if (tab === 'historico') this.loadHistorico();
        else if (tab === 'solicitar') this.renderSolicitar();
    },

    async loadPendentes() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API.trocas_pendentes();
            const trocas = data?.trocas || [];
            if (!trocas.length) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><p>Sem pedidos pendentes.</p></div>`;
                return;
            }
            el.innerHTML = trocas.map(t => `
                <div class="card card-amber">
                    <div class="card-label">📥 Pedido de troca • ${t.data}</div>
                    <div class="card-title">🔄 ${t.servico_origem}</div>
                    <div class="card-subtitle">De: ${t.id_origem}</div>
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="btn btn-success btn-sm" onclick="TrocasPage.responder(${t.__index || 0}, 'aceitar')">✅ Aceitar</button>
                        <button class="btn btn-danger btn-sm" onclick="TrocasPage.responder(${t.__index || 0}, 'rejeitar')">❌ Recusar</button>
                    </div>
                </div>`).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async loadHistorico() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API.minhas_trocas();
            const trocas = (data?.trocas || []).slice(0, 20);
            if (!trocas.length) {
                el.innerHTML = `<div class="empty-state"><div class="empty-icon">📋</div><p>Sem histórico de trocas.</p></div>`;
                return;
            }
            el.innerHTML = trocas.map(t => {
                const statusColor = t.status === 'Aprovada' ? 'verde' : t.status === 'Rejeitada' ? 'vermelho' : 'amber';
                return `
                    <div class="card card-${statusColor}">
                        <div class="card-label">${t.data} • ${t.status}</div>
                        <div class="card-title">🔄 ${t.servico_origem}</div>
                        <div class="card-subtitle">Com: ${t.id_destino}</div>
                    </div>`;
            }).join('');
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    renderSolicitar() {
        const el = document.getElementById('trocas-content');
        el.innerHTML = `
            <div class="alert alert-info">ℹ️ Seleciona o dia e o militar para solicitar uma troca.</div>
            <div class="form-group">
                <label class="form-label">📅 Data</label>
                <input type="date" id="troca-data" class="form-input" value="${new Date().toISOString().slice(0,10)}">
            </div>
            <button class="btn btn-primary" onclick="TrocasPage.carregarDia()">🔍 Ver escala do dia</button>
            <div id="troca-escala-dia" style="margin-top:16px"></div>
        `;
    },

    async carregarDia() {
        const dataInput = document.getElementById('troca-data');
        const dt = new Date(dataInput.value);
        const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`;
        const el = document.getElementById('troca-escala-dia');
        el.innerHTML = Components.loading();
        try {
            const data = await API.escala_dia(aba);
            const entradas = data?.entradas || [];
            const user = API.getUser();
            const outros = entradas.filter(e => String(e.id) !== String(user?.id));
            if (!outros.length) {
                el.innerHTML = `<div class="alert alert-warning">⚠️ Sem militares disponíveis neste dia.</div>`;
                return;
            }
            el.innerHTML = `
                <div class="form-group">
                    <label class="form-label">👤 Trocar com</label>
                    <select id="troca-mil" class="form-input form-select">
                        ${outros.map(e => `<option value="${e.id}">${e.id} — ${e['serviço'] || ''} (${e['horário'] || ''})</option>`).join('')}
                    </select>
                </div>
                <button class="btn btn-primary" onclick="TrocasPage.enviar('${dataInput.value}')">📨 Enviar Pedido</button>
            `;
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async enviar(dataStr) {
        const milSel = document.getElementById('troca-mil');
        if (!milSel) return;
        try {
            await API.solicitar_troca({
                tipo: 'Troca Simples',
                data: dataStr,
                id_destino: milSel.value,
                servico_origem: 'auto',
                servico_destino: 'auto',
            });
            document.getElementById('trocas-content').innerHTML = `<div class="alert alert-success">✅ Pedido enviado com sucesso!</div>`;
            setTimeout(() => this.render(), 2000);
        } catch (e) {
            document.getElementById('trocas-content').innerHTML += `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    async responder(idx, acao) {
        // TODO: implementar resposta a pedido de troca
        alert(`${acao === 'aceitar' ? '✅ Aceite' : '❌ Recusado'} — em desenvolvimento`);
    }
};
