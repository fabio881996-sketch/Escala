import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="GNR - Portal de Escalas", layout="wide")

# Ligação
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na ligação aos Secrets.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        
        if st.form_submit_button("Entrar"):
            st.cache_data.clear()
            try:
                # 1. Lemos a aba utilizadores (id, password, email, nome)
                df_u = conn.read(worksheet="utilizadores", ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                # 2. Validar (convertendo tudo para string para não haver erro de formato)
                user = df_u[
                    (df_u['email'].astype(str).str.lower() == u_email) & 
                    (df_u['password'].astype(str) == u_pass)
                ]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")
            except Exception as e:
                st.error("Erro ao ler aba 'utilizadores'.")
                st.info("Verifique se a primeira aba da Sheet se chama 'utilizadores'.")

# --- ESCALA ---
else:
    st.sidebar.write(f"Militar: **{st.session_state['nome']}**")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala")
    
    # Nome da aba que definiste
    dia_aba = "06-03"

    if st.button(f"🔄 Carregar Escala {dia_aba}"):
        st.cache_data.clear()
        try:
            # Tenta ler a aba 06-03
            df_escala = conn.read(worksheet=dia_aba, ttl=0)
            
            if df_escala is not None and not df_escala.empty:
                st.success(f"Escala de {dia_aba} carregada!")
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            else:
                st.warning(f"A aba '{dia_aba}' está vazia.")
        except Exception as e:
            st.error(f"Erro ao abrir a aba '{dia_aba}'.")
            st.markdown("""
            ### 🛠 O QUE FAZER NA GOOGLE SHEET AGORA:
            1. Vai à aba **06-03**.
            2. Clica no quadrado no canto superior esquerdo (seleciona tudo).
            3. Clica no botão **Anular Moldagem (Unmerge)**. Se houver uma única célula mesclada, o Google bloqueia a leitura.
            4. Garante que não há espaços no nome da aba (ex: "06-03 " com espaço no fim).
            """)
            
