import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração de Página
st.set_page_config(
    page_title="GNR - Sistema de Gestão de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS AVANÇADO - O segredo da beleza está aqui
st.markdown("""
    <style>
    /* Fundo Geral */
    .stApp { background-color: #f4f7f6; }
    
    /* BARRA LATERAL CUSTOMIZADA */
    [data-testid="stSidebar"] {
        background-image: linear-gradient(180deg, #2c3e50 0%, #000000 100%);
        color: white;
        border-right: 1px solid rgba(255,255,255,0.1);
        min-width: 300px !important;
    }
    
    /* Card do Perfil na Sidebar */
    .profile-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
    }
    
    /* Títulos e Textos na Sidebar */
    [data-testid="stSidebar"] .stMarkdown h2 {
        color: #ffffff !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin-bottom: 5px;
    }
    
    /* Estilo do Menu Radio */
    .stRadio [data-testid="stWidgetLabel"] p {
        color: #bdc3c7 !important;
        font-weight: bold;
        text-transform: uppercase;
        font-size: 0.8rem;
    }
    
    div[data-testid="stSidebarUserContent"] .stRadio label {
        background-color: transparent;
        color: #ecf0f1 !important;
        padding: 10px 15px;
        border-radius: 8px;
        transition: all 0.3s;
        margin-bottom: 5px;
    }
    
    div[data-testid="stSidebarUserContent"] .stRadio label:hover {
        background-color: rgba(255, 255, 255, 0.1);
        transform: translateX(5px);
    }

    /* Botões */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Card de Status (Escala) */
    .status-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 6px solid #2ecc71;
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

# 4. Lógica de Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #2c3e50;'>🚓 Portal GNR</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ACEDER AO SISTEMA"):
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
                    st.error("⚠️ Erro de ligação.")

# 5. Aplicação Principal
def main_app():
    # SIDEBAR DESIGNER
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-card">
                <div style="font-size: 40px; margin-bottom: 10px;">👮‍♂️</div>
                <h2>{st.session_state['user_nome_completo']}</h2>
                <p style="color: #95a5a6; font-size: 14px;">Militar ID: {st.session_state['user_id']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Solicitar Troca"])
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Terminar Sessão"):
            st.session_state["logged_in"] = False
            st.rerun()

    # --- MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""
                <div class="status-card">
                    <span style="color: #27ae60; font-weight: bold; text-transform: uppercase; font-size: 12px;">Serviço Confirmado</span>
                    <h1 style="margin:5px 0; color: #2c3e50; font-size: 32px;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="margin:0; font-size: 18px; color: #7f8c8d;">🕒 <b>Horário:</b> {meu_df.iloc[0]['horário']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não constas na escala para este dia.")
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    # --- CONSULTA GERAL ---
    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Completa")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            def mostrar_bloco(titulo, lista_keywords):
                padrao = '|'.join(lista_keywords).lower()
                temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
            mostrar_bloco("Atendimento e Patrulhas", ["atendimento", "patrulha", "po", "ronda"])
            mostrar_bloco("Administrativo / Apoio", ["secretaria", "tribunal", "inquérito", "pronto"])
            mostrar_bloco("Ausências", ["folga", "férias", "licença", "doente"])
        else:
            st.error("Escala não encontrada.")

    # --- SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        data_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)
        if df_dia_t is not None:
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                indisp = ["folga", "férias", "doente", "licença"]
                df_colegas = df_dia_t[(df_dia_t['id'] != st.session_state['user_id']) & (~df_dia_t['serviço'].str.lower().str.contains('|'.join(indisp)))]
                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'] + " - " + df_colegas['serviço']
                    with st.form("form_troca"):
                        colega = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_input("Motivo:")
                        if st.form_submit_button("GERAR MENSAGEM"):
                            id_c = colega.split(" - ")[0]
                            msg = f"*SOLICITAÇÃO DE TROCA ({nome_aba_t})*\n\n👉 *SAIR:* {st.session_state['user_nome_completo']} ({meu_s})\n👉 *ENTRAR:* ID {id_c}\n📝 *MOTIVO:* {motivo}"
                            st.code(msg, language="text")
            else:
                st.error("Não estás escalado para este dia.")

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
