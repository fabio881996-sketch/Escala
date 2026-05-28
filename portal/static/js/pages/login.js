/* login.js — Teclado PIN estilo GNR */

const LoginPage = {
    _pin: '',
    _erro: false,

    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;
                background:linear-gradient(160deg,#0F1F38 0%,#1A2B4A 50%,#1E3A8A 100%);padding:24px">
                <div style="width:100%;max-width:340px">

                    <div style="text-align:center;margin-bottom:36px">
                        <img src="/static/icons/icon-192.png" alt="GNR"
                            style="width:88px;height:88px;margin-bottom:14px;border-radius:20px;
                                box-shadow:0 8px 32px rgba(0,0,0,0.4)">
                        <div style="font-size:22px;font-weight:700;color:white;letter-spacing:-0.02em">Portal de Escalas</div>
                        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:6px;
                            letter-spacing:0.08em;text-transform:uppercase">Posto Territorial de Vila Nova de Famalicão</div>
                    </div>

                    <div style="background:rgba(255,255,255,0.07);backdrop-filter:blur(20px);
                        border:1px solid rgba(255,255,255,0.12);border-radius:24px;padding:28px 24px 24px">

                        <!-- Dots -->
                        <div id="pin-dots" style="display:flex;gap:20px;justify-content:center;margin-bottom:28px">
                            ${[0,1,2,3].map(i => `
                                <div id="dot-${i}" style="width:14px;height:14px;border-radius:50%;
                                    background:transparent;border:2px solid rgba(255,255,255,0.3);
                                    transition:all 0.15s ease"></div>`).join('')}
                        </div>

                        <!-- Erro -->
                        <div id="pin-error" style="display:none;text-align:center;color:#fca5a5;
                            font-size:.8rem;margin-bottom:16px">PIN incorreto. Tenta novamente.</div>

                        <!-- Teclado -->
                        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                            ${[1,2,3,4,5,6,7,8,9,'',0,'⌫'].map(n => `
                                <button onclick="LoginPage._press('${n}')"
                                    style="aspect-ratio:1;border-radius:50%;border:none;font-size:1.4rem;font-weight:500;
                                        cursor:${n==='' ? 'default' : 'pointer'};
                                        background:${n==='' ? 'transparent' : 'rgba(255,255,255,0.12)'};
                                        color:${n==='' ? 'transparent' : 'white'};
                                        transition:background .15s;
                                        ${n==='' ? 'pointer-events:none' : ''}
                                        padding:0;width:100%"
                                    onmousedown="this.style.background='${n==='' ? 'transparent' : 'rgba(255,255,255,0.25)'}'"
                                    onmouseup="this.style.background='${n==='' ? 'transparent' : 'rgba(255,255,255,0.12)'}'">
                                    ${n}
                                </button>`).join('')}
                        </div>
                    </div>

                    <p style="text-align:center;color:rgba(255,255,255,0.25);font-size:.7rem;margin-top:20px">© 2026 fferr</p>
                </div>
            </div>
        `;
        this._pin = '';
        this._erro = false;
    },

    _press(val) {
        if (val === '') return;
        const errEl = document.getElementById('pin-error');

        if (val === '⌫') {
            this._pin = this._pin.slice(0, -1);
            this._erro = false;
            if (errEl) errEl.style.display = 'none';
        } else if (this._pin.length < 4) {
            this._pin += val;
        }

        this._updateDots();

        if (this._pin.length === 4) {
            setTimeout(() => this._submit(), 150);
        }
    },

    _updateDots() {
        for (let i = 0; i < 4; i++) {
            const dot = document.getElementById(`dot-${i}`);
            if (!dot) continue;
            if (this._erro) {
                dot.style.background = '#EF4444';
                dot.style.borderColor = '#EF4444';
            } else if (i < this._pin.length) {
                dot.style.background = '#fff';
                dot.style.borderColor = '#fff';
            } else {
                dot.style.background = 'transparent';
                dot.style.borderColor = 'rgba(255,255,255,0.3)';
            }
        }
    },

    async _submit() {
        const errEl = document.getElementById('pin-error');
        try {
            await API.login(this._pin);
            App.initUI();
            Router.go('home');
        } catch(e) {
            this._erro = true;
            this._updateDots();
            if (errEl) errEl.style.display = 'block';
            setTimeout(() => {
                this._pin = '';
                this._erro = false;
                this._updateDots();
                if (errEl) errEl.style.display = 'none';
            }, 800);
        }
    }
};
