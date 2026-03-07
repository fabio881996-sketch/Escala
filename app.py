import streamlit as st
import pandas as pd

# 1. Configuração de Página
st.set_page_config(page_title="GNR - Portal de Escalas", layout="wide")

# 2. CSS - APENAS O QUE PEDISTE (SEM CAGADAS)
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Claro (Clean) */
    .stApp { 
        background-color: #F0F2F5 !important; 
    }
    
    /* BLOCOS DE SERVIÇO - Cinza Muito Claro (Quase Branco) */
    .st-expander {
        background-color: #F8F9FA !important;
        border: 1px solid #D1D9E0 !important;
        border-radius: 8px !important;
    }
    
    /* BARRA LATERAL (ORIGINAL - NÃO MEXER) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; color: white; }
    [data-testid="stSidebar"] * { color: white !important; }

    /* LOGIN (ORIGINAL - NÃO MEXER) */
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 25px; }
    div[data-testid="stForm"] * { color: white !important; }

    /* TEXTO DOS BLOCOS E PÁGINA - Preto Nítido */
    .streamlit-expanderHeader, h1, h2, p { 
        color: #263238 !important; 
        font-weight: bold !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções (O Teu Código Original)
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        csv_url = f"{url.split('/edit')[0]}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except: return None

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

# 4. Interface
if not st.session_state["logged_in"]:
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("Email").lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR"):
                st.session_state["logged_in"] = True
                st.rerun()
else:
    with st.sidebar:
        st.markdown('<div class="profile-card"><h2>Menu Militar</h2></div>', unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo"])

    if menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data")
        df = load_sheet(data_sel.strftime("%d-%m"))
        if df is not None:
            # O Bloco que pediste para ficar mais claro
            with st.expander("🔹 SERVIÇOS NOMEADOS", expanded=True):
                st.dataframe(df, use_container_width=True, hide_index=True)
