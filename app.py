import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Escala de Serviço", layout="centered")

# Simulação de base de dados (Na prática, ligaremos à Google Sheet)
# Aqui podes carregar os teus 50 utilizadores
users_db = {
    "admin@empresa.com": "1234",
    "joao@empresa.com": "senha789"
}

def login():
    st.title("🔑 Login - Escala de Serviço")
    
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Entrar"):
        if email in users_db and users_db[email] == password:
            st.session_state["logged_in"] = True
            st.session_state["user_email"] = email
            st.rerun()
        else:
            st.error("Email ou password incorretos")

def main_app():
    st.sidebar.write(f"Sessão: {st.session_state['user_email']}")
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.title("📅 A Minha Escala")
    
    # Exemplo de como filtrarias os dados para o utilizador logado
    # df = carregar_dados_google_sheets()
    # minha_escala = df[df['email'] == st.session_state['user_email']]
    
    st.info("Aqui aparecerão os teus turnos para a próxima semana.")
    
    # Exemplo de tabela de escala
    data_exemplo = {
        'Data': ['2024-05-20', '2024-05-21', '2024-05-22'],
        'Turno': ['08:00 - 16:00', 'Folga', '16:00 - 00:00'],
        'Local': ['Posto A', '-', 'Posto B']
    }
    st.table(data_exemplo)

# Lógica de Navegação
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
