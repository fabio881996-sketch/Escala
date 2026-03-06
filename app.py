import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Ligação Direta", layout="wide")

# Botão para limpar a memória se der erro
if st.sidebar.button("Limpar Cache da App"):
    st.cache_data.clear()
    st.rerun()

try:
    # Criar conexão
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    st.title("🚓 Teste de Acesso Direto")

    # TENTATIVA 1: Ler a folha sem especificar aba (Lê a primeira aba por padrão)
    st.subheader("Tentativa 1: Ler primeira aba disponível")
    df_primeira = conn.read(ttl=0) 
    if df_primeira is not None:
        st.success("✅ Consegui ler a folha!")
        st.write("Dados da primeira aba:")
        st.dataframe(df_primeira.head())

    st.divider()

    # TENTATIVA 2: Ler a aba 'users'
    st.subheader("Tentativa 2: Ler aba 'users'")
    df_users = conn.read(worksheet="users", ttl=0)
    if df_users is not None:
        st.success("✅ Consegui ler a aba 'users'!")
        st.dataframe(df_users.head())

except Exception as e:
    st.error("🚨 Erro 400 persistente")
    st.write("Isto indica que o Google aceita o link, mas rejeita o conteúdo do pedido.")
    
    with st.expander("Clique aqui para ver a solução do Google Cloud"):
        st.markdown("""
        **Se o erro 400 continuar, faça isto:**
        1. Vá ao [Google Cloud Console](https://console.cloud.google.com/).
        2. Verifique se a **Google Sheets API** está **ATIVADA** para o projeto 'escala-489421'.
        3. Se estiver ativada, o problema é a **chave privada** (Private Key). Certifique-se de que no Secret ela começa com `-----BEGIN PRIVATE KEY-----` e termina com `-----END PRIVATE KEY-----\\n`.
        """)
    st.code(str(e))
    
