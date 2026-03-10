import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    h1, h2, h3 { color: #1E3A8A !important; font-weight: 800 !important; }
    
    .stButton > button {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        font-weight: bold !important;
    }

    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    
    .sidebar-id { color: #D1D1D1 !important; font-size: 0.9rem; margin-top: -15px; }
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]
IMPEDIMENTOS = ["férias", "licença", "doente", "diligência", "tribunal", "pronto", "secretaria", "inquérito"]

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def load_data(aba_nome):
    try:
        client = get_client()
        if client:
            sh = client.open_by_url(st.secrets["gsheet_url"])
            df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df.fillna("")
        return pd.DataFrame()
    except: return pd.DataFrame()

def atualizar_status_gsheet(index_linha, novo_status, admin_nome=""):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status)
        if admin_nome:
            data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            aba.update_cell(index_linha + 2, 8, admin_nome)
            aba.update_cell(index_linha + 2, 9, data_agora)
        return True
    except: return False

def salvar_troca_gsheet(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
        return True
    except: return False

def gerar_pdf_troca(dados):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "Comprovativo de Troca de Servico", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "", 12)
    # Nota: Removidos acentos complexos para evitar erro de encoding da lib FPDF padrão
    texto = (
        f"Certifica-se que o militar {dados['nome_origem']} (ID {dados['id_origem']}), "
        f"requereu a troca do servico '{dados['serv_orig']}' pelo servico '{dados['serv_dest']}' "
        f"do militar {dados['nome_destino']} (ID {dados['id_destino']}), para o dia {dados['data']}.\n\n"
        f"O pedido foi aceite pelo militar de destino e validado superiormente por "
        f"{dados['validador']} no dia {dados['data_val']}."
    )
    pdf.multi_cell(190, 10, texto)
    pdf.ln(20)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="R")
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align:center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("Email").strip().lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                if not user.empty:
                    st.session_state.update({
                        "logged_in": True, "user_id": str(user.iloc[0]['id']), 
                        "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                        "user_email": u, "is_admin": u in ADMINS
                    })
                    st.rerun()
                else: st.error("Dados incorretos.")
else:
    df_trocas = load_data("registos_trocas")
    df_util = load_data("utilizadores")
    
    menu_options = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state.get("is_admin", False):
        menu_options.extend(["⚖️ Validar Trocas", "📜 Trocas Validadas"])
    menu_options.append("👥 Efetivo")

    with st.sidebar:
        st.write(f"👮‍♂️ **{st.session_state['user_nome']}**")
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]}</p>', unsafe_allow_html=True)
        st.write("---")
        menu = st.radio("MENU", menu_options)
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 4. MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        user_atual = str(st.session_state['user_id'])
        for i in range(8):
            dt = hoje + timedelta(days=i); d_str = dt.strftime('%d/%m/%Y'); label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            troca_v = pd.DataFrame()
            if not df_trocas.empty:
                troca_v = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['status'] == 'Aprovada') & 
                                   ((df_trocas['id_origem'].astype(str) == user_atual) | (df_trocas['id_destino'].astype(str) == user_atual))]
            if not troca_v.empty:
                t = troca_v.iloc[0]
                serv_ex, era, com = (t['servico_destino'], t['servico_origem'], t['id_destino']) if str(t['id_origem']) == user_atual else (t['servico_origem'], t['servico_destino'], t['id_origem'])
                st.markdown(f'<div class="card-servico card-troca"><b>{label}</b><br><h3>{serv_ex}</h3><p style="margin:0; color:#666;">🔙 Troca de: {era}</p><p style="margin:0; font-weight: bold;">🔄 Com ID: {com}</p></div>', unsafe_allow_html=True)
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    meu = df_d[df_d['id'].astype(str) == user_atual]
                    if not meu.empty: st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    # --- 5. ESCALA GERAL ---
    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(data_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at = df_dia.copy(); df_at['id_disp'] = df_at['id'].astype(str)
            if not df_trocas.empty:
                tr_v = df_trocas[(df_trocas['data'] == data_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
                for _, t in tr_v.iterrows():
                    m_orig = df_at['id'].astype(str) == str(t['id_origem'])
                    if any(m_orig): df_at.loc[m_orig, 'serviço'] = t['servico_destino']; df_at.loc[m_orig, 'id_disp'] = f"{t['id_origem']} (🔄)"
                    m_dest = df_at['id'].astype(str) == str(t['id_destino'])
                    if any(m_dest): df_at.loc[m_dest, 'serviço'] = t['servico_origem']; df_at.loc[m_dest, 'id_disp'] = f"{t['id_destino']} (🔄)"

            def mostrar_sec(tit, keys, df_f):
                p = '|'.join(keys).lower(); temp = df_f[df_f['serviço'].str.lower().str.contains(p, na=False)].copy()
                if not temp.empty:
                    with st.expander(f"🔹 {tit.upper()}", expanded=True):
                        ag = temp.groupby(['serviço', 'horário'], sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(ag.rename(columns={'id_disp': 'id'}), use_container_width=True, hide_index=True)
                    return df_f[~df_f['id'].isin(temp['id'])]
                return df_f

            df_p = df_at.copy()
            df_p = mostrar_sec("Comando e Administrativos", ["pronto", "secretaria", "inquérito"], df_p)
            df_p = mostrar_sec("Atendimento", ["atendimento"], df_p)
            df_p = mostrar_sec("Apoio ao Atendimento", ["apoio"], df_p)
            df_p = mostrar_sec("Patrulhas", ["po", "patrulha", "ronda", "vtr"], df_p)
            df_f = df_p[df_p['serviço'].str.lower().str.contains("folga|férias|licença|doente|diligência|remu|grat", na=False)]
            _ = mostrar_sec("Outros Serviços", [""], df_p[~df_p['id'].isin(df_f['id'])])
            df_f = mostrar_sec("Remunerados", ["remu", "grat"], df_f)
            df_f = mostrar_sec("Folga", ["folga"], df_f)
            _ = mostrar_sec("Ausentes", ["férias", "licença", "doente", "diligência"], df_f)
        else: st.warning("Sem dados.")

    # --- 6. SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca")
        dt_sol = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        df_d = load_data(dt_sol.strftime("%d-%m"))
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == str(st.session_state['user_id'])]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço: **{meu_s}**")
                padrao_imp = '|'.join(IMPEDIMENTOS).lower()
                colegas = df_d[(df_d['id'].astype(str) != str(st.session_state['user_id'])) & (~df_d['serviço'].str.lower().str.contains(padrao_imp, na=False))]
                if not colegas.empty:
                    opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                    with st.form("form_tr"):
                        alvo = st.selectbox("Com quem queres trocar?", opcoes)
                        if st.form_submit_button("ENVIAR PEDIDO"):
                            id_dest = alvo.split(" - ")[0]; serv_dest = alvo.split(" - ", 1)[1]
                            email_dest = df_util[df_util['id'].astype(str) == id_dest]['email'].values[0]
                            if salvar_troca_gsheet([dt_sol.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_dest, serv_dest, "Pendente_Militar", email_dest]):
                                st.success("Enviado!"); st.balloons()
                else: st.warning("Ninguém disponível para troca.")
            else: st.warning("Não estás escalado.")

    # --- 7. PEDIDOS RECEBIDOS ---
    elif menu == "📥 Pedidos Recebidos":
        st.title("📥 Pedidos Recebidos")
        if not df_trocas.empty:
            minhas = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'].astype(str) == str(st.session_state['user_id']))]
            if not minhas.empty:
                for idx, row in minhas.iterrows():
                    st.markdown(f'<div class="card-servico card-troca">📅 <b>{row["data"]}</b><br>ID {row["id_origem"]} quer trocar.<br><b>Recebes:</b> {row["servico_origem"]}<br><b>Dás:</b> {row["servico_destino"]}</div>', unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    if c1.button("✅ ACEITAR", key=f"ac_{idx}"): atualizar_status_gsheet(idx, "Pendente_Admin"); st.rerun()
                    if c2.button("❌ RECUSAR", key=f"re_{idx}"): atualizar_status_gsheet(idx, "Recusada"); st.rerun()
            else: st.info("Sem pedidos.")

    # --- 8. VALIDAR TROCAS (ADMIN) ---
    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validação Admin")
        pend = df_trocas[df_trocas['status'] == 'Pendente_Admin']
        if not pend.empty:
            for idx, row in pend.iterrows():
                st.warning(f"Troca: {row['data']} | ID {row['id_origem']} ↔️ ID {row['id_destino']}")
                c1, c2 = st.columns(2)
                if c1.button("✔️ VALIDAR", key=f"ok_{idx}"):
                    if atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome']): st.rerun()
                if c2.button("🚫 REJEITAR", key=f"no_{idx}"):
                    atualizar_status_gsheet(idx, "Rejeitada_Admin", st.session_state['user_nome']); st.rerun()
        else: st.info("Nada pendente.")

    # --- 9. HISTÓRICO / TROCAS VALIDADAS ---
    elif menu == "📜 Trocas Validadas":
        st.title("📜 Histórico de Trocas Validadas")
        aprovadas = df_trocas[df_trocas['status'] == 'Aprovada']
        if not aprovadas.empty:
            for idx, row in aprovadas.iterrows():
                # Obter Nomes dos Militares para o PDF
                def get_n(id_m):
                    res = df_util[df_util['id'].astype(str) == str(id_m)]
                    return f"{res.iloc[0]['posto']} {res.iloc[0]['nome']}" if not res.empty else f"ID {id_m}"
                
                n_orig = get_n(row['id_origem']); n_dest = get_n(row['id_destino'])
                
                with st.expander(f"📅 {row['data']} - {n_orig} / {n_dest}"):
                    st.write(f"**Validador:** {row.get('validador', 'N/A')}")
                    st.write(f"**Data Validação:** {row.get('data_validacao', 'N/A')}")
                    
                    dados_pdf = {
                        "data": row['data'], "id_origem": row['id_origem'], "nome_origem": n_orig,
                        "serv_orig": row['servico_origem'], "id_destino": row['id_destino'],
                        "nome_destino": n_dest, "serv_dest": row['servico_destino'],
                        "validador": row.get('validador', 'N/A'), "data_val": row.get('data_validacao', 'N/A')
                    }
                    
                    if st.button("Gerar PDF", key=f"pdf_{idx}"):
                        pdf_b = gerar_pdf_troca(dados_pdf)
                        st.download_button("📥 Descarregar PDF", pdf_b, file_name=f"Troca_{row['data'].replace('/','_')}.pdf", mime="application/pdf")
        else: st.info("Sem histórico.")

    # --- 10. EFETIVO ---
    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        if not df_util.empty: st.dataframe(df_util[['id', 'posto', 'nome', 'telemóvel']], hide_index=True, use_container_width=True)
