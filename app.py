import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Sistema GNR - Escalas", page_icon="🚓", layout="wide")

# CONFIGURAÇÃO DO ADMIN
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# Inicializar Conexão
conn = st.connection("gsheets", type=GSheetsConnection)

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso à Escala</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        entrar = st.form_submit_button("Entrar")
        
        if entrar:
            try:
                # Carregar utilizadores via conexão segura
                df_u = conn.read(worksheet="utilizadores")
                df_u.columns = [c.strip().lower() for c in df_u.columns]
                
                # Validar credenciais
                user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = email_i
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error(f"Erro ao aceder à base de dados: {e}")
                st.info("Verifica se a aba 'utilizadores' existe e se o Segredo JSON está correto.")

def main_app():
    # Sidebar com Logout e Info
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID: {st.session_state['user_id']}")
    
    # Definição do Menu
    opcoes = ["📅 Escala Diária", "🔄 Solicitar Troca", "📋 Meus Pedidos"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        opcoes.append("🛡️ Painel Admin")
        
    menu = st.sidebar.radio("Navegação", opcoes)

    # --- 📅 ESCALA DIÁRIA (LÓGICA ANTERIOR) ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        
        try:
            df_dia = conn.read(worksheet=nome_aba)
            if df_dia is not None:
                # ... (Aqui podes manter a tua função mostrar_bloco que já tínhamos feito)
                st.success(f"Escala de {nome_aba} carregada.")
                st.dataframe(df_dia, use_container_width=True, hide_index=True)
        except:
            st.warning(f"Escala de {nome_aba} não encontrada.")

    # --- 🔄 SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Novo Pedido de Troca")
        # Lógica de escrita que enviamos anteriormente...
        st.info("Preencha os dados para enviar ao Comandante.")

    # --- 🛡️ PAINEL ADMIN ---
    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Gestão de Pedidos")
        try:
            df_trocas = conn.read(worksheet="trocas")
            st.dataframe(df_trocas)
        except:
            st.error("Aba 'trocas' não encontrada.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# --- CONTROLO DE SESSÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
