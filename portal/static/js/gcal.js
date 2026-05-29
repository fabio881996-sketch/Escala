/* ============================================
   gcal.js — Google Calendar OAuth + Sync
   ============================================ */

const GCal = {

    // Iniciar autenticação Google — redirect na mesma janela
    async autenticar(tipo) {
        const data = await API._get(`/api/calendar/auth?tipo=${tipo}`);
        // Guardar intenção antes do redirect
        sessionStorage.setItem('gcal_pending', tipo);
        window.location.href = data.auth_url;
        // Nunca resolve — a página vai fazer redirect
        return new Promise(() => {});
    },

    // Chamar no init da app após voltar do OAuth
    verificarCallbackPendente() {
        const tipo = sessionStorage.getItem('gcal_pending');
        if (!tipo) return;
        sessionStorage.removeItem('gcal_pending');
        // Pequeno delay para garantir que a app carregou
        setTimeout(() => {
            console.log('[GCal] a retomar exportação após OAuth:', tipo);
            if (tipo === 'escala') GCal.exportarEscala();
            else if (tipo === 'folgas') GCal.exportarFolgas();
            else if (tipo === 'ferias') GCal.exportarFerias();
        }, 1000);
    },

    // Verificar se já está autenticado
    async estaAutenticado() {
        try {
            const data = await API._get('/api/calendar/status');
            return data.connected;
        } catch {
            return false;
        }
    },

    // Sincronizar eventos
    async sincronizar(eventos) {
        return API._post('/api/calendar/sync', { eventos });
    },

    // Converter serviços da escala para formato Google Calendar
    servicosParaEventos(servicos) {
        const eventos = [];
        for (const s of servicos) {
            if (!s.horario || !s.data) continue;
            const [d, m, y] = s.data.split('/');
            const partes = s.horario.split('-');
            if (partes.length < 2) continue;

            const hIni = parseInt(partes[0].trim().substring(0, 2));
            const hFim = parseInt(partes[1].trim().substring(0, 2));

            const dtIni = new Date(parseInt(y), parseInt(m) - 1, parseInt(d), hIni, 0);
            const dtFim = new Date(parseInt(y), parseInt(m) - 1, parseInt(d), hFim, 0);
            if (dtFim <= dtIni) dtFim.setDate(dtFim.getDate() + 1);

            const fmt = dt => dt.toISOString();

            eventos.push({
                summary: `🛡️ ${s.servico}`,
                start: { dateTime: fmt(dtIni), timeZone: 'Europe/Lisbon' },
                end:   { dateTime: fmt(dtFim), timeZone: 'Europe/Lisbon' },
                description: s.colegas?.length ? `Colegas: ${s.colegas.join(', ')}` : '',
            });
        }
        return eventos;
    },

    // Converter férias para formato Google Calendar
    feriasParaEventos(periodos, ano) {
        return periodos.map(p => {
            const [d1, m1, y1] = p.inicio.split('/');
            const [d2, m2, y2] = p.fim.split('/');
            const dtFim = new Date(parseInt(y2), parseInt(m2) - 1, parseInt(d2));
            dtFim.setDate(dtFim.getDate() + 1); // DTEND exclusivo
            return {
                summary: `🏖️ Férias P${p.numero} (${p.dias_uteis} dias úteis)`,
                start: { date: `${y1}-${m1}-${d1}` },
                end:   { date: `${dtFim.getFullYear()}-${String(dtFim.getMonth()+1).padStart(2,'0')}-${String(dtFim.getDate()).padStart(2,'0')}` },
            };
        });
    },

    // Converter folgas para formato Google Calendar
    folgasParaEventos(texto) {
        // Parsear o ICS que vem do servidor
        const eventos = [];
        const linhas = texto.split(/\r?\n/);
        let evento = null;
        for (const linha of linhas) {
            if (linha === 'BEGIN:VEVENT') { evento = {}; }
            else if (linha === 'END:VEVENT' && evento) {
                if (evento.summary && evento.start) eventos.push(evento);
                evento = null;
            } else if (evento) {
                if (linha.startsWith('DTSTART;VALUE=DATE:')) {
                    const d = linha.replace('DTSTART;VALUE=DATE:', '');
                    evento.start = { date: `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` };
                } else if (linha.startsWith('DTEND;VALUE=DATE:')) {
                    const d = linha.replace('DTEND;VALUE=DATE:', '');
                    evento.end = { date: `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}` };
                } else if (linha.startsWith('SUMMARY:')) {
                    evento.summary = linha.replace('SUMMARY:', '');
                }
            }
        }
        return eventos;
    },

    // Fluxo completo: autenticar + sincronizar escala
    async exportarEscala() {
        try {
            const autenticado = await this.estaAutenticado();
            console.log('[GCal] autenticado:', autenticado);
            if (!autenticado) {
                console.log('[GCal] a iniciar autenticação...');
                await this.autenticar('escala');
                console.log('[GCal] autenticação concluída');
            }
            const data = await API.minha_escala();
            const servicos = (data?.servicos || []).filter(s => {
                const l = s.servico.toLowerCase();
                return !l.match(/folga|férias|ferias|licen|doente|conval|dilig|tribunal|pronto/);
            });
            console.log('[GCal] serviços a exportar:', servicos.length);
            if (!servicos.length) { alert('Sem serviços para exportar.'); return; }
            const eventos = this.servicosParaEventos(servicos);
            console.log('[GCal] eventos criados:', eventos.length, eventos);
            const result = await this.sincronizar(eventos);
            console.log('[GCal] resultado sync:', result);
            alert(`✅ ${result.criados} eventos adicionados ao Google Calendar!`);
        } catch(e) {
            console.error('[GCal] erro:', e);
            if (e.message !== 'Autenticação cancelada') alert('❌ Erro: ' + e.message);
        }
    },

    // Fluxo completo: autenticar + sincronizar férias
    async exportarFerias() {
        try {
            const autenticado = await this.estaAutenticado();
            if (!autenticado) {
                await this.autenticar('ferias');
            }
            const data = await API.minhas_ferias();
            const eventos = this.feriasParaEventos(data.periodos, data.ano);
            if (!eventos.length) { alert('Sem férias para exportar.'); return; }
            const result = await this.sincronizar(eventos);
            alert(`✅ ${result.criados} períodos de férias adicionados ao Google Calendar!`);
        } catch(e) {
            if (e.message !== 'Autenticação cancelada') alert('❌ Erro: ' + e.message);
        }
    },

    // Fluxo completo: autenticar + sincronizar folgas
    async exportarFolgas() {
        try {
            const autenticado = await this.estaAutenticado();
            if (!autenticado) {
                await this.autenticar('folgas');
            }
            const res = await fetch('/api/ferias/folgas-ics', { headers: API.headers() });
            if (!res.ok) throw new Error(await res.text());
            const texto = await res.text();
            const eventos = this.folgasParaEventos(texto);
            if (!eventos.length) { alert('Sem folgas para exportar.'); return; }
            const result = await this.sincronizar(eventos);
            alert(`✅ ${result.criados} folgas adicionadas ao Google Calendar!`);
        } catch(e) {
            if (e.message !== 'Autenticação cancelada') alert('❌ Erro: ' + e.message);
        }
    },
};
