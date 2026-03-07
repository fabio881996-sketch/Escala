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

# 2. CSS - REFINAMENTO FINAL: TEXTOS DA SIDEBAR A BRANCO
st.markdown("""
    <style>
    /* Fundo Geral da App */
    .stApp { background-color: #ECEFF1; }
    
    /* BARRA LATERAL - CINZA ANTRACITE */
    [data-testid="stSidebar"] {
        background-color: #455A64 !important;
        border-right: 1px solid #37474F;
    }
    
    /* Card do Perfil na Sidebar */
    .profile-card {
        background: #37474F;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        text-align: center;
    }
    
    /* TODOS OS TEXTOS DA SIDEBAR A BRANCO */
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label,
    [data-testid="stWidgetLabel"] p {
        color: #FFFFFF !important;
    }
    
    /* Estilo das Opções do Menu (Radio) - TEXTO A BRANCO */
    div[data-testid="stSidebarUserContent"] .stRadio label {
        color: #FFFFFF !important; 
        background-color: transparent;
        padding: 10px 15px;
        border-radius: 8px;
        transition: all 0.2s;
        margin-bottom: 5px;
        font-weight: 500;
    }
    
    /* Hover nas opções do menu */
    div[data-testid="stSidebarUserContent"] .stRadio label:hover {
        background-color: rgba(255, 255, 255, 0.15) !important;
        color: #FFFFFF !important;
    }

    /* Botões na Sidebar */
    .stButton>button {
        background-color: #37474F;
        color: #FFFFFF;
        border: 1px solid #546E7A;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #546E7A;
        border-color: #FFFFFF;
        color: #FFFFFF;
    }
    
    /* Card de Serviço (Área Principal) */
    .status-card {
        background: #FFFFFF;
        padding: 25px;
        border-radius: 15px;
        border-top: 6px solid #455A64;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    
    h1 { color: #263238; }
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

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-card">
                <div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div>
                <p style="color: #B0BEC5; font-size: 0.7rem; margin:0; font-weight: bold; text-transform: uppercase;">Militar Ativo</p>
                <h2 style="margin:0; font-size: 1.1rem; color: white;">{st.session_state['user_nome_completo']}</h2>
                <p style="color: #B0BEC5; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Menu com texto forçado a branco via CSS
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
                    <h1 style="margin:0; color: #455A64; font-size: 2.2rem;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="margin-top:10px; font-size: 1.3rem; color: #546E7A;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não consta serviço para este dia.")
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
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
                        motivo = st.text_input("Motivo:")
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
    
