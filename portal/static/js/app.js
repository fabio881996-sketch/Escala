/* app.js v2 */

const App = {
    init() {
        setTimeout(() => {
            const s = document.getElementById('splash');
            if (s) { s.classList.add('hidden'); setTimeout(() => s.remove(), 400); }
        }, 700);
        Router.init();
    },

    initUI() {
        const user = API.getUser();
        if (!user) return;

        document.getElementById('app').innerHTML = `
            <div id="navbar">
                <div class="nav-left">
                    <span class="nav-logo">🛡️</span>
                    <div>
                        <div class="nav-title">Portal de Escalas</div>
                        <div class="nav-sub">Posto de Famalicão</div>
                    </div>
                </div>
                <div class="nav-right">
                    ${user.is_admin ? '<span class="nav-badge">⭐ ADMIN</span>' : ''}
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
                    <div class="tab-badge-wrap">
                        <span class="tab-icon">🔄</span>
                        <span id="tab-dot-trocas" class="tab-dot" style="display:none"></span>
                    </div>
                    <span>Trocas</span>
                </button>
            </div>`;

        App.checkPendentes();
    },

    async checkPendentes() {
        try {
            const data = await API.trocas_pendentes();
            if (data?.trocas?.length > 0) {
                const dot = document.getElementById('tab-dot-trocas');
                if (dot) dot.style.display = 'block';
            }
        } catch(e) {}
    },

    logout() {
        if (confirm('Tens a certeza que queres sair?')) {
            API.clearToken(); API.clearCache(); location.reload();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
