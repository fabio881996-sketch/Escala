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

# 2. CSS - DESIGN HIGH-CONTRAST & ULTRA CLEAN (ÁREA DE TRABALHO)
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Branco Puro para máximo aspeto clean */
    .stApp { 
        background-color: #FFFFFF !important; 
    }
    
    /* BARRA LATERAL (Protegida - Não mexer) */
    [data-testid="stSidebar"] { 
        background-color: #455A64 !important; 
        border-right: 1px solid #37474F; 
    }
    .profile-card { 
        background: #37474F; 
        padding: 20px; 
        border-radius: 12px; 
        margin-bottom: 25px; 
        border: 1px solid rgba(255,255,255,0.1); 
        text-align: center; 
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, div[data-baseweb="radio"] div { 
        color: #FFFFFF !important; 
    }

    /* LOGIN (Protegido - Não mexer) */
    div[data-testid="stForm"] { 
        background-color: #455A64; 
        border-radius: 15px; 
        padding: 30px;
        color: white;
    }
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label, div[data-testid="stForm"] p { 
        color: white !important; 
    }

    /* BLOCOS DE SERVIÇO (Expanders) - DESIGN ULTRA CLEAN E CLARO */
    .st-expander {
        border: 1px solid #EAECEF !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        background-color: #FFFFFF !important;
        margin-bottom: 15px !important;
    }
    
    /* Título dos Blocos - Texto escuro e nítido */
    .streamlit-expanderHeader {
        color: #1A1C1E !important;
        font-weight: bold !important;
        background-color: #FFFFFF !important;
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }

    /* TABELAS - DESIGN CLEAN, CLARO E LEVÍSSIMO */
    .stDataFrame {
        background-color: #FFFFFF !important;
        border: 1px solid #EAECEF !important;
        border-radius: 8px !important;
    }
    
    /* Cabeçalho da Tabela - Fundo cinza ultra-claro para distinção leve */
    [data-testid="stDataFrame"] table thead th {
        background-color: #F8FAFC !important;
        color: #1A1C1E !important;
        font-weight: bold !important;
        border-bottom: 2px solid #EAECEF !important;
    }
    
    /* Linhas da Tabela - Fundo branco e linhas finas */
    [data-testid="stDataFrame"] table tbody td {
        background-color: #FFFFFF !important;
        color: #333639 !important;
        border-bottom: 1px solid #F1F3F5 !important;
    }
    
    /* TÍTULOS E TEXTOS DA PÁGINA - Texto escuro para contraste soberano */
    h1, h2, h3, p {
        color: #1A1C1E !important;
    }
    
    /* Botões na página principal */
    .stButton>button { 
        background-color: #FFFFFF !important; 
        color: #1A1C1E !important; 
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
    }
    .stButton>button:hover {
        background-color: #F8FAFC !important;
    }
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

# 4. Login (Protegido)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white !important;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
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
                else: st.error("⚠️ Erro de base de dados.")

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div><p style="color: #B0BEC5; font-size: 0.7rem; margin:0; font-weight: bold; text-transform: uppercase;">Militar Ativo</p><h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #B0BEC5; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        
        st.markdown("<br><br>", unsafe_allow_html=True)
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
                st.markdown(f"""<div style="background: #FFFFFF; padding: 25px; border-radius: 12px; border: 1px solid #EAECEF; border-left: 5px solid #455A64;">
                    <h1 style="margin:0; font-size: 2rem; color: #1A1C1E !important;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="color: #546E7A; font-size: 1.2rem; margin-top: 10px;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>""", unsafe_allow_html=True)
            else: st.warning("⚠️ Não consta serviço para este dia.")

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
            filtrar_e_mostrar("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando", "permanência"])
        else:
            st.error("Dia não disponível.")

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Lista de Efetivo")
        # ... Restante do código de efetivo mantido

    elif menu == "🔄 Solicitar Troca":
        # ... Restante do código de troca mantido
        pass

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
