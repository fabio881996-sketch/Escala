import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

@st.cache_data(ttl=300)
def load_data(aba_nome):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["gsheet_url"])
        
        # Carrega dados e normaliza cabeçalhos
        df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records())
        df.columns = df.columns.str.strip().str.lower()
        
        # Garante colunas essenciais para evitar KeyError
        colunas_necessarias = ['data', 'id_origem', 'servico_origem', 'id_destino', 'servico_destino', 'status', 'email_destino', 'validador', 'data_validacao']
        if aba_nome == "registos_trocas":
            for col in colunas_necessarias:
                if col not in df.columns: df[col] = ""
        
        return df.fillna("")
    except Exception as e:
        st.error(f"Erro ao carregar {aba_nome}: {e}")
        return pd.DataFrame()

# --- 2. FUNÇÕES DE APOIO ---
def atualizar_status_gsheet(index_linha, novo_status, admin_nome=""):
    try:
        client = gspread.authorize(Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']))
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status) # Coluna F
        if admin_nome:
            aba.update_cell(index_linha + 2, 8, admin_nome) # Coluna H
            aba.update_cell(index_linha + 2, 9, datetime.now().strftime("%d/%m/%Y %H:%M")) # Coluna I
        st.cache_data.clear()
        return True
    except: return False

def gerar_pdf_troca(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "Comprovativo de Troca de Servico", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    texto = (f"Requerente: {dados['nome_origem']} (ID {dados['id_origem']})\n"
             f"Servico Original: {dados['serv_orig']}\n\n"
             f"Destino: {dados['nome_destino']} (ID {dados['id_destino']})\n"
             f"Servico Aceite: {dados['serv_dest']}\n\n"
             f"Validado por: {dados['validador']} em {dados['data_val']}.")
    pdf.multi_cell(190, 10, texto)
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 3. LOGICA PRINCIPAL ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("🚓 Login Portal")
    u = st.text_input("Email").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("ENTRAR"):
        df_u = load_data("utilizadores")
        # Verifica colunas existentes antes de filtrar
        if 'email' in df_u.columns and 'password' in df_u.columns:
            user = df_u[(df_u['email'] == u) & (df_u['password'] == p)]
            if not user.empty:
                st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}", "is_admin": u in ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]})
                st.rerun()
else:
    df_trocas = load_data("registos_trocas")
    df_util = load_data("utilizadores")
    menu = st.sidebar.radio("MENU", ["🔍 Escala Geral", "⚖️ Validar Trocas", "📜 Trocas Validadas"])

    if menu == "🔍 Escala Geral":
        d_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at = df_dia.copy()
            df_at['id_disp'] = df_at['id'].astype(str)
            tr_v = df_trocas[(df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
            for _, t in tr_v.iterrows():
                m_o = df_at['id'].astype(str) == str(t['id_origem'])
                if any(m_o): df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
            st.dataframe(df_at[['id_disp', 'serviço', 'horário']], use_container_width=True)

    elif menu == "⚖️ Validar Trocas":
        pend = df_trocas[df_trocas['status'] == 'Pendente_Admin']
        for idx, r in pend.iterrows():
            if st.button(f"Validar Troca: {r['id_origem']} ↔️ {r['id_destino']}", key=idx):
                atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome'])
                st.rerun()

    elif menu == "📜 Trocas Validadas":
        aprv = df_trocas[df_trocas['status'] == 'Aprovada']
        for idx, r in aprv.iterrows():
            with st.expander(f"📅 {r['data']} | {r['id_origem']} ↔️ {r['id_destino']}"):
                if st.button("Gerar PDF", key=f"pdf_{idx}"):
                    d = {"data": r['data'], "id_origem": r['id_origem'], "nome_origem": "...", "serv_orig": r['servico_origem'], "id_destino": r['id_destino'], "nome_destino": "...", "serv_dest": r['servico_destino'], "validador": r.get('validador', 'N/A'), "data_val": r.get('data_validacao', 'N/A')}
                    st.download_button("📥 Descarregar", gerar_pdf_troca(d), "troca.pdf", "application/pdf")
