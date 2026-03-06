import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# Conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets!")
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
            # Lemos a primeira aba para validar login
            st.cache_data.clear()
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Credenciais incorretas.")

# --- ESCALA ---
else:
    st.sidebar.info(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Campo para escrever o nome da aba - Tenta mudar na Sheet para 'Escala' e escreve aqui 'Escala'
    aba_nome = st.text_input("Escreva o nome exato da aba na Google Sheet:", value="06-03")

    if st.button("🔄 Carregar Escala"):
        # O SEGREDO: Limpamos o cache e usamos o parâmetro 'worksheet' isolado
        st.cache_data.clear()
        
        try:
            # Forçamos a leitura da aba específica
            df = conn.read(worksheet=aba_nome, ttl=0)
            
            if df is not None:
                # Se ele carregar a aba de utilizadores, avisamos
                if 'email' in [str(c).lower() for c in df.columns]:
                    st.warning(f"⚠️ O Google ignorou o pedido e carregou a aba de Utilizadores.")
                    st.info("Dica: Mude o nome da aba na Google Sheet para 'Escala' (sem números ou traços) e tente novamente.")
                else:
                    st.success(f"Aba '{aba_nome}' carregada!")
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error("A aba foi encontrada mas não tem dados.")
                
        except Exception as e:
            st.error(f"Erro ao ler a aba '{aba_nome}'.")
            with st.expander("Ver Erro Técnico"):
                st.code(str(e))

    st.divider()
    st.caption("Nota: Se o erro persistir, verifique se a aba não tem células mescladas.")
    
