import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# Conectar
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na ligação. Verifique os Secrets.")
    st.stop()

# Função para ler com tratamento de erro robusto
def extrair_dados(nome_folha):
    try:
        # Tentamos ler a aba. Se der erro 400, o problema é o nome.
        return conn.read(worksheet=nome_folha, ttl=0)
    except Exception as e:
        return None

# LÓGICA DE LOGIN
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔑 Portal GNR")
    with st.form("login"):
        user_input = st.text_input("Utilizador (Email)").strip().lower()
        pass_input = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Entrar"):
            # Tentativa de ler 'utilizadores'
            df_u = extrair_dados("utilizadores")
            
            if df_u is not None:
                # Padronizar colunas (remover espaços e pôr em minúsculas)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                # Verificar credenciais
                check = df_u[(df_u['email'].astype(str).str.lower() == user_input) & 
                             (df_u['password'].astype(str) == str(pass_input))]
                
                if not check.empty:
                    st.session_state["autenticado"] = True
                    st.session_state["nome"] = check.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
            else:
                st.error("❌ Erro 400: Não consegui aceder à aba 'utilizadores'.")
                st.info("Verifique se a aba na Google Sheet não tem espaços no nome (ex: 'utilizadores ').")

# APP APÓS LOGIN
else:
    st.sidebar.success(f"Bem-vindo, {st.session_state['nome']}")
    st.title("📅 Escala de Serviço")
    
    # Botão para carregar o dia 06-03
    if st.button("Ver Escala 06-03"):
        df_escala = extrair_dados("06-03")
        if df_escala is not None:
            st.success("Dados carregados!")
            st.table(df_escala) # st.table é mais simples para testar leitura
        else:
            st.warning("Não foi possível carregar a aba '06-03'. Verifique o nome na Sheet.")

    if st.sidebar.button("Sair"):
        st.session_state["autenticado"] = False
        st.rerun()
        
