import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# Conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro Crítico nos Secrets!")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🚓 Acesso GNR")
    with st.form("login_form"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            # Lendo a 1ª aba para login
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Acesso negado.")

# --- ESCALA ---
else:
    st.sidebar.info(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Campo manual para evitar erros de data automática
    aba_teste = st.text_input("Nome da Aba na Google Sheet:", value="escala_limpa")

    if st.button("Carregar Escala"):
        # Limpar cache do Streamlit forçadamente
        st.cache_data.clear()
        
        try:
            # Tentar ler a aba escala_limpa
            df = conn.read(worksheet=aba_teste, ttl=0)
            
            if df is not None and not df.empty:
                st.success(f"Dados carregados de: {aba_teste}")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("A aba foi encontrada, mas parece estar vazia.")
        except Exception as e:
            st.error("O Google Sheets bloqueou o acesso a esta aba específica.")
            st.info("Verifique se não há CÉLULAS MESCLADAS na aba 'escala_limpa'.")
            with st.expander("Ver Erro Detalhado"):
                st.code(str(e))
                
