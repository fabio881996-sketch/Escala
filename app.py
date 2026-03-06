import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# Conexão principal
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Erro nos Secrets.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- ÁREA DE LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            # Lemos apenas a primeira aba para validar
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Credenciais incorretas.")

# --- ÁREA DA ESCALA (Onde dava o erro 400) ---
else:
    st.sidebar.success(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Escala de Serviço")

    # ESTRATÉGIA NOVA: 
    # Em vez de worksheet="nome", usamos o comando SQL para forçar a leitura
    # de uma aba específica. Se o nome for '06-03', usamos entre aspas.
    
    aba_desejada = st.text_input("Escreva o nome exato da aba (ex: 06-03):", value="06-03")

    if st.button("Visualizar Escala"):
        st.cache_data.clear()
        try:
            # Tentamos ler a aba através de uma Query Direta (Bypass do Erro 400)
            query = f'SELECT * FROM "{aba_desejada}"'
            df_escala = conn.query(query, ttl=0)
            
            if df_escala is not None:
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            else:
                st.warning("Aba encontrada, mas sem dados.")
                
        except Exception as e:
            st.error(f"O Google ainda recusa ler a aba '{aba_desejada}'.")
            
            # Última tentativa: Mostrar o que a API está a ver
            with st.expander("Explicação Técnica"):
                st.write("Se o erro for 'Bad Request', o Google não está a aceitar o nome da aba via API.")
                st.write("**Tente isto:** Mude o nome da aba na Sheet para apenas 'Escala' (sem números) e tente ler.")
                st.code(str(e))
                
