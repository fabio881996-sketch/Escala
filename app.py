import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Sistema GNR", layout="wide")

# Inicializa conexão
conn = st.connection("gsheets", type=GSheetsConnection)

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# TELA DE LOGIN
if not st.session_state["logged_in"]:
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        email = st.text_input("Email").strip().lower()
        senha = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # Tenta ler a aba 'users'
                df_u = conn.read(worksheet="users", ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                user = df_u[(df_u['email'].astype(str).str.lower() == email) & 
                            (df_u['password'].astype(str) == senha)]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Senha incorretos.")
            except Exception as e:
                st.error("Erro ao aceder à Google Sheet. Verifique se a aba se chama 'users'.")
                st.code(e)

# TELA PRINCIPAL
else:
    st.sidebar.success(f"Ligado: {st.session_state['user_nome']}")
    st.title("📅 Escala de Serviço")
    
    # Seletor de data para buscar a aba (ex: 06-03)
    data_sel = st.date_input("Selecione o dia", value=pd.to_datetime("2026-03-06"))
    nome_aba = data_sel.strftime("%d-%m")

    if st.button(f"Ver Escala {nome_aba}"):
        try:
            df_escala = conn.read(worksheet=nome_aba, ttl=0)
            st.dataframe(df_escala, use_container_width=True)
        except:
            st.warning(f"Aba '{nome_aba}' não encontrada na folha.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
