/* minha_escala.js v2 */

const MinhaEscalaPage = {
    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();
        content.innerHTML = `
            <div class="section-h">👤 ${user?.nome || ''}</div>
            <div id="me-list">${Components.skeleton(3)}</div>`;
        try {
            const [data, anivData] = await Promise.all([
                API.minha_escala(),
                API._get('/api/escala/aniversarios', false).catch(() => null),
            ]);
            this.renderServicos(data?.servicos || []);
            const aniv = anivData?.aniversariantes || [];
            if (aniv.length) {
                const banner = document.createElement('div');
                banner.style.cssText = 'padding:8px 16px 0';
                banner.innerHTML = aniv.map(a => `
                    <div style="background:linear-gradient(135deg,#FEF9C3,#FEF08A);border-left:4px solid #EAB308;
                        border-radius:10px;padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px">
                        <span style="font-size:1.6rem">🎂</span>
                        <div>
                            <div style="font-weight:700;color:#713F12;font-size:.9rem">Hoje é o aniversário de ${a.nome}!</div>
                            <div style="color:#92400E;font-size:.8rem">Completa ${a.idade} anos — Parabéns! 🎉</div>
                        </div>
                    </div>`).join('');
                content.prepend(banner);
            }
        } catch (e) {
            document.getElementById('me-list').innerHTML =
                `<div class="alert alert-error">❌ ${e.message}</div>`;
        }
    },

    renderServicos(servicos) {
        const el = document.getElementById('me-list');
        if (!servicos.length) {
            el.innerHTML = `<div class="empty"><div class="empty-icon">📅</div><div class="empty-txt">Sem serviços publicados.</div></div>`;
            return;
        }
        el.innerHTML = servicos.map(s => this.card(s)).join('');
    },

    // Limpa valores nulos/nan devolvendo string vazia
    _val(v) {
        if (v === null || v === undefined) return '';
        const s = String(v).trim();
        return (s === 'nan' || s === 'None' || s === 'NaN' || s === 'none') ? '' : s;
    },

    card(s) {
        const cls = this.cardClass(s.servico);
        const icone = this.icone(s.servico);
        const v = (x) => this._val(x);

        let badge = '';
        if (s.is_hoje) badge = '<span class="badge badge-hoje">🟢 HOJE</span>';
        else if (s.is_amanha) badge = '<span class="badge badge-amanha">🔵 AMANHÃ</span>';
        else {
            const _diasSem = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
            const _parts = s.data.split('/');
            const _dObj = new Date(parseInt(_parts[2]), parseInt(_parts[1])-1, parseInt(_parts[0]));
            const _diaSem = _diasSem[_dObj.getDay()];
            badge = `<span class="badge badge-neutro">📅 ${_diaSem} ${s.data}</span>`;
        }
        if (s.troca_aprovada) badge += ' <span style="background:#f59e0b;color:#fff;font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:99px;margin-left:4px">🔄 TROCA</span>';
        if (s.is_remunerado) badge += ' <span style="background:#16a34a;color:#fff;font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:99px;margin-left:4px">💶 REMUNERADO</span>';

        // Horário ao lado do título
        const horario = v(s.horario);
        const tituloHorario = horario
            ? `<span style="font-size:.8rem;font-weight:500;opacity:.75;margin-left:8px">${horario}</span>`
            : '';

        let rows = '';
        const viatura    = v(s.viatura);
        const radio      = v(s.radio);
        const indicativo = v(s.indicativo);
        const obs        = v(s.observacoes);

        if (viatura)    rows += `<div class="card-row"><span class="card-row-icon">🚔</span>${viatura}</div>`;

        // Rádio e indicativo na mesma linha
        if (radio || indicativo) {
            const radioInd = [radio, indicativo].filter(Boolean).join(' · ');
            rows += `<div class="card-row"><span class="card-row-icon">📻</span>${radioInd}</div>`;
        }

        const isAusencia = /folga|férias|ferias|licen|doente|conval|dilig|tribunal|pronto|secretaria|inquér|inquer|baixa/i.test(s.servico);
        if (!isAusencia && s.colegas && s.colegas.length > 0) {
            rows += `<div class="card-row"><span class="card-row-icon">👥</span><span style="font-size:.8rem">${s.colegas.join(' · ')}</span></div>`;
        }
        if (!isAusencia && s.troca_com) {
            const label = s.troca_com_label || 'Trocou c/';
            rows += `<div class="card-row"><span class="card-row-icon">🔄</span><span style="font-size:.8rem;color:#d97706;font-weight:600">${label} ${s.troca_com}</span></div>`;
        }
        if (obs) rows += `<div class="card-row"><span class="card-row-icon">📝</span>${obs}</div>`;

        return `
            <div class="card ${cls}">
                <div class="card-label">${badge}</div>
                <div class="card-title">${icone} ${s.servico}${tituloHorario}</div>
                ${rows}
            </div>`;
    },

    cardClass(s) {
        const l = s.toLowerCase();
        if (l.includes('folga')) return 'card-roxo';
        if (l.includes('férias') || l.includes('licen')) return '';
        if (l.includes('remu') || l.includes('grat')) return 'card-verde';
        if (l.includes('tribunal') || l.includes('dilig')) return 'card-amber';
        return 'card-azul';
    },

    icone(s) {
        const l = s.toLowerCase();
        if (l.includes('folga')) return '😴';
        if (l.includes('férias')) return '🏖️';
        if (l.includes('licen') || l.includes('doente') || l.includes('conval')) return '🏥';
        if (l.includes('remu') || l.includes('grat')) return '💰';
        if (l.includes('tribunal')) return '⚖️';
        if (l.includes('atendimento')) return '📞';
        if (l.includes('patrulha')) return '🚔';
        if (l.includes('instrução')) return '📚';
        return '🛡️';
    }
};
