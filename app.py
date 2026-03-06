import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# Conectar aos Secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets. Verifique se o JSON está bem colado.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    
    # Botão para forçar limpeza de erros antigos
    if st.sidebar.button("Limpar Cache de Erros"):
        st.cache_data.clear()
        st.rerun()

    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # ESTRATÉGIA: Ler a folha sem especificar o nome da aba
                # Isto evita o erro 400 se o nome da aba tiver caracteres estranhos
                df_u = conn.read(ttl=0) 
                
                if df_u is not None:
                    # Normalizar nomes das colunas (retira espaços e põe minúsculas)
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    
                    # Validar se as colunas existem
                    if 'email' in df_u.columns and 'password' in df_u.columns:
                        user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                                    (df_u['password'].astype(str) == str(u_pass))]
                        
                        if not user.empty:
                            st.session_state["logado"] = True
                            st.session_state["user_nome"] = user.iloc[0]['nome']
                            st.rerun()
                        else:
                            st.error("Email ou Password incorretos.")
                    else:
                        st.warning("A aba foi lida, mas não encontrei as colunas 'email' e 'password'.")
                        st.write("Colunas detetadas:", list(df_u.columns))
            except Exception as e:
                st.error("🚨 Erro Crítico 400")
                st.info("O Google Sheets rejeitou o pedido. Verifique se a folha não tem células mescladas ou filtros ativos.")
                st.code(e)

else:
    st.sidebar.success(f"Logado: {st.session_state['user_nome']}")
    st.title("📅 Escala de Serviço")
    
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
        
