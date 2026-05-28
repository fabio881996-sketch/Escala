/* ============================================
   pages/login.js — Página de Login (só PIN)
   ============================================ */

const LoginPage = {
    pin: '',

    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div id="login-page" style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(160deg,#1A2B4A 0%,#243B5C 60%,#1A2B4A 100%);padding:24px">
                <div style="width:100%;max-width:340px">
                    <!-- Header -->
                    <div style="text-align:center;margin-bottom:32px">
                        <img src="/static/icons/icon-192.png" alt="GNR" style="width:100px;height:100px;margin-bottom:16px;border-radius:16px">
                        <h1 style="color:#fff;font-size:1.4rem;font-weight:800;margin:0 0 4px 0">Portal de Escalas</h1>
                        <p style="color:#94a3b8;font-size:.85rem;margin:0">Guarda Nacional Republicana<br>Posto Territorial de Famalicão</p>
                    </div>

                    <!-- PIN display -->
                    <div style="display:flex;justify-content:center;gap:12px;margin-bottom:24px">
                        ${[0,1,2,3].map(i => `<div id="pin-dot-${i}" style="width:16px;height:16px;border-radius:50%;border:2px solid #94a3b8;background:transparent;transition:all .2s"></div>`).join('')}
                    </div>

                    <div id="login-error" style="display:none;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:#fca5a5;padding:10px 14px;border-radius:10px;font-size:.82rem;text-align:center;margin-bottom:16px"></div>

                    <!-- Teclado numérico -->
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
                        ${[1,2,3,4,5,6,7,8,9,'',0,'⌫'].map(n => `
                            <button onclick="LoginPage.press('${n}')"
                                style="padding:18px;font-size:1.3rem;font-weight:600;border:none;border-radius:12px;
                                    background:${n==='' ? 'transparent' : 'rgba(255,255,255,.1)'};
                                    color:#fff;cursor:${n==='' ? 'default' : 'pointer'};
                                    ${n==='' ? 'pointer-events:none' : ''}">
                                ${n}
                            </button>`).join('')}
                    </div>

                    <p style="text-align:center;color:#475569;font-size:.72rem;margin-top:24px">© 2026 fferr</p>
                </div>
            </div>
        `;
        this.pin = '';
    },

    press(val) {
        const errEl = document.getElementById('login-error');
        if (errEl) errEl.style.display = 'none';

        if (val === '⌫') {
            this.pin = this.pin.slice(0, -1);
        } else if (val !== '' && this.pin.length < 4) {
            this.pin += val;
        }

        // Actualizar dots
        for (let i = 0; i < 4; i++) {
            const dot = document.getElementById(`pin-dot-${i}`);
            if (dot) {
                dot.style.background = i < this.pin.length ? '#fff' : 'transparent';
                dot.style.borderColor = i < this.pin.length ? '#fff' : '#94a3b8';
            }
        }

        if (this.pin.length === 4) {
            setTimeout(() => this.submit(), 100);
        }
    },

    async submit() {
        const errEl = document.getElementById('login-error');
        try {
            await API.login(this.pin, this.pin);
            App.initUI();
            Router.go('home');
        } catch (e) {
            if (errEl) {
                errEl.textContent = '❌ PIN incorreto. Tenta novamente.';
                errEl.style.display = 'block';
            }
            this.pin = '';
            for (let i = 0; i < 4; i++) {
                const dot = document.getElementById(`pin-dot-${i}`);
                if (dot) { dot.style.background = 'transparent'; dot.style.borderColor = '#94a3b8'; }
            }
        }
    }
};
