import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Sistema GNR - Escala", page_icon="🚓", layout="wide")

# NOME DO FICHEIRO NO GOOGLE DRIVE
NOME_FOLHA = "escala"
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# --- FUNÇÃO DE LIGAÇÃO (GSPREAD) ---
def get_gspread_client():
    try:
        # Lê o JSON diretamente dos Secrets do Streamlit
        creds_json = st.secrets["connections"]["gsheets"]["service_account"]
        creds_dict = json.loads(creds_json)
        
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na configuração das credenciais: {e}")
        return None

def load_data(aba_nome):
    try:
        client = get_gspread_client()
        if client:
            sh = client.open(NOME_FOLHA)
            worksheet = sh.worksheet(aba_nome)
            # get_all_records() lê a folha e transforma em lista de dicionários
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            # Limpa nomes de colunas
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"Aba '{aba_nome}' não encontrada na folha 'escala'.")
        return None
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None

# --- INTERFACE DE LOGIN ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            with st.form("login_form"):
                u_email = st.text_input("Email").strip().lower()
                u_pass = st.text_input("Password", type="password")
                btn_login = st.form_submit_button("Entrar")
                
                if btn_login:
                    df_u = load_data("utilizadores")
                    if df_u is not None:
                        # Validação (procura email e password na aba utilizadores)
                        user = df_u[
                            (df_u['email'].astype(str).str.strip().str.lower() == u_email) & 
                            (df_u['password'].astype(str).str.strip() == str(u_pass))
                        ]
                        
                        if not user.empty:
                            st.session_state["logged_in"] = True
                            st.session_state["user_name"] = user.iloc[0]['nome']
                            st.session_state["user_email"] = u_email
                            st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                            st.rerun()
                        else:
                            st.error("Email ou Password incorretos.")

# --- CONTEÚDO PRINCIPAL ---
def main_app():
    # Sidebar
    st.sidebar.title(f"👮 {st.session_state['user_name']}")
    
    menu_opcoes = ["📅 Escala Diária", "🔄 Trocas de Serviço"]
    if st.session_state["user_email"] == EMAIL_ADMIN:
        menu_opcoes.append("🛡️ Painel Admin")
        
    escolha = st.sidebar.radio("Navegação", menu_opcoes)

    if escolha == "📅 Escala Diária":
        st.title("📅 Consulta de Escala")
        data_sel = st.date_input("Escolha o dia", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        
        df_dia = load_data(nome_aba)
        if df_dia is not None:
            st.success(f"Escala carregada para o dia {nome_aba}")
            st.dataframe(df_dia, use_container_width=True, hide_index=True)
            
    elif escolha == "🔄 Trocas de Serviço":
        st.title("🔄 Gestão de Trocas")
        st.info("Funcionalidade em desenvolvimento: Os pedidos serão gravados na aba 'trocas'.")

    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()

# --- CONTROLO DE FLUXO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
