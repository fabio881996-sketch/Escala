/* escala_geral.js v3 — layout igual ao Streamlit */

const EscalaGeralPage = {
    async render() {
        const content = document.getElementById('content');
        content.innerHTML = `
            <div class="section-h">🔍 Escala Geral</div>
            <div class="form-group" style="display:flex;align-items:center;gap:8px">
                <button onclick="EscalaGeralPage.navDia(-1)" style="padding:10px 14px;border:1.5px solid var(--cinza-borda);border-radius:var(--radius-sm);background:#fff;font-size:1rem;cursor:pointer">◀</button>
                <input type="date" id="eg-data" class="form-input" style="flex:1;font-size:.9rem;font-weight:600"
                    value="${new Date().toISOString().slice(0,10)}"
                    onchange="EscalaGeralPage.carregar()">
                <button onclick="EscalaGeralPage.navDia(1)" style="padding:10px 14px;border:1.5px solid var(--cinza-borda);border-radius:var(--radius-sm);background:#fff;font-size:1rem;cursor:pointer">▶</button>
            </div>
            <div id="eg-content">${Components.skeleton(3)}</div>`;
        await this.carregar();
    },

    navDia(delta) {
        const inp = document.getElementById('eg-data');
        if (!inp) return;
        const dt = new Date(inp.value);
        dt.setDate(dt.getDate() + delta);
        inp.value = dt.toISOString().slice(0,10);
        this.carregar();
    },

    async carregar() {
        const inp = document.getElementById('eg-data');
        if (!inp) return;
        const dt = new Date(inp.value);
        const aba = `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}`;
        const diaSemana = ['Domingo','Segunda','Terça','Quarta','Quinta','Sexta','Sábado'][dt.getDay()];
        const el = document.getElementById('eg-content');
        el.innerHTML = Components.loading();
        try {
            const data = await API.escala_dia(aba);
            this.renderEscala(data, dt, diaSemana);
        } catch (e) {
            el.innerHTML = `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    renderEscala(data, dt, diaSemana) {
        const el = document.getElementById('eg-content');
        const entradas = data?.entradas || [];

        if (!entradas.length) {
            el.innerHTML = `<div class="empty"><div class="empty-icon">📅</div><div class="empty-txt">Sem escala publicada para este dia.</div></div>`;
            return;
        }

        // Classificar entradas
        const ausencias = {};
        const adm = {};
        const atendimento = [];
        const apoio = [];
        const patOcorr = [];
        const outros = [];

        const AUSENCIA_TIPOS = ['folga semanal','folga complementar','férias','licença','convalescença','outras licenças','doente'];
        const ADM_TIPOS = ['diligência','tribunal','pronto','secretaria','inquérito','fcaa','instrução','remunerado'];

        for (const e of entradas) {
            const sv = (e['serviço'] || '').toLowerCase().trim();
            const nome = e['nome_fmt'] || e['id'] || '';

            if (AUSENCIA_TIPOS.some(t => sv.includes(t))) {
                const tipo = e['serviço'] || sv;
                if (!ausencias[tipo]) ausencias[tipo] = [];
                ausencias[tipo].push(nome);
            } else if (ADM_TIPOS.some(t => sv.includes(t))) {
                const tipo = e['serviço'] || sv;
                if (!adm[tipo]) adm[tipo] = [];
                adm[tipo].push(nome);
            } else if (sv.includes('atendimento') && !sv.includes('apoio')) {
                atendimento.push(e);
            } else if (sv.includes('apoio')) {
                apoio.push(e);
            } else if (sv.includes('patrulha ocorr')) {
                patOcorr.push(e);
            } else {
                outros.push(e);
            }
        }

        let html = `<div style="font-size:.82rem;color:var(--cinza-txt);margin-bottom:12px;font-weight:500">${diaSemana}, ${dt.getDate().toString().padStart(2,'0')}/${(dt.getMonth()+1).toString().padStart(2,'0')}/${dt.getFullYear()}</div>`;

        // AUSÊNCIAS
        if (Object.keys(ausencias).length || Object.keys(adm).length) {
            html += `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">`;

            if (Object.keys(ausencias).length) {
                html += `<div class="card" style="padding:12px">
                    <div style="font-size:.68rem;font-weight:800;color:#fff;background:var(--azul);padding:5px 10px;border-radius:6px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">Ausências</div>`;
                for (const [tipo, ids] of Object.entries(ausencias)) {
                    html += `<div style="margin-bottom:6px"><span style="font-size:.75rem;font-weight:700;color:#374151">${tipo}:</span> <span style="font-size:.75rem;color:#475569">${ids.join(', ')}</span></div>`;
                }
                html += `</div>`;
            }

            if (Object.keys(adm).length) {
                html += `<div class="card" style="padding:12px">
                    <div style="font-size:.68rem;font-weight:800;color:#fff;background:var(--azul);padding:5px 10px;border-radius:6px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">ADM / Outras</div>`;
                for (const [tipo, ids] of Object.entries(adm)) {
                    html += `<div style="margin-bottom:6px"><span style="font-size:.75rem;font-weight:700;color:#374151">${tipo}:</span> <span style="font-size:.75rem;color:#475569">${ids.join(', ')}</span></div>`;
                }
                html += `</div>`;
            }

            html += `</div>`;
        }

        // Tabela genérica
        const renderTabela = (titulo, linhas, comServico = false) => {
            if (!linhas.length) return '';
            // Agrupar por horário+serviço
            const mapa = {};
            for (const e of linhas) {
                const h = e['horário'] || '';
                const sv = e['serviço'] || '';
                const key = comServico ? `${h}|${sv}` : h;
                if (!mapa[key]) mapa[key] = { h, sv, nomes:[], vtr:'', rad:'', ind:'' };
                mapa[key].nomes.push(e['nome_fmt'] || e['id'] || '');
                if (e['viatura'] && e['viatura'] !== 'nan') mapa[key].vtr = e['viatura'];
                if (e['rádio'] && e['rádio'] !== 'nan') mapa[key].rad = e['rádio'];
                if (e['indicativo rádio'] && e['indicativo rádio'] !== 'nan') mapa[key].ind = e['indicativo rádio'];
            }

            let t = `<div class="card" style="padding:0;overflow:hidden;margin-bottom:8px">
                <div style="font-size:.7rem;font-weight:800;color:#fff;background:var(--azul);padding:8px 14px;text-transform:uppercase;letter-spacing:.06em">${titulo}</div>
                <table style="width:100%;border-collapse:collapse">
                <thead><tr style="background:#EFF6FF">
                    <th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Horário</th>
                    <th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Militares</th>
                    ${comServico ? '<th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Serviço</th>' : ''}
                    ${linhas.some(e => e['indicativo rádio']) ? '<th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Indicativo</th>' : ''}
                    ${linhas.some(e => e['rádio']) ? '<th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Rádio</th>' : ''}
                    ${linhas.some(e => e['viatura']) ? '<th style="padding:7px 10px;font-size:.7rem;font-weight:700;color:var(--azul);text-align:left;border-bottom:1px solid var(--cinza-borda)">Viatura</th>' : ''}
                </tr></thead><tbody>`;

            let alt = false;
            for (const { h, sv, nomes, vtr, rad, ind } of Object.values(mapa)) {
                const bg = alt ? '#F8FAFC' : '#fff';
                t += `<tr style="background:${bg};border-bottom:1px solid #F1F5F9">
                    <td style="padding:8px 10px;font-size:.78rem;font-weight:700;color:var(--azul);white-space:nowrap">${h || '—'}</td>
                    <td style="padding:8px 10px;font-size:.78rem;color:#1E293B">${nomes.join(', ')}</td>
                    ${comServico ? `<td style="padding:8px 10px;font-size:.75rem;color:var(--azul-vivo)">${sv}</td>` : ''}
                    ${linhas.some(e => e['indicativo rádio']) ? `<td style="padding:8px 10px;font-size:.78rem;color:#475569">${ind}</td>` : ''}
                    ${linhas.some(e => e['rádio']) ? `<td style="padding:8px 10px;font-size:.78rem;color:#475569">${rad}</td>` : ''}
                    ${linhas.some(e => e['viatura']) ? `<td style="padding:8px 10px;font-size:.78rem;color:#475569">${vtr}</td>` : ''}
                </tr>`;
                alt = !alt;
            }
            t += `</tbody></table></div>`;
            return t;
        };

        html += renderTabela('Atendimento', atendimento);
        html += renderTabela('Apoio ao Atendimento', apoio);
        html += renderTabela('Patrulha Ocorrências', patOcorr);
        if (outros.length) html += renderTabela('Outros Serviços', outros, true);

        el.innerHTML = html;
    }
};
