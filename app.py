import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# 1. CONEXÃO
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets. Verifique a formatação.")
    st.stop()

# 2. LOGIN
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🚓 Sistema GNR - Acesso")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # Tentamos ler a aba 'utilizadores'
                # Se mudaste o nome na Google Sheet para 'dados', muda aqui para "dados"
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
                        st.error("Credenciais incorretas.")
            except Exception as e:
                st.error("🚨 Erro 404/400: A App não encontra a Folha ou a Aba.")
                st.info("Verifique se o ID no link dos Secrets está correto e se a aba se chama 'utilizadores'.")
                st.code(str(e))

# 3. APP PRINCIPAL
else:
    st.sidebar.success(f"Logado como: {st.session_state['user_nome']}")
    st.title("📅 Escala de Serviço")
    
    # Seletor de data para o dia 06-03
    data_sel = st.date_input("Consultar dia:", value=pd.to_datetime("2026-03-06"))
    aba_dia = data_sel.strftime("%d-%m") # Formata como 06-03

    if st.button(f"Ver Escala {aba_dia}"):
        try:
            df_escala = conn.read(worksheet=aba_dia, ttl=0)
            st.dataframe(df_escala, use_container_width=True)
        except:
            st.warning(f"Aba '{aba_dia}' não encontrada. Verifique o nome na Sheet.")

    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
        
