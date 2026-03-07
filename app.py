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

# 2. CSS CUSTOMIZADO - SIDEBAR CLARA E TEXTO ESCURO
st.markdown("""
    <style>
    /* Fundo Geral da App */
    .stApp { background-color: #FFFFFF; }
    
    /* BARRA LATERAL - FUNDO CLARO */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA !important;
        border-right: 1px solid #E0E0E0;
    }
    
    /* Card do Perfil na Sidebar - Branco com Sombra */
    .profile-card {
        background: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
    }
    
    /* Textos na Sidebar - AGORA ESCUROS */
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] .stMarkdown p {
        color: #2C3E50 !important;
    }
    
    /* Estilo das Opções do Menu (Radio) */
    div[data-testid="stSidebarUserContent"] .stRadio label {
        color: #444444 !important;
        background-color: transparent;
        padding: 10px 15px;
        border-radius: 8px;
        transition: all 0.2s;
        font-weight: 500;
        margin-bottom: 5px;
    }
    
    /* Hover nas opções do menu */
    div[data-testid="stSidebarUserContent"] .stRadio label:hover {
        background-color: #E9ECEF !important;
        color: #000000 !important;
    }
    
    /* Opção Selecionada (Destaque Azul Suave) */
    div[data-testid="stWidgetLabel"] p {
        color: #6C757D !important;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Botões na Sidebar */
    .stButton>button {
        background-color: #FFFFFF;
        color: #2C3E50;
        border: 1px solid #D1D1D1;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #F8F9FA;
        border-color: #2C3E50;
        color: #2C3E50;
    }
    
    /* Card de Serviço (Área Principal) */
    .status-card {
        background: #F8F9FA;
        padding: 25px;
        border-radius: 15px;
        border-left: 6px solid #1E88E5; /* Azul GNR */
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    h1 { color: #2C3E50; }
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

# 4. Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🚓 Sistema de Escalas</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
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
                    else:
                        st.error("❌ Credenciais incorretas.")
                else:
                    st.error("⚠️ Erro de base de dados.")

# 5. App
def main_app():
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-card">
                <div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div>
                <p style="color: #6C757D; font-size: 0.7rem; margin:0; font-weight: bold;">MILITAR AUTENTICADO</p>
                <h2 style="margin:0; font-size: 1.1rem;">{st.session_state['user_nome_completo']}</h2>
                <p style="color: #6C757D; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        menu = st.radio("MENU DE NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Solicitar Troca"])
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Terminar Sessão"):
            st.session_state["logged_in"] = False
            st.rerun()

    # --- MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Escolher data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""
                <div class="status-card">
                    <h1 style="margin:0; color: #1E88E5; font-size: 2.2rem;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="margin-top:10px; font-size: 1.3rem; color: #444444;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não consta serviço escalado para este dia.")
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            def mostrar_bloco(titulo, keywords):
                padrao = '|'.join(keywords).lower()
                temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
            
            mostrar_bloco("Operacional e Patrulhas", ["atendimento", "patrulha", "po", "ronda"])
            mostrar_bloco("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto"])
            mostrar_bloco("Inoperacionais", ["folga", "férias", "licença", "doente"])
        else:
            st.error("Dia não disponível.")

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        data_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)
        if df_dia_t is not None:
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                meu_s = meu_df.iloc[0]['serviço']
                indisp = ["folga", "férias", "doente", "licença"]
                df_colegas = df_dia_t[(df_dia_t['id'] != st.session_state['user_id']) & (~df_dia_t['serviço'].str.lower().str.contains('|'.join(indisp)))]
                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'] + " - " + df_colegas['serviço']
                    with st.form("form_troca"):
                        colega = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_input("Motivo da troca:")
                        if st.form_submit_button("GERAR MENSAGEM"):
                            id_c = colega.split(" - ")[0]
                            msg = f"*SOLICITAÇÃO DE TROCA ({nome_aba_t})*\n\n👉 *SAIR:* {st.session_state['user_nome_completo']} ({meu_s})\n👉 *ENTRAR:* ID {id_c}\n📝 *MOTIVO:* {motivo}"
                            st.code(msg, language="text")
            else:
                st.error("Não estás escalado neste dia.")

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
