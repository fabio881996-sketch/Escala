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

# 2. CSS - DESIGN FINAL COM SUBTÍTULOS FORÇADOS A BRANCO
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA */
    .stApp { background-color: #FFFFFF !important; }
    
    /* BARRA LATERAL */
    [data-testid="stSidebar"] { 
        background-color: #455A64 !important; 
        border-right: 1px solid #37474F; 
    }
    .profile-card { 
        background: #37474F; padding: 20px; border-radius: 12px; margin-bottom: 25px; text-align: center; 
    }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* --- OS SUBTÍTULOS EM BRANCO (SOLUÇÃO DEFINITIVA) --- */
    /* Este seletor ataca diretamente o texto dentro do cabeçalho do expander */
    div[data-testid="stExpander"] summary p {
        color: white !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
    }

    /* Fundo do cabeçalho para o branco se ler */
    div[data-testid="stExpander"] summary {
        background-color: #455A64 !important;
        border-radius: 8px !important;
        padding: 5px 10px !important;
    }

    /* Ícone da seta em branco */
    div[data-testid="stExpander"] summary svg {
        fill: white !important;
    }

    /* Estilo do bloco */
    .st-expander {
        border: none !important;
        background-color: transparent !important;
    }
    /* -------------------------------------------------- */

    /* TÍTULOS PRINCIPAIS EM PRETO */
    h1, h2, h3 { color: #1A1C1E !important; }
    
    /* TABELAS */
    [data-testid="stDataFrame"] table thead th { background-color: #F8FAFC !important; color: #1A1C1E !important; }
    [data-testid="stDataFrame"] table tbody td { background-color: #FFFFFF !important; color: #333639 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. Função de Carregamento
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        csv_url = f"{url.split('/edit')[0]}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except: return None

# 4. Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
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
                        st.session_state["user_nome_completo"] = f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}".strip()
                        st.session_state["user_id"] = user.iloc[0]['id']
                        st.rerun()

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><h2 style="color: white !important;">{st.session_state['user_nome_completo']}</h2></div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral"])
        if st.button("🚪 Sair"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""<div style="background:#FFF; padding:20px; border-radius:10px; border-left:6px solid #455A64; border:1px solid #EEE;">
                    <h1 style="margin:0;">{meu_df.iloc[0]['serviço']}</h1>
                </div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
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
                    # TITULOS QUE QUERES A BRANCO:
                    with st.expander(f"{titulo.upper()}", expanded=True):
                        st.dataframe(temp_df[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "grat"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente"])

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
