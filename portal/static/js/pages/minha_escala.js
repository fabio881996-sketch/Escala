/* ============================================
   pages/minha_escala.js — Minha Escala
   ============================================ */

const MinhaEscalaPage = {
    async render() {
        const content = document.getElementById('content');
        const user = API.getUser();

        content.innerHTML = `
            <div class="section-header">👤 ${user?.nome || ''}</div>
            <div id="minha-escala-list">
                ${Components.skeleton(3)}
            </div>
        `;

        try {
            const data = await API.minha_escala();
            this.renderServicos(data?.servicos || []);
        } catch (e) {
            document.getElementById('minha-escala-list').innerHTML =
                `<div class="alert alert-error">❌ Erro ao carregar: ${e.message}</div>`;
        }
    },

    renderServicos(servicos) {
        const el = document.getElementById('minha-escala-list');
        if (!servicos.length) {
            el.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📅</div>
                    <p>Não foram encontrados serviços escalados.</p>
                </div>`;
            return;
        }

        el.innerHTML = servicos.map(s => this.cardServico(s)).join('');
    },

    cardServico(s) {
        const cardClass = this.getCardClass(s.servico);
        const icone = this.getIcone(s.servico);

        let badge = '';
        if (s.is_hoje) badge = '<span class="badge badge-hoje">🟢 HOJE</span>';
        else if (s.is_amanha) badge = '<span class="badge badge-amanha">🔵 AMANHÃ</span>';
        else badge = `<span style="font-size:0.75rem;color:var(--cinza-texto)">${s.data}</span>`;

        let extras = '';
        if (s.horario) extras += `<div class="card-row">🕒 ${s.horario}</div>`;
        if (s.viatura && s.viatura !== 'nan') extras += `<div class="card-row">🚔 ${s.viatura}</div>`;
        if (s.radio && s.radio !== 'nan') extras += `<div class="card-row">📻 ${s.radio}</div>`;
        if (s.colegas && s.colegas.length > 0) extras += `<div class="card-row">👥 ${s.colegas.join(', ')}</div>`;
        if (s.observacoes && s.observacoes !== 'nan') extras += `<div class="card-row">📝 ${s.observacoes}</div>`;

        return `
            <div class="card ${cardClass}">
                <div class="card-label">${badge}</div>
                <div class="card-title">${icone} ${s.servico}</div>
                ${extras}
            </div>`;
    },

    getCardClass(servico) {
        const s = servico.toLowerCase();
        if (s.includes('folga')) return 'card-roxo';
        if (s.includes('férias') || s.includes('licen') || s.includes('doente')) return '';
        if (s.includes('remu') || s.includes('grat')) return 'card-verde';
        if (s.includes('tribunal') || s.includes('dilig')) return 'card-vermelho';
        return 'card-azul';
    },

    getIcone(servico) {
        const s = servico.toLowerCase();
        if (s.includes('folga')) return '😴';
        if (s.includes('férias') || s.includes('licen')) return '🏖️';
        if (s.includes('remu') || s.includes('grat')) return '💰';
        if (s.includes('tribunal')) return '⚖️';
        if (s.includes('atendimento')) return '📞';
        if (s.includes('patrulha')) return '🚔';
        return '🛡️';
    }
};
