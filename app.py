import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# Inicializar conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro Crítico nos Secrets. Verifique a formatação TOML.")
    st.stop()

# FUNÇÃO PARA LER DADOS
def load_sheet(nome_aba):
    try:
        # ttl=0 obriga a ler dados frescos da Google
        df = conn.read(worksheet=nome_aba, ttl=0)
        return df
    except Exception as e:
        st.error(f"Não consegui ler a aba: {nome_aba}")
        return None

# TELA DE LOGIN
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                # Normalizar colunas para evitar erros de nomes
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                # Procura o utilizador
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == str(u_pass))]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            else:
                st.warning("Dica: Verifique se a aba se chama exatamente 'utilizadores' na Google Sheet.")

# APP PRINCIPAL (SÓ APARECE APÓS LOGIN)
else:
    st.sidebar.success(f"Utilizador: {st.session_state['user_name']}")
    st.title("📅 Escala de Serviço")
    
    # Tenta ler a escala do dia 06-03
    if st.button("Carregar Escala 06-03"):
        df_escala = load_sheet("06-03")
        if df_escala is not None:
            st.success("Escala carregada!")
            st.dataframe(df_escala, use_container_width=True)

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
