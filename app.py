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

# 2. CSS - ESTÉTICA CLEAN ABSOLUTA (BRANCO E AZUL)
st.markdown("""
    <style>
    /* FUNDO TOTALMENTE BRANCO E LIMPO */
    .stApp { 
        background-color: #FFFFFF !important; 
    }
    
    /* LATERAL (INTOCADA - ESTILO DARK) */
    [data-testid="stSidebar"] { 
        background-color: #455A64 !important; 
        border-right: none !important;
    }
    .profile-card { 
        background: #37474F; 
        padding: 20px; 
        border-radius: 12px; 
        margin-bottom: 25px; 
        text-align: center; 
    }

    /* LOGIN (INTOCADO - ESTILO DARK) */
    div[data-testid="stForm"] { 
        background-color: #455A64; 
        border-radius: 15px; 
        padding: 30px;
    }
    div[data-testid="stForm"] * { color: white !important; }

    /* BLOCOS DE SERVIÇO (EXPANDERS) - O QUE PRECISAVA MUDAR */
    /* Removemos a caixa, a borda e a sombra. Fica só o título e o conteúdo. */
    .st-expander {
        border: none !important;
        background-color: transparent !important;
        box-shadow: none !important;
        margin-bottom: 5px !important;
    }
    
    /* Estilo do cabeçalho do bloco - Texto Azul GNR nítido sobre fundo branco */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        color: #1A3A5A !important;
        font-size: 1.1rem !important;
        border-bottom: 1px solid #E0E4E8 !important; /* Linha fininha para separar */
        padding: 10px 0px !important;
    }

    /* TABELAS - DESIGN MINIMALISTA */
    .stDataFrame {
        border: none !important;
        margin-top: 10px;
    }
    
    /* FORÇAR TEXTOS ESCUROS NA PÁGINA BRANCA */
    h1, h2, h3, [data-testid="stMarkdownContainer"] p {
        color: #1A1C1E !important;
    }

    /* Esconder elementos desnecessários do Streamlit para ficar mais clean */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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

# 4. Login (Protegido - Estilo Sidebar)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Posto Territorial de Famalicão</p>", unsafe_allow_html=True)
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
                    else: st.error("❌ Credenciais incorretas.")

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div><p style="color: #B0BEC5; font-size: 0.7rem; margin:0; font-weight: bold; text-transform: uppercase;">Militar Ativo</p><h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #B0BEC5; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
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
                st.markdown(f"""<div style="padding: 20px; border-left: 5px solid #455A64; background: #F8F9FA;">
                    <h1 style="margin:0;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="font-size: 1.2rem;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>""", unsafe_allow_html=True)
            else: st.warning("⚠️ Sem serviço.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Escolher dia:", format="DD/MM/YYYY", key="geral")
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
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "grat"], excluir=False)
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Ausentes", ["férias", "doente", "licença"])

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email', 'password']], use_container_width=True, hide_index=True)

    elif menu == "🔄 Solicitar Troca":
        pass

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
