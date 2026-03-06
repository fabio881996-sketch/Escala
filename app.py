import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Sistema GNR", layout="wide")

# Ligação simplificada
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets")
    st.stop()

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # O ttl=0 força a ler dados frescos
                df = conn.read(worksheet="utilizadores", ttl=0)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                user = df[(df['email'].astype(str).str.strip().str.lower() == u_email) & 
                          (df['password'].astype(str).str.strip() == str(u_pass))]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error("Erro 400 ou de Permissão")
                st.write("Verifica se a aba se chama exatamente: utilizadores")
                st.write(e)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.success(f"Bem-vindo, {st.session_state['user_name']}!")
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
