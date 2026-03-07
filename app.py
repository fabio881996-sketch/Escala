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

# 2. CSS - FOCO NOS BLOCOS DE SERVIÇO
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA */
    .stApp { background-color: #ECEFF1; }
    
    /* LATERAL E LOGIN (INTOCADOS - CONFORME GOSTAS) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 25px; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 20px; }
    div[data-testid="stForm"] * { color: white !important; }

    /* BLOCOS DE SERVIÇO (EXPANDERS) - MAIS CLAROS E LUMINOSOS */
    .st-expander {
        background-color: #FFFFFF !important; /* Bloco Branco */
        border: 1px solid #D1D9E0 !important;
        border-radius: 10px !important;
        margin-bottom: 10px !important;
    }
    
    /* INTERIOR DO BLOCO (Onde estão os nomes) - FORÇAR BRANCO */
    [data-testid="stExpanderDetails"] {
        background-color: #FFFFFF !important;
        padding: 15px !important;
        border-radius: 0 0 10px 10px !important;
    }

    .streamlit-expanderHeader {
        background-color: #F8F9FA !important; /* Cabeçalho cinza clarinho */
        color: #263238 !important;
        font-weight: bold !important;
    }

    /* TABELA DE PESSOAL MAIS CLARA */
    .stDataFrame {
        background-color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções de Carga (Inalteradas)
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except: return None

# 4. Login (Inalterado)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Escala de Serviço</h1>", unsafe_allow_html=True)
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
        st.markdown(f"""<div class="profile-card">
            <div style="font-size: 35px;">👮‍♂️</div>
            <h2 style="color: white !important;">{st.session_state['user_nome_completo']}</h2>
            <p style="color: #B0BEC5;">ID: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        if st.button("🚪 Sair"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Escolher dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            def filtrar_e_mostrar(titulo, keywords):
                padrao = '|'.join(keywords).lower()
                temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        # AQUI É ONDE O PESSOAL APARECE - AGORA EM FUNDO BRANCO CLARO
                        st.dataframe(temp_df[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Folga", ["folga"])
        else: st.info("Escala não disponível.")
    
    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
