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
    .stButton > button { background-color: #FFFFFF !important; color: #000000 !important; border: 2px solid #000000 !important; font-weight: bold !important; }
    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .sidebar-id { color: #D1D1D1 !important; font-size: 0.9rem; margin-top: -15px; }
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]
IMPEDIMENTOS = ["férias", "licença", "doente", "diligência", "tribunal", "pronto", "secretaria", "inquérito"]

# --- 2. FUNÇÕES DE DADOS ---
@st.cache_data(ttl=300)
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

def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def atualizar_status_gsheet(index_linha, novo_status, admin_nome=""):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status)
        if admin_nome:
            dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            aba.update_cell(index_linha + 2, 8, admin_nome)
            aba.update_cell(index_linha + 2, 9, dt_agora)
        st.cache_data.clear()
        return True
    except: return False

def salvar_troca_gsheet(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
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
    texto = (f"Certifica-se que o militar {dados['nome_origem']} (ID {dados['id_origem']}), "
             f"requereu a troca do servico '{dados['serv_orig']}' pelo servico '{dados['serv_dest']}' "
             f"do militar {dados['nome_destino']} (ID {dados['id_destino']}), para o dia {dados['data']}.\n\n"
             f"O pedido foi aceite pelo militar de destino e validado superiormente por {dados['validador']} no dia {dados['data_val']}.")
    pdf.multi_cell(190, 10, texto)
    pdf.ln(20)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="R")
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_pdf_escala_dia(data_str, df_original):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    # Cabeçalho Compacto (Estilo GNR)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "POSTO TERRITORIAL DE VILA NOVA DE FAMALICÃO", ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"ESCALA DE SERVIÇO PARA O DIA {data_str}", border="B", ln=True, align='C')
    pdf.ln(3)

    # Lógica de Grupos para o PDF
    df_aus = df_original[df_original['serviço'].str.lower().str.contains("férias|licença|doente|folga", na=False)]
    df_out = df_original[df_original['serviço'].str.lower().str.contains("pronto|secretaria|inquérito|diligência|tribunal", na=False)]
    df_at = df_original[df_original['serviço'].str.lower().str.contains("atendimento|apoio", na=False)]
    df_pat = df_original[df_original['serviço'].str.lower().str.contains("po|patrulha|ronda|vtr|auto", na=False)]
    df_remu = df_original[df_original['serviço'].str.lower().str.contains("remu|grat", na=False)]

    # 1. Ausências e Outras Situações (Compacto)
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 6, " OUTRAS SITUAÇÕES / AUSÊNCIAS", 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    txt = ", ".join([f"{r['serviço'].upper()}: {r['id_disp']}" for _, r in pd.concat([df_aus, df_out]).iterrows()])
    pdf.multi_cell(0, 5, txt if txt else "Sem registos", 1)
    pdf.ln(2)

    # 2. Atendimento
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, " ATENDIMENTO", 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    for _, r in df_at.iterrows():
        pdf.cell(40, 5, r['horário'], 1, 0, 'C')
        pdf.cell(150, 5, r['id_disp'], 1, 1, 'L')
    pdf.ln(2)

    # 3. Patrulhas (Tabela Completa)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(0, 6, " PATRULHAS", 1, 1, 'L', True)
    pdf.set_font("Arial", "B", 7)
    w = [25, 60, 25, 25, 55]
    h_titles = ["HORÁRIO", "MILITARES", "INDICATIVO", "VIATURA", "OBSERVAÇÕES"]
    for i, h in enumerate(h_titles): pdf.cell(w[i], 5, h, 1, 0, 'C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 7)
    for _, r in df_pat.iterrows():
        pdf.cell(w[0], 5, r['horário'], 1, 0, 'C')
        pdf.cell(w[1], 5, r['id_disp'], 1, 0, 'L')
        pdf.cell(w[2], 5, r.get('indicativo rádio', ''), 1, 0, 'C')
        pdf.cell(w[3], 5, r.get('viatura', ''), 1, 0, 'C')
        pdf.cell(w[4], 5, r.get('observações', ''), 1, 1, 'L')

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login"):
            st.markdown("<h1 style='text-align:center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("Email").strip().lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                if not user.empty:
                    st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}", "user_email": u, "is_admin": u in ADMINS})
                    st.rerun()
                else: st.error("Dados incorretos.")
else:
    df_trocas = load_data("registos_trocas")
    df_util = load_data("utilizadores")
    
    menu_opt = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state.get("is_admin"): menu_opt.extend(["⚖️ Validar Trocas", "📜 Trocas Validadas"])
    menu_opt.append("👥 Efetivo")

    with st.sidebar:
        st.write(f"👮‍♂️ **{st.session_state['user_nome']}**")
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]}</p>', unsafe_allow_html=True)
        menu = st.radio("MENU", menu_opt)
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    # --- 📅 MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hj = datetime.now(); u_at = str(st.session_state['user_id'])
        for i in range(8):
            dt = hj + timedelta(days=i); d_s = dt.strftime('%d/%m/%Y'); lbl = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            tr_v = df_trocas[(df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') & ((df_trocas['id_origem'].astype(str) == u_at) | (df_trocas['id_destino'].astype(str) == u_at))] if not df_trocas.empty else pd.DataFrame()
            if not tr_v.empty:
                t = tr_v.iloc[0]; s_ex, era, com = (t['servico_destino'], t['servico_origem'], t['id_destino']) if str(t['id_origem']) == u_at else (t['servico_origem'], t['servico_destino'], t['id_origem'])
                st.markdown(f'<div class="card-servico card-troca"><b>{lbl}</b><br><h3>{s_ex}</h3><p style="margin:0;">🔙 Troca de: {era}</p><p style="margin:0; font-weight:bold;">🔄 Com ID: {com}</p></div>', unsafe_allow_html=True)
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    m = df_d[df_d['id'].astype(str) == u_at]
                    if not m.empty: st.markdown(f'<div class="card-servico card-meu"><b>{lbl}</b><br><h3>{m.iloc[0]["serviço"]}</h3>🕒 {m.iloc[0]["horário"]}</div>', unsafe_allow_html=True)

    # --- 🔍 ESCALA GERAL (RESTAURADO COM TODOS OS GRUPOS WEB) ---
    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        d_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at = df_dia.copy(); df_at['id_disp'] = df_at['id'].astype(str)
            if not df_trocas.empty:
                tr_v = df_trocas[(df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
                for _, t in tr_v.iterrows():
                    m_o = df_at['id'].astype(str) == str(t['id_origem'])
                    if any(m_o): df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                    m_d = df_at['id'].astype(str) == str(t['id_destino'])
                    if any(m_d): df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"
            
            st.download_button("📥 Descarregar Escala Oficial (PDF)", gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at), file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf", use_container_width=True)

            def mostrar_sec_geral(tit, keys, df_f, mostrar_extras=False):
                p = '|'.join(keys).lower(); temp = df_f[df_f['serviço'].str.lower().str.contains(p, na=False)].copy()
                if not temp.empty:
                    with st.expander(f"🔹 {tit.upper()}", expanded=True):
                        cols_ag = ['serviço', 'horário']
                        if mostrar_extras:
                            ag = temp.groupby(cols_ag, sort=False).agg({'id_disp': lambda x: ', '.join(x), 'viatura': lambda x: ', '.join(x.unique()), 'rádio': lambda x: ', '.join(x.unique()), 'indicativo rádio': lambda x: ', '.join(x.unique()), 'observações': lambda x: ', '.join(x.unique())}).reset_index()
                        else: ag = temp.groupby(cols_ag, sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(ag.rename(columns={'id_disp': 'Militar'}), use_container_width=True, hide_index=True)
                    return df_f[~df_f['id'].isin(temp['id'])]
                return df_f

            df_res = df_at.copy(); df_aus = df_res[df_res['serviço'].str.lower().str.contains("férias|licença|doente|diligência|tribunal", na=False)].copy()
            df_res = df_res[~df_res['id'].isin(df_aus['id'])]
            df_res = mostrar_sec_geral("Comando e Administrativos", ["pronto", "secretaria", "inquérito"], df_res, False)
            df_res = mostrar_sec_geral("Atendimento", ["atendimento", "apoio"], df_res, False)
            df_res = mostrar_sec_geral("Patrulhas", ["po", "patrulha", "ronda", "vtr", "auto"], df_res, True)
            df_remu = df_res[df_res['serviço'].str.lower().str.contains("remu|grat", na=False)].copy()
            df_folga = df_res[df_res['serviço'].str.lower().str.contains("folga", na=False)].copy()
            df_outros = df_res[~df_res['id'].isin(df_remu['id']) & ~df_res['id'].isin(df_folga['id'])]
            if not df_outros.empty: mostrar_sec_geral("Outros Serviços", [""], df_outros, False)
            if not df_remu.empty: mostrar_sec_geral("Remunerados", ["remu", "grat"], df_remu, True)
            if not df_folga.empty: mostrar_sec_geral("Folga", ["folga"], df_folga, False)
            if not df_aus.empty:
                with st.expander("🔹 AUSENTES", expanded=True):
                    ag = df_aus.groupby(['serviço', 'horário'], sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(ag, use_container_width=True, hide_index=True)

    # --- 📜 TROCAS VALIDADAS (RESTAURADO COM DETALHES E PDF) ---
    elif menu == "📜 Trocas Validadas":
        st.title("📜 Histórico de Trocas Aprovadas")
        if not df_trocas.empty:
            aprv = df_trocas[df_trocas['status'] == 'Aprovada']
            for idx, r in aprv.sort_index(ascending=False).iterrows():
                def get_n(id_m):
                    res = df_util[df_util['id'].astype(str) == str(id_m)]
                    return f"{res.iloc[0]['posto']} {res.iloc[0]['nome']}" if not res.empty else f"ID {id_m}"
                n_o, n_d = get_n(r['id_origem']), get_n(r['id_destino'])
                with st.expander(f"📅 {r['data']} | {n_o} ↔️ {n_d}"):
                    st.write(f"**Origem:** {r['servico_origem']} | **Destino:** {r['servico_destino']}")
                    val_por = r.get('validador', 'N/A'); val_em = r.get('data_validacao', 'N/A')
                    st.caption(f"⚖️ Validado por {val_por} em {val_em}")
                    dados_pdf = {"data": r['data'], "id_origem": r['id_origem'], "nome_origem": n_o, "serv_orig": r['servico_origem'], "id_destino": r['id_destino'], "nome_destino": n_d, "serv_dest": r['servico_destino'], "validador": val_por, "data_val": val_em}
                    st.download_button("📥 Guia de Troca", gerar_pdf_troca(dados_pdf), file_name=f"Troca_{r['data'].replace('/','-')}.pdf", key=f"h_{idx}")

    # --- RESTANTES SEM ALTERAÇÃO ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca")
        dt_s = st.date_input("Data:", format="DD/MM/YYYY"); df_d = load_data(dt_s.strftime("%d-%m"))
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == str(st.session_state['user_id'])]
            if not meu.empty:
                opts = df_d[(df_d['id'].astype(str) != str(st.session_state['user_id'])) & (~df_d['serviço'].str.lower().str.contains('|'.join(IMPEDIMENTOS), na=False))].apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                with st.form("tr"):
                    alvo = st.selectbox("Trocar com:", opts)
                    if st.form_submit_button("ENVIAR"):
                        id_d = alvo.split(" - ")[0]; em_d = df_util[df_util['id'].astype(str) == id_d]['email'].values[0]
                        salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), st.session_state['user_id'], f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})", id_d, alvo.split(" - ", 1)[1], "Pendente_Militar", em_d])
                        st.success("Enviado!")

    elif menu == "📥 Pedidos Recebidos":
        st.title("📥 Pedidos")
        m = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'].astype(str) == str(st.session_state['user_id']))]
        for idx, r in m.iterrows():
            st.info(f"{r['data']}: ID {r['id_origem']} quer trocar.")
            if st.button("✅ ACEITAR", key=f"a{idx}"): atualizar_status_gsheet(idx, "Pendente_Admin"); st.rerun()

    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validação")
        for idx, r in df_trocas[df_trocas['status'] == 'Pendente_Admin'].iterrows():
            st.warning(f"Troca {r['data']}: {r['id_origem']} ↔️ {r['id_destino']}")
            if st.button("✔️ VALIDAR", key=f"v{idx}"): atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome']); st.rerun()

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        st.dataframe(df_util[['id', 'nim', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)
        
