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
            try:
                # Lemos a 1ª aba (sempre a da esquerda) para login
                df_u = conn.read(ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Acesso negado.")
            except:
                st.error("Erro ao validar login. Verifique a primeira aba da Sheet.")

# --- ÁREA DA ESCALA ---
else:
    st.sidebar.info(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Lista manual de abas para evitar o erro 400 de "aba não encontrada"
    # Adicione aqui os nomes das abas que tem na sua Sheet
    opcao_aba = st.selectbox("Selecione a Escala:", ["escala_limpa", "06-03", "dia1"])

    if st.button("Carregar Dados"):
        st.cache_data.clear()
        
        try:
            # TÉCNICA DE BYPASS: 
            # Tentamos ler a aba específica. Se der erro 400, o problema está 
            # na permissão do Google para essa aba.
            df = conn.read(worksheet=opcao_aba, ttl=0)
            
            if df is not None:
                st.success(f"Exibindo: {opcao_aba}")
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("A aba parece estar vazia.")
                
        except Exception as e:
            st.error("O Google Sheets continua a rejeitar esta aba específica.")
            
            # EXPLICAÇÃO DO MOTIVO REAL:
            with st.expander("PORQUE É QUE ISTO ACONTECE? (Clique aqui)"):
                st.write("""
                O Erro 400 acontece quando o Google Sheets API encontra algo que não consegue 'ler' como uma tabela simples.
                
                **Tente isto na sua Google Sheet agora:**
                1. Na aba **escala_limpa**, selecione as colunas de A a Z.
                2. Clique com o botão direito -> **Eliminar colunas**. (Isto remove lixo invisível à direita).
                3. Selecione as linhas de 100 para baixo -> **Eliminar linhas**. (Isto remove lixo invisível abaixo).
                4. Garanta que a célula **A1** não está vazia.
                """)
                st.code(str(e))
                
