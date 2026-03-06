import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="GNR - Gestão de Escalas", layout="wide")

# --- LIGAÇÃO DIRETA AO GOOGLE (via gspread) ---
def get_gspread_client():
    # Usa os mesmos Secrets que já tens no Streamlit
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # Criar credenciais a partir do dicionário nos secrets
    creds_dict = st.secrets["connections"]["gsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# URL da tua Google Sheet (Copia o link completo da barra de endereços do browser)
# EX: https://docs.google.com/spreadsheets/d/ID_DA_TUA_SHEET/edit
URL_SHEET = st.secrets["connections"]["gsheets"]["spreadsheet"] 

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                client = get_gspread_client()
                sheet = client.open_by_url(URL_SHEET)
                # Forçamos a leitura da primeira aba (index 0) para o login
                aba_users = sheet.get_worksheet(0)
                df_u = pd.DataFrame(aba_users.get_all_records())
                
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                user = df_u[(df_u['email'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
            except Exception as e:
                st.error("Erro ao conectar à Google Sheet. Verifique as permissões.")
                st.code(e)

# --- ÁREA DA ESCALA ---
else:
    st.sidebar.write(f"Militar: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    st.title("📅 Consulta de Escala Diária")
    
    # Seleção de data
    data_sel = st.date_input("Escolha o dia", value=datetime.now())
    nome_aba = data_sel.strftime("%d-%m") # Ex: 06-03

    if st.button(f"Carregar Escala ({nome_aba})"):
        try:
            client = get_gspread_client()
            sheet = client.open_by_url(URL_SHEET)
            
            # COMANDO DIRETO: Busca a aba pelo nome exato
            aba_escala = sheet.worksheet(nome_aba)
            dados = aba_escala.get_all_records()
            
            if dados:
                df = pd.DataFrame(dados)
                st.success(f"Aba '{nome_aba}' carregada com sucesso!")
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.warning("A aba foi encontrada mas parece não ter dados formatados em tabela.")
                
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"A aba '{nome_aba}' não existe na sua Google Sheet.")
            st.info("Dica: Certifique-se que a aba se chama exatamente 06-03 (exemplo).")
        except Exception as e:
            st.error("Ocorreu um erro ao ler os dados.")
            st.code(e)
            
