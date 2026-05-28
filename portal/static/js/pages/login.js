/* ============================================
   pages/login.js — Página de Login
   ============================================ */

const LoginPage = {
    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div id="login-page" style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(160deg,#1A2B4A 0%,#243B5C 60%,#1A2B4A 100%);padding:24px">
                <div style="width:100%;max-width:360px">
                    <!-- Header -->
                    <div style="text-align:center;margin-bottom:32px">
                        <img src="/static/icons/icon-192.png" alt="GNR" style="width:96px;height:96px;margin-bottom:16px;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.4))">
                        <h1 style="color:#fff;font-size:1.4rem;font-weight:800;margin:0 0 4px 0">Portal de Escalas</h1>
                        <p style="color:#94a3b8;font-size:.85rem;margin:0">Guarda Nacional Republicana<br>Posto Territorial de Famalicão</p>
                    </div>

                    <!-- Card -->
                    <div style="background:#fff;border-radius:16px;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,0.3)">
                        <div id="login-error" class="alert alert-error" style="display:none;margin-bottom:16px"></div>

                        <div class="form-group">
                            <label class="form-label">📧 Email GNR</label>
                            <input type="email" id="login-email" class="form-input"
                                placeholder="nome.apelido@gnr.pt"
                                autocomplete="email" autocapitalize="none">
                        </div>

                        <div class="form-group">
                            <label class="form-label">🔐 PIN</label>
                            <input type="password" id="login-pin" class="form-input"
                                placeholder="••••••" maxlength="6"
                                inputmode="numeric" pattern="[0-9]*">
                        </div>

                        <button class="btn btn-primary" id="login-btn" onclick="LoginPage.submit()" style="width:100%;margin-top:8px">
                            Entrar
                        </button>
                    </div>

                    <p style="text-align:center;color:#475569;font-size:.75rem;margin-top:20px">
                        © ${new Date().getFullYear()} GNR Famalicão
                    </p>
                </div>
            </div>
        `;

        document.getElementById('login-pin').addEventListener('keydown', e => {
            if (e.key === 'Enter') LoginPage.submit();
        });
        document.getElementById('login-email').addEventListener('keydown', e => {
            if (e.key === 'Enter') document.getElementById('login-pin').focus();
        });
    },

    async submit() {
        const email = document.getElementById('login-email').value.trim();
        const pin   = document.getElementById('login-pin').value.trim();
        const btn   = document.getElementById('login-btn');
        const errEl = document.getElementById('login-error');

        errEl.style.display = 'none';

        if (!email || !pin) {
            errEl.textContent = '⚠️ Preenche o email e o PIN.';
            errEl.style.display = 'block';
            return;
        }

        btn.disabled = true;
        btn.textContent = 'A entrar...';

        try {
            await API.login(email, pin);
            App.initUI();
            Router.go('home');
        } catch (e) {
            errEl.textContent = '❌ ' + (e.message || 'PIN ou email incorretos.');
            errEl.style.display = 'block';
            btn.disabled = false;
            btn.textContent = 'Entrar';
            document.getElementById('login-pin').value = '';
        }
    }
};
