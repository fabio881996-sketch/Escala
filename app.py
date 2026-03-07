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

# 2. CSS - ALTERAÇÃO DIRETA: TEXTO DOS SUBTÍTULOS PARA BRANCO
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; }
    div[data-testid="stForm"] * { color: white !important; }

    /* --- ALTERAÇÃO SOLICITADA --- */
    /* Garante que o texto do expander e qualquer parágrafo dentro do cabeçalho seja BRANCO */
    .streamlit-expanderHeader, 
    .streamlit-expanderHeader p, 
    .streamlit-expanderHeader span,
    .streamlit-expanderHeader div {
        color: #FFFFFF !important;
    }
    
    .streamlit-expanderHeader {
        background-color: #455A64 !important;
        border-radius: 10px !important;
    }

    .st-expander {
        border: 1px solid #455A64 !important;
        border-radius: 10px !important;
        margin-bottom: 15px !important;
    }
    /* ---------------------------- */

    h1, h2, h3, p { color: #1A1C1E !important; }
    
    .stButton>button { background-color: #FFFFFF !important; color: #1A1C1E !important; border: 1px solid #D1D1D1 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. Função de Carregamento
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        csv_url = f"{url.split('/edit')[0]}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns: df[col] = df[col].astype(str).str.strip().replace("nan", "")
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
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
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
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
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
                st.markdown(f"""<div style="background: #FFFFFF; padding: 25px; border-radius: 12px; border-left: 5px solid #455A64; border: 1px solid #EAECEF;">
                    <h1 style="margin:0;">{meu_df.iloc[0]['serviço']}</h1>
                    <p>🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            df_restante = df_dia.copy()
            def filtrar_e_mostrar(titulo, keywords):
                nonlocal df_restante
                padrao = '|'.join(keywords).lower()
                temp_df = df_restante[df_restante['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente"])

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
