import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="GNR Escalas", layout="wide")

# 1. Ligação (Simples)
conn = st.connection("gsheets", type=GSheetsConnection)

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- BLOCO 1: LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login"):
        u = st.text_input("Email").lower().strip()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            # Lemos a primeira aba (Utilizadores)
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'] == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Credenciais Erradas")

# --- BLOCO 2: ESCALA (SÓ APARECE APÓS LOGIN) ---
else:
    st.sidebar.write(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Escala de Serviço")
    
    # Criamos o nome da aba (ex: 06-03)
    data_hoje = datetime.now().strftime("%d-%m")
    
    # IMPORTANTE: Usamos o parâmetro 'worksheet' diretamente no read
    # Se a aba 06-03 não existir, ele vai dar erro aqui
    try:
        # Forçamos a leitura da aba específica
        df_escala = conn.read(worksheet=data_hoje, ttl=0)
        
        if df_escala is not None:
            st.subheader(f"Serviço para o dia {data_hoje}")
            st.dataframe(df_escala, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro: Não encontrei a aba '{data_hoje}'")
        st.info("Verifique se na sua Google Sheet a aba tem exatamente o nome do dia (ex: 06-03).")
        # Se quiser testar outra aba manualmente:
        aba_manual = st.text_input("Ou digite o nome da aba manualmente:", value=data_hoje)
        if st.button("Tentar Carregar Aba Manual"):
            df_manual = conn.read(worksheet=aba_manual, ttl=0)
            st.dataframe(df_manual)
            
