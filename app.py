import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Sistema GNR", layout="wide")

# Conectar aos Secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets.")
    st.stop()

# --- LÓGICA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    st.title("🔑 Sistema GNR - Login")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # LER A PRIMEIRA ABA (Onde devem estar os utilizadores)
                # Não passamos o nome da worksheet para evitar o Erro 400
                df_u = conn.read(ttl=0) 
                
                if df_u is not None:
                    # Normalizar nomes das colunas
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    
                    # Verificar se as colunas necessárias existem
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
                        st.error("A aba de utilizadores deve ter as colunas 'email' e 'password'.")
            except Exception as e:
                st.error("Erro ao carregar base de dados.")
                st.code(e)

# --- APP APÓS LOGIN ---
else:
    st.sidebar.success(f"Bem-vindo, {st.session_state['user_nome']}")
    st.title("📅 Consulta de Escala")

    # Para a escala, como são várias abas, tentamos a leitura específica
    data_sel = st.date_input("Data:", value=pd.to_datetime("today"))
    nome_aba = data_sel.strftime("%d-%m")

    if st.button(f"Ver Escala {nome_aba}"):
        try:
            df_escala = conn.read(worksheet=nome_aba, ttl=0)
            st.dataframe(df_escala, use_container_width=True, hide_index=True)
        except Exception:
            st.warning(f"Não encontrei a aba '{nome_aba}'. Verifique se o nome está correto na Sheet.")

    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
        
