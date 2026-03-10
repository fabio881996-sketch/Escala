import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    h1, h2, h3 { color: #1E3A8A !important; font-weight: 800 !important; }
    .stButton > button { background-color: #FFFFFF !important; color: #000000 !important; border: 2px solid #000000 !important; font-weight: bold !important; }
    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]

# --- 2. FUNÇÕES DE DADOS (CACHE) ---
@st.cache_data(ttl=300)
def load_data(aba_nome):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["gsheet_url"])
        data = sh.worksheet(aba_nome).get_all_records()
        df = pd.DataFrame(data)
        # NORMALIZAÇÃO: Garante que as colunas são minúsculas e sem espaços
        df.columns = df.columns.str.strip().str.lower()
        return df.fillna("")
    except Exception as e:
        st.error(f"Erro ao carregar {aba_nome}: {e}")
        return pd.DataFrame()

def atualizar_status_gsheet(index_linha, novo_status, admin_nome=""):
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"])
    client = gspread.authorize(creds)
    sh = client.open_by_url(st.secrets["gsheet_url"])
    aba = sh.worksheet("registos_trocas")
    aba.update_cell(index_linha + 2, 6, novo_status)
    if admin_nome:
        aba.update_cell(index_linha + 2, 8, admin_nome)
        aba.update_cell(index_linha + 2, 9, datetime.now().strftime("%d/%m/%Y %H:%M"))
    st.cache_data.clear()

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("🚓 Portal de Escalas")
    u = st.text_input("Email").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("ENTRAR"):
        df_u = load_data("utilizadores")
        # Conversão explícita para string evita erros de comparação
        user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'].astype(str) == p)]
        if not user.empty:
            st.session_state.update({
                "logged_in": True, 
                "user_id": str(user.iloc[0]['id']), 
                "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}", 
                "is_admin": u in ADMINS
            })
            st.rerun()
        else: st.error("Email ou password incorretos.")
else:
    # --- 4. INTERFACE ---
    df_trocas = load_data("registos_trocas")
    
    with st.sidebar:
        st.write(f"👮‍♂️ {st.session_state['user_nome']}")
        menu = st.radio("MENU", ["🔍 Escala Geral", "⚖️ Validar Trocas"])
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    if menu == "🔍 Escala Geral":
        d_sel = st.date_input("Data:")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            st.dataframe(df_dia[['id', 'serviço', 'horário']], use_container_width=True)

    elif menu == "⚖️ Validar Trocas":
        pnd = df_trocas[df_trocas['status'] == 'Pendente_Admin']
        for idx, r in pnd.iterrows():
            if st.button(f"Validar: {r['id_origem']} ↔️ {r['id_destino']}", key=idx):
                atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome'])
                st.rerun()
                
