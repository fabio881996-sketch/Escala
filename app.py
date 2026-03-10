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

# --- 3. FUNÇÃO DO PDF (MANTÉM AS REGRAS DE CENTRAMENTO E ORDENAÇÃO) ---
def gerar_pdf_escala_dia(data_str, df_original):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    def clean(txt):
        return str(txt).encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, clean("POSTO TERRITORIAL DE VILA NOVA DE FAMALICÃO"), ln=True)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, clean(f"ESCALA DE SERVIÇO PARA O DIA {data_str.upper()}"), border="B", ln=True, align='C')
    pdf.ln(4)

    servicos = df_original['serviço'].str.lower()
    df_aus = df_original[servicos.str.contains("férias|licença|doente|folga", na=False)]
    df_adm = df_original[servicos.str.contains("pronto|secretaria|inquérito|comando|diligência|tribunal", na=False)]
    df_at = df_original[servicos.str.contains("atendimento", na=False) & ~servicos.str.contains("apoio", na=False)]
    df_apoi = df_original[servicos.str.contains("apoio", na=False)]
    df_pat = df_original[servicos.str.contains("po|patrulha|ronda|vtr|auto|expediente|tiro|instrução", na=False) & ~servicos.str.contains("atendimento|apoio", na=False)]
    df_remu = df_original[servicos.str.contains("remu|grat", na=False)]

    # 1. AUSÊNCIAS (Alinhado à Esquerda 'L')
    y_topo = pdf.get_y()
    pdf.set_font("Arial", "B", 8); pdf.set_fill_color(240, 240, 240)
    pdf.cell(92, 6, clean(" AUSÊNCIAS E FOLGAS"), 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    if not df_aus.empty:
        ag_aus = df_aus.groupby('serviço')['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_aus.iterrows():
            pdf.multi_cell(92, 4, clean(f" {r['serviço'].upper()}: {r['id_disp']}"), border='LR', align='L')
    pdf.cell(92, 1, "", border='T', ln=1)

    y_f_aus = pdf.get_y()
    pdf.set_xy(107, y_topo)
    pdf.set_font("Arial", "B", 8); pdf.cell(93, 6, clean(" OUTRAS SITUAÇÕES / ADM"), 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    if not df_adm.empty:
        ag_adm = df_adm.groupby(['serviço', 'horário'])['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_adm.iterrows():
            pdf.set_x(107); pdf.multi_cell(93, 4, clean(f" {r['serviço'].upper()} ({r['horário']}): {r['id_disp']}"), border='LR', align='L')
    pdf.set_x(107); pdf.cell(93, 1, "", border='T', ln=1)
    
    pdf.set_y(max(y_f_aus, pdf.get_y()) + 4)

    # 2. ATENDIMENTO E APOIO (Centrado 'C')
    y_at_start = pdf.get_y()
    pdf.set_font("Arial", "B", 8); pdf.cell(92, 6, clean(" ATENDIMENTO"), 1, 1, 'L', True)
    pdf.set_font("Arial", "B", 7); pdf.cell(30, 5, "HORÁRIO", 1, 0, 'C'); pdf.cell(62, 5, "MILITAR(ES)", 1, 1, 'C')
    pdf.set_font("Arial", "", 7)
    if not df_at.empty:
        ag_at = df_at.groupby(['horário', 'serviço'])['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_at.sort_values('horário').iterrows():
            pdf.cell(30, 5, clean(r['horário']), 1, 0, 'C'); pdf.cell(62, 5, clean(r['id_disp']), 1, 1, 'C')
    
    y_f_at = pdf.get_y()
    pdf.set_xy(107, y_at_start)
    pdf.set_font("Arial", "B", 8); pdf.cell(93, 6, clean(" APOIO AO ATENDIMENTO"), 1, 1, 'L', True)
    pdf.set_font("Arial", "B", 7); pdf.set_x(107); pdf.cell(30, 5, "HORÁRIO", 1, 0, 'C'); pdf.cell(63, 5, "MILITAR(ES)", 1, 1, 'C')
    pdf.set_font("Arial", "", 7)
    if not df_apoi.empty:
        ag_apoi = df_apoi.groupby(['horário', 'serviço'])['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_apoi.sort_values('horário').iterrows():
            pdf.set_x(107); pdf.cell(30, 5, clean(r['horário']), 1, 0, 'C'); pdf.cell(63, 5, clean(r['id_disp']), 1, 1, 'C')
    
    pdf.set_y(max(y_f_at, pdf.get_y()) + 4)

    # 3. PATRULHAS (Ordenação por PO -> Horário)
    pdf.set_font("Arial", "B", 8); pdf.cell(0, 6, clean(" PATRULHAS E POLICIAMENTO"), 1, 1, 'L', True)
    pdf.set_font("Arial", "B", 7)
    w_p = [22, 65, 43, 30, 30]
    h_p = ["HORÁRIO", "MILITARES", "SERVIÇO", "RÁDIO/INDIC.", "VIATURA"]
    for i, h in enumerate(h_p): pdf.cell(w_p[i], 5, h, 1, 0, 'C')
    pdf.ln(5); pdf.set_font("Arial", "", 7)
    
    if not df_pat.empty:
        ag_pat = df_pat.groupby(['horário', 'serviço', 'indicativo rádio', 'rádio', 'viatura'], as_index=False).agg({'id_disp': lambda x: ', '.join(x), 'observações': lambda x: ' | '.join([v for v in x if v])})
        def prioridade_servico(nome):
            n = str(nome).lower()
            return "0_PO" if 'po' in n or 'ocorrências' in n else "1_" + n
        ag_pat['ordem_serv'] = ag_pat['serviço'].apply(prioridade_servico)
        ag_pat = ag_pat.sort_values(by=['ordem_serv', 'horário'])
        for _, r in ag_pat.iterrows():
            pdf.cell(w_p[0], 5, clean(r['horário']), 1, 0, 'C'); pdf.cell(w_p[1], 5, clean(r['id_disp']), 1, 0, 'C'); pdf.cell(w_p[2], 5, clean(r['serviço'].upper()), 1, 0, 'C')
            indic = r['indicativo rádio'] if r['indicativo rádio'] else r['rádio']
            pdf.cell(w_p[3], 5, clean(indic), 1, 0, 'C'); pdf.cell(w_p[4], 5, clean(r['viatura']), 1, 1, 'C')

    # 4. REMUNERADOS
    if not df_remu.empty:
        pdf.ln(4); pdf.set_font("Arial", "B", 8); pdf.cell(0, 6, clean(" SERVIÇOS REMUNERADOS"), 1, 1, 'L', True)
        pdf.set_font("Arial", "B", 7); pdf.cell(25, 5, "HORÁRIO", 1, 0, 'C'); pdf.cell(60, 5, "MILITARES", 1, 0, 'C'); pdf.cell(105, 5, "OBSERVAÇÃO", 1, 1, 'C')
        pdf.set_font("Arial", "", 7)
        ag_remu = df_remu.groupby(['horário', 'serviço', 'observações'])['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_remu.sort_values('horário').iterrows():
            pdf.cell(25, 5, clean(r['horário']), 1, 0, 'C'); pdf.cell(60, 5, clean(r['id_disp']), 1, 0, 'C'); pdf.cell(105, 5, clean(r['observações']), 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 4. LOGIN E INTERFACE (WEB) ---
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

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hj = datetime.now(); u_at = str(st.session_state['user_id'])
        for i in range(8):
            dt = hj + timedelta(days=i); d_s = dt.strftime('%d/%m/%Y'); lbl = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            df_d = load_data(dt.strftime("%d-%m"))
            meus_servicos = df_d[df_d['id'].astype(str) == u_at] if not df_d.empty else pd.DataFrame()
            
            if not meus_servicos.empty:
                for _, s in meus_servicos.iterrows():
                    # Verifica trocas para este serviço específico
                    st.markdown(f'<div class="card-servico card-meu"><b>{lbl}</b><br><h3>{s["serviço"]}</h3>🕒 {s["horário"]}</div>', unsafe_allow_html=True)

    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        d_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at_v = df_dia.copy(); df_at_v['id_disp'] = df_at_v['id'].astype(str)
            # Aplicar trocas visuais
            if not df_trocas.empty:
                tr_v = df_trocas[(df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
                for _, t in tr_v.iterrows():
                    m_o, m_d = df_at_v['id'].astype(str) == str(t['id_origem']), df_at_v['id'].astype(str) == str(t['id_destino'])
                    if any(m_o): df_at_v.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                    if any(m_d): df_at_v.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"
            
            st.download_button("📥 Escala Oficial (PDF)", gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at_v), file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf", use_container_width=True)

            # --- NOVA LÓGICA DE EXIBIÇÃO: PERMITE DUPLICIDADE ---
            def mostrar_bloco(tit, keys, df_total, extras=False):
                p = '|'.join(keys).lower()
                # Filtra apenas os serviços que batem com as chaves
                temp = df_total[df_total['serviço'].str.lower().str.contains(p, na=False)].copy()
                if not temp.empty:
                    with st.expander(f"🔹 {tit.upper()}", expanded=True):
                        ag_cols = ['serviço', 'horário']
                        if extras:
                            ag = temp.groupby(ag_cols, sort=False).agg({'id_disp': lambda x: ', '.join(x), 'viatura': lambda x: '/'.join(x.unique()), 'indicativo rádio': lambda x: '/'.join(x.unique())}).reset_index()
                        else:
                            ag = temp.groupby(ag_cols, sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(ag.rename(columns={'id_disp': 'Militar(es)'}), use_container_width=True, hide_index=True)

            # Exibição por categorias (sem remover do DF original para permitir que o militar apareça em duas categorias se necessário)
            mostrar_bloco("Comando e Adm", ["pronto", "secretaria", "inquérito", "comando"], df_at_v)
            mostrar_bloco("Atendimento", ["atendimento", "apoio"], df_at_v)
            mostrar_bloco("Patrulhas", ["po", "patrulha", "ronda", "vtr", "auto", "expediente", "tiro", "instrução"], df_at_v, True)
            mostrar_bloco("Remunerados", ["remu", "grat"], df_at_v)
            
            # Ausências e Folgas num bloco separado e discreto
            df_aus_fol = df_at_v[df_at_v['serviço'].str.lower().str.contains("férias|licença|doente|folga", na=False)]
            if not df_aus_fol.empty:
                with st.expander("🔹 FOLGAS E AUSÊNCIAS", expanded=False):
                    ag_af = df_aus_fol.groupby('serviço')['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(ag_af, use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        st.dataframe(df_util[['id', 'nim', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)

    # --- SISTEMA DE TROCAS (MANTIDO) ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca")
        dt_s = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_data(dt_s.strftime("%d-%m"))
        if not df_d.empty:
            meu_df = df_d[df_d['id'].astype(str) == str(st.session_state['user_id'])]
            if not meu_df.empty:
                meus_opts = meu_df.apply(lambda x: f"{x['serviço']} ({x['horário']})", axis=1).tolist()
                serv_meu = st.selectbox("O teu serviço para trocar:", meus_opts)
                
                outros = df_d[(df_d['id'].astype(str) != str(st.session_state['user_id'])) & (~df_d['serviço'].str.lower().str.contains('|'.join(IMPEDIMENTOS), na=False))].apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                with st.form("tr"):
                    alvo = st.selectbox("Trocar com:", outros)
                    if st.form_submit_button("ENVIAR PEDIDO"):
                        id_d = alvo.split(" - ")[0]; em_d = df_util[df_util['id'].astype(str) == id_d]['email'].values[0]
                        salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), st.session_state['user_id'], serv_meu, id_d, alvo.split(" - ", 1)[1], "Pendente_Militar", em_d])
                        st.success("Pedido enviado!")

    elif menu == "📥 Pedidos Recebidos":
        st.title("📥 Pedidos por Aceitar")
        m = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'].astype(str) == str(st.session_state['user_id']))]
        for idx, r in m.iterrows():
            st.info(f"{r['data']}: ID {r['id_origem']} quer trocar o serviço {r['servico_origem']} pelo teu {r['servico_destino']}")
            if st.button("✅ ACEITAR", key=f"a{idx}"): atualizar_status_gsheet(idx, "Pendente_Admin"); st.rerun()

    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validação (Comando)")
        for idx, r in df_trocas[df_trocas['status'] == 'Pendente_Admin'].iterrows():
            st.warning(f"Troca {r['data']}: {r['id_origem']} ↔️ {r['id_destino']}")
            if st.button("✔️ APROVAR", key=f"v{idx}"): atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome']); st.rerun()
                
