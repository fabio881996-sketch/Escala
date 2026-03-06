import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR Escalas", layout="wide")

# Conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Erro nos Secrets.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🚓 Login")
    with st.form("login"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Dados incorretos.")

# --- ESCALA ---
else:
    st.sidebar.write(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Visualizar Escala")
    
    # Em vez de gerar a data automática, vamos escrever o nome da aba
    # para testar se a ligação manual funciona.
    nome_aba = st.text_input("Escreva o nome exato da aba (ex: 06-03):", value="06-03")

    if st.button("Carregar Dados"):
        st.cache_data.clear()
        try:
            # Tenta ler a aba que escreveste
            df = conn.read(worksheet=nome_aba, ttl=0)
            
            if df is not None:
                st.success(f"Aba {nome_aba} carregada!")
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"O Google não permitiu ler a aba '{nome_aba}'")
            st.warning("FAÇA ISTO NA GOOGLE SHEET AGORA:")
            st.write("1. Clique na aba '06-03' com o botão direito -> Mudar Nome -> Apague tudo e escreva 'dia1'.")
            st.write("2. No campo acima, escreva 'dia1' e clique em Carregar.")
            with st.expander("Erro Detalhado"):
                st.code(str(e))
                
