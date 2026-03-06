import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração Base
st.set_page_config(page_title="Sistema GNR", layout="wide")

# Tentar estabelecer a ligação
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro Crítico: A ligação 'gsheets' não está configurada nos Secrets.")
    st.stop()

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # Tenta ler a aba utilizadores
                df = conn.read(worksheet="utilizadores", ttl=0)
                
                # Limpeza de colunas (converte tudo para minúsculas e tira espaços)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                # Procura o utilizador
                user = df[
                    (df['email'].astype(str).str.strip().str.lower() == u_email) & 
                    (df['password'].astype(str).str.strip() == str(u_pass))
                ]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error("🚨 Erro de Acesso")
                st.info("Causas prováveis:\n1. A aba 'utilizadores' não existe na folha.\n2. A folha não foi partilhada com o email da Service Account.")
                st.expander("Ver detalhe do erro").write(e)

def main_app():
    st.sidebar.success(f"Ligado como: {st.session_state['user_name']}")
    
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
    st.title("🚓 Painel de Controlo")
    st.write("Se vês isto, a ligação está a funcionar!")
    
    # Exemplo de leitura de escala
    aba_hoje = "utilizadores" # Apenas para teste inicial
    df_teste = conn.read(worksheet=aba_hoje)
    st.dataframe(df_teste)

# Início da App
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
