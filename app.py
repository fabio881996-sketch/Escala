import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Gestão de Escalas", layout="wide")

# 1. Ligação aos Secrets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("Erro nos Secrets. Verifique o link e as credenciais.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- BLOCO DE LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            # Lemos a 1ª aba (Utilizadores)
            df_u = conn.read(ttl=0)
            df_u.columns = [str(c).strip().lower() for c in df_u.columns]
            user = df_u[(df_u['email'] == u) & (df_u['password'].astype(str) == p)]
            if not user.empty:
                st.session_state["logado"] = True
                st.session_state["nome"] = user.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Email ou Password incorretos.")

# --- BLOCO DA ESCALA ---
else:
    st.sidebar.success(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    st.write("Se a escala não aparecer, selecione a aba correta na lista abaixo.")

    # ESTRATÉGIA DE BYPASS: Seleção manual da aba
    # Tente escrever aqui o nome exato da aba (ex: 06-03 ou Escala)
    nome_aba = st.text_input("Nome da aba na Google Sheet:", value="06-03")

    if st.button("🚀 Carregar Escala"):
        # Limpar cache para forçar nova leitura
        st.cache_data.clear()
        
        try:
            # Tentamos ler a aba pedida
            df_escala = conn.read(worksheet=nome_aba, ttl=0)
            
            if df_escala is not None:
                # Verificar se ele carregou os utilizadores por erro
                if 'email' in [c.lower() for c in df_escala.columns]:
                    st.error("O sistema carregou a aba de utilizadores. O Google não está a encontrar a aba que escreveu.")
                    st.info("Verifique se o nome da aba na Google Sheet tem espaços ou se é exatamente igual.")
                else:
                    st.subheader(f"Folha: {nome_aba}")
                    st.dataframe(df_escala, use_container_width=True, hide_index=True)
            
        except Exception as e:
            st.error(f"Erro ao tentar abrir a aba '{nome_aba}'")
            st.warning("DICA: Vá à Google Sheet e garanta que não existem CÉLULAS MESCLADAS (Unmerge).")
            with st.expander("Ver Detalhes do Erro"):
                st.code(str(e))

    st.divider()
    st.info("Nota: Se a tabela aparecer em branco, verifique se os dados na Google Sheet começam na linha 1.")
