/* login.js — Teclado PIN estilo GNR */

const LoginPage = {
    render() {
        const appEl = document.getElementById('app');
        appEl.innerHTML = `
            <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;
                background:linear-gradient(160deg,#0F1F38 0%,#1A2B4A 50%,#1E3A8A 100%);padding:24px">
                <div style="width:100%;max-width:340px">

                    <div style="text-align:center;margin-bottom:36px">
                        <div style="font-size:56px;margin-bottom:12px;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.4))">🛡️</div>
                        <div style="font-size:22px;font-weight:700;color:white;letter-spacing:-0.02em">Portal de Escalas</div>
                        <div style="font-size:12px;color:rgba(255,255,255,0.5);margin-top:6px;letter-spacing:0.08em;text-transform:uppercase">Posto Territorial de Vila Nova de Famalicão</div>
                    </div>

                    <div style="background:rgba(255,255,255,0.07);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.12);
                        border-radius:24px;padding:28px 24px 24px">

                        <div id="pin-dots" style="display:flex;gap:20px;justify-content:center;margin-bottom:28px">
                            ${[0,1,2,3].map(i => `<div class="pdot" data-i="${i}" style="width:16px;height:16px;border-radius:50%;
                                border:2px solid rgba(255,255,255,0.3);background:transparent;transition:all 0.2s"></div>`).join('')}
                        </div>

                        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
                            ${[1,2,3,4,5,6,7,8,9].map(n => `
                            <button onclick="LoginPage.press('${n}')"
                                style="height:68px;width:68px;margin:0 auto;display:flex;align-items:center;justify-content:center;
                                font-size:24px;font-weight:400;color:white;
                                border:1.5px solid rgba(255,255,255,0.2);border-radius:50%;
                                background:rgba(255,255,255,0.08);cursor:pointer;
                                transition:all 0.15s;-webkit-tap-highlight-color:transparent"
                                onmousedown="this.style.background='rgba(255,255,255,0.2)'"
                                onmouseup="this.style.background='rgba(255,255,255,0.08)'"
                                ontouchstart="this.style.background='rgba(255,255,255,0.2)'"
                                ontouchend="this.style.background='rgba(255,255,255,0.08)'">${n}</button>`).join('')}
                            <div></div>
                            <button onclick="LoginPage.press('0')"
                                style="height:68px;width:68px;margin:0 auto;display:flex;align-items:center;justify-content:center;
                                font-size:24px;font-weight:400;color:white;
                                border:1.5px solid rgba(255,255,255,0.2);border-radius:50%;
                                background:rgba(255,255,255,0.08);cursor:pointer;
                                transition:all 0.15s;-webkit-tap-highlight-color:transparent"
                                onmousedown="this.style.background='rgba(255,255,255,0.2)'"
                                onmouseup="this.style.background='rgba(255,255,255,0.08)'"
                                ontouchstart="this.style.background='rgba(255,255,255,0.2)'"
                                ontouchend="this.style.background='rgba(255,255,255,0.08)'">0</button>
                            <button onclick="LoginPage.del()"
                                style="height:68px;width:68px;margin:0 auto;display:flex;align-items:center;justify-content:center;
                                font-size:20px;color:rgba(255,255,255,0.6);
                                border:none;border-radius:50%;background:none;cursor:pointer;
                                -webkit-tap-highlight-color:transparent">⌫</button>
                        </div>

                        <div id="pin-msg" style="text-align:center;font-size:13px;min-height:20px;margin-top:16px;color:#F87171"></div>
                    </div>
                </div>
            </div>`;

        LoginPage._pin = '';
    },

    _pin: '',
    _MAX: 4,

    updateDots() {
        document.querySelectorAll('.pdot').forEach((d, i) => {
            if (i < this._pin.length) {
                d.style.background = 'white';
                d.style.borderColor = 'white';
                d.style.transform = 'scale(1.2)';
            } else {
                d.style.background = 'transparent';
                d.style.borderColor = 'rgba(255,255,255,0.3)';
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
            d.style.background = '#F87171';
            d.style.borderColor = '#F87171';
        });
        setTimeout(() => {
            this._pin = '';
            this.updateDots();
        }, 500);
    },

    async submit() {
        const msg = document.getElementById('pin-msg');
        msg.style.color = 'rgba(255,255,255,0.5)';
        msg.textContent = 'A verificar...';

        try {
            await API.login(this._pin, this._pin);
            App.initUI();
            Router.go('home');
        } catch (e) {
            msg.style.color = '#F87171';
            msg.textContent = 'PIN incorreto';
            this.shake();
        }
    }
};
