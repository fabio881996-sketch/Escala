/* ============================================
   pages/escala_geral.js — Escala Geral
   ============================================ */

const EscalaGeralPage = {
    async render() {
        const content = document.getElementById('content');

        content.innerHTML = `
            <div class="section-header">🔍 Escala Geral</div>
            <div class="form-group">
                <label class="form-label">Selecionar dia</label>
                <input type="date" id="escala-data" class="form-input"
                    value="${new Date().toISOString().slice(0,10)}"
                    onchange="EscalaGeralPage.carregar()">
            </div>
            <div id="escala-geral-content">
                ${Components.skeleton(2)}
            </div>
        `;

        await this.carregar();
    },

    async carregar() {
        const dataInput = document.getElementById('escala-data');
        if (!dataInput) return;
        const dt = new Date(dataInput.value);
        const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`;
        const el = document.getElementById('escala-geral-content');
        el.innerHTML = Components.loading();

        try {
            const data = await API.escala_dia(aba);
            this.renderEscala(data);
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    renderEscala(data) {
        const el = document.getElementById('escala-geral-content');
        const entradas = data?.entradas || [];

        if (!entradas.length) {
            el.innerHTML = `<div class="empty-state"><div class="empty-icon">📅</div><p>Sem escala para este dia.</p></div>`;
            return;
        }

        // Agrupar por tipo de serviço
        const grupos = {};
        for (const e of entradas) {
            const sv = e['serviço'] || e['servico'] || '';
            const sv_n = sv.toLowerCase();
            let grupo = 'Outros';
            if (sv_n.includes('atendimento')) grupo = 'Atendimento';
            else if (sv_n.includes('apoio')) grupo = 'Apoio ao Atendimento';
            else if (sv_n.includes('patrulha ocorr')) grupo = 'Patrulha Ocorrências';
            else if (sv_n.includes('patrulha') || sv_n.includes('ronda')) grupo = 'Patrulhas';
            else if (sv_n.includes('folga') || sv_n.includes('férias') || sv_n.includes('licen') || sv_n.includes('conval') || sv_n.includes('doente')) grupo = 'Ausências';
            else if (sv_n.includes('dilig') || sv_n.includes('tribunal') || sv_n.includes('pronto') || sv_n.includes('secret') || sv_n.includes('inquer')) grupo = 'ADM / Outras';
            grupos[grupo] = grupos[grupo] || [];
            grupos[grupo].push(e);
        }

        const ordem = ['Atendimento', 'Apoio ao Atendimento', 'Patrulha Ocorrências', 'Patrulhas', 'Ausências', 'ADM / Outras', 'Outros'];
        let html = '';

        for (const g of ordem) {
            if (!grupos[g]) continue;
            html += `<div class="section-header">${g}</div>`;
            // Agrupar por horário
            const porHorario = {};
            for (const e of grupos[g]) {
                const h = e['horário'] || e['horario'] || '';
                porHorario[h] = porHorario[h] || [];
                porHorario[h].push(e);
            }
            for (const [hor, items] of Object.entries(porHorario)) {
                const ids = items.map(i => i['id'] || '').filter(Boolean).join(', ');
                const sv = items[0]['serviço'] || items[0]['servico'] || '';
                const vtr = items[0]['viatura'] || '';
                const rad = items[0]['rádio'] || items[0]['radio'] || '';
                const mostrarSv = !['Atendimento','Apoio ao Atendimento'].includes(g);

                html += `
                    <div class="card" style="padding:12px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                            <span style="font-size:0.78rem;font-weight:700;color:var(--cinza-texto)">🕒 ${hor || '—'}</span>
                            ${mostrarSv && sv ? `<span style="font-size:0.75rem;color:var(--azul-forte)">${sv}</span>` : ''}
                        </div>
                        <div style="font-size:0.88rem;font-weight:600">👤 ${ids}</div>
                        ${vtr && vtr !== 'nan' ? `<div class="card-row">🚔 ${vtr}</div>` : ''}
                        ${rad && rad !== 'nan' ? `<div class="card-row">📻 ${rad}</div>` : ''}
                    </div>`;
            }
        }

        el.innerHTML = html;
    }
};
