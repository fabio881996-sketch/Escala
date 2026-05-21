/* ============================================
   api.js — Comunicação com o backend FastAPI
   ============================================ */

const API = {
    // Token JWT guardado em localStorage
    getToken() { return localStorage.getItem('gnr_token'); },
    setToken(t) { localStorage.setItem('gnr_token', t); },
    clearToken() { localStorage.removeItem('gnr_token'); localStorage.removeItem('gnr_user'); },
    getUser() { const u = localStorage.getItem('gnr_user'); return u ? JSON.parse(u) : null; },
    setUser(u) { localStorage.setItem('gnr_user', JSON.stringify(u)); },

    // Headers com autenticação
    headers() {
        const h = { 'Content-Type': 'application/json' };
        const t = this.getToken();
        if (t) h['Authorization'] = `Bearer ${t}`;
        return h;
    },

    // GET genérico com cache
    async get(url, useCache = true) {
        const cacheKey = 'api_' + url;
        if (useCache) {
            const cached = sessionStorage.getItem(cacheKey);
            if (cached) {
                const { data, ts } = JSON.parse(cached);
                if (Date.now() - ts < 300000) return data; // 5 min cache
            }
        }
        const res = await fetch(url, { headers: this.headers() });
        if (res.status === 401) { this.clearToken(); Router.go('login'); return null; }
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (useCache) sessionStorage.setItem(cacheKey, JSON.stringify({ data, ts: Date.now() }));
        return data;
    },

    // POST genérico
    async post(url, body) {
        const res = await fetch(url, { method: 'POST', headers: this.headers(), body: JSON.stringify(body) });
        if (res.status === 401) { this.clearToken(); Router.go('login'); return null; }
        if (!res.ok) throw new Error(await res.text());
        return await res.json();
    },

    // DELETE genérico
    async delete(url) {
        const res = await fetch(url, { method: 'DELETE', headers: this.headers() });
        if (!res.ok) throw new Error(await res.text());
        return await res.json();
    },

    // Login
    async login(email, pin) {
        const form = new URLSearchParams();
        form.append('username', email);
        form.append('password', pin);
        const res = await fetch('/api/auth/login', { method: 'POST', body: form });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Erro no login');
        }
        const data = await res.json();
        this.setToken(data.access_token);
        this.setUser({ id: data.user_id, nome: data.user_nome, is_admin: data.is_admin });
        return data;
    },

    // Endpoints específicos
    minha_escala: () => API.get('/api/escala/minha', false),
    escala_dia: (aba) => API.get(`/api/escala/dia/${aba}`, false),
    dias_publicados: () => API.get('/api/escala/publicados'),
    trocas_pendentes: () => API.get('/api/trocas/pendentes', false),
    minhas_trocas: () => API.get('/api/trocas/minhas', false),
    efetivo: () => API.get('/api/utilizadores/efetivo'),
    utilizadores: () => API.get('/api/utilizadores/'),

    solicitar_troca: (dados) => API.post('/api/trocas/solicitar', dados),
    publicar_dia: (aba) => API.post(`/api/escala/publicar/${aba}`, {}),
    despublicar_dia: (aba) => API.delete(`/api/escala/publicar/${aba}`),

    // Limpar cache da sessão
    clearCache() { Object.keys(sessionStorage).filter(k => k.startsWith('api_')).forEach(k => sessionStorage.removeItem(k)); },
};
