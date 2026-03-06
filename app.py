import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Sistema GNR", layout="wide", page_icon="🚓")

# Estabelecer conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na conexão. Verifique os Secrets.")
    st.stop()

# Inicializar estado da sessão
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "user_nome" not in st.session_state:
    st.session_state["user_nome"] = ""

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🚓 Acesso ao Sistema")
    
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        
        if st.form_submit_button("Entrar"):
            # Limpa o cache para ler dados novos dos utilizadores
            st.cache_data.clear()
            try:
                # Lemos a aba 'utilizadores'
                df_u = conn.read(worksheet="utilizadores", ttl=0)
                
                # Normalizar colunas (garante que id, password, email, nome são lidos corretamente)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                # Validar credenciais
                user = df_u[(df_u['email'] == u_email) & (df_u['password'].astype(str) == u_pass)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["user_nome"] = user.iloc[0]['nome']
                    st.success(f"Bem-vindo, {st.session_state['user_nome']}!")
                    st.rerun()
                else:
                    st.error("Email ou Palavra-passe incorretos.")
            except Exception as e:
                st.error("Erro ao ler aba 'utilizadores'. Verifique o nome da aba na Sheet.")

# --- ÁREA LOGADA (ESCALA) ---
else:
    st.sidebar.title(f"Militar: {st.session_state['user_nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Escala de Serviço")
    
    # Instrução visual
    st.info("Clique no botão abaixo para carregar os dados atualizados da aba 'escala'.")

    if st.button("🔄 Carregar Escala"):
        # Limpa o cache para forçar a mudança de aba (Reset do erro 400)
        st.cache_data.clear()
        
        try:
            # Lemos a aba 'escala'
            df_escala = conn.read(worksheet="escala", ttl=0)
            
            if df_escala is not None and not df_escala.empty:
                st.success("Dados da escala carregados!")
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            else:
                st.warning("A aba 'escala' está vazia.")
                
        except Exception as e:
            st.error("Não foi possível carregar a aba 'escala'.")
            st.markdown("""
            **Verificações rápidas:**
            1. A aba na Google Sheet chama-se exatamente `escala`?
            2. Existem células mescladas? (Se sim, use o botão 'Unmerge').
            3. A primeira linha tem os títulos das colunas?
            """)
            with st.expander("Erro Técnico Detalhado"):
                st.code(e)
                
