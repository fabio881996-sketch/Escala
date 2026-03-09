import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. Configuração de Página
st.set_page_config(page_title="GNR - Portal de Escalas", layout="wide")

# 2. Função de Ligação Direta (API GSPREAD)
def get_data(aba_nome):
    try:
        # Tenta ligar usando as credenciais do JSON nos Secrets
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        
        # Abre a folha pelo URL exato
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet(aba_nome)
        
        # Converte para DataFrame
        data = worksheet.get_all_records()
        df = pd.DataFrame(data).astype(str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro de Acesso à aba '{aba_nome}': {e}")
        return None

# 3. Login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("🚓 Login Portal GNR")
    with st.form("login"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRAR"):
            df_u = get_data("utilizadores")
            if df_u is not None:
                user = df_u[(df_u['email'] == u) & (df_u['password'] == p)]
                if not user.empty:
                    st.session_state.update({
                        "logged_in": True,
                        "user_id": user.iloc[0]['id'],
                        "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"
                    })
                    st.rerun()
                else:
                    st.error("Utilizador ou Password incorretos.")

# 4. Conteúdo Pós-Login
else:
    st.sidebar.success(f"Ligado como: {st.session_state['user_nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
    
    tab1, tab2 = st.tabs(["📅 Minha Escala", "🔄 Registar Troca"])
    
    with tab1:
        st.write("A carregar escala...")
        # Aqui podes testar se ele lê as datas
        hoje_aba = datetime.now().strftime("%d-%m")
        df_hoje = get_data(hoje_aba)
        if df_hoje is not None:
            st.dataframe(df_hoje)
            
