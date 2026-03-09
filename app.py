import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO (CORREÇÃO DO BOTÃO SAIR) ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    h1, h2, h3 { color: #1E3A8A !important; }
    /* Garantir que o botão Sair seja visível (Fundo branco, texto preto) */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }
    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def load_data(aba_nome):
    try:
        client = get_client()
        if client:
            sh = client.open_by_url(st.secrets["gsheet_url"])
            df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df.fillna("")
        return pd.DataFrame()
    except: return pd.DataFrame()

def atualizar_status_gsheet(index_linha, novo_status):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status)
        return True
    except: return False

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # (Bloco de login omitido para brevidade, mantém-se igual)
    st.markdown("<h1 style='text-align:center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRAR"):
            df_u = load_data("utilizadores")
            user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
            if not user.empty:
                st.session_state.update({
                    "logged_in": True, "user_id": str(user.iloc[0]['id']), 
                    "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                    "user_email": u, "is_admin": u in ADMINS
                })
                st.rerun()
else:
    df_trocas = load_data("registos_trocas")
    
    # 3. RESTRICÇÃO DE MENU: Só Admins vêem "Validar Trocas"
    menu_options = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state["is_admin"]:
        menu_options.append("⚖️ Validar Trocas")
    menu_options.append("👥 Efetivo")

    with st.sidebar:
        st.write(f"👮‍♂️ {st.session_state['user_nome']}")
        menu = st.radio("MENU", menu_options)
        if st.button("Sair"): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 4. MINHA ESCALA (DETALHE DA TROCA CORRIGIDO) ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            
            # Procurar se este utilizador tem uma troca aprovada para este dia
            troca_v = pd.DataFrame()
            if not df_trocas.empty and 'status' in df_trocas.columns:
                # Caso o utilizador seja a Origem ou o Destino da troca
                troca_v = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['status'] == 'Aprovada') & 
                                   ((df_trocas['id_origem'].astype(str) == st.session_state['user_id']) | 
                                    (df_trocas['id_destino'].astype(str) == st.session_state['user_id']))]
            
            if not troca_v.empty:
                t = troca_v.iloc[0]
                # Lógica para mostrar o que vai fazer e com quem trocou
                if str(t['id_origem']) == st.session_state['user_id']:
                    faz = t['servico_destino']
                    era = t['servico_origem']
                    com = t['id_destino']
                else:
                    faz = t['servico_origem']
                    era = t['servico_destino']
                    com = t['id_origem']
                
                st.markdown(f"""
                <div class="card-servico card-troca">
                    <b>{label}</b><br>
                    <h3>FAZ: {faz}</h3>
                    <p style="margin:0;">🔙 Troca de: {era}</p>
                    <p style="margin:0; font-weight: bold;">🔄 Trocado com ID: {com}</p>
                </div>""", unsafe_allow_html=True)
            else:
                # Serviço normal
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
                    if not meu.empty:
                        st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    # --- RESTANTE DO CÓDIGO (Escala Geral, Pedidos, etc.) ---
    elif menu == "🔍 Escala Geral":
        # (Mantém a lógica da escala geral que já tinhas)
        st.title("🔍 Escala Geral")
        # ...
