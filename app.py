import streamlit as st
import pandas as pd

# Substitui a parte do login por esta que lê a Google Sheet
def load_data():
    url = st.secrets["gsheet_url"]
    # Transforma o link normal num link de exportação CSV para o pandas ler
    csv_url = url.replace("/edit#gid=", "/export?format=csv&gid=")
    return pd.read_csv(csv_url)

def login():
    st.title("🔑 Login - Escala de Serviço")
    
    # Carrega utilizadores da folha
    try:
        df_users = load_data()
        
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if st.button("Entrar"):
            # Verifica se o email existe e a password coincide
            user_row = df_users[(df_users['email'] == email) & (df_users['password'].astype(str) == password)]
            
            if not user_row.empty:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = email
                st.session_state["user_name"] = user_row.iloc[0]['nome']
                st.rerun()
            else:
                st.error("Email ou password incorretos")
    except:
        st.error("Erro ao ligar à base de dados. Verifica o link nos Secrets.")

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
