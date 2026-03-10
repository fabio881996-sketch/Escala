import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. CONFIGURAÇÃO E PERFORMANCE ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

# Otimização de Cache: Só volta ao Google a cada 10 min ou se for forçado
@st.cache_data(ttl=600)
def load_data(aba_nome):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["gsheet_url"])
        df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except: return pd.DataFrame()

# --- 2. FUNÇÕES DE ESCRITA E PDF ---
def atualizar_status_gsheet(index_linha, novo_status, admin_nome=""):
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open_by_url(st.secrets["gsheet_url"])
    aba = sh.worksheet("registos_trocas")
    aba.update_cell(index_linha + 2, 6, novo_status)
    if admin_nome:
        dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        aba.update_cell(index_linha + 2, 8, admin_nome)
        aba.update_cell(index_linha + 2, 9, dt_agora)
    st.cache_data.clear() # Limpa cache após alteração

def salvar_troca_gsheet(linha):
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open_by_url(st.secrets["gsheet_url"])
    sh.worksheet("registos_trocas").append_row(linha)
    st.cache_data.clear()

def gerar_pdf_troca(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "Comprovativo de Troca de Servico", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    texto = (f"Certifica-se que o militar {dados['nome_origem']} (ID {dados['id_origem']}), "
             f"requereu a troca do servico '{dados['serv_orig']}' pelo servico '{dados['serv_dest']}' "
             f"do militar {dados['nome_destino']} (ID {dados['id_destino']}), para o dia {dados['data']}.\n\n"
             f"O pedido foi aceite e validado superiormente por {dados['validador']} no dia {dados['data_val']}.")
    pdf.multi_cell(190, 10, texto)
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 3. LOGIN E INTERFACE ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    u = st.text_input("Email").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("ENTRAR"):
        df_u = load_data("utilizadores")
        user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
        if not user.empty:
            st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}", "is_admin": u in ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]})
            st.rerun()
else:
    df_trocas = load_data("registos_trocas")
    df_util = load_data("utilizadores")
    menu_opt = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state.get("is_admin"): menu_opt.extend(["⚖️ Validar Trocas", "📜 Trocas Validadas"])
    menu = st.sidebar.radio("MENU", menu_opt)
    
    # --- LÓGICA DE NAVEGAÇÃO ---
    if menu == "🔍 Escala Geral":
        d_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at = df_dia.copy(); df_at['id_disp'] = df_at['id'].astype(str)
            tr_v = df_trocas[(df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
            for _, t in tr_v.iterrows():
                m_o = df_at['id'].astype(str) == str(t['id_origem'])
                if any(m_o): df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                m_d = df_at['id'].astype(str) == str(t['id_destino'])
                if any(m_d): df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"
            st.dataframe(df_at[['id_disp', 'serviço', 'horário']], use_container_width=True)

    # --- HISTÓRICO ---
    elif menu == "📜 Trocas Validadas":
        aprv = df_trocas[df_trocas['status'] == 'Aprovada']
        for idx, r in aprv.iterrows():
            with st.expander(f"📅 {r['data']} | ID {r['id_origem']} ↔️ ID {r['id_destino']}"):
                st.write(f"**Validado por:** {r.get('validador', 'N/A')} em {r.get('data_validacao', 'N/A')}")
                if st.button("Gerar PDF", key=f"pdf_{idx}"):
                    d_pdf = {"data": r['data'], "id_origem": r['id_origem'], "nome_origem": "...", "serv_orig": r['servico_origem'], "id_destino": r['id_destino'], "nome_destino": "...", "serv_dest": r['servico_destino'], "validador": r.get('validador', 'N/A'), "data_val": r.get('data_validacao', 'N/A')}
                    pdf_b = gerar_pdf_troca(d_pdf)
                    st.download_button("📥 Descarregar PDF", pdf_b, file_name=f"Troca_{r['data'].replace('/','_')}.pdf", mime="application/pdf")
