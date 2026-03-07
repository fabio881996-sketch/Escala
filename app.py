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

# 2. CSS - REMOÇÃO DOS TONS ESCUROS NOS BLOCOS
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Gelo */
    .stApp { background-color: #F0F2F5; }
    
    /* BLOCOS (EXPANDERS) - TOTALMENTE CLAROS */
    .st-expander {
        background-color: #FFFFFF !important;
        border: 1px solid #E1E4E8 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
    }
    
    /* CABEÇALHO DO BLOCO (Onde se clica) - FORÇAR BRANCO */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        color: #1A1C1E !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
    }

    /* INTERIOR DO BLOCO (Onde estão os nomes) - FORÇAR BRANCO */
    [data-testid="stExpanderDetails"] {
        background-color: #FFFFFF !important;
        padding: 15px !important;
        border-radius: 0 0 12px 12px !important;
    }

    /* TEXTO GERAL */
    h1, h2, h3, p, span, label { color: #1A1C1E !important; }
    
    /* SIDEBAR (Mantida Original Dark) */
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* LOGIN (Mantido Original Dark) */
    div[data-testid="stForm"] {
        background-color: #455A64;
        border-radius: 15px;
        padding: 40px;
    }
    div[data-testid="stForm"] * { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. Função de Carregamento
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
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ENTRAR NO PORTAL", use_container_width=True):
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
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px;">👮‍♂️</div><h2 style="margin:0; font-size: 1.1rem;">{st.session_state['user_nome_completo']}</h2><p>ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        if st.button("🚪 Terminar Sessão"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "🔍 Consulta Geral":
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
                    # Agora estes blocos estão 100% claros (Branco Puro)
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente", "diligência"])
            filtrar_e_mostrar("Outros Serviços", [""])
        else: st.error("Escala não disponível.")

    elif menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        # (Lógica da escala individual...)

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
