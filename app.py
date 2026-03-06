import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# 1. CONEXÃO (TTL=0 para ler sempre o que está na Sheet agora)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro Crítico: Verifique os Secrets no Streamlit Cloud.")
    st.stop()

# 2. LOGICA DE LOGIN
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🚓 Portal de Acesso GNR")
    
    with st.form("login_form"):
        u_email = st.text_input("Email (ex: nome.apelido@gnr.pt)").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # Lendo a nova aba 'users'
                df_u = conn.read(worksheet="users", ttl=0)
                
                if df_u is not None:
                    # Limpeza de colunas (converte para minúsculas e retira espaços)
                    df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                    
                    # Procura o utilizador na tabela
                    user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                                (df_u['password'].astype(str) == str(u_pass))]
                    
                    if not user.empty:
                        st.session_state["autenticado"] = True
                        st.session_state["user_nome"] = user.iloc[0]['nome']
                        st.session_state["user_id"] = str(user.iloc[0]['id'])
                        st.rerun()
                    else:
                        st.error("Email ou Palavra-passe incorretos.")
                else:
                    st.error("A aba 'users' parece estar vazia.")
            except Exception as e:
                st.error("🚨 Erro de Ligação (404/400)")
                st.info("Verifique se o link no Secret termina no ID da folha (sem /edit ou /gid).")
                st.code(str(e))

# 3. APP APÓS LOGIN
else:
    st.sidebar.success(f"Logado: {st.session_state['user_nome']}")
    st.title("📅 Consulta de Escala")
    
    # Seletor de Data para o dia de hoje (06-03)
    # Podes mudar manualmente para testar outras abas
    data_sel = st.date_input("Selecione o dia:", value=pd.to_datetime("2026-03-06"))
    nome_aba_escala = data_sel.strftime("%d-%m") # Resultado: 06-03

    if st.button(f"Carregar Escala de {nome_aba_escala}"):
        try:
            df_escala = conn.read(worksheet=nome_aba_escala, ttl=0)
            if df_escala is not None:
                st.success(f"Escala de {nome_aba_escala} carregada!")
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            else:
                st.warning("Aba encontrada, mas sem dados.")
        except:
            st.error(f"Não encontrei a aba '{nome_aba_escala}'.")
            st.info("💡 Confirma se a aba se chama exatamente '06-03' na Google Sheet.")

    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()
        
