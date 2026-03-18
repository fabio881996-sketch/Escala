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
    initial_sidebar_state=st.session_state.get("sidebar_state", "expanded")
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
.card-rem {
    border-left-color: #059669 !important;
    background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%) !important;
}
.card-folga {
    border-left-color: #7C3AED !important;
    background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%) !important;
}
.card-ausencia {
    border-left-color: #64748B !important;
    background: linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 100%) !important;
}
.card-tribunal {
    border-left-color: #DC2626 !important;
    background: linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%) !important;
}
.card-servico h3 { font-size: 1.1rem !important; margin: 4px 0 !important; }
.card-servico p  { margin: 2px 0 !important; font-size: 0.88rem !important; color: #475569; }

/* --- Badge de utilizador na sidebar --- */
.user-badge {
    background: rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border: 1px solid rgba(255,255,255,0.08);
}
.user-badge .nome { font-weight: 700; font-size: 0.95rem; color: #FFFFFF !important; }
.user-badge .id   { font-size: 0.78rem; color: #94A3B8 !important; margin-top: 2px; }
.user-badge .role { font-size: 0.72rem; background: #1E3A8A; color: #93C5FD !important;
                    padding: 2px 8px; border-radius: 20px; display: inline-block; margin-top: 4px; }

/* --- Login Page --- */
.login-header {
    text-align: center;
    padding: 24px 0 16px 0;
}
.login-header .escudo {
    font-size: 3.8rem;
    display: block;
    filter: drop-shadow(0 4px 8px rgba(30,58,138,0.25));
}
.login-header h1 {
    font-size: 1.7rem !important;
    color: #1A2B4A !important;
    margin: 10px 0 6px 0 !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
}
.login-header .org-line {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 4px 0 2px 0;
}
.login-header .org-line::before,
.login-header .org-line::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, transparent, #CBD5E1);
}
.login-header .org-line::after {
    background: linear-gradient(to left, transparent, #CBD5E1);
}
.login-header .org-name {
    font-size: 0.82rem;
    color: #475569;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
}
.login-header .posto-name {
    font-size: 0.78rem;
    color: #64748B;
    margin: 0;
    letter-spacing: 0.02em;
}
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
IMPEDIMENTOS = ["férias", "licença", "doente", "diligência", "tribunal", "pronto", "secretaria", "inquérito", "remuner", "gratific"]
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

@st.cache_resource
def get_sheet():
    """Abre a Sheet uma única vez e reutiliza — evita open_by_url repetido."""
    client = get_gsheet_client()
    if client is None:
        return None
    return client.open_by_url(st.secrets["gsheet_url"])

def _df_from_records(records) -> pd.DataFrame:
    """Converte records para DataFrame normalizado.
    Se a coluna 'id' tiver múltiplos IDs separados por vírgula, expande para uma linha por ID."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).astype(str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.fillna("")
    if 'id' in df.columns:
        # Expandir linhas com múltiplos IDs (ex: "1089, 1162" → duas linhas)
        df['id'] = df['id'].str.split(r'[,;]')
        df = df.explode('id')
        df['id'] = df['id'].str.strip()
        df = df[df['id'] != ''].reset_index(drop=True)
    return df

@st.cache_data(ttl=120)
def load_data(aba_nome: str) -> pd.DataFrame:
    """Carrega dados de uma aba da Google Sheet com cache de 2 minutos."""
    try:
        sh = get_sheet()
        if sh is None:
            return pd.DataFrame()
        return _df_from_records(sh.worksheet(aba_nome).get_all_records())
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_utilizadores() -> pd.DataFrame:
    """Carrega utilizadores com cache de 60s — fresco o suficiente para PIN funcionar."""
    try:
        sh = get_sheet()
        if sh is None:
            return pd.DataFrame()
        return _df_from_records(sh.worksheet("utilizadores").get_all_records())
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_ferias(ano: int) -> pd.DataFrame:
    """Carrega plano de férias de um ano — cache 1h."""
    try:
        sh = get_sheet()
        if sh is None:
            return pd.DataFrame()
        ws = sh.worksheet(f"férias {ano}")
        valores = ws.get_all_values()
        if not valores or len(valores) < 2:
            return pd.DataFrame()
        headers = [str(h).strip() for h in valores[0]]
        df = pd.DataFrame(valores[1:], columns=headers)
        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def load_feriados(ano: int) -> list:
    """Carrega feriados de um ano da aba 'feriados' — cache 24h."""
    try:
        sh = get_sheet()
        if sh is None:
            return []
        ws = sh.worksheet("feriados")
        valores = ws.get_all_values()
        feriados = []
        for col in zip(*valores):
            col = [str(v).strip() for v in col if str(v).strip()]
            if not col:
                continue
            # Primeira linha é o ano
            try:
                ano_col = int(col[0])
            except:
                continue
            if ano_col != ano:
                continue
            for v in col[1:]:
                try:
                    feriados.append(datetime.strptime(v, '%d/%m/%Y').date())
                except:
                    pass
        return feriados
    except Exception:
        return []

def militar_de_ferias(u_id: str, data: date, df_ferias: pd.DataFrame) -> bool:
    """Verifica se um militar está de férias numa data."""
    if df_ferias.empty:
        return False
    cols = df_ferias.columns.tolist()
    ini_cols = [c for c in cols if 'ini' in c.lower()]
    fim_cols  = [c for c in cols if 'fim' in c.lower()]
    id_col = 'id' if 'id' in cols else cols[0]
    mil = df_ferias[df_ferias[id_col].astype(str).str.strip() == str(u_id).strip()]
    if mil.empty:
        return False
    for ini_c, fim_c in zip(ini_cols, fim_cols):
        for _, row in mil.iterrows():
            ini_s = str(row.get(ini_c, '')).strip()
            fim_s = str(row.get(fim_c, '')).strip()
            if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan':
                continue
            try:
                ini_d = datetime.strptime(ini_s, '%d/%m/%Y').date()
                fim_d = datetime.strptime(fim_s, '%d/%m/%Y').date()
                if ini_d <= data <= fim_d:
                    return True
            except:
                pass
    return False



import unicodedata as _ud3

@st.cache_data(ttl=86400)
def contar_servicos_historico(alvo_id_c: str, sheet_id_c: str) -> pd.DataFrame:
    """Conta serviços históricos de um militar — cache 24h."""
    def _n3(t): return _ud3.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(sheet_id_c)
        abas = sh.worksheets()
        resultados = []
        hoje = datetime.now()
        for aba in abas:
            titulo = aba.title
            partes = titulo.split("-")
            if len(partes) != 2 or not all(p.isdigit() for p in partes):
                continue
            try:
                dados = aba.get_all_records()
                df_aba = pd.DataFrame(dados)
                if df_aba.empty or 'id' not in df_aba.columns:
                    continue
                mil_rows = df_aba[df_aba['id'].astype(str).str.strip() == alvo_id_c]
                for _, row in mil_rows.iterrows():
                    serv = str(row.get('serviço', '')).strip()
                    if not serv:
                        continue
                    mm = int(partes[1])
                    ano = hoje.year if mm <= hoje.month + 1 else hoje.year - 1
                    resultados.append({
                        'data': f"{partes[0]}/{partes[1]}/{ano}",
                        'mes': f"{partes[1]:>02}/{ano}",
                        'serviço': serv,
                        'tipo': _n3(serv)
                    })
            except Exception:
                continue
        return pd.DataFrame(resultados)
    except Exception:
        return pd.DataFrame()

ATENDIMENTO_PATTERN = r'atendimento|apoio'

def _parse_horario(hor: str):
    """Converte 'HH-HH' ou 'HH:MM-HH:MM' em (inicio_min, fim_min, passa_meia_noite).
    Valores relativos ao próprio dia. fim pode ser > 1440 se passa meia-noite."""
    try:
        hor = str(hor).strip()
        partes = hor.replace(':', '').split('-')
        if len(partes) != 2:
            return None, None
        def to_min(s):
            s = s.strip()
            if len(s) <= 2:
                return int(s) * 60
            return int(s[:-2]) * 60 + int(s[-2:])
        ini = to_min(partes[0])
        fim = to_min(partes[1])
        if fim == 0:
            fim = 1440  # 24 = meia-noite do dia seguinte
        if fim < ini:
            fim += 1440  # passa a meia-noite (ex: 18-02 → fim=1560)
        return ini, fim
    except Exception:
        return None, None

def _e_atendimento(serv: str) -> bool:
    import unicodedata as _u
    n = _u.normalize('NFKD', str(serv).lower()).encode('ascii','ignore').decode('ascii')
    return bool(__import__('re').search(ATENDIMENTO_PATTERN, n))

def verificar_descanso(militar_id: str, data: datetime, serv_novo: str, hor_novo: str, serv_orig_hor: str = "") -> tuple:
    """Verifica se o militar tem >= 8h de descanso entre o serviço novo e os adjacentes.
    serv_orig_hor: horário do serviço original que está a ser trocado (para excluir da verificação).
    Retorna (ok: bool, motivo: str).
    Exceção: se serviço novo OU adjacente for atendimento/apoio, permite sempre."""
    if _e_atendimento(serv_novo):
        return True, ""
    ini_novo, fim_novo = _parse_horario(hor_novo)
    if ini_novo is None:
        return True, ""  # não consegue validar, deixa passar

    MIN_DESCANSO = 6 * 60  # 480 minutos

    for delta, label in [(-1, "dia anterior"), (1, "dia seguinte")]:
        dt_adj = data + timedelta(days=delta)
        df_adj = load_data(dt_adj.strftime("%d-%m"))
        if df_adj.empty:
            continue
        rows = df_adj[df_adj['id'].astype(str).str.strip() == str(militar_id).strip()]
        for _, r in rows.iterrows():
            serv_adj = str(r.get('serviço', ''))
            hor_adj  = str(r.get('horário', ''))
            if not hor_adj.strip():
                continue
            # Excluir o próprio serviço que está a ser trocado
            if serv_orig_hor and hor_adj.strip() == serv_orig_hor.strip():
                continue
            if _e_atendimento(serv_adj):
                continue  # exceção — adjacente é atendimento/apoio
            import unicodedata as _ud_loc, re as _re_loc
            if _re_loc.search(r'remu|grat', _ud_loc.normalize('NFKD', serv_adj.lower()).encode('ascii','ignore').decode('ascii')):
                continue  # remunerados não contam para descanso
            ini_adj, fim_adj = _parse_horario(hor_adj)
            if ini_adj is None:
                continue

            if delta == -1:
                # serviço anterior acaba, novo começa
                fim_adj_rel = fim_adj - 1440
                descanso = ini_novo - fim_adj_rel
            else:
                # novo acaba, próximo começa
                ini_adj_rel = ini_adj + 1440
                descanso = ini_adj_rel - fim_novo

            if descanso < MIN_DESCANSO:
                horas = descanso // 60
                mins  = descanso % 60
                return False, (f"Apenas {horas}h{mins:02d}m de descanso face ao serviço do {label} "
                               f"({serv_adj} {hor_adj})")
    return True, ""

def verificar_descanso_troca(u_id, id_d, dt_s, meu_serv_nome, meu_hor_val, serv_d_nome, hor_d_val, df_dia,
                             df_anterior=None, df_seguinte=None):
    """Verifica se após a troca ambos os militares respeitam 8h de descanso.
    Usa linha de tempo absoluta em minutos (dia-1=0, dia=1440, dia+1=2880).
    Retorna lista de erros (vazia se tudo ok)."""
    import unicodedata as _ud_loc, re as _re_loc
    MIN = 6 * 60

    def _norm_serv(s):
        return _ud_loc.normalize('NFKD', str(s).lower()).encode('ascii','ignore').decode('ascii')
    def _e_rem(s):
        return bool(_re_loc.search(r'remu|grat', _norm_serv(s)))
    def _isento(s):
        return _e_atendimento(s) or _e_rem(s)

    def get_servicos_fixos(mil_id, hor_excluir):
        result = []
        for delta, offset, df_adj in [(-1, 0, df_anterior), (0, 1440, df_dia), (1, 2880, df_seguinte)]:
            if df_adj is None or df_adj.empty:
                continue
            rows = df_adj[df_adj['id'].astype(str).str.strip() == str(mil_id).strip()]
            for _, r in rows.iterrows():
                h = str(r.get('horário', '')).strip()
                s = str(r.get('serviço', ''))
                if not h:
                    continue
                # excluir o serviço que está a ser trocado
                if delta == 0 and h == hor_excluir.strip():
                    continue
                if _isento(s):
                    continue
                ini, fim = _parse_horario(h)
                if ini is None:
                    continue
                duracao = fim - ini  # duração em minutos (sempre positiva)
                ini_abs = ini + offset
                fim_abs = ini_abs + duracao
                result.append((ini_abs, fim_abs, s, h))
        return result

    def verificar_militar(mil_id, serv_novo, hor_novo, hor_excluir, label):
        """Verifica se serv_novo respeita 8h face a todos os serviços fixos."""
        if _isento(serv_novo):
            return []
        ini_novo, fim_novo = _parse_horario(hor_novo)
        if ini_novo is None:
            return []
        ini_novo_abs = ini_novo + 1440
        fim_novo_abs = ini_novo_abs + (fim_novo - ini_novo)

        fixos = get_servicos_fixos(mil_id, hor_excluir)
        msgs = []
        for ini_f, fim_f, s_f, h_f in fixos:
            # descanso entre fim do fixo e início do novo
            d1 = ini_novo_abs - fim_f
            # descanso entre fim do novo e início do fixo
            d2 = ini_f - fim_novo_abs
            # verificar transição fixo→novo
            if d1 < MIN and fim_f <= fim_novo_abs:  # fixo acaba antes do novo
                d1_real = max(0, d1)
                h2, m2 = d1_real // 60, d1_real % 60
                msgs.append(f"{label}: apenas {h2}h{m2:02d}m de descanso entre '{s_f} ({h_f})' e o serviço novo '{serv_novo} ({hor_novo})'")
            # verificar transição novo→fixo
            elif d2 < MIN and fim_novo_abs <= fim_f:  # novo acaba antes do fixo
                d2_real = max(0, d2)
                h2, m2 = d2_real // 60, d2_real % 60
                msgs.append(f"{label}: apenas {h2}h{m2:02d}m de descanso entre o serviço novo '{serv_novo} ({hor_novo})' e '{s_f} ({h_f})'")
        return msgs

    erros  = verificar_militar(u_id,  serv_d_nome,  hor_d_val,  meu_hor_val, "Não podes fazer esta troca")
    erros += verificar_militar(id_d,  meu_serv_nome, meu_hor_val, hor_d_val,  "O militar de destino não pode fazer esta troca")
    return erros

def atualizar_status_gsheet(index_linha: int, novo_status: str, admin_nome: str = "") -> bool:
    """Atualiza o status de uma troca na Google Sheet — batch update numa chamada."""
    try:
        sh = get_sheet()
        aba = sh.worksheet("registos_trocas")
        row = index_linha + 2  # +1 cabeçalho, +1 índice base-0
        if admin_nome:
            dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            # Batch: atualiza status, validador e data numa só chamada
            aba.batch_update([
                {"range": f"F{row}", "values": [[novo_status]]},
                {"range": f"H{row}", "values": [[admin_nome]]},
                {"range": f"I{row}", "values": [[dt_agora]]},
            ])
        else:
            aba.update_cell(row, 6, novo_status)
        invalidar_trocas()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
        return False

def salvar_troca_gsheet(linha: list) -> bool:
    """Adiciona uma nova linha de troca na Google Sheet."""
    try:
        sh = get_sheet()
        sh.worksheet("registos_trocas").append_row(linha)
        invalidar_trocas()
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
    pdf.set_font("Arial", "B", 17.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 30, "GNR - Comprovativo de Troca de Servico", 0, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.set_font("Arial", "", 10.5)
    texto = (
        f"Certifica-se que o militar {s(dados['nome_origem'])} (ID {s(dados['id_origem'])}), "
        f"requereu a troca do servico '{s(dados['serv_orig'])}' pelo servico '{s(dados['serv_dest'])}' "
        f"do militar {s(dados['nome_destino'])} (ID {s(dados['id_destino'])}), para o dia {s(dados['data'])}.\n\n"
        f"O pedido foi aceite pelo militar de destino e validado superiormente por "
        f"{s(dados['validador'])} no dia {s(dados['data_val'])}."
    )
    pdf.multi_cell(190, 8, texto)
    pdf.ln(15)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 0, 'R')
    return pdf.output(dest='S').encode('latin-1', 'replace')

def gerar_pdf_escala_dia(data: str, df_raw: pd.DataFrame) -> bytes:
    """Gera PDF da escala diaria em A4 retrato. Inclui indicacao de trocas."""
    import unicodedata
    from datetime import datetime as _dt

    def c(txt):
        return unicodedata.normalize('NFKD', str(txt)).encode('latin-1','ignore').decode('latin-1')

    # ---- formatar id_disp para mostrar troca de forma legivel ----
    # id_disp pode ser "123 🔄 456" — converter para "123 (T:456)"
    def fmt_id(txt):
        t = str(txt)
        if '\U0001f504' in t:          # emoji 🔄
            parts = t.split('\U0001f504')
            a, b = parts[0].strip(), parts[1].strip()
            return f"{a} (Troca c/{b})"
        return t

    df_raw = df_raw.copy()
    import unicodedata as _ud
    def _norm(t): return _ud.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
    df_raw['servico_col'] = df_raw['serviço'].apply(_norm)
    df_raw['id_fmt'] = df_raw['id_disp'].apply(fmt_id)

    # Separar logo à partida linhas sem militar (id vazio) — não aparecem nas tabelas
    df_raw_com = df_raw[df_raw['id'].astype(str).str.strip().str.len() > 0].copy()
    df_raw_sem = df_raw[df_raw['id'].astype(str).str.strip().str.len() == 0].copy()

    # Filtros sequenciais sobre linhas COM militar
    def filtrar(pat, df):
        mask = df['servico_col'].str.contains(pat, na=False)
        return df[mask].copy(), df[~mask].copy()

    df_aus,  df_rest = filtrar(r'ferias|licen|doente|folga', df_raw_com)
    df_adm,  df_rest = filtrar(r'pronto|secretaria|inquer|comando|dilig', df_rest)
    df_ap,   df_rest = filtrar(r'apoio', df_rest)           # apoio ANTES do atendimento
    df_at,   df_rest = filtrar(r'atendimento', df_rest)     # agora não apanha apoio
    df_pat,  df_rest = filtrar(r'po|patrulha|ronda|vtr|giro', df_rest)
    df_rem,  df_rest = filtrar(r'remu|grat', df_rest)
    df_outros = df_rest

    # ---- Iniciar PDF ----
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=False)   # SEM quebra automatica — evita pagina em branco
    pdf.add_page()

    W  = 190
    C1 = 10
    C2 = 107
    CW = 92

    # ---- Helpers ----
    def sec_title(label, w=W, x=None):
        if x is not None:
            pdf.set_x(x)
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(26, 46, 100)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(w, 5.5, c(f"  {label.upper()}"), 1, 1, 'L', True)
        pdf.set_text_color(0, 0, 0)

    def tbl_hdr(cols, widths, x=None):
        if x is not None:
            pdf.set_x(x)
        pdf.set_font("Arial", "B", 9.5)
        pdf.set_fill_color(205, 215, 242)
        pdf.set_text_color(15, 35, 90)
        for col, w in zip(cols, widths):
            pdf.cell(w, 5, c(col), 1, 0, 'C', True)
        pdf.ln(5)
        pdf.set_text_color(0, 0, 0)

    def tbl_row(vals, widths, x=None, fill=False):
        pdf.set_font("Arial", "", 8)
        if fill:
            pdf.set_fill_color(235, 241, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        x0 = x if x is not None else pdf.get_x()
        y0 = pdf.get_y()

        # Calcular altura real necessária para cada célula
        def calc_altura(txt, w):
            if not txt:
                return 5
            words = txt.replace('\n', ' \n ').split(' ')
            linha_w = 0
            n_linhas = 1
            for word in words:
                if word == '\n':
                    n_linhas += 1
                    linha_w = 0
                    continue
                ww = pdf.get_string_width(word + ' ')
                if linha_w + ww > w - 2:
                    n_linhas += 1
                    linha_w = ww
                else:
                    linha_w += ww
            return max(5, n_linhas * 5)

        altura_max = 5
        for v, w in zip(vals, widths):
            altura_max = max(altura_max, calc_altura(c(str(v)), w))

        # Desenhar todas as células com a mesma altura
        xi = x0
        for v, w in zip(vals, widths):
            txt = c(str(v))
            pdf.set_xy(xi, y0)
            pdf.multi_cell(w, 5, txt, 1, 'C', fill)
            cell_h = pdf.get_y() - y0
            if cell_h < altura_max:
                pdf.set_xy(xi, y0 + cell_h)
                pdf.cell(w, altura_max - cell_h, '', 'LRB', 0, 'C', fill)
            xi += w
        pdf.set_xy(x0, y0 + altura_max)

    # ====================================================
    # CABECALHO
    # ====================================================
    pdf.set_fill_color(20, 40, 95)
    pdf.rect(10, 10, W, 14, 'F')
    pdf.set_xy(10, 11)
    pdf.set_font("Arial", "B", 10.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(W, 6, c("POSTO TERRITORIAL DE VILA NOVA DE FAMALICAO"), 0, 1, 'C')
    pdf.set_x(10)
    pdf.set_font("Arial", "B", 10.5)
    try:
        dt_obj   = _dt.strptime(data, "%d/%m/%Y")
        dias_pt  = ["Segunda-feira","Terca-feira","Quarta-feira","Quinta-feira",
                    "Sexta-feira","Sabado","Domingo"]
        meses_pt = ["","Janeiro","Fevereiro","Marco","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        titulo   = f"ESCALA DE SERVICO  |  {dias_pt[dt_obj.weekday()]}  {dt_obj.day} de {meses_pt[dt_obj.month]} de {dt_obj.year}"
    except Exception:
        titulo = f"ESCALA DE SERVICO  |  {data}"
    pdf.cell(W, 6, c(titulo), 0, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # ====================================================
    # BLOCO 1 — AUSENCIAS (esq) | ADM (dir)
    # ====================================================
    y_top = pdf.get_y()

    pdf.set_x(C1)
    sec_title("Ausencias, Folgas e Licencas", CW, C1)
    if not df_aus.empty:
        ag = df_aus.groupby('serviço')['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag.iterrows():
            pdf.set_x(C1)
            pdf.set_font("Arial", "", 8.5)
            pdf.set_fill_color(255, 245, 245)
            pdf.multi_cell(CW, 3.5, c(f"  {r['serviço'].upper()}: {r['id_fmt']}"), border='LR', align='L', fill=True)
    pdf.set_x(C1)
    pdf.cell(CW, 0.5, "", border='T', ln=1)
    y_c1 = pdf.get_y()

    pdf.set_xy(C2, y_top)
    sec_title("Outras Situacoes / ADM", CW, C2)
    if not df_adm.empty:
        ag = df_adm.groupby(['serviço','horário'])['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()
        for _, r in ag.iterrows():
            pdf.set_x(C2)
            pdf.set_font("Arial", "", 8.5)
            pdf.set_fill_color(245, 245, 255)
            horario_txt = f" ({r['horário']})" if str(r['horário']).strip() else ""
            pdf.multi_cell(CW, 3.5, c(f"  {r['serviço'].upper()}{horario_txt}: {r['id_fmt']}"), border='LR', align='L', fill=True)
    pdf.set_x(C2)
    pdf.cell(CW, 0.5, "", border='T', ln=1)
    y_c2 = pdf.get_y()

    pdf.set_y(max(y_c1, y_c2) + 2)

    # ====================================================
    # BLOCO 2 — ATENDIMENTO (esq) | APOIO (dir)
    # ====================================================
    y_top2 = pdf.get_y()

    pdf.set_x(C1)
    sec_title("Atendimento", CW, C1)
    tbl_hdr(["Horario", "Militar(es)"], [26, CW-26], C1)
    if not df_at.empty:
        ag = df_at.groupby(['horário','serviço'])['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()
        fill = False
        for _, r in ag.sort_values('horário').iterrows():
            tbl_row([r['horário'], r['id_fmt']], [26, CW-26], C1, fill)
            fill = not fill
    y_at = pdf.get_y()

    pdf.set_xy(C2, y_top2)
    sec_title("Apoio ao Atendimento", CW, C2)
    tbl_hdr(["Horario", "Militar(es)"], [26, CW-26], C2)
    if not df_ap.empty:
        ag = df_ap.groupby(['horário','serviço'])['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()
        fill = False
        for _, r in ag.sort_values('horário').iterrows():
            tbl_row([r['horário'], r['id_fmt']], [26, CW-26], C2, fill)
            fill = not fill
    y_ap = pdf.get_y()

    pdf.set_y(max(y_at, y_ap) + 2)

    # ====================================================
    # BLOCO 3 — PATRULHAS (largura total)
    # ====================================================
    if not df_pat.empty:
        has_obs   = 'observações' in df_pat.columns
        has_indic = 'indicativo rádio' in df_pat.columns
        has_radio = 'rádio' in df_pat.columns
        has_vtr   = 'viatura' in df_pat.columns
        has_giro  = 'giro' in df_pat.columns

        cols_grp = ['horário', 'serviço']
        if has_indic: cols_grp.append('indicativo rádio')
        if has_radio: cols_grp.append('rádio')
        if has_vtr:   cols_grp.append('viatura')
        if has_giro:  cols_grp.append('giro')

        agg_dict = {'id_fmt': lambda x: ', '.join(x)}
        if has_obs: agg_dict['observações'] = lambda x: ' | '.join(v for v in x if str(v).strip())

        ag = df_pat.groupby(cols_grp, as_index=False).agg(agg_dict)

        # Separar Ocorrências das outras patrulhas
        mask_ocorr = ag['serviço'].str.lower().str.contains('ocorr|ocorrencia', na=False)
        ag_ocorr   = ag[mask_ocorr].sort_values('horário')
        ag_outras  = ag[~mask_ocorr].sort_values('horário')

        # Larguras sem giro (ocorrências) e com giro (patrulhas)
        w_p_base = [18, 44, 54, 24, 28, 22]
        w_p_giro = [18, 40, 48, 22, 26, 20, 16] if has_giro else w_p_base
        hdr_base = ["Horario","Militares","Servico","Indicativo","Radio","Viatura"]
        hdr_giro = hdr_base + (["Giro"] if has_giro else [])

        def _row_pat(r, com_giro=False):
            vals = [r['horário'], r['id_fmt'], r['serviço'].upper(),
                    str(r.get('indicativo rádio','')), str(r.get('rádio','')),
                    r.get('viatura','')]
            if com_giro: vals.append(str(r.get('giro','')))
            return vals

        # Grupo 1 — Patrulha Ocorrências (sem giro)
        if not ag_ocorr.empty:
            sec_title("Patrulha Ocorrencias", W)
            tbl_hdr(hdr_base, w_p_base)
            fill = False
            for _, r in ag_ocorr.iterrows():
                tbl_row(_row_pat(r, com_giro=False), w_p_base, fill=fill)
                fill = not fill

        # Grupo 2 — Outras Patrulhas e Policiamento (com giro)
        if not ag_outras.empty:
            pdf.ln(1)
            sec_title("Patrulhas e Policiamento", W)
            tbl_hdr(hdr_giro, w_p_giro)
            fill = False
            for _, r in ag_outras.iterrows():
                tbl_row(_row_pat(r, com_giro=has_giro), w_p_giro, fill=fill)
                fill = not fill

    # ====================================================
    # BLOCO 4 — OUTROS SERVIÇOS
    # ====================================================
    if not df_outros.empty:
        pdf.ln(1)
        sec_title("Outros Servicos", W)
        has_vtr_o   = 'viatura' in df_outros.columns
        has_indic_o = 'indicativo rádio' in df_outros.columns
        has_radio_o = 'rádio' in df_outros.columns
        cols_grp_o  = ['horário', 'serviço']
        if has_indic_o: cols_grp_o.append('indicativo rádio')
        if has_radio_o: cols_grp_o.append('rádio')
        if has_vtr_o:   cols_grp_o.append('viatura')
        ag_out = df_outros.groupby(cols_grp_o, as_index=False)['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()

        hdr_o = ["Horario","Militares","Servico"]
        w_o2  = [18, 54, 44]
        if has_indic_o: hdr_o.append("Indicativo"); w_o2.append(24)
        if has_radio_o: hdr_o.append("Radio");      w_o2.append(24)
        if has_vtr_o:   hdr_o.append("Viatura");    w_o2.append(190 - sum(w_o2))
        tbl_hdr(hdr_o, w_o2)
        fill = False
        for _, r in ag_out.sort_values(['serviço','horário']).iterrows():
            vals = [r['horário'], r['id_fmt'], r['serviço'].upper()]
            if has_indic_o: vals.append(r.get('indicativo rádio',''))
            if has_radio_o: vals.append(r.get('rádio',''))
            if has_vtr_o:   vals.append(r.get('viatura',''))
            tbl_row(vals, w_o2, fill=fill)
            fill = not fill

    # ====================================================
    # BLOCO 5 — REMUNERADOS
    # ====================================================
    if not df_rem.empty:
        pdf.ln(1)
        sec_title("Servicos Remunerados / Gratificados", W)
        w_r = [22, 38, 130]
        tbl_hdr(["Horario","Militares","Observacao"], w_r)
        obs_col = 'observações' if 'observações' in df_rem.columns else 'serviço'
        ag = df_rem.groupby(['horário', obs_col], as_index=False)['id_fmt'].apply(lambda x: ', '.join(x)).reset_index()
        ag = ag.sort_values([obs_col, 'horário']).reset_index(drop=True)

        # Agrupar linhas consecutivas com a mesma observação
        i = 0
        fill = False
        while i < len(ag):
            obs_txt = str(ag.loc[i, obs_col])
            grupo = [i]
            j = i + 1
            while j < len(ag) and str(ag.loc[j, obs_col]) == obs_txt:
                grupo.append(j)
                j += 1

            pdf.set_font("Arial", "", 8.5)
            if fill:
                pdf.set_fill_color(235, 241, 255)
            else:
                pdf.set_fill_color(255, 255, 255)

            y_grupo = pdf.get_y()

            # Calcular altura mínima para cada linha do grupo
            h_linha = 5

            # Calcular altura da observação (multi_cell)
            def _h_rem(txt, w):
                words = c(txt).replace('\n',' \n ').split(' ')
                lw, nl = 0, 1
                for wd in words:
                    if wd == '\n': nl += 1; lw = 0; continue
                    ww = pdf.get_string_width(wd + ' ')
                    if lw + ww > w - 2: nl += 1; lw = ww
                    else: lw += ww
                return max(h_linha * len(grupo), nl * h_linha)

            altura_obs = _h_rem(obs_txt, w_r[2])
            altura_total = max(altura_obs, h_linha * len(grupo))
            altura_linha = altura_total / len(grupo)

            # Desenhar observação (célula única para todo o grupo)
            pdf.set_xy(C1 + w_r[0] + w_r[1], y_grupo)
            pdf.multi_cell(w_r[2], 5, c(obs_txt), border=1, align='L', fill=fill)
            y_fim_obs = pdf.get_y()
            altura_real = y_fim_obs - y_grupo
            altura_total = max(altura_real, h_linha * len(grupo))
            altura_linha = altura_total / len(grupo)

            # Completar borda da observação se necessário
            if altura_real < altura_total:
                pdf.set_xy(C1 + w_r[0] + w_r[1], y_grupo + altura_real)
                pdf.cell(w_r[2], altura_total - altura_real, '', 'LRB', 0, 'L', fill)

            # Desenhar horário e militares linha a linha
            for k, idx in enumerate(grupo):
                y_linha = y_grupo + k * altura_linha
                pdf.set_xy(C1, y_linha)
                pdf.cell(w_r[0], altura_linha, c(str(ag.loc[idx, 'horário'])), 1, 0, 'C', fill)
                pdf.cell(w_r[1], altura_linha, c(ag.loc[idx, 'id_fmt']), 1, 0, 'C', fill)

            pdf.set_y(y_grupo + altura_total)
            fill = not fill
            i = j

    # ====================================================
    # BLOCO 6 — OBSERVACOES DE PATRULHA
    # ====================================================
    def get_indic(r):
        return (str(r.get('indicativo rádio','') or '').strip()
             or str(r.get('rádio','') or '').strip()
             or str(r.get('serviço','') or '').strip()
             or 'S/I')

    df_obs_total = pd.concat([df_pat, df_outros], ignore_index=True) if not df_outros.empty else df_pat
    if not df_obs_total.empty and 'observações' in df_obs_total.columns:
        obs_df = df_obs_total[df_obs_total['observações'].str.strip().str.len() > 0].copy()
        if not obs_df.empty:
            pdf.ln(1)
            sec_title("Observacoes de Patrulha", W)
            w_o = [28, 162]
            tbl_hdr(["Indicativo","Detalhe"], w_o)

            obs_df['_indic'] = obs_df.apply(get_indic, axis=1)

            # Agrupar por observação, juntando indicativos diferentes
            obs_grp = obs_df.groupby('observações', sort=False).agg(
                _indic=('_indic', lambda x: ' / '.join(dict.fromkeys(v for v in x if v and v != 'S/I')) or 'S/I'),
                horário=('horário', 'first')
            ).reset_index()

            # Detetar indicativos duplicados para mostrar horário
            indics_count = obs_df['_indic'].value_counts()
            indics_duplicados = set(indics_count[indics_count > 1].index)

            fill = False
            for _, r in obs_grp.iterrows():
                indic = r['_indic']
                horario_val = str(r.get('horário','') or '').strip()
                if any(i in indics_duplicados for i in indic.split(' / ')) and horario_val:
                    indic = f"{indic}\n{horario_val}"
                pdf.set_font("Arial", "", 8.5)
                if fill:
                    pdf.set_fill_color(255, 255, 220)
                else:
                    pdf.set_fill_color(255, 255, 255)
                y_antes = pdf.get_y()

                # Se não cabe no espaço restante, parar (rodapé fixo em 282)
                if y_antes > 270:
                    break

                # Calcular altura real de cada coluna
                def _h(txt, w):
                    words = c(txt).replace('\n',' \n ').split(' ')
                    lw, nl = 0, 1
                    for wd in words:
                        if wd == '\n': nl += 1; lw = 0; continue
                        ww = pdf.get_string_width(wd + ' ')
                        if lw + ww > w - 2: nl += 1; lw = ww
                        else: lw += ww
                    return max(5, nl * 5)

                h_indic = _h(indic, 28)
                h_obs   = _h(r['observações'], 162)
                altura  = max(h_indic, h_obs)

                # Se esta linha ultrapassa o rodapé, truncar
                if y_antes + altura > 278:
                    break

                # Desenhar observação
                pdf.set_xy(C1 + 28, y_antes)
                pdf.multi_cell(162, 5, c(r['observações']), border=1, align='L', fill=fill)
                h_obs_real = pdf.get_y() - y_antes
                if h_obs_real < altura:
                    pdf.set_xy(C1 + 28, y_antes + h_obs_real)
                    pdf.cell(162, altura - h_obs_real, '', 'LRB', 0, 'L', fill)

                # Desenhar indicativo
                pdf.set_xy(C1, y_antes)
                pdf.multi_cell(28, 5, c(indic), border=1, align='C', fill=fill)
                h_ind_real = pdf.get_y() - y_antes
                if h_ind_real < altura:
                    pdf.set_xy(C1, y_antes + h_ind_real)
                    pdf.cell(28, altura - h_ind_real, '', 'LRB', 0, 'C', fill)

                pdf.set_y(y_antes + altura)
                fill = not fill

    # ====================================================
    # RODAPE — fixo no fundo da pagina
    # ====================================================
    pdf.set_xy(10, 282)
    pdf.set_draw_color(160, 160, 160)
    pdf.line(10, 282, 200, 282)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.set_xy(10, 283)
    pdf.cell(95, 4, c(f"Gerado em: {_dt.now().strftime('%d/%m/%Y %H:%M')}"), 0, 0, 'L')
    pdf.cell(95, 4, c("O COMANDANTE"), 0, 0, 'R')

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

def _limpar_sem_militar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas onde id está vazio — serviços sem militar escalado."""
    if 'id' not in df.columns:
        return df
    return df[df['id'].astype(str).str.strip().str.len() > 0].copy()

def _cel_expandivel(val: str, limite: int = 60) -> str:
    """Renderiza texto diretamente sem truncar."""
    return str(val).replace('\n', '<br>')

def _render_tabela(df: pd.DataFrame, expandivel: bool = False) -> str:
    """Tabela HTML com wrap. Se expandivel=True, texto longo fica colapsado com 'ver mais'."""
    def _cel(val, limite=60):
        txt = str(val).replace('\n', '<br>')
        if not expandivel or len(str(val)) <= limite:
            return txt
        resumo = str(val)[:limite].rstrip() + "…"
        resumo_esc = resumo.replace('"','&quot;').replace("'","&#39;")
        txt_esc = str(val).replace('"','&quot;').replace("'","&#39;").replace('\n','<br>')
        return (f"<details style='cursor:pointer'>"
                f"<summary style='list-style:none;outline:none;color:#1E293B'>{resumo_esc}"
                f"<span style='color:#1E3A8A;font-size:0.75rem;margin-left:4px'>ver mais</span></summary>"
                f"<span style='color:#1E293B'>{txt_esc}</span></details>")

    th_s = "background:#1E3A8A;color:white;padding:7px 10px;text-align:left;font-size:0.8rem;white-space:nowrap;"
    td_s = "padding:6px 10px;font-size:0.82rem;color:#1E293B;vertical-align:top;border-bottom:1px solid #E2E8F0;word-break:break-word;"
    td_a = td_s + "background:#F8FAFC;"
    html = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;'><thead><tr>"
    for col in df.columns:
        extra = " max-width:180px;" if 'observa' in str(col).lower() else ""
        html += f"<th style='{th_s}{extra}'>{str(col).capitalize()}</th>"
    html += "</tr></thead><tbody>"
    for i, (_, row) in enumerate(df.iterrows()):
        td = td_a if i % 2 == 0 else td_s
        html += "<tr>"
        for col, val in zip(df.columns, row):
            extra = " max-width:180px;" if 'observa' in str(col).lower() else ""
            html += f"<td style='{td}{extra}'>{_cel(str(val))}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

def mostrar_secao(titulo: str, df_sec: pd.DataFrame, mostrar_extras: bool = False, excluir_cols: list = [], esconder_servico: bool = False):
    """Renderiza uma secção da escala num expander."""
    if df_sec.empty:
        return
    with st.expander(f"🔹 {titulo.upper()}", expanded=True):
        if mostrar_extras:
            cols_ag = ['serviço', 'horário']
            for col in ['indicativo rádio', 'rádio', 'viatura', 'giro']:
                if col in df_sec.columns and col not in excluir_cols:
                    cols_ag.append(col)
            agg_dict: dict = {'id_disp': lambda x: ', '.join(x)}
            if 'observações' in df_sec.columns:
                agg_dict['observações'] = lambda x: ', '.join(v for v in x.dropna().unique() if str(v).strip())
            ag = df_sec.groupby(cols_ag, sort=False).agg(agg_dict).reset_index()
            col_order = ['serviço', 'horário', 'id_disp']
            for col in ['indicativo rádio', 'rádio', 'viatura', 'giro', 'observações']:
                if col in ag.columns and col not in excluir_cols:
                    col_order.append(col)
            ag = ag[col_order]
        else:
            ag = df_sec.groupby(['serviço', 'horário'], sort=False)['id_disp'] \
                       .apply(lambda x: ', '.join(x)).reset_index()
        ag = ag.rename(columns={
            'id_disp': 'Militares',
            'serviço': 'Serviço',
            'horário': 'Horário',
            'indicativo rádio': 'Indicativo',
            'rádio': 'Rádio',
            'viatura': 'Viatura',
            'giro': 'Giro',
            'observações': 'Observações',
        })
        if esconder_servico and 'Serviço' in ag.columns:
            ag = ag.drop(columns=['Serviço'])
        st.markdown(_render_tabela(ag), unsafe_allow_html=True)

# ============================================================
# 7. LOGIN
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "login_modo" not in st.session_state:
    st.session_state["login_modo"] = "pin"
if "pin_buf" not in st.session_state:
    st.session_state["pin_buf"] = ""
if "pin_erro" not in st.session_state:
    st.session_state["pin_erro"] = False
if "pin_tentativas" not in st.session_state:
    st.session_state["pin_tentativas"] = 0
if "pin_bloqueado_ate" not in st.session_state:
    st.session_state["pin_bloqueado_ate"] = None

def fazer_login(user_row, u_email):
    u_id = str(user_row['id'])
    if 'posto' in user_row.index and 'nome' in user_row.index and str(user_row.get('posto','')).strip():
        u_nome = f"{user_row['posto']} {user_row['nome']}"
    else:
        df_u = load_utilizadores()
        row_sheet = df_u[df_u['id'].astype(str).str.strip() == u_id]
        u_nome = f"{row_sheet.iloc[0]['posto']} {row_sheet.iloc[0]['nome']}" if not row_sheet.empty else u_email
    st.session_state.update({
        "logged_in":  True,
        "user_id":    u_id,
        "user_nome":  u_nome,
        "user_email": u_email,
        "is_admin":   u_email in ADMINS,
        "pin_tentativas": 0,
        "pin_bloqueado_ate": None,
        "pin_buf": "",
        "pin_erro": False,
    })

if not st.session_state["logged_in"]:
    modo = st.session_state["login_modo"]

    @st.fragment
    def _keypad_fragment():
        buf = st.session_state["pin_buf"]
        err = st.session_state["pin_erro"]
        n   = len(buf)
        bloqueado = st.session_state["pin_bloqueado_ate"] and datetime.now() < st.session_state["pin_bloqueado_ate"]
        err_msg = "PIN incorreto. Tenta novamente." if err else ""
        if bloqueado:
            resto = int((st.session_state["pin_bloqueado_ate"] - datetime.now()).total_seconds())
            err_msg = f"🔒 Bloqueado. Aguarda {resto}s."

        dots_html = '<div style="display:flex;gap:16px;justify-content:center;margin-bottom:10px;">'
        for i in range(4):
            if err:
                style = "background:#EF4444;border:2px solid #EF4444;"
            elif i < n:
                style = "background:#0F172A;border:2px solid #0F172A;"
            else:
                style = "background:transparent;border:2px solid #CBD5E1;"
            dots_html += f'<div style="width:14px;height:14px;border-radius:50%;{style}transition:all 0.15s ease;"></div>'
        dots_html += '</div>'

        st.markdown(f"""
        <div style="display:flex;flex-direction:column;align-items:center;padding:48px 0 24px 0;">
            <div style="font-size:2.8rem;margin-bottom:6px;filter:drop-shadow(0 4px 8px rgba(30,58,138,0.25))">🚓</div>
            <div style="font-size:1.4rem;font-weight:800;color:#1A2B4A;letter-spacing:-0.02em;margin-bottom:2px">Portal de Escalas</div>
            <div style="font-size:0.72rem;font-weight:600;color:#2563EB;letter-spacing:0.04em;text-transform:uppercase;margin-bottom:2px">Guarda Nacional Republicana</div>
            <div style="font-size:0.68rem;color:#64748B;margin-bottom:28px">Posto Territorial de Famalicão</div>
            {dots_html}
            <div style="min-height:20px;font-size:13px;font-weight:600;color:#EF4444;text-align:center;margin-bottom:16px;">{err_msg}</div>
        </div>
        """, unsafe_allow_html=True)

        rows = [["1","2","3"], ["4","5","6"], ["7","8","9"], ["_","0","⌫"]]
        for row in rows:
            c1, c2, c3 = st.columns(3)
            for col, val in zip([c1, c2, c3], row):
                with col:
                    if val == "_":
                        st.markdown("<div style='height:76px'></div>", unsafe_allow_html=True)
                    elif st.button(val, key=f"pk_{val}"):
                        if not bloqueado:
                            if val == "⌫":
                                st.session_state["pin_buf"] = buf[:-1]
                                st.session_state["pin_erro"] = False
                            else:
                                new = buf + val
                                st.session_state["pin_erro"] = False
                                if len(new) == 4:
                                    df_u = load_utilizadores()
                                    if not df_u.empty and 'pin' in df_u.columns:
                                        user = df_u[df_u['pin'].astype(str).str.strip().str.zfill(4) == new.zfill(4)]
                                        if not user.empty:
                                            fazer_login(user.iloc[0], user.iloc[0]['email'])
                                            st.rerun(scope="app")
                                        else:
                                            st.session_state["pin_tentativas"] += 1
                                            if st.session_state["pin_tentativas"] >= 3:
                                                st.session_state["pin_bloqueado_ate"] = datetime.now() + timedelta(seconds=30)
                                                st.session_state["pin_tentativas"] = 0
                                            st.session_state["pin_erro"] = True
                                            st.session_state["pin_buf"] = ""
                                    else:
                                        st.session_state["pin_erro"] = True
                                        st.session_state["pin_buf"] = ""
                                else:
                                    st.session_state["pin_buf"] = new
                        st.rerun()

    if modo == "pin":
        buf = st.session_state["pin_buf"]
        err = st.session_state["pin_erro"]
        n   = len(buf)

        bloqueado = st.session_state["pin_bloqueado_ate"] and datetime.now() < st.session_state["pin_bloqueado_ate"]
        err_msg = "PIN incorreto. Tenta novamente." if err else ""
        if bloqueado:
            resto = int((st.session_state["pin_bloqueado_ate"] - datetime.now()).total_seconds())
            err_msg = f"🔒 Bloqueado. Aguarda {resto}s."

        st.markdown("""
        <style>
        .stApp { background:#FFFFFF !important; }
        header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], #MainMenu { display:none !important; }
        .block-container { padding:0 !important; max-width:100% !important; }
        div[data-testid="stButton"]>button {
            width:76px !important; height:76px !important; border-radius:50% !important;
            background:#F1F5F9 !important; color:#0F172A !important;
            font-size:24px !important; font-weight:300 !important;
            border:none !important; box-shadow:0 2px 8px rgba(0,0,0,0.08) !important;
            padding:0 !important; margin:0 auto !important;
            transition:transform 0.08s ease, background 0.08s ease !important; }
        div[data-testid="stButton"]>button:hover {
            background:#E2E8F0 !important; transform:scale(0.95) !important; }
        div[data-testid="stButton"]>button:active {
            background:#CBD5E1 !important; transform:scale(0.90) !important; }
        [data-testid="stHorizontalBlock"] {
            display:flex !important; flex-direction:row !important;
            justify-content:center !important; gap:14px !important; flex-wrap:nowrap !important; }
        [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {
            flex:0 0 76px !important; min-width:76px !important;
            max-width:76px !important; width:76px !important; padding:0 !important; }
        </style>
        """, unsafe_allow_html=True)
        _keypad_fragment()
        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        if col_a.button("🔑 Entrar com email", use_container_width=True):
            st.session_state["login_modo"] = "email"
            st.rerun()
        if col_b.button("📱 Registar PIN", use_container_width=True):
            st.session_state["login_modo"] = "registar_pin"
            st.rerun()

    # ── MODO EMAIL/PASSWORD ──
    elif modo == "email":
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col2, _ = st.columns([1, 1.4, 1])
        with col2:
            st.markdown("""
            <div class="login-box">
                <div class="login-header">
                    <span class="escudo">🚓</span>
                    <h1>Portal de Escalas</h1>
                    <div class="org-line"><span class="org-name">Guarda Nacional Republicana</span></div>
                    <p class="posto-name">Posto Territorial de Famalicão</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            with st.form("form_email", clear_on_submit=False):
                st.markdown("<br>", unsafe_allow_html=True)
                u = st.text_input("📧 Email institucional", placeholder="utilizador@gnr.pt").strip().lower()
                p = st.text_input("🔒 Password", type="password", placeholder="••••••••")
                st.markdown("<br>", unsafe_allow_html=True)
                entrar = st.form_submit_button("ENTRAR", use_container_width=True)
                if entrar:
                    if not u or not p:
                        st.warning("Preenche o email e a password.")
                    else:
                        df_u = load_utilizadores()
                        if df_u.empty or 'email' not in df_u.columns:
                            st.error("❌ Erro ao carregar dados.")
                        else:
                            user = df_u[
                                (df_u['email'].str.lower() == u) &
                                (df_u['password'] == p)
                            ]
                            if not user.empty:
                                fazer_login(user.iloc[0], u)
                                st.rerun()
                            else:
                                st.error("❌ Email ou password incorretos.")
            if st.button("← Voltar ao PIN", use_container_width=True):
                st.session_state["login_modo"] = "pin"
                st.rerun()

    # ── MODO REGISTAR PIN ──
    elif modo == "registar_pin":
        st.markdown("<br><br>", unsafe_allow_html=True)
        _, col2, _ = st.columns([1, 1.4, 1])
        with col2:
            st.markdown("""
            <div class="login-box">
                <div class="login-header">
                    <span class="escudo">🚓</span>
                    <h1>Registar PIN</h1>
                    <div class="org-line"><span class="org-name">Guarda Nacional Republicana</span></div>
                    <p class="posto-name">Posto Territorial de Famalicão</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;color:#475569;font-size:0.88rem'>Autentica-te primeiro para criar o teu PIN</p>", unsafe_allow_html=True)
            with st.form("form_reg_pin", clear_on_submit=False):
                st.markdown("<br>", unsafe_allow_html=True)
                u_r = st.text_input("📧 Email institucional", placeholder="utilizador@gnr.pt").strip().lower()
                p_r = st.text_input("🔒 Password", type="password", placeholder="••••••••")
                st.markdown("---")
                pin1 = st.text_input("📱 Novo PIN (4 dígitos)", type="password",
                                     placeholder="● ● ● ● ● ●", max_chars=6)
                pin2 = st.text_input("📱 Confirmar PIN", type="password",
                                     placeholder="● ● ● ● ● ●", max_chars=6)
                st.markdown("<br>", unsafe_allow_html=True)
                registar = st.form_submit_button("CRIAR PIN", use_container_width=True)
                if registar:
                    if not u_r or not p_r or not pin1 or not pin2:
                        st.warning("Preenche todos os campos.")
                    elif len(pin1) != 4 or not pin1.isdigit():
                        st.warning("O PIN deve ter exatamente 4 dígitos numéricos.")
                    elif pin1 != pin2:
                        st.error("❌ Os PINs não coincidem.")
                    else:
                        df_u = load_utilizadores()
                        if df_u.empty or 'email' not in df_u.columns:
                            st.error("❌ Erro ao carregar dados.")
                        else:
                            user = df_u[
                                (df_u['email'].str.lower() == u_r) &
                                (df_u['password'] == p_r)
                            ]
                            if user.empty:
                                st.error("❌ Email ou password incorretos.")
                            else:
                                if 'pin' in df_u.columns:
                                    pin_existe = df_u[
                                        (df_u['pin'].astype(str).str.strip().str.zfill(4) == pin1.zfill(4)) &
                                        (df_u['email'].str.lower() != u_r)
                                    ]
                                    if not pin_existe.empty:
                                        st.error("❌ Este PIN já está a ser usado. Escolhe outro.")
                                        st.stop()
                                try:
                                    sh = get_sheet()
                                    ws = sh.worksheet("utilizadores")
                                    headers = ws.row_values(1)
                                    headers_lower = [h.strip().lower() for h in headers]
                                    if 'pin' not in headers_lower:
                                        st.error("❌ Coluna 'pin' não existe na Sheet.")
                                        st.stop()
                                    col_pin = headers_lower.index('pin') + 1
                                    ids_col = ws.col_values(headers_lower.index('email') + 1)
                                    linha_user = None
                                    for i, email_val in enumerate(ids_col):
                                        if email_val.strip().lower() == u_r:
                                            linha_user = i + 1
                                            break
                                    if linha_user:
                                        ws.update_cell(linha_user, col_pin, pin1)
                                        load_utilizadores.clear()
                                        st.success("✅ PIN criado! Já podes entrar com o PIN.")
                                        st.session_state["login_modo"] = "pin"
                                        st.rerun()
                                    else:
                                        st.error("❌ Utilizador não encontrado.")
                                except Exception as e:
                                    st.error(f"❌ Erro ao guardar PIN: {e}")
            if st.button("← Voltar ao PIN", use_container_width=True):
                st.session_state["login_modo"] = "pin"
                st.rerun()



# ============================================================
# 8. APP PRINCIPAL (pós-login)
# ============================================================
else:
    # Carregar dados globais uma vez por sessão de render
    df_trocas = load_data("registos_trocas")
    df_util   = load_utilizadores()
    ano_atual = datetime.now().year
    df_ferias  = load_ferias(ano_atual)
    feriados   = load_feriados(ano_atual)

    u_id      = str(st.session_state['user_id'])
    u_nome    = st.session_state['user_nome']
    is_admin  = st.session_state.get("is_admin", False)

    # --- Sidebar ---
    with st.sidebar:
        # Badge do utilizador
        st.markdown("""
        <div style='text-align:center;padding:12px 4px 16px 4px;margin-bottom:14px;background:linear-gradient(180deg,rgba(30,58,138,0.4) 0%,rgba(15,23,42,0) 100%);border-radius:10px'>
            <div style='font-size:2rem;line-height:1;margin-bottom:8px;filter:drop-shadow(0 2px 6px rgba(147,197,253,0.4))'>🚓</div>
            <div style='font-size:0.85rem;font-weight:800;color:#F1F5F9;letter-spacing:0.08em;text-transform:uppercase;line-height:1.2'>Portal de Escalas</div>
            <div style='width:40px;height:2px;background:linear-gradient(90deg,transparent,#3B82F6,transparent);margin:6px auto 5px auto;border-radius:2px'></div>
            <div style='font-size:0.72rem;color:#93C5FD;font-weight:600;letter-spacing:0.04em'>Guarda Nacional Republicana</div>
            <div style='font-size:0.67rem;color:#64748B;margin-top:3px;letter-spacing:0.02em'>Posto Territorial de Famalicão</div>
        </div>
        """, unsafe_allow_html=True)

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

        menu_geral = [
            "📅 Minha Escala",
            "🔍 Escala Geral",
            "📊 Estatísticas",
            "🏖️ Férias",
            "🔄 Solicitar Troca",
            "📥 Pedidos Recebidos",
            "📋 Histórico de Trocas",
            "🔄 Giros",
            "👥 Efetivo",
        ]
        menu_admin = ["⚖️ Validar Trocas", "📜 Trocas Validadas", "🚨 Alertas"]

        st.markdown("<p style='font-size:0.75rem;letter-spacing:0.08em;color:#94A3B8;margin:0 0 4px 0;'>MENU</p>", unsafe_allow_html=True)

        menu_opt = [
            "📅 Minha Escala",
            "🔍 Escala Geral",
            "📊 Estatísticas",
            "🏖️ Férias",
            "🔄 Solicitar Troca",
            "📥 Pedidos Recebidos",
            "📋 Histórico de Trocas",
            "🔄 Giros",
            "👥 Efetivo",
        ]
        if is_admin:
            menu_opt += ["", "⚖️ Validar Trocas", "📜 Trocas Validadas"]

        menu = st.radio("MENU", menu_opt, label_visibility="collapsed",
                        format_func=lambda x: "──────────" if x == "" else x)

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # ============================================================
    # FECHAR SIDEBAR NO MOBILE APÓS SELEÇÃO
    # ============================================================
    if "menu_anterior" not in st.session_state:
        st.session_state["menu_anterior"] = menu
    elif st.session_state["menu_anterior"] != menu:
        st.session_state["menu_anterior"] = menu
        st.session_state["sidebar_state"] = "collapsed"
        st.rerun()

    # ============================================================
    # BANNER NOTIFICAÇÕES
    # ============================================================
    if not df_trocas.empty:
        n_pend = len(df_trocas[
            (df_trocas['status'] == 'Pendente_Militar') &
            (df_trocas['id_destino'].astype(str) == u_id)
        ])
        if n_pend > 0:
            st.warning(f"🔔 Tens **{n_pend} pedido(s) de troca** por responder! Vai a **📥 Pedidos Recebidos**.")

        # Verificar trocas validadas cujo serviço original já não existe na escala
        minhas_apr = df_trocas[
            (df_trocas['status'] == 'Aprovada') &
            (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
            ((df_trocas['id_origem'].astype(str) == u_id) |
             (df_trocas['id_destino'].astype(str) == u_id))
        ]
        for _, t in minhas_apr.iterrows():
            fui_origem = str(t['id_origem']) == u_id
            serv_meu_t = t['servico_origem'] if fui_origem else t['servico_destino']
            id_meu     = u_id
            serv_nome  = serv_meu_t.rsplit('(', 1)[0].strip().lower()
            hor_val    = serv_meu_t.rsplit('(', 1)[1].rstrip(')') if '(' in serv_meu_t else ''
            try:
                dt_t = datetime.strptime(t['data'], '%d/%m/%Y')
            except:
                continue
            # Só verificar nos próximos 30 dias
            hoje_b = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if dt_t < hoje_b or (dt_t - hoje_b).days > 30:
                continue
            df_dia_t = load_data(dt_t.strftime('%d-%m'))
            if df_dia_t.empty:
                continue
            existe = df_dia_t[
                (df_dia_t['id'].astype(str) == id_meu) &
                (df_dia_t['serviço'].astype(str).str.strip().str.lower() == serv_nome) &
                (df_dia_t['horário'].astype(str).str.strip() == hor_val.strip())
            ]
            if existe.empty:
                outro_nome = get_nome_militar(df_util, t['id_destino'] if fui_origem else t['id_origem'])
                st.error(f"⚠️ **Atenção!** A tua troca de **{t['data']}** com **{outro_nome}** pode estar afetada por uma alteração na escala. Contacta o teu superior.")

    # ============================================================
    # EXPIRAÇÃO DE SESSÃO (4 horas)
    # ============================================================
    if "login_time" not in st.session_state:
        st.session_state["login_time"] = datetime.now()
    elif (datetime.now() - st.session_state["login_time"]).total_seconds() > 4 * 3600:
        st.session_state["logged_in"] = False
        st.warning("⏱️ Sessão expirada. Por favor volta a fazer login.")
        st.stop()

    # ============================================================
    # PÁGINAS
    # ============================================================

    # --- 📅 MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 A Minha Escala")

        # ── Aniversários de hoje ──
        hoje = datetime.now()
        if 'nascimento' in df_util.columns:
            aniversariantes = []
            for _, row in df_util.iterrows():
                nasc = str(row.get('nascimento', '')).strip()
                if not nasc or nasc == 'nan':
                    continue
                try:
                    nasc_norm = nasc.replace("/", "-")
                    dt_nasc = datetime.strptime(nasc_norm, "%d-%m-%Y")
                    if dt_nasc.day == hoje.day and dt_nasc.month == hoje.month:
                        idade = hoje.year - dt_nasc.year
                        nome = f"{row.get('posto','')} {row.get('nome','')}".strip()
                        aniversariantes.append((nome, idade))
                except:
                    continue
            if aniversariantes:
                for nome, idade in aniversariantes:
                    st.markdown(f"""
                    <div style='background:linear-gradient(135deg,#FEF9C3,#FEF08A);border-left:4px solid #EAB308;
                    border-radius:10px;padding:12px 16px;margin-bottom:10px;display:flex;align-items:center;gap:12px'>
                        <span style='font-size:1.8rem'>🎂</span>
                        <div>
                            <div style='font-weight:700;color:#713F12;font-size:0.95rem'>Hoje é o aniversário de {nome}!</div>
                            <div style='color:#92400E;font-size:0.82rem'>Completa {idade} anos — Parabéns! 🎉</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        vista = st.radio("Vista:", ["📋 Próximos Serviços", "📅 Calendário Mensal"], horizontal=True, label_visibility="collapsed")
        st.markdown("---")

        # ── CALENDÁRIO MENSAL ──
        if vista == "📅 Calendário Mensal":
            from calendar import monthrange
            hj_cal = datetime.now()
            col_m, col_a, _ = st.columns([1, 1, 3])
            with col_m:
                mes_sel = st.selectbox("Mês:", list(range(1,13)),
                    index=hj_cal.month - 1,
                    format_func=lambda m: ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                                           "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][m-1])
            with col_a:
                ano_sel = st.selectbox("Ano:", [hj_cal.year - 1, hj_cal.year, hj_cal.year + 1], index=1)

            _, n_dias = monthrange(ano_sel, mes_sel)

            # Carregar todos os dias do mês
            servicos_mes = {}
            for d in range(1, n_dias + 1):
                dt_cal = datetime(ano_sel, mes_sel, d)
                aba = dt_cal.strftime("%d-%m")
                df_cal = load_data(aba)
                if not df_cal.empty:
                    m_cal = df_cal[df_cal['id'].astype(str) == u_id]
                    if not m_cal.empty:
                        row_cal = m_cal.iloc[0]
                        # Verificar trocas
                        troca_cal = None
                        if not df_trocas.empty:
                            tr_c = df_trocas[
                                (df_trocas['data'] == dt_cal.strftime('%d/%m/%Y')) &
                                (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                                ((df_trocas['id_origem'].astype(str) == u_id) |
                                 (df_trocas['id_destino'].astype(str) == u_id))
                            ]
                            if not tr_c.empty:
                                t_c = tr_c.iloc[0]
                                troca_cal = t_c['servico_destino'] if str(t_c['id_origem']) == u_id else t_c['servico_origem']
                        servicos_mes[d] = {
                            'serviço': troca_cal if troca_cal else row_cal['serviço'],
                            'horário': row_cal['horário'],
                            'troca': troca_cal is not None,
                            'obs': str(row_cal.get('observações','') or '').strip(),
                            'remunerados': []
                        }
                        # Verificar remunerados no mesmo dia
                        rem_cal = df_cal[df_cal['id'].astype(str) == u_id]
                        import unicodedata as _udc
                        def _nc(t): return _udc.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
                        rem_cal = rem_cal[rem_cal['serviço'].apply(_nc).str.contains('remu|grat', na=False)]
                        if not df_trocas.empty:
                            # Excluir remunerados cedidos
                            cedidos_cal = df_trocas[
                                (df_trocas['data'] == dt_cal.strftime('%d/%m/%Y')) &
                                (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                (df_trocas['id_destino'].astype(str) == u_id)
                            ]
                            for _, cd in cedidos_cal.iterrows():
                                serv_cd = cd['servico_destino'].rsplit('(', 1)[0].strip()
                                hor_cd  = cd['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in cd['servico_destino'] else ''
                                rem_cal = rem_cal[
                                    ~(
                                        (rem_cal['serviço'].astype(str).str.strip().str.lower() == serv_cd.lower()) &
                                        (rem_cal['horário'].astype(str).str.strip() == hor_cd.strip())
                                    )
                                ]
                            # Adicionar remunerados obtidos via matar remunerado
                            matar_cal = df_trocas[
                                (df_trocas['data'] == dt_cal.strftime('%d/%m/%Y')) &
                                (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                (df_trocas['id_origem'].astype(str) == u_id)
                            ]
                            for _, mt in matar_cal.iterrows():
                                serv_r = mt['servico_destino'].rsplit('(', 1)[0].strip()
                                hor_r  = mt['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt['servico_destino'] else ''
                                linha_r = df_cal[
                                    (df_cal['serviço'].astype(str).str.strip().str.lower() == serv_r.lower()) &
                                    (df_cal['horário'].astype(str).str.strip() == hor_r.strip())
                                ]
                                if not linha_r.empty:
                                    rem_cal = pd.concat([rem_cal, linha_r.iloc[[0]]], ignore_index=True)
                        for _, rr in rem_cal.iterrows():
                            servicos_mes[d]['remunerados'].append(f"💰 {rr['serviço']} ({rr['horário']})")

            hoje_d = datetime.now().date()

            # Renderizar como lista de cards compactos (funciona em mobile e desktop)
            nomes_mes = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                         "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
            nomes_dia = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
            st.markdown(f"### {nomes_mes[mes_sel]} {ano_sel}")

            tem_servicos = False
            for d in range(1, n_dias + 1):
                dt_cel = datetime(ano_sel, mes_sel, d).date()
                is_hoje = dt_cel == hoje_d
                weekday = dt_cel.weekday()
                dia_sem = nomes_dia[weekday]
                is_fds = weekday >= 5
                is_feriado = dt_cel in feriados

                borda_esq = "4px solid #1E3A8A" if is_hoje else ("3px solid #DC2626" if is_feriado else ("3px solid #F59E0B" if is_fds else "3px solid #E2E8F0"))
                cor_num = "#DC2626" if is_feriado else ("#B45309" if is_fds else "#1E293B")
                cor_dia = "#DC2626" if is_feriado else ("#B45309" if is_fds else "#64748B")
                hoje_badge = " <span style='background:#1E3A8A;color:white;font-size:0.65rem;padding:1px 6px;border-radius:10px'>HOJE</span>" if is_hoje else ""

                if d in servicos_mes:
                    tem_servicos = True
                    info = servicos_mes[d]
                    if info['troca']:
                        bg, cor_txt, icone = "#FFFBEB", "#92400E", "🔄"
                    else:
                        import unicodedata as _udc
                        def _nc(t): return _udc.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
                        s_n = _nc(info['serviço'])
                        if any(x in s_n for x in ['ferias','licen','doente']):
                            bg, cor_txt, icone = "#F8FAFC", "#64748B", "🏖️"
                        elif 'folga' in s_n:
                            bg, cor_txt, icone = "#F5F3FF", "#7C3AED", "😴"
                        elif any(x in s_n for x in ['tribunal','dilig']):
                            bg, cor_txt, icone = "#FFF1F2", "#DC2626", "⚖️"
                        elif any(x in s_n for x in ['remu','grat']):
                            bg, cor_txt, icone = "#ECFDF5", "#065F46", "💰"
                        else:
                            bg, cor_txt, icone = "#EFF6FF", "#1E3A8A", "🛡️"
                    # Fundo mais quente ao fim de semana
                    if is_fds and bg == "#EFF6FF":
                        bg = "#FFFBEB"
                    rems = info.get('remunerados', [])
                    rem_html = "".join([f"<div style='font-size:0.75rem;color:#065F46;margin-top:2px'>{r}</div>" for r in rems]) if rems else ""
                    st.markdown(f"""
                    <div style='background:{bg};border-left:{borda_esq};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px'>
                        <div style='min-width:48px;text-align:center'>
                            <div style='font-size:1.2rem;font-weight:800;color:{cor_num};line-height:1'>{d}</div>
                            <div style='font-size:0.7rem;color:{cor_dia};font-weight:{"700" if is_fds else "400"}'>{dia_sem}</div>
                        </div>
                        <div>
                            <div style='font-size:0.9rem;font-weight:700;color:{cor_txt}'>{icone} {info['serviço']}{hoje_badge}</div>
                            <div style='font-size:0.8rem;color:#475569'>🕒 {info['horário']}</div>{rem_html}
                        </div>
                    </div>""", unsafe_allow_html=True)
                elif is_hoje:
                    st.markdown(f"""
                    <div style='background:#F8FAFC;border-left:{borda_esq};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px'>
                        <div style='min-width:48px;text-align:center'>
                            <div style='font-size:1.2rem;font-weight:800;color:#94A3B8;line-height:1'>{d}</div>
                            <div style='font-size:0.7rem;color:#94A3B8'>{dia_sem}</div>
                        </div>
                        <div style='color:#94A3B8;font-size:0.85rem'>Sem serviço escalado{hoje_badge}</div>
                    </div>""", unsafe_allow_html=True)

            if not tem_servicos:
                st.info("Não foram encontrados serviços escalados neste mês.")

        # ── PRÓXIMOS SERVIÇOS ──
        else:
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

                # Verificar trocas aprovadas (excluindo matar remunerado)
                if not df_trocas.empty:
                    tr_v = df_trocas[
                        (df_trocas['data'] == d_s) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
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
                    # Ir buscar dados completos do novo serviço na escala
                    df_d = load_data(dt.strftime("%d-%m"))
                    serv_novo_nome = s_ex.rsplit('(', 1)[0].strip()
                    hor_novo = s_ex.rsplit('(', 1)[1].rstrip(')') if '(' in s_ex else ''
                    row_novo = None
                    if not df_d.empty:
                        mask_novo = (
                            (df_d['serviço'].astype(str).str.strip().str.lower() == serv_novo_nome.lower()) &
                            (df_d['horário'].astype(str).str.strip() == hor_novo.strip())
                        )
                        if mask_novo.any():
                            row_novo = df_d[mask_novo].iloc[0]
                    com_nome = get_nome_militar(df_util, com)
                    try:
                        obs_novo = str(row_novo.get('observações','') or '').strip() if row_novo is not None else ''
                    except Exception:
                        obs_novo = ''
                    obs_html_t = f'<p>📝 {obs_novo}</p>' if obs_novo else ''
                    # Colegas no mesmo serviço trocado (com trocas aplicadas)
                    colegas_troca_html = ''
                    if not df_d.empty and row_novo is not None:
                        colegas_orig_t = df_d[
                            (df_d['serviço'].astype(str).str.strip().str.lower() == serv_novo_nome.lower()) &
                            (df_d['horário'].astype(str).str.strip() == hor_novo.strip()) &
                            (df_d['id'].astype(str).str.strip() != u_id) &
                            (df_d['id'].astype(str).str.strip() != str(com).strip()) &
                            (df_d['id'].astype(str).str.strip() != '') &
                            (df_d['id'].astype(str).str.strip() != 'nan')
                        ]['id'].astype(str).str.strip().tolist()

                        ids_finais_t = set()
                        for c_id in colegas_orig_t:
                            saiu = False
                            if not df_trocas.empty:
                                tr_o = df_trocas[
                                    (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                                    (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                                    (df_trocas['id_origem'].astype(str) == c_id) &
                                    (df_trocas['servico_origem'].str.lower().str.contains(serv_novo_nome.lower()[:8], na=False)) &
                                    (df_trocas['servico_origem'].str.contains(hor_novo, na=False))
                                ]
                                if not tr_o.empty:
                                    saiu = True
                                    novo = str(tr_o.iloc[0]['id_destino'])
                                    if novo != u_id: ids_finais_t.add(novo)
                                tr_d = df_trocas[
                                    (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                                    (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                                    (df_trocas['id_destino'].astype(str) == c_id) &
                                    (df_trocas['servico_destino'].str.lower().str.contains(serv_novo_nome.lower()[:8], na=False)) &
                                    (df_trocas['servico_destino'].str.contains(hor_novo, na=False))
                                ]
                                if not tr_d.empty:
                                    saiu = True
                                    novo = str(tr_d.iloc[0]['id_origem'])
                                    if novo != u_id: ids_finais_t.add(novo)
                            if not saiu:
                                ids_finais_t.add(c_id)

                        if ids_finais_t:
                            partes = []
                            for c_id in sorted(ids_finais_t):
                                c_row = df_util[df_util['id'].astype(str).str.strip() == c_id] if 'id' in df_util.columns else pd.DataFrame()
                                if not c_row.empty:
                                    c_posto = c_row.iloc[0].get('posto','')
                                    c_nomes = c_row.iloc[0].get('nome','').strip().split()
                                    c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else ' '.join(c_nomes)
                                    partes.append(f"{c_id} {c_posto} {c_nome_curto}")
                                else:
                                    partes.append(c_id)
                            colegas_troca_html = f'<p style="font-size:0.78rem;color:#475569">👥 {" | ".join(partes)}</p>'
                    st.markdown(
                        f'<div class="card-servico card-troca">'
                        f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#92400E;">Troca Aprovada</span></p>'
                        f'<h3>🔄 {serv_novo_nome}</h3>'
                        f'<p>🕒 {hor_novo}</p>'
                        f'{colegas_troca_html}'
                        f'<p style="font-size:0.78rem;color:#92400E">🔄 c/ {com_nome}</p>'
                        f'{obs_html_t}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    dias_sem_dados = 0
                    encontrou_algum = True
                    # Verificar remunerados mesmo quando há troca de serviço
                    df_d_rem = load_data(dt.strftime("%d-%m"))
                    if not df_d_rem.empty and 'serviço' in df_d_rem.columns:
                        import unicodedata as _ud2r
                        def _nr(t): return _ud2r.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
                        rem_mil_t = df_d_rem[df_d_rem['id'].astype(str) == u_id]
                        rem_mil_t = rem_mil_t[rem_mil_t['serviço'].apply(_nr).str.contains('remu|grat', na=False)]
                        if not df_trocas.empty:
                            cedidos_t = df_trocas[
                                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                (df_trocas['id_destino'].astype(str) == u_id)
                            ]
                            for _, cd in cedidos_t.iterrows():
                                serv_cd = cd['servico_destino'].rsplit('(', 1)[0].strip()
                                hor_cd  = cd['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in cd['servico_destino'] else ''
                                rem_mil_t = rem_mil_t[~((rem_mil_t['serviço'].astype(str).str.strip().str.lower() == serv_cd.lower()) & (rem_mil_t['horário'].astype(str).str.strip() == hor_cd.strip()))]
                            matar_apr_t = df_trocas[
                                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                (df_trocas['id_origem'].astype(str) == u_id)
                            ]
                            for _, mt in matar_apr_t.iterrows():
                                serv_r2 = mt['servico_destino'].rsplit('(', 1)[0].strip()
                                hor_r2  = mt['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt['servico_destino'] else ''
                                linha_r2 = df_d_rem[(df_d_rem['serviço'].astype(str).str.strip().str.lower() == serv_r2.lower()) & (df_d_rem['horário'].astype(str).str.strip() == hor_r2.strip())]
                                if not linha_r2.empty:
                                    rem_mil_t = pd.concat([rem_mil_t, linha_r2.iloc[[0]]], ignore_index=True)
                        for _, rr in rem_mil_t.iterrows():
                            obs_r = str(rr.get('observações','') or '').strip()
                            obs_r_html = f'<p>📝 {obs_r}</p>' if obs_r else ''
                            serv_rr_t = str(rr['serviço']).strip().lower()
                            hor_rr_t  = str(rr['horário']).strip()
                            # Colegas no mesmo remunerado
                            colegas_r = df_d_rem[
                                (df_d_rem['serviço'].astype(str).str.strip().str.lower() == serv_rr_t) &
                                (df_d_rem['horário'].astype(str).str.strip() == hor_rr_t) &
                                (df_d_rem['id'].astype(str).str.strip() != u_id) &
                                (df_d_rem['id'].astype(str).str.strip() != '') &
                                (df_d_rem['id'].astype(str).str.strip() != 'nan')
                            ]
                            ids_r = []
                            for _, c in colegas_r.iterrows():
                                c_id = str(c['id']).strip()
                                if not df_trocas.empty:
                                    cedeu = df_trocas[(df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') & (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') & (df_trocas['id_destino'].astype(str) == c_id) & (df_trocas['servico_destino'].str.lower().str.contains(serv_rr_t[:10], na=False))]
                                    if not cedeu.empty:
                                        novo_id = str(cedeu.iloc[0]['id_origem'])
                                        if novo_id != u_id: ids_r.append(novo_id)
                                        continue
                                if c_id != u_id: ids_r.append(c_id)
                            colegas_r_html = ''
                            if ids_r:
                                partes = []
                                for c_id in ids_r:
                                    c_row = df_util[df_util['id'].astype(str).str.strip() == c_id] if 'id' in df_util.columns else pd.DataFrame()
                                    if not c_row.empty:
                                        c_nomes = c_row.iloc[0].get('nome','').strip().split()
                                        c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else ' '.join(c_nomes)
                                        partes.append(f"{c_id} {c_row.iloc[0].get('posto','')} {c_nome_curto}")
                                    else:
                                        partes.append(c_id)
                                colegas_r_html = f'<p style="font-size:0.78rem;color:#475569">👥 {" | ".join(partes)}</p>'
                            matar_html_t = ''
                            if not df_trocas.empty:
                                mt_este = df_trocas[(df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') & (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') & (df_trocas['id_origem'].astype(str) == u_id) & (df_trocas['servico_destino'].str.lower().str.contains(serv_rr_t[:10], na=False))]
                                if not mt_este.empty:
                                    cedente_nome = get_nome_militar(df_util, mt_este.iloc[0]['id_destino'])
                                    matar_html_t = f'<p style="font-size:0.78rem;color:#059669">🔄 c/ {cedente_nome}</p>'
                            st.markdown(f'<div class="card-servico card-rem"><p><b>💶 REMUNERADO</b></p><h3>💰 {rr["serviço"]}</h3><p>🕒 {rr["horário"]}</p>{colegas_r_html}{matar_html_t}{obs_r_html}</div>', unsafe_allow_html=True)
                else:
                    df_d = load_data(dt.strftime("%d-%m"))
                    if not df_d.empty:
                        m = df_d[df_d['id'].astype(str) == u_id]
                        if not m.empty:
                            row = m.iloc[0]
                            obs_val = str(row.get('observações', '') or '').strip()
                            obs_html = f'<p>📝 {obs_val}</p>' if obs_val else ''
                            # Escolher classe e ícone conforme o tipo de serviço
                            import unicodedata as _uds
                            def _ns(t): return _uds.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
                            s_norm = _ns(row['serviço'])
                            if any(x in s_norm for x in ['ferias','licen','doente']):
                                card_class, icone_s = 'card-ausencia', '🏖️'
                            elif 'folga' in s_norm:
                                card_class, icone_s = 'card-folga', '😴'
                            elif any(x in s_norm for x in ['tribunal','dilig']):
                                card_class, icone_s = 'card-tribunal', '⚖️'
                            else:
                                card_class, icone_s = 'card-meu', '🛡️'

                            # Colegas no mesmo serviço e horário (excluindo ausências e ADM)
                            colegas_html = ''
                            _excluir_cols = ['ferias','licen','doente','folga','pronto','secretaria','inquer','dilig','tribunal']
                            if not any(x in s_norm for x in _excluir_cols):
                                serv_meu = str(row['serviço']).strip().lower()
                                hor_meu  = str(row['horário']).strip()
                                colegas_orig = df_d[
                                    (df_d['serviço'].astype(str).str.strip().str.lower() == serv_meu) &
                                    (df_d['horário'].astype(str).str.strip() == hor_meu) &
                                    (df_d['id'].astype(str).str.strip() != u_id) &
                                    (df_d['id'].astype(str).str.strip() != '') &
                                    (df_d['id'].astype(str).str.strip() != 'nan')
                                ]['id'].astype(str).str.strip().tolist()

                                ids_finais = set()
                                for c_id in colegas_orig:
                                    saiu = False
                                    if not df_trocas.empty:
                                        tr_o = df_trocas[
                                            (df_trocas['data'] == d_s) &
                                            (df_trocas['status'] == 'Aprovada') &
                                            (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                                            (df_trocas['id_origem'].astype(str) == c_id) &
                                            (df_trocas['servico_origem'].str.lower().str.contains(serv_meu[:8], na=False)) &
                                            (df_trocas['servico_origem'].str.contains(hor_meu, na=False))
                                        ]
                                        tr_d = df_trocas[
                                            (df_trocas['data'] == d_s) &
                                            (df_trocas['status'] == 'Aprovada') &
                                            (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                                            (df_trocas['id_destino'].astype(str) == c_id) &
                                            (df_trocas['servico_destino'].str.lower().str.contains(serv_meu[:8], na=False)) &
                                            (df_trocas['servico_destino'].str.contains(hor_meu, na=False))
                                        ]
                                        if not tr_o.empty:
                                            saiu = True
                                            novo = str(tr_o.iloc[0]['id_destino'])
                                            if novo != u_id: ids_finais.add(novo)
                                        if not tr_d.empty:
                                            saiu = True
                                            novo = str(tr_d.iloc[0]['id_origem'])
                                            if novo != u_id: ids_finais.add(novo)
                                    if not saiu:
                                        ids_finais.add(c_id)

                                if ids_finais:
                                    partes = []
                                    for c_id in sorted(ids_finais):
                                        if 'id' in df_util.columns:
                                            c_row = df_util[df_util['id'].astype(str).str.strip() == c_id]
                                        else:
                                            c_row = pd.DataFrame()
                                        if not c_row.empty:
                                            c_posto = c_row.iloc[0].get('posto','')
                                            c_nome_completo = c_row.iloc[0].get('nome','')
                                            c_nomes = c_nome_completo.strip().split()
                                            c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else c_nome_completo
                                            partes.append(f"{c_id} {c_posto} {c_nome_curto}")
                                        else:
                                            partes.append(c_id)
                                    if partes:
                                        colegas_html = f'<p style="font-size:0.78rem;color:#475569">👥 {" | ".join(partes)}</p>'

                            st.markdown(
                                f'<div class="card-servico {card_class}">'
                                f'<p><b>{lbl}</b></p>'
                                f'<h3>{icone_s} {row["serviço"]}</h3>'
                                f'<p>🕒 {row["horário"]}</p>'
                                f'{colegas_html}'
                                f'{obs_html}'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                            # Verificar se tem remunerado no mesmo dia
                            df_rem_dia = load_data(dt.strftime("%d-%m"))
                            if not df_rem_dia.empty and 'serviço' in df_rem_dia.columns:
                                import unicodedata as _ud2
                                def _n(t): return _ud2.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')
                                # Remunerados escalados diretamente
                                rem_mil = df_rem_dia[df_rem_dia['id'].astype(str) == u_id]
                                rem_mil = rem_mil[rem_mil['serviço'].apply(_n).str.contains('remu|grat', na=False)]
                                # Excluir remunerados que foram cedidos (matar remunerado aprovado onde sou o cedente)
                                if not df_trocas.empty:
                                    cedidos = df_trocas[
                                        (df_trocas['data'] == d_s) &
                                        (df_trocas['status'] == 'Aprovada') &
                                        (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                        (df_trocas['id_destino'].astype(str) == u_id)
                                    ]
                                    for _, cd in cedidos.iterrows():
                                        serv_cd = cd['servico_destino'].rsplit('(', 1)[0].strip()
                                        hor_cd  = cd['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in cd['servico_destino'] else ''
                                        rem_mil = rem_mil[
                                            ~(
                                                (rem_mil['serviço'].astype(str).str.strip().str.lower() == serv_cd.lower()) &
                                                (rem_mil['horário'].astype(str).str.strip() == hor_cd.strip())
                                            )
                                        ]
                                # Remunerados obtidos via matar remunerado aprovado
                                if not df_trocas.empty:
                                    matar_apr = df_trocas[
                                        (df_trocas['data'] == d_s) &
                                        (df_trocas['status'] == 'Aprovada') &
                                        (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                        (df_trocas['id_origem'].astype(str) == u_id)
                                    ]
                                    for _, mt in matar_apr.iterrows():
                                        # Encontrar a linha do remunerado na escala
                                        serv_r = mt['servico_destino'].rsplit('(', 1)[0].strip()
                                        hor_r  = mt['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt['servico_destino'] else ''
                                        linha_rem = df_rem_dia[
                                            (df_rem_dia['serviço'].astype(str).str.strip().str.lower() == serv_r.lower()) &
                                            (df_rem_dia['horário'].astype(str).str.strip() == hor_r.strip())
                                        ]
                                        if not linha_rem.empty:
                                            rem_mil = pd.concat([rem_mil, linha_rem.iloc[[0]]], ignore_index=True)
                                for _, rr in rem_mil.iterrows():
                                    obs_r = str(rr.get('observações', '') or '').strip()
                                    obs_r_html = f'<p>📝 {obs_r}</p>' if obs_r else ''
                                    # Colegas no mesmo remunerado
                                    # Substituir IDs tendo em conta matar remunerado aprovado
                                    serv_rr = str(rr['serviço']).strip().lower()
                                    hor_rr  = str(rr['horário']).strip()
                                    obs_rr  = str(rr.get('observações','')).strip().lower()
                                    colegas_rem = df_rem_dia[
                                        (df_rem_dia['serviço'].astype(str).str.strip().str.lower() == serv_rr) &
                                        (df_rem_dia['horário'].astype(str).str.strip() == hor_rr) &
                                        (df_rem_dia['id'].astype(str).str.strip() != u_id) &
                                        (df_rem_dia['id'].astype(str).str.strip() != '') &
                                        (df_rem_dia['id'].astype(str).str.strip() != 'nan')
                                    ]
                                    # Se não encontrou, tentar sem horário (fallback)
                                    if colegas_rem.empty:
                                        colegas_rem = df_rem_dia[
                                            (df_rem_dia['serviço'].astype(str).str.strip().str.lower() == serv_rr) &
                                            (df_rem_dia['observações'].astype(str).str.strip().str.lower() == obs_rr) &
                                            (df_rem_dia['id'].astype(str).str.strip() != '') &
                                            (df_rem_dia['id'].astype(str).str.strip() != 'nan')
                                        ] if 'observações' in df_rem_dia.columns and obs_rr else colegas_rem
                                    # Construir lista real de quem vai fazer o remunerado
                                    ids_reais = []
                                    for _, c in colegas_rem.iterrows():
                                        c_id = str(c['id']).strip()
                                        # Ver se este ID cedeu o remunerado a alguém
                                        if not df_trocas.empty:
                                            cedeu = df_trocas[
                                                (df_trocas['data'] == d_s) &
                                                (df_trocas['status'] == 'Aprovada') &
                                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                                (df_trocas['id_destino'].astype(str) == c_id) &
                                                (df_trocas['servico_destino'].str.lower().str.contains(serv_rr[:10], na=False))
                                            ]
                                            if not cedeu.empty:
                                                # Substituir pelo novo titular
                                                novo_id = str(cedeu.iloc[0]['id_origem'])
                                                if novo_id != u_id:
                                                    ids_reais.append(novo_id)
                                                continue
                                        if c_id != u_id:
                                            ids_reais.append(c_id)

                                    colegas_rem_html = ''
                                    if ids_reais:
                                        partes = []
                                        for c_id in ids_reais:
                                            if 'id' in df_util.columns:
                                                c_row = df_util[df_util['id'].astype(str).str.strip() == c_id]
                                            else:
                                                c_row = pd.DataFrame()
                                            if not c_row.empty:
                                                c_posto = c_row.iloc[0].get('posto','')
                                                c_nome_completo = c_row.iloc[0].get('nome','')
                                                c_nomes = c_nome_completo.strip().split()
                                                c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else c_nome_completo
                                                partes.append(f"{c_id} {c_posto} {c_nome_curto}")
                                            else:
                                                partes.append(c_id)
                                        colegas_rem_html = f'<p style="font-size:0.78rem;color:#475569">👥 {" | ".join(partes)}</p>'
                                    # Verificar se foi obtido via matar remunerado
                                    matar_html = ''
                                    if not df_trocas.empty:
                                        serv_rr_full = f"{str(rr['serviço']).strip()} ({str(rr['horário']).strip()})"
                                        mt_este = df_trocas[
                                            (df_trocas['data'] == d_s) &
                                            (df_trocas['status'] == 'Aprovada') &
                                            (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                            (df_trocas['id_origem'].astype(str) == u_id) &
                                            (df_trocas['servico_destino'].str.lower().str.contains(str(rr['serviço']).strip().lower()[:10], na=False))
                                        ]
                                        if not mt_este.empty:
                                            cedente_nome = get_nome_militar(df_util, mt_este.iloc[0]['id_destino'])
                                            matar_html = f'<p style="font-size:0.78rem;color:#059669">🔄 c/ {cedente_nome}</p>'
                                    st.markdown(
                                        f'<div class="card-servico card-rem">'
                                        f'<p><b>💶 REMUNERADO</b></p>'
                                        f'<h3>💰 {rr["serviço"]}</h3>'
                                        f'<p>🕒 {rr["horário"]}</p>'
                                        f'{colegas_rem_html}'
                                        f'{matar_html}'
                                        f'{obs_r_html}'
                                        f'</div>',
                                        unsafe_allow_html=True
                                    )
                            encontrou_algum = True
                        # Aba existe mas o militar não está escalado
                        else:
                            is_fds_a = dt.weekday() >= 5
                            is_fer_a = dt.date() in feriados
                            # Verificar se está de férias
                            if militar_de_ferias(u_id, dt.date(), df_ferias):
                                st.markdown(
                                    f'<div class="card-servico card-ausencia">'
                                    f'<p><b>{lbl}</b></p>'
                                    f'<h3>🏖️ Férias</h3>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                encontrou_algum = True
                            else:
                                borda_a = "3px solid #DC2626" if is_fer_a else ("3px solid #F59E0B" if is_fds_a else "3px solid #E2E8F0")
                                cor_a = "#DC2626" if is_fer_a else ("#94A3B8" if not is_fds_a else "#B45309")
                                msg_a = "🎌 Feriado" if is_fer_a else "Sem serviço escalado"
                                st.markdown(
                                    f'<div style="background:#F8FAFC;border-left:{borda_a};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px">'
                                    f'<div style="min-width:48px;text-align:center">'
                                    f'<div style="font-size:1.2rem;font-weight:800;color:{cor_a};line-height:1">{dt.day}</div>'
                                    f'<div style="font-size:0.7rem;color:{cor_a}">{"Sáb" if dt.weekday()==5 else "Dom" if dt.weekday()==6 else dt.strftime("%a").capitalize()}</div>'
                                    f'</div>'
                                    f'<div style="color:{cor_a};font-size:0.85rem">{msg_a}</div>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                        dias_sem_dados = 0
                    else:
                        dias_sem_dados += 1

                i += 1

            if not encontrou_algum:
                st.info("Não foram encontrados serviços escalados a partir de hoje.")


    # --- 📊 ESTATÍSTICAS ---
    elif menu == "📊 Estatísticas":
        st.title("📊 Estatísticas de Serviço")

        if is_admin:
            militares_opts = {f"{r['posto']} {r['nome']} (ID: {r['id']})": str(r['id']) for _, r in df_util.iterrows()}
            sel_mil = st.selectbox("Selecionar militar:", ["— O meu próprio —"] + list(militares_opts.keys()))
            alvo_id   = u_id if sel_mil == "— O meu próprio —" else militares_opts[sel_mil]
            alvo_nome = u_nome if sel_mil == "— O meu próprio —" else sel_mil
        else:
            alvo_id   = u_id
            alvo_nome = u_nome

        st.caption(f"A contar serviços originais escalados para **{alvo_nome}**")

        _gsheet_url = st.secrets["gsheet_url"]
        _sheet_id   = _gsheet_url.split("/d/")[1].split("/")[0]

        with st.spinner("A carregar histórico..."):
            df_stats = contar_servicos_historico(alvo_id, _sheet_id)

        if df_stats.empty:
            st.info("Não foram encontrados serviços no histórico.")
        else:
            def categorizar(tipo):
                if 'ocorr' in tipo: return 'Patrulha Ocorrências'
                if any(x in tipo for x in ['patrulha','ronda','po ','vtr']): return 'Patrulha'
                if 'folga' in tipo: return 'Folga'
                if any(x in tipo for x in ['remu','grat']): return 'Remunerado'
                if 'apoio' in tipo: return 'Apoio Atendimento'
                if 'atendimento' in tipo: return 'Atendimento'
                if any(x in tipo for x in ['feria','licen','doente']): return 'Férias'
                return 'Outros'

            df_stats['categoria'] = df_stats['tipo'].apply(categorizar)

            # ── Filtro mensal / anual ──
            meses_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
            hoje = datetime.now()

            periodo = st.radio("Período:", ["📅 Mensal", "📆 Anual"], horizontal=True)

            if periodo == "📅 Mensal":
                # extrair meses disponíveis do histórico
                meses_disp = sorted(df_stats['mes'].unique(),
                                    key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
                mes_atual = f"{hoje.month:02d}/{hoje.year}"
                idx_default = meses_disp.index(mes_atual) if mes_atual in meses_disp else len(meses_disp) - 1

                def fmt_mes(m):
                    mm, aa = m.split('/')
                    return f"{meses_pt[int(mm)-1]} {aa}"

                mes_sel = st.selectbox("Mês:", meses_disp,
                                       index=idx_default,
                                       format_func=fmt_mes)
                df_filtrado = df_stats[df_stats['mes'] == mes_sel]
                st.caption(f"A mostrar: **{fmt_mes(mes_sel)}**")

            else:
                anos_disp = sorted(df_stats['mes'].apply(lambda x: x.split('/')[1]).unique(), reverse=True)
                ano_atual = str(hoje.year)
                idx_ano = anos_disp.index(ano_atual) if ano_atual in anos_disp else 0
                ano_sel = st.selectbox("Ano:", anos_disp, index=idx_ano)
                df_filtrado = df_stats[df_stats['mes'].str.endswith(f"/{ano_sel}")]
                st.caption(f"A mostrar: **{ano_sel}**")

            st.markdown("---")

            if df_filtrado.empty:
                st.info("Sem serviços no período selecionado.")
            else:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown("**Por categoria**")
                    df_cat = df_filtrado.groupby('categoria').size().reset_index(name='total').sort_values('total', ascending=False)
                    st.dataframe(df_cat, use_container_width=True, hide_index=True)
                with col_g2:
                    st.markdown("**Detalhe por serviço**")
                    df_det = df_filtrado.groupby('serviço').size().reset_index(name='vezes').sort_values('vezes', ascending=False)
                    st.dataframe(df_det, use_container_width=True, hide_index=True)

    # --- 🏖️ FÉRIAS ---
    elif menu == "🏖️ Férias":
        st.title("🏖️ Plano de Férias")
        ano_sel_f = st.selectbox("Ano:", [ano_atual, ano_atual + 1], index=0)
        df_f = load_ferias(ano_sel_f)
        fer_f = load_feriados(ano_sel_f)

        if df_f.empty:
            st.info(f"Não há plano de férias para {ano_sel_f}.")
        else:
            cols_f = df_f.columns.tolist()
            id_col_f = 'id' if 'id' in cols_f else cols_f[0]
            ini_cols_f = [c for c in cols_f if 'ini' in c.lower()]
            fim_cols_f  = [c for c in cols_f if 'fim' in c.lower()]
            dias_cols_f = [c for c in cols_f if 'dias' in c.lower() and 'total' not in c.lower()]
            total_col_f = next((c for c in cols_f if 'total' in c.lower()), None)

            if is_admin:
                # Admin vê todos os militares
                st.markdown("#### 👥 Plano Geral")
                for _, row_f in df_f.iterrows():
                    mid_f = str(row_f.get(id_col_f, '')).strip()
                    if not mid_f: continue
                    nome_f = get_nome_militar(df_util, mid_f)
                    total_f = str(row_f.get(total_col_f, '')).strip() if total_col_f else ''
                    with st.expander(f"👤 {nome_f} {f'— {total_f} dias' if total_f and total_f != 'nan' else ''}"):
                        for ini_c, fim_c in zip(ini_cols_f, fim_cols_f):
                            ini_v = str(row_f.get(ini_c, '')).strip()
                            fim_v = str(row_f.get(fim_c, '')).strip()
                            if not ini_v or ini_v == 'nan': continue
                            # Calcular dias úteis
                            try:
                                ini_d = datetime.strptime(ini_v, '%d/%m/%Y').date()
                                fim_d = datetime.strptime(fim_v, '%d/%m/%Y').date()
                                du = sum(1 for n in range((fim_d - ini_d).days + 1)
                                        if (ini_d + timedelta(days=n)).weekday() < 5
                                        and (ini_d + timedelta(days=n)) not in fer_f)
                                st.markdown(f"📅 **{ini_v}** → **{fim_v}** &nbsp;·&nbsp; {du} dias úteis")
                            except:
                                st.markdown(f"📅 {ini_v} → {fim_v}")
            else:
                # Militar vê só as suas férias
                mil_f = df_f[df_f[id_col_f].astype(str).str.strip() == u_id]
                if mil_f.empty:
                    st.info("Não tens férias planeadas para este ano.")
                else:
                    row_f = mil_f.iloc[0]
                    total_f = str(row_f.get(total_col_f, '')).strip() if total_col_f else ''
                    if total_f and total_f != 'nan':
                        st.metric("Total de dias úteis", total_f)
                    st.markdown("---")
                    for ini_c, fim_c in zip(ini_cols_f, fim_cols_f):
                        ini_v = str(row_f.get(ini_c, '')).strip()
                        fim_v = str(row_f.get(fim_c, '')).strip()
                        if not ini_v or ini_v == 'nan': continue
                        try:
                            ini_d = datetime.strptime(ini_v, '%d/%m/%Y').date()
                            fim_d = datetime.strptime(fim_v, '%d/%m/%Y').date()
                            du = sum(1 for n in range((fim_d - ini_d).days + 1)
                                    if (ini_d + timedelta(days=n)).weekday() < 5
                                    and (ini_d + timedelta(days=n)) not in fer_f)
                            num_periodo = ini_cols_f.index(ini_c) + 1
                            st.markdown(
                                f'<div class="card-servico card-ausencia">'
                                f'<p><b>Período {num_periodo}</b></p>'
                                f'<h3>🏖️ {ini_v} → {fim_v}</h3>'
                                f'<p>📆 {du} dias úteis</p>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                        except:
                            st.markdown(f"📅 {ini_v} → {fim_v}")

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

            # Aplicar trocas aprovadas (excluindo remunerados e matar remunerado)
            if not df_trocas.empty:
                tr_v = df_trocas[
                    (df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) &
                    (df_trocas['status'] == 'Aprovada') &
                    (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                ]
                mask_rem = df_at['serviço'].str.lower().str.contains('remu|grat', na=False)
                for _, t in tr_v.iterrows():
                    m_o = (df_at['id'].astype(str) == str(t['id_origem'])) & ~mask_rem
                    if m_o.any():
                        df_at.loc[m_o, 'id_disp'] = f"{t['id_destino']} 🔄 {t['id_origem']}"
                    m_d = (df_at['id'].astype(str) == str(t['id_destino'])) & ~mask_rem
                    if m_d.any():
                        df_at.loc[m_d, 'id_disp'] = f"{t['id_origem']} 🔄 {t['id_destino']}"

                # Aplicar matar remunerado — mesmo formato que trocas normais
                matar_apr = df_trocas[
                    (df_trocas['data'] == d_sel.strftime('%d/%m/%Y')) &
                    (df_trocas['status'] == 'Aprovada') &
                    (df_trocas['servico_origem'] == 'MATAR_REMUNERADO')
                ]
                for _, mt in matar_apr.iterrows():
                    serv_r = mt['servico_destino'].rsplit('(', 1)[0].strip()
                    hor_r  = mt['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt['servico_destino'] else ''
                    mask_linha = (
                        df_at['serviço'].astype(str).str.strip().str.lower() == serv_r.lower()
                    ) & (df_at['horário'].astype(str).str.strip() == hor_r.strip())
                    # Linha do cedente — substitui pelo novo titular
                    m_cedente = mask_linha & (df_at['id'].astype(str) == str(mt['id_destino']))
                    if m_cedente.any():
                        df_at.loc[m_cedente, 'id_disp'] = f"{mt['id_origem']} 🔄 {mt['id_destino']}"

            # Adicionar militares de férias que não estão na escala diária
            if not df_ferias.empty and not df_util.empty:
                ids_na_escala = set(df_at['id'].astype(str).str.strip().tolist())
                cols_f = df_ferias.columns.tolist()
                id_col_f = 'id' if 'id' in cols_f else cols_f[0]
                for _, row_f in df_ferias.iterrows():
                    mid_f = str(row_f.get(id_col_f, '')).strip()
                    if not mid_f or mid_f in ids_na_escala:
                        continue
                    if militar_de_ferias(mid_f, d_sel, df_ferias):
                        nova_linha = {c: '' for c in df_at.columns}
                        nova_linha['id'] = mid_f
                        nova_linha['id_disp'] = mid_f
                        nova_linha['serviço'] = 'Férias'
                        nova_linha['horário'] = ''
                        df_at = pd.concat([df_at, pd.DataFrame([nova_linha])], ignore_index=True)

            pdf_bytes = gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at)
            col_pdf, col_full, _ = st.columns([1, 1.5, 3])
            with col_pdf:
                st.download_button(
                    "📥 Escala do Dia",
                    pdf_bytes,
                    file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf",
                    mime="application/pdf"
                )
            with col_full:
                if st.button("📦 Gerar Escala Completa (hoje→)"):
                    with st.spinner("A gerar PDF com todas as escalas disponíveis..."):
                        import tempfile, os, io as _io
                        try:
                            from pypdf import PdfWriter, PdfReader
                        except ImportError:
                            from PyPDF2 import PdfWriter, PdfReader
                        writer = PdfWriter()
                        hj2 = datetime.now()
                        dias_sem2 = 0
                        j2 = 0
                        paginas = 0
                        while dias_sem2 < 5:
                            dt2 = hj2 + timedelta(days=j2)
                            df_d2 = load_data(dt2.strftime("%d-%m"))
                            if not df_d2.empty:
                                df_d2['id_disp'] = df_d2['id'].astype(str)
                                if not df_trocas.empty:
                                    tr2 = df_trocas[
                                        (df_trocas['data'] == dt2.strftime('%d/%m/%Y')) &
                                        (df_trocas['status'] == 'Aprovada') &
                                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                                    ]
                                    mask_rem2 = df_d2['serviço'].str.lower().str.contains('remu|grat', na=False)
                                    for _, t2 in tr2.iterrows():
                                        m_o2 = (df_d2['id'].astype(str) == str(t2['id_origem'])) & ~mask_rem2
                                        if m_o2.any(): df_d2.loc[m_o2, 'id_disp'] = f"{t2['id_destino']} 🔄 {t2['id_origem']}"
                                        m_d2 = (df_d2['id'].astype(str) == str(t2['id_destino'])) & ~mask_rem2
                                        if m_d2.any(): df_d2.loc[m_d2, 'id_disp'] = f"{t2['id_origem']} 🔄 {t2['id_destino']}"
                                    # Matar remunerado
                                    matar2 = df_trocas[
                                        (df_trocas['data'] == dt2.strftime('%d/%m/%Y')) &
                                        (df_trocas['status'] == 'Aprovada') &
                                        (df_trocas['servico_origem'] == 'MATAR_REMUNERADO')
                                    ]
                                    for _, mt2 in matar2.iterrows():
                                        serv_r2 = mt2['servico_destino'].rsplit('(', 1)[0].strip()
                                        hor_r2  = mt2['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt2['servico_destino'] else ''
                                        m_ced2 = (
                                            (df_d2['serviço'].astype(str).str.strip().str.lower() == serv_r2.lower()) &
                                            (df_d2['horário'].astype(str).str.strip() == hor_r2.strip()) &
                                            (df_d2['id'].astype(str) == str(mt2['id_destino']))
                                        )
                                        if m_ced2.any(): df_d2.loc[m_ced2, 'id_disp'] = f"{mt2['id_origem']} 🔄 {mt2['id_destino']}"
                                # Adicionar militares de férias
                                if not df_ferias.empty and not df_util.empty:
                                    ids_esc2 = set(df_d2['id'].astype(str).str.strip().tolist())
                                    cols_f2 = df_ferias.columns.tolist()
                                    id_col_f2 = 'id' if 'id' in cols_f2 else cols_f2[0]
                                    for _, row_f2 in df_ferias.iterrows():
                                        mid_f2 = str(row_f2.get(id_col_f2, '')).strip()
                                        if not mid_f2 or mid_f2 in ids_esc2: continue
                                        if militar_de_ferias(mid_f2, dt2.date(), df_ferias):
                                            nl2 = {c: '' for c in df_d2.columns}
                                            nl2['id'] = mid_f2
                                            nl2['id_disp'] = mid_f2
                                            nl2['serviço'] = 'Férias'
                                            nl2['horário'] = ''
                                            df_d2 = pd.concat([df_d2, pd.DataFrame([nl2])], ignore_index=True)
                                pb2 = gerar_pdf_escala_dia(dt2.strftime("%d/%m/%Y"), df_d2)
                                reader = PdfReader(_io.BytesIO(pb2))
                                for pg in reader.pages:
                                    writer.add_page(pg)
                                paginas += 1
                                dias_sem2 = 0
                            else:
                                dias_sem2 += 1
                            j2 += 1
                        if paginas > 0:
                            buf = _io.BytesIO()
                            writer.write(buf)
                            st.download_button(
                                f"⬇️ Descarregar ({paginas} dias)",
                                data=buf.getvalue(),
                                file_name=f"Escala_Completa_{datetime.now().strftime('%d_%m_%Y')}.pdf",
                                mime="application/pdf",
                                key="dl_completa"
                            )
                        else:
                            st.info("Não há escalas disponíveis.")

            # Remover linhas sem militar para a visualização na escala geral
            df_at = _limpar_sem_militar(df_at)

            # Separar ausências primeiro (inclui férias, licenças, doentes, diligências)
            df_aus, df_res = filtrar_secao(["férias", "licença", "doente", "diligência"], df_at)

            # Extrair cada grupo do df_res por ordem
            df_cmd,  df_res = filtrar_secao(["pronto", "secretaria", "inquérito"],    df_res)
            df_apoi, df_res = filtrar_secao(["apoio"],                                 df_res)
            df_aten, df_res = filtrar_secao(["atendimento"],                           df_res)
            df_pat,  df_res = filtrar_secao(["po", "patrulha", "ronda", "vtr", "giro"], df_res)
            df_remu, df_res = filtrar_secao(["remu", "grat"],                            df_res)
            df_folga,df_res = filtrar_secao(["folga"],                                   df_res)
            df_outros       = df_res
            # Separar Patrulha Ocorrências das outras patrulhas
            df_pat_ocorr, df_pat_outras = filtrar_secao(["ocorr"], df_pat)

            mostrar_secao("Comando e Administrativos", df_cmd)
            mostrar_secao("Atendimento",               df_aten,       esconder_servico=True)
            mostrar_secao("Apoio ao Atendimento",      df_apoi,       esconder_servico=True)
            mostrar_secao("Patrulha Ocorrências",      df_pat_ocorr,  mostrar_extras=True, esconder_servico=True)
            mostrar_secao("Patrulhas",                 df_pat_outras, mostrar_extras=True)
            mostrar_secao("Outros Serviços",           df_outros,     mostrar_extras=True, excluir_cols=['giro'])
            # Remunerados: horário | militares | observações (sem rádio/indicativo)
            if not df_remu.empty:
                with st.expander("🔹 REMUNERADOS", expanded=True):
                    cols_grp_r = ['horário'] + [c for c in ['observações'] if c in df_remu.columns]
                    ag_r = df_remu.groupby(cols_grp_r, sort=False)['id_disp'] \
                                  .apply(lambda x: ', '.join(x)).reset_index()
                    col_order = ['horário', 'id_disp'] + [c for c in cols_grp_r if c != 'horário']
                    ag_r = ag_r[col_order].rename(columns={'id_disp': 'Militares', 'horário': 'Horário', 'serviço': 'Serviço', 'observações': 'Observações'})
                    st.markdown(_render_tabela(ag_r), unsafe_allow_html=True)
            if not df_folga.empty:
                with st.expander("🔹 FOLGA", expanded=True):
                    ag_f = df_folga.groupby('serviço', sort=False)['id_disp'] \
                                   .apply(lambda x: ', '.join(x)).reset_index()
                    st.markdown(_render_tabela(ag_f.rename(columns={'id_disp': 'Militares', 'serviço': 'Serviço'})), unsafe_allow_html=True)

            if not df_aus.empty:
                with st.expander("🔹 AUSENTES", expanded=True):
                    ag = df_aus.groupby('serviço', sort=False)['id_disp'] \
                               .apply(lambda x: ', '.join(x)).reset_index()
                    st.markdown(_render_tabela(ag.rename(columns={'id_disp': 'Militares', 'serviço': 'Serviço'})), unsafe_allow_html=True)

    # --- 🔄 SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca de Serviço")

        tipo_troca = st.radio(
            "Tipo de pedido:",
            ["🔄 Troca Simples", "🔁 Troca a 3", "❌ Matar Remunerado"],
            horizontal=True
        )
        st.markdown("---")

        dt_s = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_data(dt_s.strftime("%d-%m"))

        if df_d.empty:
            st.info("Não existem dados para esta data.")
        else:
            df_d = df_d.copy()
            # Pré-carregar dias adjacentes uma só vez para verificação de descanso
            df_ant = load_data((dt_s - timedelta(days=1)).strftime("%d-%m"))
            df_seg = load_data((dt_s + timedelta(days=1)).strftime("%d-%m"))
            # Aplicar trocas aprovadas a TODOS os militares no df_d (excluindo remunerados)
            # para que as listas mostrem o serviço real de cada um
            servico_override = None
            if not df_trocas.empty:
                tr_dia = df_trocas[
                    (df_trocas['data'] == dt_s.strftime('%d/%m/%Y')) &
                    (df_trocas['status'] == 'Aprovada') &
                    (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                ]
                mask_rem = df_d['serviço'].str.lower().str.contains('remu|grat', na=False)
                for _, t in tr_dia.iterrows():
                    id_o = str(t['id_origem']).strip()
                    id_dest = str(t['id_destino']).strip()
                    s_o = t['servico_origem']; s_d_t = t['servico_destino']
                    # extrair serviço e horário de cada lado
                    serv_o = s_o.rsplit('(', 1)[0].strip()
                    hor_o  = s_o.rsplit('(', 1)[1].rstrip(')') if '(' in s_o else ''
                    serv_d2 = s_d_t.rsplit('(', 1)[0].strip()
                    hor_d2  = s_d_t.rsplit('(', 1)[1].rstrip(')') if '(' in s_d_t else ''
                    # militar origem passa a ter serviço destino
                    m_o = (df_d['id'].astype(str).str.strip() == id_o) & ~mask_rem
                    if m_o.any():
                        df_d.loc[m_o, 'serviço'] = serv_d2
                        if hor_d2: df_d.loc[m_o, 'horário'] = hor_d2
                    # militar destino passa a ter serviço origem
                    m_d = (df_d['id'].astype(str).str.strip() == id_dest) & ~mask_rem
                    if m_d.any():
                        df_d.loc[m_d, 'serviço'] = serv_o
                        if hor_o: df_d.loc[m_d, 'horário'] = hor_o
                    # registar override do próprio utilizador
                    if id_o == u_id.strip():
                        servico_override = s_d_t
                    elif id_dest == u_id.strip():
                        servico_override = s_o

            meu = df_d[df_d['id'].astype(str) == u_id]

            # ── Troca Simples ──
            if tipo_troca == "🔄 Troca Simples":
                if meu.empty:
                    st.warning("Não tens serviço escalado neste dia.")
                else:
                    meu_s = servico_override if servico_override else f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                    st.info(f"📋 O teu serviço: **{meu_s}**")
                    meu_serv_orig = meu.iloc[0]['serviço']
                    meu_hor_orig  = meu.iloc[0]['horário']
                    estou_de_folga = 'folga' in meu_serv_orig.lower()
                    base_mask = (
                        (df_d['id'].astype(str).str.strip() != u_id) &
                        (df_d['id'].astype(str).str.strip() != '') &
                        (df_d['id'].astype(str).str.strip() != 'nan') &
                        ~((df_d['serviço'] == meu_serv_orig) & (df_d['horário'] == meu_hor_orig)) &
                        ~(estou_de_folga & df_d['serviço'].str.lower().str.contains('folga', na=False))
                    )
                    # Folgas: disponíveis sempre (sem verificação de descanso)
                    mask_folga = df_d['serviço'].str.lower().str.contains('folga', na=False)
                    cols_folga = df_d[base_mask & mask_folga]
                    # Restantes: sujeitos a impedimentos e verificação de descanso
                    cols = df_d[base_mask & ~mask_folga & (~df_d['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False))]
                    if cols.empty and cols_folga.empty:
                        st.warning("Não há militares disponíveis para troca neste dia.")
                    else:
                        meu_serv_nome = meu_s.rsplit('(', 1)[0].strip()
                        meu_hor_val   = meu_s.rsplit('(', 1)[1].rstrip(')') if '(' in meu_s else meu.iloc[0]['horário']
                        opts = []
                        # Folgas — verificar só o descanso do militar de folga (destino)
                        for _, row_c in cols_folga.iterrows():
                            id_c   = str(row_c['id'])
                            serv_c = str(row_c['serviço'])
                            hor_c  = str(row_c['horário'])
                            erros_destino = verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg)
                            erros_dest_only = [e for e in erros_destino if e.startswith("O militar de destino")]
                            if not erros_dest_only:
                                nome_c = get_nome_militar(df_util, id_c)
                                opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")
                        # Restantes — com verificação de descanso
                        for _, row_c in cols.iterrows():
                            id_c   = str(row_c['id'])
                            serv_c = str(row_c['serviço'])
                            hor_c  = str(row_c['horário'])
                            if not verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg):
                                nome_c = get_nome_militar(df_util, id_c)
                                opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")
                        if not opts:
                            st.warning("Não há militares disponíveis para troca neste dia (restrições de descanso).")
                        else:
                            with st.form("tr_simples"):
                                alvo = st.selectbox("👤 Trocar com:", opts)
                                st.markdown("<br>", unsafe_allow_html=True)
                                if st.form_submit_button("📨 ENVIAR PEDIDO", use_container_width=True):
                                    id_d  = alvo.split(" ")[0]
                                    s_d   = alvo.split(" - ", 1)[1]
                                    if salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), u_id, meu_s, id_d, s_d, "Pendente_Militar", ""]):
                                        st.success("✅ Pedido enviado com sucesso!")

            # ── Troca a 3 ──
            elif tipo_troca == "🔁 Troca a 3":
                if meu.empty:
                    st.warning("Não tens serviço escalado nesse dia.")
                else:
                    if servico_override:
                        meu_serv_t3 = servico_override.split('(')[0].strip()
                        meu_hor_t3  = servico_override.split('(')[1].rstrip(')') if '(' in servico_override else ''
                    else:
                        meu_serv_t3 = meu.iloc[0]['serviço']
                        meu_hor_t3  = meu.iloc[0]['horário']
                    st.info(f"📋 O teu serviço: **{meu_serv_t3} ({meu_hor_t3})**")
                    outros_t3 = df_d[
                        (df_d['id'].astype(str).str.strip() != u_id) &
                        (df_d['id'].astype(str).str.strip() != '') &
                        (df_d['id'].astype(str).str.strip() != 'nan')
                    ]
                    outros_t3 = outros_t3[~outros_t3['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False)]
                    opcoes_t3 = {f"{r['id']} — {r['serviço']} ({r['horário']})": r['id'] for _, r in outros_t3.iterrows() if str(r['id']).strip()}
                    if len(opcoes_t3) < 2:
                        st.warning("Não há militares suficientes disponíveis para uma troca a 3.")
                    else:
                        sel1 = st.selectbox("1º militar (vai para o teu serviço):", list(opcoes_t3.keys()), key="t3_sel1")
                        sel2 = st.selectbox("2º militar (vai para o serviço do 1º):", [o for o in opcoes_t3.keys() if o != sel1], key="t3_sel2")
                        id1   = str(opcoes_t3[sel1])
                        id2   = str(opcoes_t3[sel2])
                        row1  = df_d[df_d['id'].astype(str) == id1].iloc[0]
                        row2  = df_d[df_d['id'].astype(str) == id2].iloc[0]
                        serv1 = row1['serviço']; hor1 = row1['horário']
                        serv2 = row2['serviço']; hor2 = row2['horário']
                        st.markdown(f"""
                        **Resumo da troca a 3:**
                        - **Tu** `{meu_serv_t3}` → ficas com o serviço do 1º
                        - **{sel1}** `{serv1}` → vai para o teu serviço
                        - **{sel2}** `{serv2}` → vai para o serviço do 1º
                        """)
                        if st.button("📨 Enviar pedidos de troca a 3", use_container_width=True):
                            data_str = dt_s.strftime('%d/%m/%Y')
                            meu_serv_t3_completo = servico_override if servico_override else f"{meu_serv_t3} ({meu_hor_t3})"
                            linha1 = [data_str, u_id, meu_serv_t3_completo, id1, f"{serv1} ({hor1})", "Pendente_Militar", "", "", ""]
                            linha2 = [data_str, id1, f"{serv1} ({hor1})", id2, f"{serv2} ({hor2})", "Pendente_Militar", "", "", ""]
                            salvar_troca_gsheet(linha1)
                            salvar_troca_gsheet(linha2)
                            st.success("✅ Dois pedidos de troca enviados! Aguarda aceitação de ambos.")

            # ── Matar Remunerado ──
            elif tipo_troca == "❌ Matar Remunerado":
                rem_dia = df_d[
                    (df_d['id'].astype(str).str.strip() != u_id) &
                    (df_d['id'].astype(str).str.strip() != '') &
                    (df_d['id'].astype(str).str.strip() != 'nan') &
                    (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))
                ]
                if rem_dia.empty:
                    st.info("Não há serviços remunerados escalados neste dia.")
                else:
                    # Verificar sobreposição de horário com o meu serviço
                    meu_ini, meu_fim = (None, None)
                    if not meu.empty and meu.iloc[0]['horário']:
                        meu_ini, meu_fim = _parse_horario(meu.iloc[0]['horário'])

                    opts_rem = []
                    for _, r in rem_dia.iterrows():
                        hor_rem = str(r['horário']).strip()
                        if meu_ini is not None and hor_rem:
                            ini_r, fim_r = _parse_horario(hor_rem)
                            if ini_r is not None:
                                if not (fim_r <= meu_ini or ini_r >= meu_fim):
                                    continue
                        nome_r = get_nome_militar(df_util, str(r['id']))
                        opts_rem.append(f"{r['id']} {nome_r} - {r['serviço']} ({hor_rem})")

                    if not opts_rem:
                        st.warning("Não há remunerados disponíveis sem sobreposição de horário.")
                    else:
                        with st.form("matar_rem"):
                            st.info("Seleciona o remunerado que queres fazer.")
                            rem_sel = st.selectbox("Serviço remunerado:", opts_rem)
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.form_submit_button("✅ QUERO FAZER ESTE REMUNERADO", use_container_width=True):
                                id_d = rem_sel.split(" ")[0]
                                s_d  = rem_sel.split(" - ", 1)[1]
                                if salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), u_id, "MATAR_REMUNERADO", id_d, s_d, "Pendente_Militar", ""]):
                                    st.success("✅ Pedido enviado! Aguarda aceitação do militar.")

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
                    is_matar = str(r['servico_origem']) == 'MATAR_REMUNERADO'
                    try:
                        dt_r = datetime.strptime(r['data'], '%d/%m/%Y')
                        dia_sem_r = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"][dt_r.weekday()]
                        data_fmt = f"{r['data']} ({dia_sem_r})"
                    except:
                        data_fmt = r['data']
                    if is_matar:
                        st.markdown(
                            f'<div class="card-servico card-troca">'
                            f'<h3>📅 {data_fmt}</h3>'
                            f'<p>👤 <b>{nome_orig}</b> quer fazer o teu remunerado</p>'
                            f'<p>🔴 O teu remunerado: <b>{r["servico_destino"]}</b></p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<div class="card-servico card-troca">'
                            f'<h3>📅 {data_fmt}</h3>'
                            f'<p>👤 <b>{nome_orig}</b> quer trocar contigo</p>'
                            f'<p>🟢 Recebes: <b>{r["servico_origem"]}</b></p>'
                            f'<p>🔴 Dás: <b>{r["servico_destino"]}</b></p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    c1, c2 = st.columns(2)
                    if c1.button("✅ ACEITAR", key=f"ac_{idx}", use_container_width=True):
                        # Matar remunerado: aprovação direta sem validação admin
                        novo_status = "Aprovada" if is_matar else "Pendente_Admin"
                        atualizar_status_gsheet(idx, novo_status)
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
            # ── Aguardam aceitação do militar ──
            pnd_mil = df_trocas[
                (df_trocas['status'] == 'Pendente_Militar') &
                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
            ]
            if not pnd_mil.empty:
                st.markdown(f"#### 🕐 Aguardam aceitação do militar ({len(pnd_mil)})")
                for idx, r in pnd_mil.sort_values('data').iterrows():
                    n_o = get_nome_militar(df_util, r['id_origem'])
                    n_d = get_nome_militar(df_util, r['id_destino'])
                    with st.expander(f"📅 {r['data']}  |  {n_o} → {n_d}", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Requerente:**\n\n{n_o}\n\n`{r['servico_origem']}`")
                        with col2:
                            st.warning(f"**Aguarda aceitação:**\n\n{n_d}\n\n`{r['servico_destino']}`")
                st.markdown("---")

            # ── Aguardam validação do admin ──
            pnd = df_trocas[df_trocas['status'] == 'Pendente_Admin']
            if pnd.empty:
                st.success("✅ Não há trocas pendentes de validação.")
            else:
                st.markdown(f"#### ⚖️ Aguardam validação ({len(pnd)})")
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
                aprv = aprv.copy()
                aprv['_data_ord'] = pd.to_datetime(aprv['data'], format='%d/%m/%Y', errors='coerce')
                aprv = aprv.sort_values('_data_ord', ascending=False).drop(columns='_data_ord')
                for idx, r in aprv.iterrows():
                    n_o = get_nome_militar(df_util, r['id_origem'])
                    n_d = get_nome_militar(df_util, r['id_destino'])
                    is_matar = str(r['servico_origem']) == 'MATAR_REMUNERADO'
                    titulo = f"📅 {r['data']}  |  {n_o} 💶 {n_d}" if is_matar else f"📅 {r['data']}  |  {n_o} ↔️ {n_d}"
                    with st.expander(titulo):
                        col1, col2 = st.columns(2)
                        if is_matar:
                            with col1:
                                st.info(f"**Requerente:**\n\n{n_o}")
                                st.markdown("**Ação:** Matar Remunerado")
                            with col2:
                                st.success(f"**Cedente:**\n\n{n_d}")
                                st.markdown(f"**Remunerado:**\n`{r['servico_destino']}`")
                        else:
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
                        if not is_matar:
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

    # --- 📋 HISTÓRICO DE TROCAS DO PRÓPRIO ---
    elif menu == "📋 Histórico de Trocas":
        st.title("📋 Histórico das Minhas Trocas")
        if df_trocas.empty:
            st.info("Não existem trocas registadas.")
        else:
            minhas = df_trocas[
                (df_trocas['id_origem'].astype(str) == u_id) |
                (df_trocas['id_destino'].astype(str) == u_id)
            ].copy()
            minhas['_data_ord'] = pd.to_datetime(minhas['data'], format='%d/%m/%Y', errors='coerce')
            minhas = minhas.sort_values('_data_ord', ascending=False).drop(columns='_data_ord')
            if minhas.empty:
                st.info("Não tens trocas registadas.")
            else:
                estados = ["Todos"] + sorted(minhas['status'].dropna().unique().tolist())
                filtro = st.selectbox("Filtrar por estado:", estados)
                if filtro != "Todos":
                    minhas = minhas[minhas['status'] == filtro]
                st.caption(f"{len(minhas)} registo(s)")
                for idx, r in minhas.iterrows():
                    fui_origem = str(r['id_origem']) == u_id
                    outro_id   = r['id_destino'] if fui_origem else r['id_origem']
                    outro_nome = get_nome_militar(df_util, outro_id)
                    meu_serv   = r['servico_origem'] if fui_origem else r['servico_destino']
                    outro_serv = r['servico_destino'] if fui_origem else r['servico_origem']
                    is_matar   = str(r['servico_origem']) == 'MATAR_REMUNERADO'
                    status     = r.get('status','')
                    cor = "🟢" if status == "Aprovada" else ("🔴" if status in ("Rejeitada","Cancelada") else "🟡")

                    if is_matar:
                        papel = "Requerente" if fui_origem else "Cedente"
                        titulo = f"{cor} {r['data']} — Matar Remunerado: {outro_serv} ({status})"
                    else:
                        papel = "Requerente" if fui_origem else "Substituto"
                        titulo = f"{cor} {r['data']} — {meu_serv} ↔ {outro_serv} ({status})"

                    with st.expander(titulo, expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**O meu papel:** {papel}")
                            if not is_matar:
                                st.markdown(f"**O meu serviço:** `{meu_serv}`")
                        with col2:
                            st.markdown(f"**Contraparte:** {outro_nome}")
                            st.markdown(f"**Remunerado:** `{outro_serv}`" if is_matar else f"**Serviço contraparte:** `{outro_serv}`")
                        if status == "Aprovada":
                            st.caption(f"⚖️ Validado por **{r.get('validador','N/A')}** em {r.get('data_validacao','N/A')}")
                        elif status in ("Pendente_Militar", "Pendente_Admin") and fui_origem:
                            if st.button("🚫 Cancelar pedido", key=f"cancel_{idx}"):
                                if atualizar_status_gsheet(idx, "Cancelada"):
                                    st.success("Pedido cancelado.")
                                    st.rerun()

    # --- 🔄 GIROS ---
    elif menu == "🔄 Giros":
        st.title("🔄 Giros")
        try:
            client = get_gsheet_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            ws = sh.worksheet("giros")
            valores = ws.get_all_values()
            if not valores or len(valores) < 2:
                st.info("Não existem giros definidos.")
            else:
                headers = [str(h).strip() for h in valores[0]]
                df_giros = pd.DataFrame(valores[1:], columns=headers)
                df_giros = df_giros[df_giros.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
                pesq_g = st.text_input("🔍 Pesquisar:", placeholder="nome, serviço...")
                df_g = df_giros.copy()
                if pesq_g:
                    p_g = pesq_g.lower()
                    mask_g = pd.Series([False] * len(df_g), index=df_g.index)
                    for col in df_g.columns:
                        mask_g |= df_g[col].astype(str).str.lower().str.contains(p_g, na=False)
                    df_g = df_g[mask_g]

                st.markdown(_render_tabela(df_g, expandivel=True), unsafe_allow_html=True)
        except Exception:
            st.info("Aba 'giros' não encontrada na Google Sheet. Cria a aba e volta aqui.")

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

    # --- 🚨 ALERTAS (ADMIN) ---
    elif menu == "🚨 Alertas":
        st.title("🚨 Alertas da Escala")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()

        import unicodedata as _uda
        def _na(t): return _uda.normalize('NFKD', str(t).lower()).encode('ascii','ignore').decode('ascii')

        hoje_a = datetime.now()
        # Verificar os próximos 30 dias
        alertas_trocas   = []
        alertas_duplos   = []
        alertas_descanso = []
        alertas_esquecidos = []

        # IDs de todos os militares ativos
        ids_ativos = set(df_util['id'].astype(str).str.strip().tolist()) if not df_util.empty else set()

        with st.spinner("A verificar escalas..."):
            dias_sem = 0
            j = 0
            while dias_sem < 5 and j < 60:
                dt_a = hoje_a + timedelta(days=j)
                d_s_a = dt_a.strftime('%d/%m/%Y')
                aba_a = dt_a.strftime('%d-%m')
                df_a = load_data(aba_a)
                j += 1
                if df_a.empty:
                    dias_sem += 1
                    continue
                dias_sem = 0

                # ── Alerta 1: Trocas validadas com escala alterada ──
                if not df_trocas.empty:
                    tr_val = df_trocas[
                        (df_trocas['data'] == d_s_a) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                    ]
                    for _, t in tr_val.iterrows():
                        # Verificar se o servico_origem ainda existe para id_origem
                        serv_o = t['servico_origem'].rsplit('(', 1)[0].strip().lower()
                        hor_o  = t['servico_origem'].rsplit('(', 1)[1].rstrip(')') if '(' in t['servico_origem'] else ''
                        existe = df_a[
                            (df_a['id'].astype(str) == str(t['id_origem'])) &
                            (df_a['serviço'].astype(str).str.strip().str.lower() == serv_o) &
                            (df_a['horário'].astype(str).str.strip() == hor_o.strip())
                        ]
                        if existe.empty:
                            n_o = get_nome_militar(df_util, t['id_origem'])
                            n_d = get_nome_militar(df_util, t['id_destino'])
                            alertas_trocas.append(f"**{d_s_a}** — Troca {n_o} ↔ {n_d}: serviço `{t['servico_origem']}` já não existe na escala")

                # ── Alerta 2: Militar escalado em 2 serviços no mesmo dia ──
                df_a_serv = df_a[~df_a['serviço'].apply(_na).str.contains('remu|grat', na=False)]
                contagem = df_a_serv[df_a_serv['id'].astype(str).str.strip() != ''].groupby('id').size()
                for mid, count in contagem.items():
                    if count > 1:
                        n = get_nome_militar(df_util, mid)
                        servs = df_a_serv[df_a_serv['id'].astype(str) == str(mid)][['serviço','horário']].values.tolist()
                        servs_str = ' / '.join([f"{s} ({h})" for s, h in servs])
                        alertas_duplos.append(f"**{d_s_a}** — {n}: {servs_str}")

                # ── Alerta 3: Menos de 8h de descanso entre dias consecutivos ──
                dt_ant = dt_a - timedelta(days=1)
                df_ant_a = load_data(dt_ant.strftime('%d-%m'))
                if not df_ant_a.empty:
                    ids_hoje = df_a[df_a['id'].astype(str).str.strip() != '']['id'].astype(str).unique()
                    for mid in ids_hoje:
                        rows_hoje = df_a[
                            (df_a['id'].astype(str) == mid) &
                            (~df_a['serviço'].apply(_na).str.contains('remu|grat|folga|ferias|licen|doente', na=False))
                        ]
                        rows_ant = df_ant_a[
                            (df_ant_a['id'].astype(str) == mid) &
                            (~df_ant_a['serviço'].apply(_na).str.contains('remu|grat|folga|ferias|licen|doente', na=False))
                        ]
                        for _, rh in rows_hoje.iterrows():
                            ini_h, fim_h = _parse_horario(rh['horário'])
                            if ini_h is None: continue
                            if _e_atendimento(rh['serviço']): continue
                            for _, ra in rows_ant.iterrows():
                                ini_a, fim_a = _parse_horario(ra['horário'])
                                if ini_a is None: continue
                                if _e_atendimento(ra['serviço']): continue
                                # fim do dia anterior → início de hoje
                                descanso = (ini_h + 1440) - fim_a
                                if 0 <= descanso < 480:
                                    n = get_nome_militar(df_util, mid)
                                    h2, m2 = descanso // 60, descanso % 60
                                    alertas_descanso.append(f"**{d_s_a}** — {n}: apenas {h2}h{m2:02d}m entre `{ra['serviço']} ({ra['horário']})` ({dt_ant.strftime('%d/%m')}) e `{rh['serviço']} ({rh['horário']})`")

                # ── Alerta 4: Militar não escalado no dia ──
                ids_na_escala = set(df_a[df_a['id'].astype(str).str.strip() != '']['id'].astype(str).str.strip().tolist())
                esquecidos = ids_ativos - ids_na_escala
                for mid in sorted(esquecidos):
                    # Excluir militares de férias
                    if militar_de_ferias(mid, dt_a.date(), df_ferias):
                        continue
                    n = get_nome_militar(df_util, mid)
                    alertas_esquecidos.append(f"**{d_s_a}** — {n} (ID: {mid}) não está escalado")
        with st.expander(f"🔍 Militares não escalados ({len(alertas_esquecidos)})", expanded=len(alertas_esquecidos) > 0):
            if alertas_esquecidos:
                for a in alertas_esquecidos:
                    st.warning(a)
            else:
                st.success("✅ Sem alertas")

        with st.expander(f"⚠️ Trocas com escala alterada ({len(alertas_trocas)})", expanded=len(alertas_trocas) > 0):
            if alertas_trocas:
                for a in alertas_trocas:
                    st.warning(a)
            else:
                st.success("✅ Sem alertas")

        with st.expander(f"👥 Militar escalado em 2 serviços ({len(alertas_duplos)})", expanded=len(alertas_duplos) > 0):
            if alertas_duplos:
                for a in alertas_duplos:
                    st.warning(a)
            else:
                st.success("✅ Sem alertas")

        with st.expander(f"😴 Menos de 8h de descanso ({len(alertas_descanso)})", expanded=len(alertas_descanso) > 0):
            if alertas_descanso:
                for a in alertas_descanso:
                    st.warning(a)
            else:
                st.success("✅ Sem alertas")
