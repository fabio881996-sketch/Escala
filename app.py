import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="GNR - Portal de Escalas", layout="wide")

# Ligação simplificada
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na ligação. Verifique os Secrets.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            st.cache_data.clear()
            try:
                # Lemos a aba 'utilizadores' (id, password, email, nome)
                df_u = conn.read(worksheet="utilizadores", ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                user = df_u[
                    (df_u['email'].astype(str).str.lower() == u_email) & 
                    (df_u['password'].astype(str) == u_pass)
                ]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error("Erro ao ler aba 'utilizadores'. Verifique o nome na Sheet.")

# --- ÁREA DA ESCALA ---
else:
    st.sidebar.write(f"Militar: **{st.session_state['nome']}**")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Definimos o dia que queres procurar
    dia_procurado = "06-03"
    
    st.info(f"A carregar escala do dia: **{dia_procurado}**")

    # Botão para visualizar
    if st.button(f"Visualizar Escala {dia_procurado}"):
        st.cache_data.clear()
        try:
            # PROCURA A ABA 06-03
            df_escala = conn.read(worksheet=dia_procurado, ttl=0)
            
            if df_escala is not None and not df_escala.empty:
                st.success(f"Dados do dia {dia_procurado} carregados!")
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            else:
                st.warning(f"A aba '{dia_procurado}' parece estar vazia.")
                
        except Exception as e:
            st.error(f"Não foi possível encontrar a aba '{dia_procurado}'.")
            st.info(f"Garante que na Google Sheet a aba tem exatamente o nome: {dia_procurado}")
            with st.expander("Ver erro técnico"):
                st.code(e)
