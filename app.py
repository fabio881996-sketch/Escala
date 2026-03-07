import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração de Página
st.set_page_config(
    page_title="GNR - Portal de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS - FOCO NOS TÍTULOS PRINCIPAIS EM PRETO
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA */
    .stApp { background-color: #F0F2F5; }
    
    /* --- A ALTERAÇÃO: TÍTULOS PRINCIPAIS (H1) EM PRETO --- */
    h1 {
        color: #000000 !important;
        font-weight: 800 !important;
    }

    /* BLOCOS DE SERVIÇO (Expanders) - Mantidos Claros */
    .st-expander {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D9E0 !important;
        border-radius: 10px !important;
    }
    .streamlit-expanderHeader {
        color: #1A1C1E !important;
        font-weight: bold !important;
    }

    /* SIDEBAR E LOGIN (Mantidos Dark) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; }
    div[data-testid="stForm"] * { color: white !important; }

    /* TEXTO GERAL */
    h2, h3, p, label { color: #1A1C1E !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        csv_url = f"{url.split('/edit')[0]}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except: return None

# 4. Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white !important;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'] == str(pass_i))]
                    if not user.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user.iloc[0]['id']
                        st.session_state["user_nome_completo"] = f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}".strip()
                        st.rerun()

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><h2 style="color: white !important;">{st.session_state['user_nome_completo']}</h2><p>ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral"])
        if st.button("🚪 Sair"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço") # Este título agora é PRETO
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""<div style="background:#FFFFFF; padding:20px; border-radius:10px; border-left:6px solid #455A64;">
                    <h1 style="color:#000000 !important;">{meu_df.iloc[0]['serviço']}</h1>
                    <p>Horário: {meu_df.iloc[0]['horário']}</p>
                </div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral") # Este título agora é PRETO
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            df_restante = df_dia.copy()
            def filtrar_e_mostrar(titulo, keywords):
                nonlocal df_restante
                padrao = '|'.join(keywords).lower()
                temp_df = df_restante[df_restante['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo.upper()}", expanded=True):
                        st.dataframe(temp_df[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "vtr"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente"])

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
