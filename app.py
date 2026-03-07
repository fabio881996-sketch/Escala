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

# 2. CSS - O ESTILO QUE ESTÁ IMPECAVEL (ESTÁVEL)
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Claro Suave */
    .stApp { background-color: #F0F2F5 !important; }
    
    /* BLOCOS DE SERVIÇO - Cinza Muito Claro (Quase Branco) */
    .st-expander {
        background-color: #F8F9FA !important;
        border: 1px solid #D1D9E0 !important;
        border-radius: 8px !important;
    }
    
    /* BARRA LATERAL (ESTILO DARK) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { 
        background: #37474F; 
        padding: 20px; 
        border-radius: 12px; 
        text-align: center; 
        color: white; 
    }
    [data-testid="stSidebar"] * { color: white !important; }

    /* LOGIN (ESTILO DARK) */
    div[data-testid="stForm"] { 
        background-color: #455A64; 
        border-radius: 15px; 
        padding: 25px; 
    }
    div[data-testid="stForm"] * { color: white !important; }

    /* TEXTO DOS SERVIÇOS NOMEADOS - Preto Nítido */
    .streamlit-expanderHeader, h1, h2, p { 
        color: #263238 !important; 
        font-weight: bold !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções de Carga de Dados
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        # Limpeza básica de colunas
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except:
        return None

# Inicialização de Estado
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# 4. Interface de Login
def login_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Posto Territorial de Famalicão</p>", unsafe_allow_html=True)
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            
            if st.form_submit_button("ENTRAR NO PORTAL", use_container_width=True):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'] == str(pass_i))]
                    if not user.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user.iloc[0]['id']
                        st.session_state["user_nome"] = f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"
                        st.rerun()
                    else:
                        st.error("❌ Credenciais incorretas.")
                else:
                    st.error("⚠️ Erro ao ligar à base de dados.")

# 5. Interface Principal (Main App)
def main_app():
    # SIDEBAR
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-card">
                <div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div>
                <h2>{st.session_state.get('user_nome', 'Militar')}</h2>
                <p>ID: {st.session_state.get('user_id', '---')}</p>
            </div>
        """, unsafe_allow_html=True)
        
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Terminar Sessão", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # CONTEÚDO CENTRAL
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Escolher Data:", format="DD/MM/YYYY")
        # Aqui virá a lógica de mostrar o serviço individual

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        
        if df_dia is not None:
            with st.expander("🔹 PESSOAL EM SERVIÇO", expanded=True):
                st.dataframe(df_dia, use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ Escala de {nome_aba} ainda não disponível.")

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo do Posto")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        st.info("Módulo de trocas em desenvolvimento.")

# --- EXECUÇÃO ---
if not st.session_state["logged_in"]:
    login_page()
else:
    main_app()
    
