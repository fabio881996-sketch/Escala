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

# 2. CSS - O TEU ESTILO DE VOLTA + PÁGINA CLEAN
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - O Cinza Claro que pediste */
    .stApp { background-color: #F1F3F4; }
    
    /* BARRA LATERAL - EXATAMENTE COMO ESTAVA ANTES */
    [data-testid="stSidebar"] { background-color: #455A64 !important; border-right: 1px solid #37474F; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stWidgetLabel"] p, div[data-baseweb="radio"] div, div[data-baseweb="radio"] span { color: #FFFFFF !important; font-weight: 500 !important; }
    
    /* LOGIN - REVERTIDO PARA O TEU ORIGINAL (Escuro/Sidebar style) */
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; }
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label, div[data-testid="stForm"] p { color: white !important; }

    /* BLOCOS (Expanders) - BRANCO PURO COM TEXTO PRETO (Contraste) */
    .st-expander {
        background-color: #FFFFFF !important;
        border: 1px solid #DCDFE3 !important;
        border-radius: 8px !important;
    }
    .streamlit-expanderHeader {
        color: #000000 !important; /* Texto Preto para ler bem */
        background-color: #FFFFFF !important;
        font-weight: bold !important;
    }
    
    /* CARD DE SERVIÇO (Minha Escala) */
    .status-card { background: #FFFFFF; padding: 25px; border-radius: 15px; border-top: 6px solid #455A64; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    
    .stButton>button { background-color: #37474F; color: #FFFFFF; border: 1px solid #546E7A; }
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
    except:
        return None

# 4. Login (O teu original)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Escala de Serviço - Posto Famalicão</h1>", unsafe_allow_html=True)
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
                    else: st.error("❌ Credenciais incorretas.")

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div><p style="color: #B0BEC5; font-size: 0.7rem; margin:0; font-weight: bold; text-transform: uppercase;">Militar Ativo</p><h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #B0BEC5; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
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
                st.markdown(f"""<div class="status-card"><h1 style="margin:0; color: #455A64; font-size: 2.2rem;">{meu_df.iloc[0]['serviço']}</h1><p style="margin-top:10px; font-size: 1.3rem; color: #546E7A;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p></div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            df_restante = df_dia.copy()
            def filtrar_e_mostrar(titulo, keywords, excluir=True):
                nonlocal df_restante
                padrao = '|'.join(keywords).lower()
                df_busca = df_dia if not excluir else df_restante
                temp_df = df_busca[df_busca['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    if excluir:
                        df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Apoio ao Atendimento", ["apoio"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "renu", "grat", "extra"], excluir=False)
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente", "diligência", "falta"])
            filtrar_e_mostrar("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando"])

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email', 'password']], use_container_width=True, hide_index=True)

    elif menu == "🔄 Solicitar Troca":
        # ... Mantém-se igual
        pass

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
