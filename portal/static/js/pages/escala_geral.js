/* escala_geral.js v2 */

const EscalaGeralPage = {
    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="section-h">🔍 Escala Geral</div>
            <div class="form-group">
                <input type="date" id="eg-data" class="form-input"
                    value="${new Date().toISOString().slice(0,10)}"
                    onchange="EscalaGeralPage.carregar()" style="font-size:.95rem;font-weight:600">
            </div>
            <div id="eg-content">${Components.skeleton(2)}</div>`;
        await this.carregar();
    },

    async carregar() {
        const inp = document.getElementById('eg-data');
        if (!inp) return;
        const dt = new Date(inp.value);
        const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`;
        const el = document.getElementById('eg-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API.escala_dia(aba);
            this.render_escala(data, dt);
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    render_escala(data, dt) {
        const el = document.getElementById('eg-content');
        const entradas = data?.entradas || [];

        if (!entradas.length) {
            el.innerHTML = `<div class="empty"><div class="empty-icon">📅</div><div class="empty-txt">Sem escala publicada para este dia.</div></div>`;
            return;
        }

        const grupos = {
            'Atendimento': [],
            'Apoio ao Atendimento': [],
            'Patrulha Ocorrências': [],
            'Patrulhas / Outros': [],
            'Ausências': [],
            'ADM': [],
        };

        for (const e of entradas) {
            const sv = (e['serviço'] || e['servico'] || '').toLowerCase();
            if (sv.includes('atendimento') && !sv.includes('apoio')) grupos['Atendimento'].push(e);
            else if (sv.includes('apoio')) grupos['Apoio ao Atendimento'].push(e);
            else if (sv.includes('patrulha ocorr')) grupos['Patrulha Ocorrências'].push(e);
            else if (sv.includes('folga') || sv.includes('férias') || sv.includes('licen') || sv.includes('conval') || sv.includes('doente')) grupos['Ausências'].push(e);
            else if (sv.includes('dilig') || sv.includes('tribunal') || sv.includes('pronto') || sv.includes('secret') || sv.includes('inquer') || sv.includes('fcaa')) grupos['ADM'].push(e);
            else grupos['Patrulhas / Outros'].push(e);
        }

        let html = '';
        for (const [grupo, items] of Object.entries(grupos)) {
            if (!items.length) continue;
            html += `<div class="eg-section">${grupo}</div>`;

            // Agrupar por horário+serviço
            const mapa = {};
            for (const e of items) {
                const h = e['horário'] || e['horario'] || '';
                const sv = e['serviço'] || e['servico'] || '';
                const key = `${h}|${sv}`;
                if (!mapa[key]) mapa[key] = { h, sv, ids:[], vtr:'', rad:'' };
                mapa[key].ids.push(e['id'] || '');
                if (e['viatura'] && e['viatura'] !== 'nan') mapa[key].vtr = e['viatura'];
                if (e['rádio'] && e['rádio'] !== 'nan') mapa[key].rad = e['rádio'];
            }

            for (const { h, sv, ids, vtr, rad } of Object.values(mapa)) {
                const mostrarSv = !['Atendimento','Apoio ao Atendimento'].includes(grupo);
                html += `
                    <div class="eg-card">
                        <div class="eg-hora">${h || '—'}</div>
                        <div class="eg-info">
                            ${mostrarSv && sv ? `<div class="eg-servico">${sv}</div>` : ''}
                            <div class="eg-ids">${ids.filter(Boolean).join(', ')}</div>
                            ${vtr || rad ? `<div class="eg-extra">${[vtr,rad].filter(Boolean).join(' · ')}</div>` : ''}
                        </div>
                    </div>`;
            }
        }

        el.innerHTML = html;
    }
};
