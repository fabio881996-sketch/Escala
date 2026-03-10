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
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]
IMPEDIMENTOS = ["férias", "licença", "doente", "diligência", "tribunal", "pronto", "secretaria", "inquérito"]

# --- 2. FUNÇÕES DE DADOS (CORRIGIDAS PARA EVITAR KEYERROR) ---
@st.cache_data(ttl=300)
def load_data(aba_nome):
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["gsheet_url"])
        df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
        # Limpa espaços e coloca tudo em minúsculas para evitar erros de leitura
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df.fillna("")
    except Exception as e:
        return pd.DataFrame()

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

# --- 3. FUNÇÃO DO PDF ---
def gerar_pdf_escala_dia(data_str, df_original):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    def clean(txt): return str(txt).encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, clean("POSTO TERRITORIAL DE VILA NOVA DE FAMALICÃO"), ln=True)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 10, clean(f"ESCALA DE SERVIÇO PARA O DIA {data_str.upper()}"), border="B", ln=True, align='C')
    pdf.ln(4)

    # Filtros baseados nas colunas normalizadas (minúsculas com underscore)
    servicos = df_original['serviço'].str.lower()
    df_aus = df_original[servicos.str.contains("férias|licença|doente|folga", na=False)]
    df_adm = df_original[servicos.str.contains("pronto|secretaria|inquérito|comando|diligência|tribunal", na=False)]
    df_at = df_original[servicos.str.contains("atendimento", na=False) & ~servicos.str.contains("apoio", na=False)]
    df_apoi = df_original[servicos.str.contains("apoio", na=False)]
    df_pat = df_original[servicos.str.contains("po|patrulha|ronda|vtr|auto|expediente", na=False) & ~servicos.str.contains("atendimento|apoio", na=False)]
    df_remu = df_original[servicos.str.contains("remu|grat", na=False)]

    # Cabeçalho Lateral
    y_topo = pdf.get_y()
    pdf.set_font("Arial", "B", 8); pdf.set_fill_color(240, 240, 240)
    pdf.cell(92, 6, clean(" AUSÊNCIAS E FOLGAS"), 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    if not df_aus.empty:
        ag_aus = df_aus.groupby('serviço')['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_aus.iterrows():
            pdf.multi_cell(92, 4, clean(f" {r['serviço'].upper()}: {r['id_disp']}"), border='LR', align='L')
    pdf.cell(92, 1, "", border='T', ln=1)

    pdf.set_xy(107, y_topo)
    pdf.set_font("Arial", "B", 8); pdf.cell(93, 6, clean(" OUTRAS SITUAÇÕES / ADM"), 1, 1, 'L', True)
    pdf.set_font("Arial", "", 7)
    if not df_adm.empty:
        ag_adm = df_adm.groupby(['serviço', 'horário'])['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag_adm.iterrows():
            pdf.set_x(107); pdf.multi_cell(93, 4, clean(f" {r['serviço'].upper()} ({r['horário']}): {r['id_disp']}"), border='LR', align='L')
    pdf.set_x(107); pdf.cell(93, 1, "", border='T', ln=1)
    
    pdf.set_y(pdf.get_y() + 5)

    # Patrulhas
    pdf.set_font("Arial", "B", 8); pdf.cell(0, 6, clean(" PATRULHAS E POLICIAMENTO"), 1, 1, 'L', True)
    if not df_pat.empty:
        pdf.set_font("Arial", "", 7)
        for _, r in df_pat.iterrows():
            pdf.cell(0, 5, clean(f"{r['horário']} - {r['serviço'].upper()} - {r['id_disp']} ({r['viatura']})"), 1, 1, 'L')

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 4. INTERFACE ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
    u = st.text_input("Email").strip().lower()
    p = st.text_input("Password", type="password")
    if st.button("ENTRAR", use_container_width=True):
        df_u = load_data("utilizadores")
        user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
        if not user.empty:
            st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}", "user_email": u, "is_admin": u in ADMINS})
            st.rerun()
else:
    df_trocas = load_data("registos_trocas")
    df_util = load_data("utilizadores")
    menu_opt = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state.get("is_admin"): menu_opt.extend(["⚖️ Validar Trocas", "📜 Trocas Validadas"])
    menu_opt.append("👥 Efetivo")

    with st.sidebar:
        st.write(f"👮‍♂️ **{st.session_state['user_nome']}**")
        menu = st.radio("MENU", menu_opt)
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hj = datetime.now(); u_at = str(st.session_state['user_id'])
        for i in range(8):
            dt = hj + timedelta(days=i); d_s = dt.strftime('%d/%m/%Y'); lbl = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            tr_v = df_trocas[(df_trocas['data'] == d_s) & (df_trocas['status'] == 'aprovada')] if not df_trocas.empty else pd.DataFrame()
            filtro_eu = tr_v[(tr_v['id_origem'].astype(str) == u_at) | (tr_v['id_destino'].astype(str) == u_at)] if not tr_v.empty else pd.DataFrame()
            
            if not filtro_eu.empty:
                t = filtro_eu.iloc[0]; s_ex = t['servico_destino'] if str(t['id_origem']) == u_at else t['servico_origem']
                st.markdown(f'<div class="card-servico card-troca"><b>{lbl}</b><br><h3>{s_ex}</h3><p>🔄 Troca Aprovada</p></div>', unsafe_allow_html=True)
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    meus = df_d[df_d['id'].astype(str) == u_at]
                    for _, m in meus.iterrows():
                        st.markdown(f'<div class="card-servico card-meu"><b>{lbl}</b><br><h3>{m["serviço"]}</h3>🕒 {m["horário"]}</div>', unsafe_allow_html=True)

    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        d_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_at_v = df_dia.copy(); df_at_v['id_disp'] = df_at_v['id'].astype(str)
            st.download_button("📥 Baixar PDF", gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at_v), file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf", use_container_width=True)

            def mostrar_sec(tit, keys, df_f, remover=True):
                p = '|'.join(keys).lower()
                temp = df_f[df_f['serviço'].str.lower().str.contains(p, na=False)].copy()
                if not temp.empty:
                    with st.expander(f"🔹 {tit.upper()}", expanded=True):
                        ag = temp.groupby(['serviço', 'horário'], sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(ag.rename(columns={'id_disp': 'Militar(es)'}), use_container_width=True, hide_index=True)
                return df_f[~df_f.index.isin(temp.index)] if remover else df_f

            df_r = df_at_v.copy()
            df_fol = df_r[df_r['serviço'].str.lower().str.contains("folga", na=False)].copy()
            df_aus = df_r[df_r['serviço'].str.lower().str.contains("férias|licença|doente", na=False)].copy()
            df_r = df_r[~df_r.index.isin(df_fol.index) & ~df_r.index.isin(df_aus.index)]

            df_r = mostrar_sec("Comando e Adm", ["pronto", "secretaria", "inquérito", "comando"], df_r)
            df_r = mostrar_sec("Atendimento", ["atendimento"], df_r)
            df_r = mostrar_sec("Apoio ao Atendimento", ["apoio"], df_r)
            df_r = mostrar_sec("Patrulhas", ["po", "patrulha", "ronda", "vtr", "auto", "expediente"], df_r)
            mostrar_sec("Remunerados", ["remu", "grat"], df_r, remover=False)

            if not df_fol.empty:
                with st.expander("🔹 FOLGAS", expanded=True):
                    df_fs = df_fol[df_fol['serviço'].str.lower().str.contains("semanal|fs", na=False)]
                    df_fc = df_fol[df_fol['serviço'].str.lower().str.contains("complementar|fc", na=False)]
                    if not df_fs.empty: st.write(f"**Folga Semanal:** {', '.join(df_fs['id_disp'].tolist())}")
                    if not df_fc.empty: st.write(f"**Folga Complementar:** {', '.join(df_fc['id_disp'].tolist())}")
            if not df_aus.empty:
                with st.expander("🔹 AUSÊNCIAS", expanded=False):
                    st.dataframe(df_aus.groupby('serviço')['id_disp'].apply(lambda x: ', '.join(x)).reset_index(), use_container_width=True, hide_index=True)

    elif menu == "📜 Trocas Validadas":
        st.title("📜 Trocas Validadas")
        if not df_trocas.empty:
            # Seleciona apenas as colunas que existem de forma segura
            aprov = df_trocas[df_trocas['status'].str.lower() == 'aprovada'].copy()
            if not aprov.empty:
                cols_para_mostrar = [c for c in ['data', 'id_origem', 'servico_origem', 'id_destino', 'servico_destino', 'validador_comando'] if c in aprov.columns]
                st.dataframe(aprov[cols_para_mostrar].sort_values('data', ascending=False), use_container_width=True, hide_index=True)
            else: st.info("Sem trocas aprovadas.")

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca")
        dt_s = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_data(dt_s.strftime("%d-%m"))
        if not df_d.empty:
            meus = df_d[df_d['id'].astype(str) == str(st.session_state['user_id'])]
            if not meus.empty:
                meu_sel = st.selectbox("Teu serviço:", meus.apply(lambda x: f"{x['serviço']} ({x['horário']})", axis=1).tolist())
                outros = df_d[(df_d['id'].astype(str) != str(st.session_state['user_id'])) & (~df_d['serviço'].str.lower().str.contains('|'.join(IMPEDIMENTOS), na=False))]
                alvo = st.selectbox("Trocar com:", outros.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist())
                if st.button("ENVIAR"):
                    id_d = alvo.split(" - ")[0]; em_d = df_util[df_util['id'].astype(str) == id_d]['email'].values[0]
                    salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_sel, id_d, alvo.split(" - ", 1)[1], "Pendente_Militar", em_d])
                    st.success("Pedido Enviado!")

    elif menu == "📥 Pedidos Recebidos":
        st.title("📥 Pedidos Recebidos")
        m = df_trocas[(df_trocas['status'].str.lower() == 'pendente_militar') & (df_trocas['id_destino'].astype(str) == str(st.session_state['user_id']))]
        for idx, r in m.iterrows():
            st.warning(f"{r['data']}: {r['id_origem']} quer trocar {r['servico_origem']} por {r['servico_destino']}")
            if st.button("✅ ACEITAR", key=f"acc_{idx}"): atualizar_status_gsheet(idx, "Pendente_Admin"); st.rerun()

    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validar Trocas")
        for idx, r in df_trocas[df_trocas['status'].str.lower() == 'pendente_admin'].iterrows():
            st.info(f"{r['data']}: {r['id_origem']} ↔️ {r['id_destino']}")
            if st.button("✔️ APROVAR", key=f"v_{idx}"): atualizar_status_gsheet(idx, "Aprovada", st.session_state['user_nome']); st.rerun()

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        st.dataframe(df_util[['id', 'nim', 'posto', 'nome', 'telemóvel', 'email']], use_container_width=True, hide_index=True)
        
