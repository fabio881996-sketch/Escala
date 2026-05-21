/* ============================================
   app.js — Inicialização da app
   ============================================ */

const App = {
    init() {
        // Esconder splash após carregar
        setTimeout(() => {
            const splash = document.getElementById('splash');
            if (splash) splash.classList.add('hidden');
            setTimeout(() => { if (splash) splash.remove(); }, 400);
        }, 800);

        Router.init();
    },

    initUI() {
        const user = API.getUser();
        if (!user) return;

        // Navbar
        document.getElementById('app').innerHTML = `
            <div id="navbar">
                <div>
                    <div class="nav-title">🛡️ Portal de Escalas</div>
                    <div class="nav-subtitle">Posto de Famalicão</div>
                </div>
                <div class="nav-user">
                    ${user.is_admin ? '<span class="nav-badge">⭐ Admin</span>' : ''}
                    <button class="nav-btn" onclick="App.logout()" title="Sair">🚪</button>
                </div>
            </div>
            <div id="content"></div>
            <div id="tabbar">
                <button class="tab-item" data-page="home" onclick="Router.go('home')">
                    <span class="tab-icon">📅</span>
                    <span>Minha Escala</span>
                </button>
                <button class="tab-item" data-page="escala-geral" onclick="Router.go('escala-geral')">
                    <span class="tab-icon">🔍</span>
                    <span>Escala Geral</span>
                </button>
                <button class="tab-item" data-page="trocas" onclick="Router.go('trocas')">
                    <div class="tab-badge">
                        <span class="tab-icon">🔄</span>
                        <span id="badge-trocas" class="tab-badge-count" style="display:none">0</span>
                    </div>
                    <span>Trocas</span>
                </button>
            </div>
        `;

        // Verificar trocas pendentes
        App.checkPendentes();
    },

    async checkPendentes() {
        try {
            const data = await API.trocas_pendentes();
            if (data && data.trocas && data.trocas.length > 0) {
                const badge = document.getElementById('badge-trocas');
                if (badge) {
                    badge.textContent = data.trocas.length;
                    badge.style.display = 'flex';
                }
            }
        } catch (e) { /* silencioso */ }
    },

    logout() {
        if (confirm('Tens a certeza que queres sair?')) {
            API.clearToken();
            API.clearCache();
            location.reload();
        }
    }
};

// Iniciar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => App.init());
