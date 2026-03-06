import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Sistema GNR", layout="wide")

# Conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na configuração dos Secrets.")
    st.stop()

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # O Erro 400 acontece aqui se o nome da aba estiver errado
                df = conn.read(worksheet="utilizadores", ttl=0)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                user = df[(df['email'].astype(str).str.strip().str.lower() == u_email) & 
                          (df['password'].astype(str).str.strip() == str(u_pass))]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")
            except Exception as e:
                st.error("🚨 Erro de Acesso: Verifique se a aba se chama 'utilizadores' e se partilhou a folha.")
                st.expander("Detalhe Técnico").write(e)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.write(f"Sessão: {st.session_state['user_name']}")
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
    st.success("Conectado com sucesso!")
    
