import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Escalas GNR", layout="wide")

# Inicializar conexão
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na ligação aos Secrets.")
    st.stop()

# Gestão de Login no Session State
if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- ESTRUTURA DE LOGIN ---
if not st.session_state["logado"]:
    st.title("🚓 Acesso às Escalas")
    with st.form("login"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # Lê a 1ª aba (utilizadores) para validar login
                df_u = conn.read(ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == u_pass)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome_militar"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")
            except Exception as e:
                st.error("Erro ao ler base de dados de utilizadores.")

# --- ESTRUTURA DA ESCALA (PÓS-LOGIN) ---
else:
    st.sidebar.write(f"Militar: **{st.session_state['nome_militar']}**")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala Diária")
    
    # Seletor de Data
    # Se na folha tens '06-03', o código abaixo gera exatamente '06-03'
    data_sel = st.date_input("Escolha o dia", value=datetime.now())
    nome_da_aba = data_sel.strftime("%d-%m") 

    st.info(f"A procurar a aba chamada: **{nome_da_aba}**")

    if st.button(f"Carregar Escala de {nome_da_aba}"):
        # Limpa cache para garantir dados frescos
        st.cache_data.clear()
        
        try:
            # Tenta ler a aba específica (ex: 06-03)
            df = conn.read(worksheet=nome_da_aba, ttl=0)
            
            if df is not None and not df.empty:
                st.success(f"Escala de {nome_da_aba} carregada com sucesso!")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("A aba existe, mas não foram detetados dados.")
                
        except Exception as e:
            st.error(f"Não foi possível carregar a aba '{nome_da_aba}'")
            st.markdown("""
            **Verifique estes 3 pontos na sua Google Sheet:**
            1. O nome da aba é exatamente **{}**? (Sem espaços antes ou depois).
            2. Selecione a folha toda e clique em **Anular Moldagem** (Unmerge) para remover células mescladas.
            3. A primeira linha da folha tem de ter os títulos (Posto, Nome, etc.).
            """.format(nome_da_aba))
            with st.expander("Erro Técnico Detalhado"):
                st.code(str(e))
                
