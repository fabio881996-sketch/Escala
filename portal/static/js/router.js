/* ============================================
   router.js — Navegação SPA
   ============================================ */

const Router = {
    current: null,

    routes: {
        'login':        () => LoginPage.render(),
        'home':         () => MinhaEscalaPage.render(),
        'escala-geral': () => EscalaGeralPage.render(),
        'ferias':       () => FeriasPage.render(),
        'trocas':       () => TrocasPage.render(),
    },

    go(page, params = {}) {
        this.current = page;
        this.params = params;

        // Mostrar/esconder navbar e tabbar
        const isLogin = page === 'login';
        const navbar = document.getElementById('navbar');
        const tabbar = document.getElementById('tabbar');
        const content = document.getElementById('content');

        if (navbar) navbar.style.display = isLogin ? 'none' : 'flex';
        if (tabbar) tabbar.style.display = isLogin ? 'none' : 'flex';
        if (content) content.style.display = isLogin ? 'none' : 'block';

        if (isLogin) {
            document.getElementById('app').innerHTML = '';
            LoginPage.render();
            return;
        }

        // Actualizar tab activa
        document.querySelectorAll('.tab-item').forEach(t => {
            t.classList.toggle('active', t.dataset.page === page);
        });

        // Render da página
        const renderFn = this.routes[page];
        if (renderFn) {
            document.getElementById('content').innerHTML = '';
            renderFn();
        }
    },

    init() {
        // Verificar se está autenticado
        const user = API.getUser();
        const token = API.getToken();
        if (!user || !token) {
            this.go('login');
        } else {
            App.initUI();
            this.go('home');
        }
    }
};
