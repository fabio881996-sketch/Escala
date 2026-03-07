import streamlit as st
import pandas as pd

# 1. Configuração de Página
st.set_page_config(page_title="GNR", layout="wide")

# 2. CSS - RIGOROSO E SEM "SUJIDADE"
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Claríssimo */
    .stApp { 
        background-color: #F0F2F6 !important; 
    }
    
    /* BLOCOS (Expanders) - Cinza muito claro, quase branco */
    .st-expander {
        background-color: #F8F9FA !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 8px !important;
    }
    
    /* INTERIOR DOS BLOCOS (Onde está o pessoal nomeado) */
    [data-testid="stExpanderDetails"] {
        background-color: #F8F9FA !important;
    }

    /* BARRA LATERAL (PROTEGIDA) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* LOGIN (PROTEGIDO) */
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 20px; }
    div[data-testid="stForm"] * { color: white !important; }

    /* TEXTO NA PÁGINA - Preto para ler bem */
    h1, h2, h3, p { color: #263238 !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções e App
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        csv_url = f"{url.split('/edit')[0]}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except: return None

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # LOGIN (IGUAL AO QUE ESTAVA)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("Email").lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR"):
                st.session_state["logged_in"] = True
                st.session_state["user_nome"] = "Militar" # Exemplo
                st.rerun()
else:
    # APP PRINCIPAL
    with st.sidebar:
        st.markdown(f'<div class="profile-card"><h2>{st.session_state.get("user_nome", "Militar")}</h2></div>', unsafe_allow_html=True)
        menu = st.radio("MENU", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo"])

    if menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data")
        df = load_sheet(data_sel.strftime("%d-%m"))
        if df is not None:
            with st.expander("🔹 PATRULHAS", expanded=True):
                # O interior deste bloco agora está no cinza claro que pediste
                st.dataframe(df, use_container_width=True, hide_index=True)
                
