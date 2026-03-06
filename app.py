import streamlit as st
import pandas as pd

# Configuração da página (aspeto mobile-friendly)
st.set_page_config(page_title="Escala de Serviço", page_icon="📅", layout="centered")

# --- FUNÇÃO PARA LER A GOOGLE SHEET ---
def load_data():
    try:
        # Puxa o link dos Secrets do Streamlit
        url = st.secrets["gsheet_url"]
        # Converte o link de visualização para link de exportação direta em CSV
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/export?format=csv"
        return pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Erro ao ligar à base de dados: {e}")
        return None

# --- INTERFACE DE LOGIN ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Escala de Serviço - 50 Elementos</p>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        email = st.text_input("Email (ex: nome@gnr.pt)").strip().lower()
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Entrar")

        if submit:
            df_users = load_data()
            if df_users is not None:
                # Procura o utilizador na folha (ignora maiúsculas/minúsculas no email)
                df_users['email'] = df_users['email'].str.strip().str.lower()
                user_row = df_users[(df_users['email'] == email) & (df_users['password'].astype(str) == str(password))]
                
                if not user_row.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = email
                    st.session_state["user_name"] = user_row.iloc[0]['nome']
                    st.success(f"Bem-vindo, {st.session_state['user_name']}!")
                    st.rerun()
                else:
                    st.error("Email ou password incorretos.")

# --- INTERFACE PRINCIPAL (APÓS LOGIN) ---
def main_app():
    st.sidebar.title(f"👤 {st.session_state['user_name']}")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.title(f"📅 A Minha Escala")
    st.write(f"Olá *{st.session_state['user_name']}*, aqui estão os teus turnos:")

    # Carregar dados novamente para mostrar a escala
    df = load_data()
    
    if df is not None:
        # Filtra a tabela para mostrar apenas as linhas onde o email é o do utilizador logado
        minha_escala = df[df['email'].str.lower() == st.session_state['user_email']]
        
        if not minha_escala.empty:
            # Seleciona apenas as colunas relevantes para mostrar ao funcionário
            # Certifica-te que estas colunas existem na tua folha!
            colunas_para_mostrar = ['data', 'turno', 'local']
            # Filtra apenas as colunas que existem de facto para não dar erro
            existentes = [c for c in colunas_para_mostrar if c in minha_escala.columns]
            
            st.dataframe(minha_escala[existentes], use_container_width=True, hide_index=True)
        else:
            st.info("Ainda não tens turnos atribuídos na escala.")
    
    st.divider()
    st.caption("Sistema de Gestão de Escalas v1.0 - Gratuito e Seguro")

# --- LÓGICA DE NAVEGAÇÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
