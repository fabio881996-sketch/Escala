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

# 2. CSS - AJUSTE FINAL DE TONS (BLOCOS CINZA CLARO)
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Branco Puro */
    .stApp { 
        background-color: #FFFFFF !important; 
    }
    
    /* BLOCOS (EXPANDERS) - O CINZA CLARO QUE PEDISTE */
    .st-expander {
        background-color: #F8F9FA !important; /* Cinza muito claro e limpo */
        border: 1px solid #E9ECEF !important;
        border-radius: 10px !important;
        box-shadow: none !important;
        margin-bottom: 10px !important;
    }
    
    /* CABEÇALHO DO BLOCO - Mantém o tom cinza claro mas com texto bem visível */
    .streamlit-expanderHeader {
        background-color: #F8F9FA !important;
        color: #212529 !important; /* Texto quase preto para contraste */
        font-weight: 600 !important;
        border-radius: 10px !important;
    }

    /* BARRA LATERAL (INTOCADA) */
    [data-testid="stSidebar"] { 
        background-color: #455A64 !important; 
    }
    .profile-card { 
        background: #37474F; 
        padding: 20px; 
        border-radius: 12px; 
        margin-bottom: 25px; 
        text-align: center; 
    }

    /* LOGIN (INTOCADO) */
    div[data-testid="stForm"] { 
        background-color: #455A64; 
        border-radius: 15px; 
        padding: 30px; 
    }
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label, div[data-testid="stForm"] p { 
        color: white !important; 
    }

    /* CARD DE SERVIÇO (Minha Escala) - Branco para contrastar com o fundo */
    .status-card { 
        background: #F8F9FA; 
        padding: 25px; 
        border-radius: 15px; 
        border-left: 6px solid #455A64; 
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções de Dados
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

# 4. Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
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
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div><h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #B0BEC5; font-size: 0.8rem; margin:0;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        if st.button("🚪 Terminar Sessão"):
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
                st.markdown(f"""<div class="status-card"><h1>{meu_df.iloc[0]['serviço']}</h1><p>🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p></div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Escolher dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            def filtrar_e_mostrar(titulo, keywords):
                padrao = '|'.join(keywords).lower()
                temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        st.dataframe(temp_df[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Folga", ["folga"])

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
