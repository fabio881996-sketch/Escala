/* login.js — Teclado PIN estilo iPhone */

const LoginPage = {
    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;
                background:linear-gradient(160deg,#1A2B4A 0%,#243B5C 60%,#1E3A8A 100%);padding:24px">
                <div style="width:100%;max-width:320px;background:white;border-radius:24px;
                    padding:32px 24px 24px;box-shadow:0 24px 64px rgba(0,0,0,0.4)">

                    <div style="text-align:center;margin-bottom:32px">
                        <div style="font-size:48px;margin-bottom:8px">🛡️</div>
                        <div style="font-size:18px;font-weight:700;color:#1A2B4A">Portal de Escalas</div>
                        <div style="font-size:13px;color:#64748B;margin-top:4px">Insere o teu PIN</div>
                    </div>

                    <div id="pin-dots" style="display:flex;gap:16px;justify-content:center;margin-bottom:32px">
                        ${[0,1,2,3].map(i => `<div class="pdot" data-i="${i}" style="width:18px;height:18px;border-radius:50%;border:2px solid #CBD5E1;background:white;transition:all 0.15s"></div>`).join('')}
                    </div>

                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                        ${[1,2,3,4,5,6,7,8,9].map(n => `
                        <button onclick="LoginPage.press('${n}')" style="height:64px;font-size:22px;font-weight:400;
                            border:1px solid #E2E8F0;border-radius:50%;background:white;color:#1E293B;cursor:pointer">${n}</button>`).join('')}
                        <div></div>
                        <button onclick="LoginPage.press('0')" style="height:64px;font-size:22px;font-weight:400;
                            border:1px solid #E2E8F0;border-radius:50%;background:white;color:#1E293B;cursor:pointer">0</button>
                        <button onclick="LoginPage.del()" style="height:64px;font-size:22px;
                            border:none;border-radius:50%;background:none;color:#64748B;cursor:pointer">⌫</button>
                    </div>

                    <div id="pin-msg" style="text-align:center;font-size:13px;min-height:20px;margin-top:16px;color:#DC2626"></div>
                </div>
            </div>`;

        LoginPage._pin = '';
    },

    _pin: '',
    _MAX: 4,

    updateDots() {
        document.querySelectorAll('.pdot').forEach((d, i) => {
            if (i < this._pin.length) {
                d.style.background = '#1A2B4A';
                d.style.borderColor = '#1A2B4A';
                d.style.transform = 'scale(1.15)';
            } else {
                d.style.background = 'white';
                d.style.borderColor = '#CBD5E1';
                d.style.transform = 'scale(1)';
            }
        });
    },

    press(n) {
        if (this._pin.length >= this._MAX) return;
        this._pin += n;
        this.updateDots();
        if (this._pin.length === this._MAX) setTimeout(() => this.submit(), 200);
    },

    del() {
        this._pin = this._pin.slice(0, -1);
        this.updateDots();
        document.getElementById('pin-msg').textContent = '';
    },

    shake() {
        document.querySelectorAll('.pdot').forEach(d => {
            d.style.background = '#DC2626';
            d.style.borderColor = '#DC2626';
        });
        setTimeout(() => {
            this._pin = '';
            this.updateDots();
        }, 500);
    },

    async submit() {
        const msg = document.getElementById('pin-msg');
        msg.style.color = '#64748B';
        msg.textContent = 'A verificar...';

        try {
            await API.login(this._pin, this._pin);
            App.initUI();
            Router.go('home');
        } catch (e) {
            msg.style.color = '#DC2626';
            msg.textContent = 'PIN incorreto';
            this.shake();
        }
    }
};
