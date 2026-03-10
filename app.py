import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="GNR - Portal de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 2. ESTILOS CSS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

/* --- App Background --- */
.stApp { background-color: #F0F2F6 !important; }

/* --- Sidebar --- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A2B4A 0%, #243B5C 60%, #1E3A8A 100%) !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * { color: #E8EDF5 !important; }
[data-testid="stSidebar"] .stRadio label { 
    font-size: 0.88rem !important; 
    padding: 4px 0 !important;
}
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }

/* --- Títulos --- */
h1 { color: #1A2B4A !important; font-weight: 800 !important; font-size: 1.8rem !important; }
h2 { color: #1A2B4A !important; font-weight: 700 !important; }
h3 { color: #243B5C !important; font-weight: 600 !important; }

/* --- Botões --- */
.stButton > button {
    background: #1A2B4A !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 6px rgba(26,43,74,0.25) !important;
}
.stButton > button:hover {
    background: #243B5C !important;
    box-shadow: 0 4px 12px rgba(26,43,74,0.35) !important;
    transform: translateY(-1px) !important;
}

/* --- Cards de Serviço --- */
.card-servico {
    background: #FFFFFF;
    padding: 16px 20px;
    border-radius: 12px;
    border-left: 5px solid #94A3B8;
    margin-bottom: 12px;
    color: #1E293B;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    transition: box-shadow 0.2s ease;
}
.card-meu {
    border-left-color: #1E3A8A !important;
    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
}
.card-troca {
    border-left-color: #D97706 !important;
    background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%) !important;
}
.card-servico h3 { font-size: 1.1rem !important; margin: 4px 0 !important; }
.card-servico p  { margin: 2px 0 !important; font-size: 0.88rem !important; color: #475569; }

/* --- Badge de utilizador na sidebar --- */
.user-badge {
    background: rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.user-badge .nome { font-weight: 700; font-size: 0.95rem; color: #FFFFFF !important; }
.user-badge .id   { font-size: 0.78rem; color: #94A3B8 !important; margin-top: 2px; }
.user-badge .role { font-size: 0.72rem; background: #1E3A8A; color: #93C5FD !important;
                    padding: 2px 8px; border-radius: 20px; display: inline-block; margin-top: 4px; }

/* --- Login Page --- */
.login-header {
    text-align: center;
    padding: 30px 0 20px 0;
}
.login-header .escudo { font-size: 4rem; display: block; }
.login-header h1 { font-size: 1.6rem !important; color: #1A2B4A !important; margin: 8px 0 4px 0 !important; }
.login-header p  { color: #64748B; font-size: 0.88rem; margin: 0; }
.login-box {
    background: white;
    border-radius: 16px;
    padding: 32px 36px;
    box-shadow: 0 8px 30px rgba(26,43,74,0.12);
    border: 1px solid #E2E8F0;
}

/* --- Métricas e expanders --- */
[data-testid="stMetricValue"] { color: #1A2B4A !important; font-weight: 700 !important; }
.streamlit-expanderHeader { font-weight: 600 !important; font-size: 0.9rem !important; }

/* --- Dataframe --- */
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; }

/* --- Divider --- */
hr { border-color: #E2E8F0 !important; }

/* --- Info / Warning / Success --- */
.stAlert { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. CONSTANTES
# ============================================================
ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]
IMPEDIMENTOS = ["férias", "licença", "doente", "diligência", "tribunal", "pronto", "secretaria", "inquérito"]
IMPEDIMENTOS_PATTERN = '|'.join(IMPEDIMENTOS).lower()

# ============================================================
# 4. FUNÇÕES DE DADOS
# ============================================================
@st.cache_resource
def get_gsheet_client():
    """Cria o cliente gspread uma única vez e reutiliza (cache_resource)."""
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {e}")
        return None

@st.cache_data(ttl=300)
def load_data(aba_nome: str) -> pd.DataFrame:
    """Carrega dados de uma aba da Google Sheet com cache de 5 minutos."""
    try:
        client = get_gsheet_client()
        if client is None:
            return pd.DataFrame()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        records = sh.worksheet(aba_nome).get_all_records()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records).astype(str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except Exception:
        return pd.DataFrame()

def atualizar_status_gsheet(index_linha: int, novo_status: str, admin_nome: str = "") -> bool:
    """Atualiza o status de uma troca na Google Sheet."""
    try:
        client = get_gsheet_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        row = index_linha + 2  # +1 cabeçalho, +1 índice base-0
        aba.update_cell(row, 6, novo_status)
        if admin_nome:
            dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            aba.update_cell(row, 8, admin_nome)
            aba.update_cell(row, 9, dt_agora)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
        return False

def salvar_troca_gsheet(linha: list) -> bool:
    """Adiciona uma nova linha de troca na Google Sheet."""
    try:
        client = get_gsheet_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao guardar: {e}")
        return False

# ============================================================
# 5. FUNÇÕES PDF
# ============================================================
def s(txt) -> str:
    """Remove acentos e caracteres especiais para compatibilidade com fpdf/latin-1."""
    import unicodedata
    return unicodedata.normalize('NFKD', str(txt)).encode('latin-1', 'ignore').decode('latin-1')

def gerar_pdf_troca(dados: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(26, 43, 74)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 30, "GNR - Comprovativo de Troca de Servico", 0, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.set_font("Arial", "", 11)
    texto = (
        f"Certifica-se que o militar {s(dados['nome_origem'])} (ID {s(dados['id_origem'])}), "
        f"requereu a troca do servico '{s(dados['serv_orig'])}' pelo servico '{s(dados['serv_dest'])}' "
        f"do militar {s(dados['nome_destino'])} (ID {s(dados['id_destino'])}), para o dia {s(dados['data'])}.\n\n"
        f"O pedido foi aceite pelo militar de destino e validado superiormente por "
        f"{s(dados['validador'])} no dia {s(dados['data_val'])}."
    )
    pdf.multi_cell(190, 8, texto)
    pdf.ln(15)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 0, 'R')
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_pdf_escala_dia(data: str, df_raw: pd.DataFrame) -> bytes:
    """Gera PDF da escala diária com layout fiel ao modelo oficial, em A4 paisagem."""

    # --- helpers internos ---
    def set_header_row(pdf, cols, widths, h=6):
        pdf.set_font("Arial", "B", 7)
        pdf.set_fill_color(30, 58, 138)   # azul escuro GNR
        pdf.set_text_color(255, 255, 255)
        for col, w in zip(cols, widths):
            pdf.cell(w, h, col, 1, 0, 'C', True)
        pdf.ln(h)
        pdf.set_text_color(0, 0, 0)

    def data_row(pdf, vals, widths, h=5, fill=False):
        pdf.set_font("Arial", "", 7)
        if fill:
            pdf.set_fill_color(235, 240, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        for val, w in zip(vals, widths):
            pdf.cell(w, h, s(val), 1, 0, 'C', fill)
        pdf.ln(h)

    def section_title(pdf, titulo, width=277):
        pdf.set_font("Arial", "B", 7.5)
        pdf.set_fill_color(200, 210, 235)
        pdf.set_text_color(15, 40, 100)
        pdf.cell(width, 5.5, f"  {titulo.upper()}", 1, 1, 'L', True)
        pdf.set_text_color(0, 0, 0)

    # --- separar grupos ---
    def grupo(pattern):
        return df_raw[df_raw['serviço'].str.lower().str.contains(pattern, na=False)].copy()

    df_pat   = grupo(r'po\d|patrulha|ronda|vtr')
    df_aten  = grupo(r'atendimento')
    df_apoio = grupo(r'apoio')
    df_pron  = grupo(r'pronto')
    df_sec   = grupo(r'secretaria')
    df_inq   = grupo(r'inqu')
    df_grat  = grupo(r'remu|grat')
    df_folga = grupo(r'folga')
    df_lic   = grupo(r'ferias|licen|doente|dilig|tribunal')
    ids_usados = set().union(
        *[set(d['id']) for d in [df_pat, df_aten, df_apoio, df_pron,
                                  df_sec, df_inq, df_grat, df_folga, df_lic]]
    )
    df_outros = df_raw[~df_raw['id'].isin(ids_usados)].copy()

    # --- iniciar PDF A4 paisagem ---
    pdf = FPDF(orientation='L', format='A4')
    pdf.set_margins(8, 8, 8)
    pdf.add_page()
    W = 277  # largura útil (297 - 2*8 - folga)

    # ===================== CABEÇALHO =====================
    # Faixa azul principal
    pdf.set_fill_color(20, 46, 100)
    pdf.rect(8, 8, W, 14, 'F')
    pdf.set_xy(8, 8)
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(W, 7, "POSTO TERRITORIAL DE VILA NOVA DE FAMALICAO", 0, 1, 'C')
    pdf.set_x(8)
    pdf.set_font("Arial", "B", 9)

    # Calcular dia da semana
    try:
        dt_obj = datetime.strptime(data, "%d/%m/%Y")
        dias_pt = ["Segunda-feira","Terca-feira","Quarta-feira","Quinta-feira",
                   "Sexta-feira","Sabado","Domingo"]
        meses_pt = ["","Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        data_ext = f"{dias_pt[dt_obj.weekday()]}  |  {dt_obj.day} de {meses_pt[dt_obj.month]} de {dt_obj.year}"
    except Exception:
        data_ext = data

    pdf.cell(W, 7, f"ESCALA DE SERVICO  -  {data_ext}", 0, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # ===================== LAYOUT 2 COLUNAS =====================
    # Coluna esquerda: patrulhas + atendimento + apoio
    # Coluna direita: pronto/secretaria/inquéritos + gratificados + situações
    col1_x = 8
    col2_x = 8 + W // 2 + 2
    col_w  = W // 2 - 2

    y_start = pdf.get_y()

    # ---------- COLUNA ESQUERDA ----------
    pdf.set_xy(col1_x, y_start)

    # PATRULHAS
    if not df_pat.empty:
        pdf.set_x(col1_x)
        section_title(pdf, "Patrulhas", col_w)
        set_header_row(pdf, ["Servico","Horario","Militares","Viatura","Radio","Indicativo"], 
                       [28, 22, 40, 22, 18, col_w-130])
        fill = False
        for _, r in df_pat.iterrows():
            pdf.set_x(col1_x)
            data_row(pdf, [
                r['serviço'], r['horário'], r['id_disp'],
                r.get('viatura',''), r.get('rádio',''), r.get('indicativo rádio','')
            ], [28, 22, 40, 22, 18, col_w-130], fill=fill)
            fill = not fill
        pdf.ln(1)

    # ATENDIMENTO
    if not df_aten.empty:
        pdf.set_x(col1_x)
        section_title(pdf, "Atendimento", col_w)
        set_header_row(pdf, ["Horario","Militares"], [22, col_w-22])
        fill = False
        for _, r in df_aten.iterrows():
            pdf.set_x(col1_x)
            data_row(pdf, [r['horário'], r['id_disp']], [22, col_w-22], fill=fill)
            fill = not fill
        pdf.ln(1)

    # APOIO
    if not df_apoio.empty:
        pdf.set_x(col1_x)
        section_title(pdf, "Apoio", col_w)
        set_header_row(pdf, ["Horario","Militares"], [22, col_w-22])
        fill = False
        for _, r in df_apoio.iterrows():
            pdf.set_x(col1_x)
            data_row(pdf, [r['horário'], r['id_disp']], [22, col_w-22], fill=fill)
            fill = not fill
        pdf.ln(1)

    # OUTROS
    if not df_outros.empty:
        pdf.set_x(col1_x)
        section_title(pdf, "Outros Servicos", col_w)
        set_header_row(pdf, ["Servico","Horario","Militares"], [40, 22, col_w-62])
        fill = False
        for _, r in df_outros.iterrows():
            pdf.set_x(col1_x)
            data_row(pdf, [r['serviço'], r['horário'], r['id_disp']], [40, 22, col_w-62], fill=fill)
            fill = not fill

    y_after_col1 = pdf.get_y()

    # ---------- COLUNA DIREITA ----------
    pdf.set_xy(col2_x, y_start)

    def right_section(titulo, df_s, cols, widths):
        pdf.set_x(col2_x)
        section_title(pdf, titulo, col_w)
        set_header_row(pdf, cols, widths)
        fill = False
        for _, r in df_s.iterrows():
            pdf.set_x(col2_x)
            vals = []
            for c in cols:
                mapping = {'Servico': 'serviço', 'Horario': 'horário',
                           'Militares': 'id_disp', 'Viatura': 'viatura',
                           'Radio': 'rádio', 'Obs': 'observações'}
                key = mapping.get(c, c.lower())
                vals.append(r.get(key, ''))
            data_row(pdf, vals, widths, fill=fill)
            fill = not fill
        pdf.ln(1)

    # PRONTO
    if not df_pron.empty:
        right_section("Pronto", df_pron, ["Militares"], [col_w])

    # SECRETARIA
    if not df_sec.empty:
        right_section("Secretaria", df_sec, ["Horario","Militares"], [22, col_w-22])

    # INQUÉRITOS
    if not df_inq.empty:
        right_section("Inqueritos", df_inq, ["Militares"], [col_w])

    # GRATIFICADOS
    if not df_grat.empty:
        right_section("Gratificados / Remunerados", df_grat,
                      ["Servico","Horario","Militares"], [45, 22, col_w-67])

    # FOLGAS
    if not df_folga.empty:
        pdf.set_x(col2_x)
        section_title(pdf, "Folgas", col_w)
        ag_folga = df_folga.groupby('serviço', sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        set_header_row(pdf, ["Tipo","Militares"], [30, col_w-30])
        fill = False
        for _, r in ag_folga.iterrows():
            pdf.set_x(col2_x)
            data_row(pdf, [r['serviço'], r['id_disp']], [30, col_w-30], fill=fill)
            fill = not fill
        pdf.ln(1)

    # AUSÊNCIAS / LICENÇAS
    if not df_lic.empty:
        pdf.set_x(col2_x)
        section_title(pdf, "Ausencias / Licencas / Impedimentos", col_w)
        ag_lic = df_lic.groupby('serviço', sort=False)['id_disp'].apply(lambda x: ', '.join(x)).reset_index()
        set_header_row(pdf, ["Situacao","Militares"], [35, col_w-35])
        fill = False
        for _, r in ag_lic.iterrows():
            pdf.set_x(col2_x)
            data_row(pdf, [r['serviço'], r['id_disp']], [35, col_w-35], fill=fill)
            fill = not fill

    y_after_col2 = pdf.get_y()

    # ===================== OBSERVAÇÕES =====================
    y_obs = max(y_after_col1, y_after_col2) + 2
    pdf.set_xy(8, y_obs)
    section_title(pdf, "Observacoes", W)
    pdf.set_font("Arial", "", 6.5)
    pdf.set_fill_color(255, 255, 240)
    # Agregar todas as observações não vazias
    obs_unicas = df_raw[df_raw.get('observações', pd.Series(dtype=str)).str.strip().str.len() > 0]['observações'].unique() if 'observações' in df_raw.columns else []
    obs_txt = "  |  ".join([s(o) for o in obs_unicas]) if len(obs_unicas) > 0 else "Sem observacoes."
    pdf.multi_cell(W, 4.5, obs_txt, 1, 'L', True)

    # ===================== RODAPÉ =====================
    pdf.set_xy(8, 195)
    pdf.set_font("Arial", "I", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(W//2, 5, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 0, 'L')
    pdf.cell(W//2, 5, "O COMANDANTE", 0, 0, 'R')

    return pdf.output(dest='S').encode('latin-1', 'replace')

# ============================================================
# 6. HELPERS UI
# ============================================================
def get_nome_militar(df_util: pd.DataFrame, id_m) -> str:
    res = df_util[df_util['id'].astype(str) == str(id_m)]
    return f"{res.iloc[0]['posto']} {res.iloc[0]['nome']}" if not res.empty else f"ID {id_m}"

def filtrar_secao(keys: list, df_f: pd.DataFrame) -> tuple:
    """Filtra linhas pelo padrão de keys. Devolve (df_secção, df_restante)."""
    pattern = '|'.join(k for k in keys if k).lower()
    if not pattern:
        return pd.DataFrame(), df_f
    mask = df_f['serviço'].str.lower().str.contains(pattern, na=False)
    return df_f[mask].copy(), df_f[~mask].copy()

def mostrar_secao(titulo: str, df_sec: pd.DataFrame, mostrar_extras: bool = False):
    """Renderiza uma secção da escala num expander."""
    if df_sec.empty:
        return
    with st.expander(f"🔹 {titulo.upper()}", expanded=True):
        cols_ag = ['serviço', 'horário']
        if mostrar_extras:
            agg_dict: dict = {'id_disp': lambda x: ', '.join(x)}
            for col in ['viatura', 'rádio', 'indicativo rádio', 'observações']:
                if col in df_sec.columns:
                    agg_dict[col] = lambda x: ', '.join(x.dropna().unique())
            ag = df_sec.groupby(cols_ag, sort=False).agg(agg_dict).reset_index()
        else:
            ag = df_sec.groupby(cols_ag, sort=False)['id_disp'] \
                       .apply(lambda x: ', '.join(x)).reset_index()
        st.dataframe(
            ag.rename(columns={'id_disp': 'Militar'}),
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# 7. LOGIN
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("""
        <div class="login-box">
            <div class="login-header">
                <span class="escudo">🚓</span>
                <h1>Portal de Escalas</h1>
                <p>Guarda Nacional Republicana</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.container():
            with st.form("login", clear_on_submit=False):
                st.markdown("<br>", unsafe_allow_html=True)
                u = st.text_input("📧 Email institucional", placeholder="utilizador@gnr.pt").strip().lower()
                p = st.text_input("🔒 Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                entrar = st.form_submit_button("ENTRAR", use_container_width=True)
                if entrar:
                    if not u or not p:
                        st.warning("Preenche o email e a password.")
                    else:
                        df_u = load_data("utilizadores")
                        user = df_u[
                            (df_u['email'].str.lower() == u) &
                            (df_u['password'] == p)
                        ]
                        if not user.empty:
                            st.session_state.update({
                                "logged_in":  True,
                                "user_id":    str(user.iloc[0]['id']),
                                "user_nome":  f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                                "user_email": u,
                                "is_admin":   u in ADMINS,
                            })
                            st.rerun()
                        else:
                            st.error("❌ Email ou password incorretos.")

# ============================================================
# 8. APP PRINCIPAL (pós-login)
# ============================================================
else:
    # Carregar dados globais uma vez por sessão de render
    df_trocas = load_data("registos_trocas")
    df_util   = load_data("utilizadores")

    u_id      = str(st.session_state['user_id'])
    u_nome    = st.session_state['user_nome']
    is_admin  = st.session_state.get("is_admin", False)

    # --- Sidebar ---
    with st.sidebar:
        # Badge do utilizador
        role_label = "⭐ Administrador" if is_admin else "👮 Militar"
        st.markdown(f"""
        <div class="user-badge">
            <div class="nome">👤 {u_nome}</div>
            <div class="id">ID: {u_id}</div>
            <div class="role">{role_label}</div>
        </div>
        """, unsafe_allow_html=True)

        # Contador de pedidos pendentes
        if not df_trocas.empty:
            n_pendentes = len(df_trocas[
                (df_trocas['status'] == 'Pendente_Militar') &
                (df_trocas['id_destino'].astype(str) == u_id)
            ])
            n_admin = len(df_trocas[df_trocas['status'] == 'Pendente_Admin']) if is_admin else 0

            if n_pendentes > 0:
                st.warning(f"🔔 {n_pendentes} pedido(s) de troca por responder")
            if n_admin > 0:
                st.warning(f"⚖️ {n_admin} troca(s) aguardam validação")

        st.markdown("---")

        menu_opt = [
            "📅 Minha Escala",
            "🔍 Escala Geral",
            "🔄 Solicitar Troca",
            "📥 Pedidos Recebidos",
        ]
        if is_admin:
            menu_opt += ["⚖️ Validar Trocas", "📜 Trocas Validadas"]
        menu_opt.append("👥 Efetivo")

        menu = st.radio("MENU", menu_opt, label_visibility="collapsed")

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # ============================================================
    # PÁGINAS
    # ============================================================

    # --- 📅 MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 A Minha Escala")
        st.caption(f"Toda a escala disponível a partir de hoje para **{u_nome}**")
        hj = datetime.now()

        # Percorre dias a partir de hoje até não encontrar mais abas com dados
        dias_sem_dados = 0
        i = 0
        encontrou_algum = False

        while dias_sem_dados < 5:  # Para após 5 dias consecutivos sem dados
            dt  = hj + timedelta(days=i)
            d_s = dt.strftime('%d/%m/%Y')
            lbl = "🟢 HOJE" if i == 0 else ("🔵 AMANHÃ" if i == 1 else dt.strftime("%d/%m (%a)").upper())

            # Verificar trocas aprovadas
            if not df_trocas.empty:
                tr_v = df_trocas[
                    (df_trocas['data'] == d_s) &
                    (df_trocas['status'] == 'Aprovada') &
                    ((df_trocas['id_origem'].astype(str) == u_id) |
                     (df_trocas['id_destino'].astype(str) == u_id))
                ]
            else:
                tr_v = pd.DataFrame()

            if not tr_v.empty:
                t = tr_v.iloc[0]
                if str(t['id_origem']) == u_id:
                    s_ex, era, com = t['servico_destino'], t['servico_origem'], t['id_destino']
                else:
                    s_ex, era, com = t['servico_origem'], t['servico_destino'], t['id_origem']
                st.markdown(
                    f'<div class="card-servico card-troca">'
                    f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#92400E;">Troca Aprovada</span></p>'
                    f'<h3>🔄 {s_ex}</h3>'
                    f'<p>↩️ Serviço original: {era}</p>'
                    f'<p>👤 Trocado com ID: {com}</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                dias_sem_dados = 0
                encontrou_algum = True
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    m = df_d[df_d['id'].astype(str) == u_id]
                    if not m.empty:
                        row = m.iloc[0]
                        st.markdown(
                            f'<div class="card-servico card-meu">'
                            f'<p><b>{lbl}</b></p>'
                            f'<h3>🛡️ {row["serviço"]}</h3>'
                            f'<p>🕒 {row["horário"]}</p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        encontrou_algum = True
                    # Aba existe mas o militar não está escalado — não conta como "sem dados"
                    dias_sem_dados = 0
                else:
                    dias_sem_dados += 1

            i += 1

        if not encontrou_algum:
            st.info("Não foram encontrados serviços escalados a partir de hoje.")

    # --- 🔍 ESCALA GERAL ---
    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        d_sel  = st.date_input("Seleciona a data:", format="DD/MM/YYYY")
        df_dia = load_data(d_sel.strftime("%d-%m"))

        if df_dia.empty:
            st.info("Não existem dados para esta data.")
        else:
            df_at = df_dia.copy()
            df_at['id_disp'] = df_at['id'].astype(str)

            # Aplicar trocas aprovadas
            if not df_trocas.empty:
                tr_v = df_trocas[
                    (df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) &
                    (df_trocas['status'] == 'Aprovada')
                ]
                for _, t in tr_v.iterrows():
                    m_o = df_at['id'].astype(str) == str(t['id_origem'])
                    if m_o.any():
                        df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                    m_d = df_at['id'].astype(str) == str(t['id_destino'])
                    if m_d.any():
                        df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"

            pdf_bytes = gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at)            col_pdf, _ = st.columns([1, 4])
            with col_pdf:
                st.download_button(
                    "📥 Descarregar PDF",
                    pdf_bytes,
                    file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf",
                    mime="application/pdf"
                )

            # Separar ausências primeiro
            df_aus, df_res = filtrar_secao(["férias", "licença", "doente", "diligência", "tribunal"], df_at)

            # Extrair cada grupo do df_res por ordem
            df_cmd,  df_res = filtrar_secao(["pronto", "secretaria", "inquérito"], df_res)
            df_aten, df_res = filtrar_secao(["atendimento", "apoio"],              df_res)
            df_pat,  df_res = filtrar_secao(["po", "patrulha", "ronda", "vtr"],   df_res)
            df_remu, df_res = filtrar_secao(["remu", "grat"],                      df_res)
            df_folga,df_res = filtrar_secao(["folga"],                             df_res)
            df_outros       = df_res  # o que sobrar são "Outros Serviços"

            mostrar_secao("Comando e Administrativos", df_cmd)
            mostrar_secao("Atendimento",               df_aten)
            mostrar_secao("Patrulhas",                 df_pat,    mostrar_extras=True)
            mostrar_secao("Outros Serviços",           df_outros)
            mostrar_secao("Remunerados",               df_remu,   mostrar_extras=True)
            mostrar_secao("Folga",                     df_folga)

            if not df_aus.empty:
                with st.expander("🔹 AUSENTES", expanded=True):
                    ag = df_aus.groupby(['serviço', 'horário'], sort=False)['id_disp'] \
                               .apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(ag, use_container_width=True, hide_index=True)

    # --- 🔄 SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca de Serviço")
        dt_s  = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_d  = load_data(dt_s.strftime("%d-%m"))

        if df_d.empty:
            st.info("Não existem dados para esta data.")
        else:
            meu = df_d[df_d['id'].astype(str) == u_id]
            if meu.empty:
                st.warning("Não tens serviço escalado neste dia.")
            else:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"📋 O teu serviço: **{meu_s}**")

                cols = df_d[
                    (df_d['id'].astype(str) != u_id) &
                    (~df_d['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False))
                ]

                if cols.empty:
                    st.warning("Não há militares disponíveis para troca neste dia.")
                else:
                    opts = cols.apply(
                        lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1
                    ).tolist()
                    with st.form("tr"):
                        alvo = st.selectbox("👤 Trocar com:", opts)
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("📨 ENVIAR PEDIDO", use_container_width=True):
                            id_d = alvo.split(" - ")[0]
                            s_d  = alvo.split(" - ", 1)[1]
                            email_row = df_util[df_util['id'].astype(str) == id_d]
                            if email_row.empty:
                                st.error("Militar de destino não encontrado.")
                            else:
                                em_d = email_row['email'].values[0]
                                if salvar_troca_gsheet([
                                    dt_s.strftime('%d/%m/%Y'),
                                    u_id, meu_s,
                                    id_d, s_d,
                                    "Pendente_Militar", em_d
                                ]):
                                    st.success("✅ Pedido enviado com sucesso!")
                                    st.balloons()

    # --- 📥 PEDIDOS RECEBIDOS ---
    elif menu == "📥 Pedidos Recebidos":
        st.title("📥 Pedidos de Troca Recebidos")
        if df_trocas.empty:
            st.info("Sem dados de trocas.")
        else:
            m = df_trocas[
                (df_trocas['status'] == 'Pendente_Militar') &
                (df_trocas['id_destino'].astype(str) == u_id)
            ]
            if m.empty:
                st.success("✅ Não tens pedidos pendentes.")
            else:
                st.markdown(f"**{len(m)} pedido(s) aguardam a tua resposta:**")
                for idx, r in m.iterrows():
                    nome_orig = get_nome_militar(df_util, r['id_origem'])
                    st.markdown(
                        f'<div class="card-servico card-troca">'
                        f'<p><b>📅 {r["data"]}</b></p>'
                        f'<p>👤 <b>{nome_orig}</b> quer trocar contigo</p>'
                        f'<p>🟢 Recebes: <b>{r["servico_origem"]}</b></p>'
                        f'<p>🔴 Dás: <b>{r["servico_destino"]}</b></p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    c1, c2 = st.columns(2)
                    if c1.button("✅ ACEITAR", key=f"ac_{idx}", use_container_width=True):
                        atualizar_status_gsheet(idx, "Pendente_Admin")
                        st.rerun()
                    if c2.button("❌ RECUSAR", key=f"re_{idx}", use_container_width=True):
                        atualizar_status_gsheet(idx, "Recusada")
                        st.rerun()

    # --- ⚖️ VALIDAR TROCAS (ADMIN) ---
    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validação Superior de Trocas")
        if df_trocas.empty:
            st.info("Sem dados.")
        else:
            pnd = df_trocas[df_trocas['status'] == 'Pendente_Admin']
            if pnd.empty:
                st.success("✅ Não há trocas pendentes de validação.")
            else:
                st.markdown(f"**{len(pnd)} troca(s) aguardam validação:**")
                for idx, r in pnd.iterrows():
                    n_o = get_nome_militar(df_util, r['id_origem'])
                    n_d = get_nome_militar(df_util, r['id_destino'])
                    with st.expander(f"📅 {r['data']}  |  {n_o} ↔️ {n_d}", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**{n_o}**\n\n`{r['servico_origem']}`")
                        with col2:
                            st.success(f"**{n_d}**\n\n`{r['servico_destino']}`")
                        c1, c2 = st.columns(2)
                        if c1.button("✔️ VALIDAR",  key=f"ok_{idx}", use_container_width=True):
                            atualizar_status_gsheet(idx, "Aprovada",  u_nome)
                            st.rerun()
                        if c2.button("🚫 REJEITAR", key=f"no_{idx}", use_container_width=True):
                            atualizar_status_gsheet(idx, "Rejeitada", u_nome)
                            st.rerun()

    # --- 📜 HISTÓRICO DE TROCAS ---
    elif menu == "📜 Trocas Validadas":
        st.title("📜 Histórico de Trocas Aprovadas")
        if df_trocas.empty:
            st.info("Ainda não existem registos de trocas.")
        else:
            aprv = df_trocas[df_trocas['status'] == 'Aprovada']
            if aprv.empty:
                st.write("Não existem trocas validadas.")
            else:
                for idx, r in aprv.sort_index(ascending=False).iterrows():
                    n_o = get_nome_militar(df_util, r['id_origem'])
                    n_d = get_nome_militar(df_util, r['id_destino'])
                    with st.expander(f"📅 {r['data']}  |  {n_o} ↔️ {n_d}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Requerente:**\n\n{n_o}")
                            st.markdown(f"**Serviço original:**\n`{r['servico_origem']}`")
                        with col2:
                            st.success(f"**Substituto:**\n\n{n_d}")
                            st.markdown(f"**Serviço destino:**\n`{r['servico_destino']}`")
                        st.divider()
                        val_por = r.get('validador', 'N/A')
                        val_em  = r.get('data_validacao', 'N/A')
                        st.caption(f"⚖️ Validado por **{val_por}** em {val_em}")
                        dados_pdf = {
                            "data":         r['data'],
                            "id_origem":    r['id_origem'],   "nome_origem":  n_o,
                            "serv_orig":    r['servico_origem'],
                            "id_destino":   r['id_destino'],  "nome_destino": n_d,
                            "serv_dest":    r['servico_destino'],
                            "validador":    val_por,          "data_val":     val_em,
                        }
                        st.download_button(
                            label="📥 Descarregar Guia de Troca",
                            data=gerar_pdf_troca(dados_pdf),
                            file_name=f"Guia_Troca_{r['data'].replace('/','-')}.pdf",
                            mime="application/pdf",
                            key=f"hist_pdf_{idx}"
                        )

    # --- 👥 EFETIVO ---
    elif menu == "👥 Efetivo":
        st.title("👥 Lista de Contactos")
        if df_util.empty:
            st.info("Sem dados.")
        else:
            # Pesquisa rápida
            pesq = st.text_input("🔍 Pesquisar por nome, posto ou ID:", placeholder="ex: Cabo, Ferreira...")
            df_show = df_util.copy()
            if pesq:
                p = pesq.lower()
                df_show = df_show[
                    df_show['nome'].str.lower().str.contains(p, na=False) |
                    df_show['posto'].str.lower().str.contains(p, na=False) |
                    df_show['id'].astype(str).str.contains(p, na=False)
                ]
            cols_show = [c for c in ['id','nim','posto','nome','telemóvel','email'] if c in df_show.columns]
            st.markdown(f"**{len(df_show)} militar(es) encontrado(s)**")
            st.dataframe(df_show[cols_show], use_container_width=True, hide_index=True)
            
