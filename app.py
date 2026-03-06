import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# 1. CONEXÃO COM TRATAMENTO DE ERRO
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro Crítico de Conexão. Verifique os Secrets.")
    st.stop()

# 2. LOGICA DE LOGIN
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔑 Login - Sistema GNR")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # LER A PRIMEIRA ABA DISPONÍVEL (SEM NOME)
                # O ttl=0 garante que ele não usa erros antigos guardados na memória
                df_u = conn.read(ttl=0) 
                
                if df_u is not None and not df_u.empty:
                    # Normalizar os nomes das colunas
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    
                    # Verificar se as colunas necessárias existem na folha lida
                    if 'email' in df_u.columns and 'password' in df_u.columns:
                        # Procura o utilizador
                        user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                                    (df_u['password'].astype(str) == u_pass)]
                        
                        if not user.empty:
                            st.session_state["autenticado"] = True
                            st.session_state["nome"] = user.iloc[0]['nome']
                            st.rerun()
                        else:
                            st.error("Email ou Password incorretos.")
                    else:
                        st.warning("⚠️ A aba de utilizadores foi lida, mas as colunas 'email' e 'password' não foram encontradas.")
                        st.write("Colunas detetadas:", list(df_u.columns))
                else:
                    st.error("A folha parece estar vazia.")
            except Exception as e:
                st.error("🚨 Erro 400: O Google rejeitou a leitura da primeira aba.")
                st.info("Dica: Verifique se a primeira aba da esquerda não tem células vazias no topo ou nomes de colunas estranhos.")
                st.code(str(e))

# 3. APP APÓS LOGIN
else:
    st.sidebar.success(f"Logado como: {st.session_state['nome']}")
    st.title("📅 Escala Diária")
    
    if st.sidebar.button("Sair"):
        st.session_state["autenticado"] = False
        st.rerun()
        
