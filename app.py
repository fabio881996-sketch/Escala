import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Escalas", layout="wide")

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
    st.title("🔑 Login")
    with st.form("login"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            # Lemos a primeira aba para validar login
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
    st.sidebar.success(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Vamos usar um campo de texto onde escreve o nome exato
    nome_aba = st.text_input("Nome da aba na Google Sheet:", value="EscalaHoje")

    if st.button("Carregar Dados"):
        st.cache_data.clear()
        try:
            # A query abaixo usa aspas duplas extra para garantir que o Google 
            # não confunde o nome da aba com outra coisa
            sql = f'SELECT * FROM "{nome_aba}"'
            df = conn.query(sql, ttl=0)
            
            if df is not None:
                # Se ele trouxer a aba de utilizadores por engano, avisamos
                if 'email' in [c.lower() for c in df.columns]:
                    st.warning("Atenção: O sistema carregou a aba de utilizadores em vez da escala. Verifique o nome da aba.")
                
                st.subheader(f"Dados da aba: {nome_aba}")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error("O Google devolveu uma tabela vazia.")
                
        except Exception as e:
            st.error(f"Erro ao ler a aba '{nome_aba}'")
            st.info("Dica: Certifique-se de que a aba não tem células mescladas e o nome na Sheet é igual ao escrito acima.")
            with st.expander("Erro Detalhado"):
                st.code(str(e))
                
