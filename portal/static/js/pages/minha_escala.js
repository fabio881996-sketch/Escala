/* minha_escala.js v2 */

const MinhaEscalaPage = {
    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();
        content.innerHTML = `
            <div class="section-h">👤 ${user?.nome || ''}</div>
            <div id="me-list">${Components.skeleton(3)}</div>`;
        try {
            const data = await API.minha_escala();
            this.renderServicos(data?.servicos || []);
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

    card(s) {
        const cls = this.cardClass(s.servico);
        const icone = this.icone(s.servico);

        let badge = '';
        if (s.is_hoje) badge = '<span class="badge badge-hoje">🟢 HOJE</span>';
        else if (s.is_amanha) badge = '<span class="badge badge-amanha">🔵 AMANHÃ</span>';
        else badge = `<span class="badge badge-neutro">📅 ${s.data}</span>`;
        if (s.troca_aprovada) badge += ' <span style="background:#f59e0b;color:#fff;font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:99px;margin-left:4px">🔄 TROCA</span>';

        let rows = '';
        if (s.horario) rows += `<div class="card-row"><span class="card-row-icon">🕒</span>${s.horario}</div>`;
        if (s.viatura && s.viatura !== 'nan') rows += `<div class="card-row"><span class="card-row-icon">🚔</span>${s.viatura}</div>`;
        if (s.radio && s.radio !== 'nan') rows += `<div class="card-row"><span class="card-row-icon">📻</span>${s.radio}</div>`;
        const isAusencia = /folga|férias|ferias|licen|doente|conval|dilig|tribunal|pronto|secretaria|inquér|inquer|baixa/i.test(s.servico);
        if (!isAusencia && s.colegas && s.colegas.length > 0) {
            rows += `<div class="card-row"><span class="card-row-icon">👥</span><span style="font-size:.8rem">${s.colegas.join(' · ')}</span></div>`;
        }
        if (s.observacoes && s.observacoes !== 'nan') rows += `<div class="card-row"><span class="card-row-icon">📝</span>${s.observacoes}</div>`;

        return `
            <div class="card ${cls}">
                <div class="card-label">${badge}</div>
                <div class="card-title">${icone} ${s.servico}</div>
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
