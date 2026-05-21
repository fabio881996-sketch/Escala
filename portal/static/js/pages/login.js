/* ============================================
   pages/login.js — Página de Login
   ============================================ */

const LoginPage = {
    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div id="login-page">
                <div class="login-box">
                    <div class="login-header">
                        <div class="login-icon">🛡️</div>
                        <h1>Portal de Escalas</h1>
                        <p>Guarda Nacional Republicana<br>Posto Territorial de Famalicão</p>
                    </div>

                    <div id="login-error" class="alert alert-error" style="display:none"></div>

                    <div class="form-group">
                        <label class="form-label">📧 Email GNR</label>
                        <input type="email" id="login-email" class="form-input"
                            placeholder="nome.xxx@gnr.pt"
                            autocomplete="email" autocapitalize="none">
                    </div>

                    <div class="form-group">
                        <label class="form-label">🔐 PIN</label>
                        <input type="password" id="login-pin" class="form-input"
                            placeholder="••••" maxlength="6"
                            inputmode="numeric" pattern="[0-9]*">
                    </div>

                    <button class="btn btn-primary" id="login-btn" onclick="LoginPage.submit()">
                        Entrar
                    </button>
                </div>
            </div>
        `;

        // Enter para submeter
        document.getElementById('login-pin').addEventListener('keydown', e => {
            if (e.key === 'Enter') LoginPage.submit();
        });
        document.getElementById('login-email').addEventListener('keydown', e => {
            if (e.key === 'Enter') document.getElementById('login-pin').focus();
        });
    },

    async submit() {
        const email = document.getElementById('login-email').value.trim();
        const pin = document.getElementById('login-pin').value.trim();
        const btn = document.getElementById('login-btn');
        const errEl = document.getElementById('login-error');

        errEl.style.display = 'none';

        if (!email || !pin) {
            errEl.textContent = 'Preenche o email e o PIN.';
            errEl.style.display = 'flex';
            return;
        }

        btn.disabled = true;
        btn.textContent = 'A entrar...';

        try {
            await API.login(email, pin);
            App.initUI();
            Router.go('home');
        } catch (e) {
            errEl.textContent = '❌ ' + (e.message || 'Erro no login');
            errEl.style.display = 'flex';
            btn.disabled = false;
            btn.textContent = 'Entrar';
        }
    }
};
