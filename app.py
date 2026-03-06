import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="GNR - Diagnóstico", layout="wide")

st.title("🚓 Diagnóstico de Ligação GNR")

try:
    # 1. Tentar estabelecer ligação
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 2. Tentar ler a aba 'users'
    # worksheet="users" deve ser exatamente igual ao que está na aba
    df = conn.read(worksheet="users", ttl=0)
    
    if df is not None:
        st.success("✅ SUCESSO! A aba 'users' foi lida.")
        st.write("Aqui estão os primeiros dados encontrados:")
        st.dataframe(df.head())
        
        # Se chegou aqui, o login vai funcionar.
        if st.button("Ir para o Login"):
            st.session_state["fase"] = "login"
            st.rerun()
            
except Exception as e:
    st.error("🚨 A ligação falhou com Erro 404.")
    st.markdown("""
    **Causas prováveis para o 404:**
    1. **O ID no Secret está errado:** Verifique se não há espaços antes ou depois das aspas no ID `1y40O14e-pZRFn92Dyn3JkE5gshWZl7XOwVvlP1uBazg`.
    2. **Permissões:** O email da Service Account tem de ser **Editor** no botão azul 'Partilhar' da folha.
    3. **Aba Inexistente:** A aba tem de se chamar `users` (em minúsculas).
    """)
    st.subheader("Erro Técnico Detalhado:")
    st.code(e)
    
