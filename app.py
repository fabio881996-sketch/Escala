import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# 1. CONEXÃO
conn = st.connection("gsheets", type=GSheetsConnection)

def login():
    st.title("🔑 Acesso ao Sistema GNR")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # ESTRATÉGIA SEGURA: Lemos a primeira aba (pos-0) 
                # para evitar o erro de nome "utilizadores/users"
                df_u = conn.read(ttl=0) # Sem nome de aba, lê a primeira
                
                if df_u is not None:
                    # Limpeza de colunas
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    
                    # Procura o utilizador
                    user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                                (df_u['password'].astype(str) == str(u_pass))]
                    
                    if not user.empty:
                        st.session_state["logado"] = True
                        st.session_state["user_nome"] = user.iloc[0]['nome']
                        st.session_state["user_id"] = str(user.iloc[0]['id'])
                        st.rerun()
                    else:
                        st.error("Credenciais inválidas. Verifique o email e a senha.")
            except Exception as e:
                st.error("Erro técnico ao aceder aos dados de utilizadores.")
                st.code(e)

# --- FLUXO DA APP ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    login()
else:
    st.sidebar.success(f"Ligado: {st.session_state['user_nome']}")
    st.title("📅 Escala Diária")
    
    # Seletor de data
    data_sel = st.date_input("Escolha o dia:", value=pd.to_datetime("today"))
    nome_aba = data_sel.strftime("%d-%m") # Ex: 06-03

    if st.button(f"Ver Escala {nome_aba}"):
        try:
            # Aqui temos de usar o nome da aba porque há muitas (uma para cada dia)
            df_escala = conn.read(worksheet=nome_aba, ttl=0)
            st.success(f"Escala de {nome_aba} carregada!")
            st.dataframe(df_escala, use_container_width=True, hide_index=True)
        except:
            st.error(f"Não encontrei a aba '{nome_aba}'.")
            st.info("💡 Certifique-se que a aba na Sheet tem exatamente este nome.")

    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
        
