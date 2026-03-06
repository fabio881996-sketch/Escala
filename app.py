import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Reset de Ligação", layout="wide")

# 1. TENTAR LIGAR À GOOGLE SHEET
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.sidebar.success("✅ Conexão configurada nos Secrets")
except Exception as e:
    st.error("❌ Erro nos Secrets! A App não consegue ler as tuas chaves.")
    st.exception(e)
    st.stop()

# 2. FUNÇÃO DE LEITURA DIRETA
def ler_folha(nome_aba):
    try:
        # ttl=0 ignora qualquer cache antiga
        return conn.read(worksheet=nome_aba, ttl=0)
    except Exception as e:
        return f"Erro: {e}"

st.title("🚓 Sistema GNR - Diagnóstico Total")

# --- TESTE 1: UTILIZADORES ---
st.subheader("1. Teste de Acesso: Utilizadores")
df_u = ler_folha("utilizadores")

if isinstance(df_u, pd.DataFrame):
    st.success("✅ Aba 'utilizadores' lida com sucesso!")
    st.write("Linhas encontradas:", len(df_u))
    # Mostra apenas as colunas para segurança
    st.write("Colunas detetadas:", df_u.columns.tolist())
    
    # Tenta mostrar o login só se a aba funcionar
    with st.expander("Abrir Formulário de Login"):
        with st.form("login"):
            email = st.text_input("Email")
            senha = st.text_input("Pass", type="password")
            if st.form_submit_button("Testar Login"):
                user = df_u[df_u.iloc[:, 1].astype(str).str.contains(email, na=False)]
                if not user.empty: st.write("✅ Encontrado!")
                else: st.write("❌ Não encontrado.")
else:
    st.error("❌ Não consigo ler a aba 'utilizadores'")
    st.info(f"Detalhe técnico: {df_u}")

st.divider()

# --- TESTE 2: ESCALA 06-03 ---
st.subheader("2. Teste de Acesso: Escala 06-03")
df_e = ler_folha("06-03")

if isinstance(df_e, pd.DataFrame):
    st.success("✅ Aba '06-03' lida com sucesso!")
    st.dataframe(df_e)
else:
    st.error("❌ Não consigo ler a aba '06-03'")
    st.info(f"Detalhe técnico: {df_e}")
