import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# Conectar aos Secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na configuração dos Secrets.")
    st.stop()

def login():
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # Tentativa de leitura com tratamento de erro 400
                df_u = conn.read(worksheet="utilizadores", ttl=0)
                
                # Normalizar colunas
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == str(u_pass))]
                
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error("🚨 Erro ao aceder à folha 'utilizadores'")
                st.info("Causa provável: O nome da aba na Google Sheet não é exatamente 'utilizadores' (tudo minúsculas) ou o link nos Secrets está incorreto.")
                st.code(e)

def main_app():
    st.sidebar.success(f"Ligado como: {st.session_state['user_name']}")
    
    st.title("📅 Escala Diária")
    
    # Seletor de data
    data_sel = st.date_input("Escolha o dia", value=pd.to_datetime("2026-03-06"))
    nome_aba = data_sel.strftime("%d-%m") # Tenta "06-03"

    try:
        df_dia = conn.read(worksheet=nome_aba, ttl=0)
        st.success(f"✅ Escala de {nome_aba} carregada!")
        st.dataframe(df_dia, use_container_width=True)
    except Exception:
        st.warning(f"Não encontrei a aba '{nome_aba}'.")
        st.info("Dica: Verifique se o nome da aba na Google Sheet é exatamente '06-03'.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# Fluxo da App
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
