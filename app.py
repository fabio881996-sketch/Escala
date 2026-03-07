import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração de Página
st.set_page_config(
    page_title="GNR - Escalas de Serviço",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS - REFINAMENTO DE CORES
st.markdown("""
    <style>
    /* Fundo da aplicação */
    .stApp { background-color: #F4F6F7; }
    
    /* BARRA LATERAL - AZUL NAVY PROFISSIONAL */
    [data-testid="stSidebar"] {
        background-color: #1B2631 !important;
        border-right: 2px solid #2C3E50;
    }
    
    /* Card do Perfil */
    .profile-card {
        background: #2C3E50;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        border: 1px solid #34495E;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* Títulos na Sidebar */
    [data-testid="stSidebar"] h2 {
        color: #FFFFFF !important;
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        margin-bottom: 0px !important;
    }
    
    /* Ajuste do Radio Menu */
    div[data-testid="stSidebarUserContent"] .stRadio label {
        color: #D5DBDB !important;
        background-color: transparent;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 4px;
        transition: 0.2s ease;
    }
    
    div[data-testid="stSidebarUserContent"] .stRadio label:hover {
        background-color: #2E4053 !important;
        color: #FFFFFF !important;
    }

    /* Estilo dos Botões (Sair e Login) */
    .stButton>button {
        background-color: #2C3E50;
        color: white;
        border: 1px solid #566573;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1B2631;
        border-color: #FFFFFF;
        color: white;
    }
    
    /* Card de Serviço (Main) */
    .status-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        border-top: 5px solid #27AE60; /* Verde Esmeralda */
    }
    
    h1, h3 { color: #1B2631; }
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
                <p style="color: #ABB2B9; font-size: 0.8rem; margin:0;">MILITAR ATIVO</p>
                <h2>{st.session_state['user_nome_completo']}</h2>
                <p style="color: #85929E; font-size: 0.85rem; margin-top:5px;">ID: {st.session_state['user_id']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        menu = st.radio("CONSULTAS", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Solicitar Troca"])
        
        st.divider()
        if st.button("🚪 Terminar Sessão", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Data da escala:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""
                <div class="status-card">
                    <p style="color: #27AE60; font-weight: bold; margin-bottom: 5px;">CONFIRMADO</p>
                    <h1 style="margin:0; font-size: 2.5rem;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="margin-top:10px; font-size: 1.2rem; color: #566573;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não consta serviço para este dia.")
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
                        # Agrupamento para leitura limpa
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
                        if st.form_submit_button("GERAR MENSAGEM PARA WHATSAPP"):
                            id_c = colega.split(" - ")[0]
                            msg = f"*SOLICITAÇÃO DE TROCA ({nome_aba_t})*\n\n👉 *SAIR:* {st.session_state['user_nome_completo']} ({meu_s})\n👉 *ENTRAR:* ID {id_c}\n📝 *MOTIVO:* {motivo}"
                            st.code(msg, language="text")
            else:
                st.error("Não estás escalado neste dia.")

# Init
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
