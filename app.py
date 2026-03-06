import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema", layout="wide")

# Conectar
conn = st.connection("gsheets", type=GSheetsConnection)

def login():
    st.title("🔑 Portal GNR")
    
    # Botão de emergência para limpar cache se nada der
    if st.button("Limpar Memória da App (Cache)"):
        st.cache_data.clear()
        st.rerun()

    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # Tentamos ler SEM especificar a aba primeiro para ver se a ligação geral dá
                df_u = conn.read(worksheet="utilizadores", ttl=0)
                
                if df_u is not None:
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                                (df_u['password'].astype(str) == str(u_pass))]
                    
                    if not user.empty:
                        st.session_state["logado"] = True
                        st.session_state["user_nome"] = user.iloc[0]['nome']
                        st.rerun()
                    else:
                        st.error("Utilizador ou senha incorretos.")
            except Exception as e:
                st.error("🚨 Erro de Comunicação (400)")
                st.info("Tente o seguinte na sua Google Sheet:")
                st.markdown("""
                1. **Mude o nome da aba** de `utilizadores` para `dados`.
                2. **Mude o nome da aba** de `06-03` para `escala`.
                3. Verifique se o email da conta de serviço é **Editor**.
                """)
                st.code(str(e))

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    login()
else:
    st.success(f"Bem-vindo, {st.session_state['user_nome']}")
    if st.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
