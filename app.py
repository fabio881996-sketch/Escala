import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Gestão de Escalas", page_icon="📅", layout="centered")

# --- DEFINE QUEM É ADMIN ---
ADMIN_EMAIL = "ferreira.fr@gnr.pt" 

def load_data():
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/export?format=csv"
        df = pd.read_csv(csv_url)
        # Converter coluna de data para o formato correto
        df['data'] = pd.to_datetime(df['data']).dt.date
        return df
    except Exception as e:
        st.error(f"Erro na base de dados: {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email").strip().lower()
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_users = load_data()
            if df_users is not None:
                df_users['email'] = df_users['email'].str.strip().str.lower()
                user_row = df_users[(df_users['email'] == email) & (df_users['password'].astype(str) == str(password))]
                if not user_row.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = email
                    st.session_state["user_name"] = user_row.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

def main_app():
    st.sidebar.title(f"👤 {st.session_state['user_name']}")
    
    # Navegação
    menu = ["A Minha Escala", "Ver Escala Geral"]
    if st.session_state["user_email"] == ADMIN_EMAIL:
        menu.append("Inserir Novo Turno")
    
    escolha = st.sidebar.radio("Ir para:", menu)
    df = load_data()
    if df is None: return

    # --- OPÇÃO 1: A MINHA ESCALA (POR DEFEITO) ---
    if escolha == "A Minha Escala":
        st.title("📅 Os Meus Turnos")
        minha = df[df['email'].str.lower() == st.session_state['user_email']]
        minha = minha.sort_values(by='data')
        
        if not minha.empty:
            st.dataframe(minha[['data', 'turno', 'local']], use_container_width=True, hide_index=True)
        else:
            st.info("Não tens turnos agendados.")

    # --- OPÇÃO 2: ESCALA GERAL (POR DIA) ---
    elif escolha == "Ver Escala Geral":
        st.title("👥 Escala Coletiva")
        
        # Selecionar o dia que quer consultar
        dia_escolhido = st.date_input("Consultar escala do dia:", datetime.now().date())
        
        escala_dia = df[df['data'] == dia_escolhido]
        
        if not escala_dia.empty:
            st.subheader(f"Equipa em serviço a {dia_escolhido.strftime('%d/%m/%Y')}")
            # Mostrar quem está em cada turno e local
            st.dataframe(
                escala_dia[['nome', 'turno', 'local']].sort_values(by='turno'), 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning(f"Não existem registos para o dia {dia_escolhido.strftime('%d/%m/%Y')}.")

    # --- OPÇÃO 3: ADMIN ---
    elif escolha == "Inserir Novo Turno":
        st.title("➕ Gerador de Turno")
        with st.form("add_turno"):
            func = st.selectbox("Funcionário", df['nome'].unique())
            email_f = df[df['nome'] == func]['email'].values[0]
            pass_f = df[df['nome'] == func]['password'].values[0]
            data_n = st.date_input("Data")
            turno_n = st.text_input("Turno (ex: 08:00-16:00)")
            local_n = st.text_input("Local")
            
            if st.form_submit_button("Gerar Linha"):
                st.code(f"{email_f},{pass_f},{func},{data_n},{turno_n},{local_n}", language="text")
                st.info("Copia e cola esta linha na tua Google Sheet.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# Lógica de Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
