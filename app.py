import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta, date
from fpdf import FPDF
import io
import re
import unicodedata
import hashlib
import secrets

def norm(t):
    """Normaliza texto para comparação -- remove acentos e coloca em minúsculas."""
    return unicodedata.normalize('NFKD', str(t).lower()).encode('ascii', 'ignore').decode('ascii')

def hash_pin(pin: str, salt: str = None):
    """Gera hash+salt de um PIN. Retorna (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{pin}".encode()).hexdigest()
    return h, salt

def verificar_pin(pin_input: str, pin_guardado: str) -> bool:
    """Verifica PIN -- suporta texto simples (migração) e hash:salt."""
    pin_input = str(pin_input).strip().zfill(4)
    pin_guardado = str(pin_guardado).strip()
    # Formato hash: "hash:salt"
    if ':' in pin_guardado and len(pin_guardado) > 10:
        partes = pin_guardado.split(':', 1)
        if len(partes) == 2:
            h_guardado, salt = partes
            h_input, _ = hash_pin(pin_input, salt)
            return h_input == h_guardado
    # Texto simples (antes da migração)
    return pin_guardado.zfill(4) == pin_input

def migrar_pin_para_hash(email: str, pin: str) -> bool:
    """Migra o PIN de texto simples para hash no Sheets."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("utilizadores")
        records = ws.get_all_records()
        headers = [h.strip().lower() for h in ws.row_values(1)]
        if 'pin' not in headers or 'email' not in headers:
            return False
        col_pin   = headers.index('pin') + 1
        col_email = headers.index('email') + 1
        for i, row in enumerate(records, start=2):
            if str(row.get('email', '')).strip().lower() == email.strip().lower():
                h, salt = hash_pin(pin)
                ws.update_cell(i, col_pin, f"{h}:{salt}")
                load_utilizadores.clear()
                return True
    except Exception:
        pass
    return False

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

@st.cache_resource
def get_sheet():
    """Abre a Sheet uma única vez e reutiliza -- evita open_by_url repetido."""
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

@st.cache_data(ttl=180)
def load_data(aba_nome: str) -> pd.DataFrame:
    """Carrega dados de uma aba da Google Sheet com cache de 3 minutos."""
    import time
    for tentativa in range(4):
        try:
            sh = get_sheet()
            if sh is None:
                return pd.DataFrame()
            return _df_from_records(sh.worksheet(aba_nome).get_all_records())
        except Exception as e:
            if tentativa < 3:
                wait = 15 * (tentativa + 1)
                time.sleep(wait)
    return pd.DataFrame()

def load_data_direto(sh, aba_nome: str) -> pd.DataFrame:
    """Lê aba diretamente do Sheets SEM cache -- para uso na geração de escala."""
    import time
    for tentativa in range(3):
        try:
            return _df_from_records(sh.worksheet(aba_nome).get_all_records())
        except Exception as e:
            if '429' in str(e) and tentativa < 2:
                time.sleep(20)
            else:
                return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_utilizadores() -> pd.DataFrame:
    """Carrega utilizadores com cache de 5min e retry automático."""
    import time
    for tentativa in range(3):
        try:
            sh = get_sheet()
            if sh is None:
                return pd.DataFrame()
            return _df_from_records(sh.worksheet("utilizadores").get_all_records())
        except Exception:
            if tentativa < 2:
                time.sleep(1)
    return pd.DataFrame()

@st.cache_data(ttl=30)
def load_trocas() -> pd.DataFrame:
    """Carrega registos_trocas com cache curto de 30s."""
    for tentativa in range(3):
        try:
            sh = get_sheet()
            if sh is None:
                return pd.DataFrame()
            return _df_from_records(sh.worksheet("registos_trocas").get_all_records())
        except Exception:
            if tentativa == 2:
                return pd.DataFrame()

def invalidar_trocas():
    """Limpa cache de trocas."""
    load_trocas.clear()

@st.cache_data(ttl=300)
def load_ferias(ano: int) -> pd.DataFrame:
    """Carrega plano de férias de um ano -- cache 5min."""
    try:
        sh = get_sheet()
        if sh is None:
            return pd.DataFrame()
        ws = sh.worksheet(f"ferias_{ano}")
        valores = ws.get_all_values()
        if not valores or len(valores) < 2:
            return pd.DataFrame()
        headers = [str(h).strip() for h in valores[0]]
        df = pd.DataFrame(valores[1:], columns=headers)
        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_licencas(ano: int) -> pd.DataFrame:
    """Carrega aba Licenças -- id, tipo, inicio, fim."""
    try:
        sh = get_sheet()
        if sh is None: return pd.DataFrame()
        ws = sh.worksheet("Licenças")
        vals = ws.get_all_values()
        if not vals or len(vals) < 2: return pd.DataFrame()
        hdrs = [h.strip() for h in vals[0]]
        df = pd.DataFrame(vals[1:], columns=hdrs)
        return df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
    except:
        return pd.DataFrame()

def militar_de_licenca(mid: str, data, df_licencas: pd.DataFrame) -> str:
    """Devolve tipo de licença/baixa/diligência ou '' se não está."""
    if df_licencas.empty: return ''
    cols = df_licencas.columns.tolist()
    col_id  = 'id'    if 'id'    in cols else cols[0]
    col_tp  = 'tipo'  if 'tipo'  in cols else (cols[1] if len(cols)>1 else None)
    col_ini = next((c for c in cols if 'ini' in c.lower()), None)
    col_fim = next((c for c in cols if 'fim' in c.lower()), None)
    if not col_ini or not col_fim: return ''

    data_date = data if hasattr(data, 'strftime') else datetime.strptime(str(data), '%d-%m').replace(year=datetime.now().year)
    if hasattr(data_date, 'date'): data_date = data_date.date()

    linhas = df_licencas[df_licencas[col_id].astype(str).str.strip() == str(mid).strip()]
    for _, row in linhas.iterrows():
        ini_s = str(row.get(col_ini, '')).strip()
        fim_s = str(row.get(col_fim, '')).strip()
        if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan': continue
        try:
            # Suportar DD-MM ou DD/MM/YYYY
            if '/' in ini_s:
                ini_d = datetime.strptime(ini_s, '%d/%m/%Y').date()
                fim_d = datetime.strptime(fim_s, '%d/%m/%Y').date()
            else:
                ano = data_date.year
                ini_d = datetime.strptime(f"{ini_s}-{ano}", '%d-%m-%Y').date()
                fim_d = datetime.strptime(f"{fim_s}-{ano}", '%d-%m-%Y').date()
            if ini_d <= data_date <= fim_d:
                return str(row.get(col_tp, 'Licença')).strip() if col_tp else 'Licença'
        except:
            continue
    return ''

@st.cache_data(ttl=3600)
def load_folgas(ano: int) -> pd.DataFrame:
    """Carrega aba folgas_YYYY -- id, fds, grupo."""
    try:
        sh = get_sheet()
        if sh is None: return pd.DataFrame()
        ws = sh.worksheet(f"folgas_{ano}")
        vals = ws.get_all_values()
        if not vals or len(vals) < 2: return pd.DataFrame()
        hdrs = [h.strip() for h in vals[0]]
        df = pd.DataFrame(vals[1:], columns=hdrs)
        return df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_grupos_folga() -> dict:
    """Carrega aba grupos_folga -- {grupo: {tipo_folga: [dias DD-MM]}}."""
    try:
        sh = get_sheet()
        if sh is None: return {}
        ws = sh.worksheet("grupos_folga")
        vals = ws.get_all_values()
        if not vals or len(vals) < 2: return {}
        hdrs = [h.strip() for h in vals[0]]  # ex: ['grupo','Folga Semanal','Folga Complementar']
        tipos = [h for h in hdrs if h != 'grupo']
        result = {}
        for row in vals[1:]:
            grupo = str(row[0]).strip() if row else ''
            if not grupo: continue
            result[grupo] = {}
            for t in tipos:
                idx = hdrs.index(t)
                dias_str = str(row[idx]).strip() if idx < len(row) else ''
                result[grupo][t] = [d.strip() for d in re.split(r'[;,]+', dias_str) if d.strip()]
        return result
    except:
        return {}

def militar_de_folga(mid: str, data, df_folgas: pd.DataFrame, grupos_folga: dict, feriados: list) -> str:
    """Devolve tipo de folga ('Folga Semanal', 'Folga Complementar') ou '' se não está de folga."""
    if df_folgas.empty: return ''
    aba = data.strftime('%d-%m') if hasattr(data, 'strftime') else str(data)
    data_date = data if hasattr(data, 'weekday') else datetime.strptime(str(data), '%d-%m').replace(year=datetime.now().year)

    col_id = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
    linha = df_folgas[df_folgas[col_id].astype(str).str.strip() == str(mid).strip()]
    if linha.empty: return ''
    row = linha.iloc[0]

    # Verificar exceções individuais — formato: "06-04(Folga Semanal)→09-04;..."
    excecoes_str = str(row.get('exceções', '') or row.get('excecoes', '')).strip()
    if excecoes_str and excecoes_str != 'nan':
        for exc in re.split(r'[;]+', excecoes_str):
            exc = exc.strip()
            if not exc: continue
            # Formato: DD-MM(Tipo)→DD-MM
            m_exc = re.match(r'(\d{2}-\d{2})\(([^)]+)\)→(\d{2}-\d{2})', exc)
            if m_exc:
                dia_orig, tipo_exc, dia_novo = m_exc.group(1), m_exc.group(2), m_exc.group(3)
                if dia_novo == aba:
                    return tipo_exc  # novo dia de folga
                if dia_orig == aba:
                    return ''  # dia original foi movido — não folga aqui

    # Verificar FDS
    fds = str(row.get('fds', '')).strip().lower()
    if fds in ('sim', 'yes', '1', 'true'):
        if data_date.weekday() >= 5:
            return 'Folga Semanal'
        if aba in [f.strftime('%d-%m') if hasattr(f, 'strftime') else str(f) for f in feriados]:
            return 'Folga Semanal'

    # Verificar grupo
    grupo = str(row.get('grupo', '')).strip()
    if grupo and grupo in grupos_folga:
        for tipo, dias in grupos_folga[grupo].items():
            if aba in dias:
                return tipo
    return ''

@st.cache_data(ttl=86400)
@st.cache_data(ttl=120)
def load_dias_publicados() -> set:
    """Carrega datas publicadas da aba 'escala_publicada' -- formato DD-MM."""
    try:
        sh = get_sheet()
        if sh is None:
            return set()
        ws = sh.worksheet("escala_publicada")
        valores = ws.col_values(1)
        return set(str(v).strip() for v in valores if str(v).strip() and str(v).strip() != 'data')
    except Exception:
        return set()

@st.cache_data(ttl=300)
def load_servicos() -> dict:
    """Carrega aba serviços -- dict {militar_id: [servicos]}."""
    try:
        sh = get_sheet()
        if sh is None: return {}
        vals = sh.worksheet("serviços").get_all_values()
        headers = [str(h).strip() for h in vals[0]]
        result = {}
        for col in headers:
            idx = headers.index(col)
            for row in vals[1:]:
                mid = str(row[idx]).strip() if idx < len(row) else ''
                if mid and mid != 'nan':
                    if mid not in result: result[mid] = []
                    result[mid].append(col)
        return result
    except:
        return {}

@st.cache_data(ttl=300)
def load_listas() -> dict:
    """Carrega aba listas -- dict {coluna: [valores]}."""
    try:
        sh = get_sheet()
        if sh is None: return {}
        vals = sh.worksheet("listas").get_all_values()
        if not vals: return {}
        hdrs = [h.strip() for h in vals[0]]
        result = {}
        for h in hdrs:
            idx = hdrs.index(h)
            result[h] = [''] + [str(row[idx]).strip() for row in vals[1:] if idx < len(row) and str(row[idx]).strip()]
        return result
    except:
        return {}

def load_feriados(ano: int) -> list:
    """Carrega feriados de um ano da aba 'feriados' -- cache 24h."""
    try:
        sh = get_sheet()
        if sh is None:
            return []
        ws = sh.worksheet("feriados")
        valores = ws.get_all_values()
        if not valores:
            return []
        # Debug temporário -- guardar em session_state para mostrar
        feriados = []
        num_cols = max(len(r) for r in valores)
        for ci in range(num_cols):
            col = [str(r[ci]).strip() if ci < len(r) else '' for r in valores]
            col = [v for v in col if v]
            if not col:
                continue
            try:
                ano_col = int(col[0])
            except:
                continue
            if ano_col != ano:
                continue
            for v in col[1:]:
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d'):
                    try:
                        feriados.append(datetime.strptime(v, fmt).date())
                        break
                    except:
                        pass
        return feriados
    except Exception as e:
        return []

def _parse_data_ferias(s, ano=None):
    """Tenta parsear uma data em vários formatos."""
    s = str(s).strip()
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except:
            pass
    # Formato MM/DD sem ano
    try:
        d = datetime.strptime(s, '%m/%d').date()
        return d.replace(year=ano if ano else datetime.now().year)
    except:
        pass
    return None

def _fim_ferias_real(fim_d, feriados_list):
    """Estende o fim das férias para incluir fins de semana e feriados subsequentes."""
    fim_ext = fim_d
    while True:
        proximo = fim_ext + timedelta(days=1)
        if proximo.weekday() >= 5 or proximo in feriados_list:
            fim_ext = proximo
        else:
            break
    return fim_ext

def militar_de_ferias(u_id: str, data, df_ferias: pd.DataFrame, feriados_list: list = None) -> bool:
    """Verifica se um militar está de férias numa data (incluindo extensão de fds e feriados)."""
    if df_ferias.empty:
        return False
    if feriados_list is None:
        feriados_list = []
    cols = df_ferias.columns.tolist()
    ini_cols = [c for c in cols if 'ini' in c.lower()]
    fim_cols  = [c for c in cols if 'fim' in c.lower()]
    id_col = 'id' if 'id' in cols else cols[0]
    mil = df_ferias[df_ferias[id_col].astype(str).str.strip() == str(u_id).strip()]
    if mil.empty:
        return False
    if isinstance(data, datetime):
        data = data.date()
    ano_data = data.year if data else datetime.now().year
    for ini_c, fim_c in zip(ini_cols, fim_cols):
        for _, row in mil.iterrows():
            ini_s = str(row.get(ini_c, '')).strip()
            fim_s = str(row.get(fim_c, '')).strip()
            if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan':
                continue
            ini_d = _parse_data_ferias(ini_s, ano_data)
            fim_d = _parse_data_ferias(fim_s, ano_data)
            if not ini_d or not fim_d:
                continue
            fim_real = _fim_ferias_real(fim_d, feriados_list)
            if ini_d <= data <= fim_real:
                return True
    return False

@st.cache_data(ttl=86400)
def contar_servicos_historico(alvo_id_c: str, sheet_id_c: str) -> pd.DataFrame:
    """Conta serviços históricos de um militar -- cache 24h."""
    def _n3(t): return norm(t)
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
    return bool(re.search(ATENDIMENTO_PATTERN, norm(serv)))

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

    MIN_DESCANSO = 8 * 60  # 480 minutos

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
                continue  # exceção -- adjacente é atendimento/apoio
            if re.search(r'remu|grat', norm(serv_adj)):
                continue  # remunerados não contam para descanso
            ini_adj, fim_adj = _parse_horario(hor_adj)
            if ini_adj is None:
                continue

            if delta == -1:
                # serviço do dia anterior: fim em minutos absolutos (ex: 16-24 → fim=1440)
                # serviço novo: começa em minutos do dia (ex: 00-08 → ini=0)
                # descanso = 1440 - fim_adj + ini_novo (minutos entre meia-noite anterior e início novo)
                descanso = (1440 - fim_adj) + ini_novo
            else:
                # serviço do dia seguinte: começa em minutos do dia (ex: 00-08 → ini=0)
                # serviço novo: fim em minutos do dia (ex: 16-24 → fim=1440)
                # descanso = 1440 - fim_novo + ini_adj
                descanso = (1440 - fim_novo) + ini_adj

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
    MIN = 6 * 60

    def _e_rem(s):
        return bool(re.search(r'remu|grat', norm(s)))
    def _isento(s):
        return _e_atendimento(s) or _e_rem(s)

    def get_servicos_fixos(mil_id, hor_excluir):
        result = []
        for delta, offset, df_adj in [(-1, 0, df_anterior), (0, 1440, df_dia), (1, 2880, df_seguinte)]:
            if df_adj is None or df_adj.empty:
                continue
            # Aplicar trocas aprovadas -- usar id_disp se disponível, senão id
            if 'id_disp' in df_adj.columns:
                # Militar aparece no id_disp quando tem troca
                mask = df_adj['id_disp'].astype(str).str.contains(str(mil_id), na=False)
                # Também verificar id original (pode não ter troca)
                mask2 = df_adj['id'].astype(str).str.strip() == str(mil_id).strip()
                rows = df_adj[mask | mask2]
            else:
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
                duracao = fim - ini
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
            # Se qualquer um dos serviços for atendimento/apoio -- isento
            if _isento(s_f):
                continue
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
    """Atualiza o status de uma troca na Google Sheet -- batch update numa chamada."""
    try:
        sh = get_sheet()
        aba = sh.worksheet("registos_trocas")
        row = index_linha + 2  # +1 cabeçalho, +1 índice base-0
        if admin_nome:
            dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            aba.batch_update([
                {"range": f"F{row}", "values": [[novo_status]]},
                {"range": f"H{row}", "values": [[admin_nome]]},
                {"range": f"I{row}", "values": [[dt_agora]]},
            ])
        else:
            aba.update_cell(row, 6, novo_status)

        # ── Se troca de folga aprovada → atualizar folgas_2026 ──
        if novo_status == "Aprovada":
            try:
                todos = aba.get_all_values()
                hdrs_t = [h.strip().lower() for h in todos[0]]
                row_t  = todos[index_linha + 1]  # +1 para header
                serv_o = str(row_t[hdrs_t.index('servico_origem')]).strip() if 'servico_origem' in hdrs_t else ''
                serv_d = str(row_t[hdrs_t.index('servico_destino')]).strip() if 'servico_destino' in hdrs_t else ''
                id_o   = str(row_t[hdrs_t.index('id_origem')]).strip() if 'id_origem' in hdrs_t else ''
                id_d   = str(row_t[hdrs_t.index('id_destino')]).strip() if 'id_destino' in hdrs_t else ''

                # Detetar troca de folga pelo formato "Folga DD/MM/YYYY (tipo)"
                if serv_o.startswith('Folga ') and serv_d.startswith('Folga '):
                    import re as _re
                    def _extrair_dia(s):
                        m = _re.search(r'(\d{2}/\d{2}/\d{4})', s)
                        return datetime.strptime(m.group(1), '%d/%m/%Y').strftime('%d-%m') if m else None
                    dia_o = _extrair_dia(serv_o)  # dia original do id_o → passa para id_d
                    dia_d = _extrair_dia(serv_d)  # dia original do id_d → passa para id_o

                    if dia_o and dia_d:
                        ano_f = datetime.now().year
                        ws_f = sh.worksheet(f"folgas_{ano_f}")
                        vals_f = ws_f.get_all_values()
                        hdrs_f = [h.strip().lower() for h in vals_f[0]]
                        ix_id_f   = hdrs_f.index('id') if 'id' in hdrs_f else 0
                        ix_grp_f  = hdrs_f.index('grupo') if 'grupo' in hdrs_f else None
                        ws_grp = sh.worksheet("grupos_folga")
                        vals_grp = ws_grp.get_all_values()
                        hdrs_grp = [h.strip() for h in vals_grp[0]]
                        tipos_grp = [h for h in hdrs_grp if h != 'grupo']

                        # Encontrar grupo do militar
                        def _get_grupo(mid):
                            for row_f in vals_f[1:]:
                                if str(row_f[ix_id_f]).strip() == mid and ix_grp_f:
                                    return str(row_f[ix_grp_f]).strip()
                            return None

                        if id_o == id_d:
                            # Mudança de folga — guardar exceção na coluna 'exceções' do folgas_2026
                            # Determinar tipo da folga original
                            tipo_orig = ''
                            m_tipo = re.search(r'\(([^)]+)\)', serv_o)
                            if m_tipo: tipo_orig = m_tipo.group(1)

                            grp = _get_grupo(id_o)
                            # Adicionar exceção: dia_o(tipo)→dia_d
                            nova_exc = f"{dia_o}({tipo_orig})→{dia_d}"
                            # Encontrar linha do militar no folgas_2026
                            col_exc = 'exceções' if 'exceções' in hdrs_f else ('excecoes' if 'excecoes' in hdrs_f else None)
                            if col_exc:
                                ix_exc = hdrs_f.index(col_exc)
                                for i_f, row_f in enumerate(vals_f[1:], start=2):
                                    if str(row_f[ix_id_f]).strip() == id_o:
                                        exc_atual = str(row_f[ix_exc]).strip() if ix_exc < len(row_f) else ''
                                        exc_atual = '' if exc_atual == 'nan' else exc_atual
                                        nova_lista = (exc_atual + ';' + nova_exc).strip(';')
                                        cl_exc = chr(ord('A') + ix_exc)
                                        ws_f.update(f'{cl_exc}{i_f}', [[nova_lista]])
                                        break
                        else:
                            # Troca entre dois militares — lógica original
                            def _trocar_dia_grupo(mid_from, dia_from, mid_to, dia_to):
                                grp_from = _get_grupo(mid_from)
                                grp_to   = _get_grupo(mid_to)
                                upds_grp = []
                                for i_grp, row_grp in enumerate(vals_grp[1:], start=2):
                                    grp_nome = str(row_grp[0]).strip()
                                    for tipo_g in tipos_grp:
                                        ix_t = hdrs_grp.index(tipo_g)
                                        dias_str = str(row_grp[ix_t]).strip() if ix_t < len(row_grp) else ''
                                        dias_list = [d.strip() for d in re.split(r'[;,]+', dias_str) if d.strip()]
                                        mudou = False
                                        if grp_from and grp_nome == grp_from and dia_from in dias_list:
                                            dias_list.remove(dia_from)
                                            dias_list.append(dia_to)
                                            mudou = True
                                        if grp_to and grp_nome == grp_to and dia_to in dias_list:
                                            dias_list.remove(dia_to)
                                            dias_list.append(dia_from)
                                            mudou = True
                                        if mudou:
                                            cl_g = chr(ord('A') + ix_t)
                                            upds_grp.append({'range': f'{cl_g}{i_grp}', 'values': [[';'.join(sorted(dias_list))]]})
                                if upds_grp:
                                    ws_grp.batch_update(upds_grp)
                            _trocar_dia_grupo(id_o, dia_o, id_d, dia_d)

                        load_grupos_folga.clear()
                        load_folgas.clear()
            except Exception as _ef:
                pass  # não bloquear se falhar a atualização das folgas

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

_SLOTS_AUTO = {
    (norm("Atendimento"),          "00-08"): "Atendimento 00-08",
    (norm("Atendimento"),          "08-16"): "Atendimento 08-16",
    (norm("Atendimento"),          "16-24"): "Atendimento 16-24",
    (norm("Patrulha Ocorrências"), "00-08"): "Patrulha Ocorrências 00-08",
    (norm("Patrulha Ocorrências"), "08-16"): "Patrulha Ocorrências 08-16",
    (norm("Patrulha Ocorrências"), "16-24"): "Patrulha Ocorrências 16-24",
    (norm("Apoio Atendimento"),    "08-16"): "Apoio Atendimento 08-16",
    (norm("Apoio Atendimento"),    "16-24"): "Apoio Atendimento 16-24",
}

def _atualizar_ordem_escala_dia(sh, aba_dia: str, d_gerar):
    """
    Atualiza o ordem_escala do dia seguinte com base no que ficou escalado no aba_dia.
    - Parte do ordem_escala do próprio dia (criado ao confirmar o anterior)
    - Move para o fim TODOS os militares escalados nos slots auto (auto + manuais)
    - Grava como ordem_escala do dia seguinte
    """
    try:
        abas = [ws.title for ws in sh.worksheets()]
        aba_ord = f"ordem_escala {aba_dia}"
        aba_ord_ant = f"ordem_escala {(d_gerar - timedelta(days=1)).strftime('%d-%m')}"

        # Ler base -- próprio dia > anterior
        ws_base = None
        for nome in [aba_ord, aba_ord_ant]:
            if nome in abas:
                ws_base = sh.worksheet(nome)
                break
        if not ws_base:
            return

        vals = ws_base.get_all_values()
        if not vals: return
        hdrs = [h.strip() for h in vals[0]]
        ordem = {h: [] for h in hdrs}
        for row in vals[1:]:
            for i, h in enumerate(hdrs):
                v = str(row[i]).strip() if i < len(row) else ''
                if v: ordem[h].append(v)

        # Ler aba do dia para saber quem ficou escalado
        ws_dia = sh.worksheet(aba_dia)
        vals_dia = ws_dia.get_all_values()
        if not vals_dia: return
        hdrs_dia = [h.strip().lower() for h in vals_dia[0]]
        ix_id = hdrs_dia.index('id')      if 'id'      in hdrs_dia else 0
        ix_sv = hdrs_dia.index('serviço') if 'serviço' in hdrs_dia else 1
        ix_hr = hdrs_dia.index('horário') if 'horário' in hdrs_dia else 2

        for row in vals_dia[1:]:
            sv  = norm(str(row[ix_sv]).strip()) if ix_sv < len(row) else ''
            hr  = str(row[ix_hr]).strip()        if ix_hr < len(row) else ''
            ids = str(row[ix_id]).strip()         if ix_id < len(row) else ''
            col_key = _SLOTS_AUTO.get((sv, hr))
            if not col_key or not ids or ids == 'nan':
                continue
            for mid in re.split(r'[;,]+', ids):
                mid = mid.strip()
                if mid and col_key in ordem and mid in ordem[col_key]:
                    ordem[col_key].remove(mid)
                    ordem[col_key].append(mid)

        # Gravar ordem_escala do dia seguinte
        nome_prox = f"ordem_escala {(d_gerar + timedelta(days=1)).strftime('%d-%m')}"
        nova = [hdrs]
        ml = max((len(v) for v in ordem.values()), default=1)
        for i in range(ml):
            nova.append([ordem[h][i] if i < len(ordem[h]) else '' for h in hdrs])

        if nome_prox in abas:
            ws_p = sh.worksheet(nome_prox)
            ws_p.clear()
            ws_p.update('A1', nova)
            ws_p.hide()
        else:
            ws_p = sh.add_worksheet(title=nome_prox, rows=100, cols=len(hdrs))
            ws_p.update('A1', nova)
            ws_p.hide()
    except Exception as e:
        st.error(f"Erro ao atualizar ordem_escala: {e}")

# ============================================================
# 5. FUNÇÕES PDF
# ============================================================
def s(txt) -> str:
    return str(txt)

def _rl_header(c_obj, titulo):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    c_obj.setFillColor(HexColor('#1a2b4a'))
    c_obj.rect(0, 267*mm, 210*mm, 30*mm, fill=1, stroke=0)
    c_obj.setFillColor(HexColor('#ffffff'))
    c_obj.setFont("Helvetica-Bold", 16)
    c_obj.drawCentredString(105*mm, 278*mm, titulo)

def gerar_pdf_troca(dados: dict) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    # Cabeçalho
    c.setFillColor(HexColor('#1a2b4a'))
    c.rect(0, h-30*mm, w, 30*mm, fill=1, stroke=0)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w/2, h-18*mm, "GNR - Comprovativo de Troca de Serviço")
    # Corpo
    c.setFillColor(HexColor('#000000'))
    c.setFont("Helvetica", 11)
    texto = (
        f"Certifica-se que o militar {s(dados['nome_origem'])} (ID {s(dados['id_origem'])}), "
        f"requereu a troca do serviço '{s(dados['serv_orig'])}' pelo serviço '{s(dados['serv_dest'])}' "
        f"do militar {s(dados['nome_destino'])} (ID {s(dados['id_destino'])}), para o dia {s(dados['data'])}.\n\n"
        f"O pedido foi aceite pelo militar de destino e validado superiormente por "
        f"{s(dados['validador'])} no dia {s(dados['data_val'])}."
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate
    from reportlab.lib.styles import ParagraphStyle
    style = ParagraphStyle('body', fontName='Helvetica', fontSize=11, leading=16, spaceAfter=10)
    y = h - 50*mm
    for linha in texto.split('\n'):
        if linha.strip():
            p = Paragraph(linha, style)
            pw, ph = p.wrap(170*mm, h)
            p.drawOn(c, 20*mm, y - ph)
            y -= ph + 6*mm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor('#646464'))
    c.drawRightString(w-20*mm, 15*mm, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.save()
    return buf.getvalue()

def gerar_pdf_fazer_remunerado(dados: dict) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColor(HexColor('#1a2b4a'))
    c.rect(0, h-30*mm, w, 30*mm, fill=1, stroke=0)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w/2, h-18*mm, "GNR - Comprovativo de Remunerado")
    c.setFillColor(HexColor('#000000'))
    texto = (
        f"Certifica-se que o militar {s(dados['nome_cedente'])} (ID {s(dados['id_cedente'])}) "
        f"cedeu o serviço remunerado '{s(dados['remunerado'])}' do dia {s(dados['data'])} "
        f"ao militar {s(dados['nome_requerente'])} (ID {s(dados['id_requerente'])}).\n\n"
        f"O pedido foi aceite pelo militar cedente e validado superiormente por "
        f"{s(dados['validador'])} no dia {s(dados['data_val'])}."
    )
    style = ParagraphStyle('body', fontName='Helvetica', fontSize=11, leading=16)
    y = h - 50*mm
    for linha in texto.split('\n'):
        if linha.strip():
            p = Paragraph(linha, style)
            pw, ph = p.wrap(170*mm, h)
            p.drawOn(c, 20*mm, y - ph)
            y -= ph + 6*mm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor('#646464'))
    c.drawRightString(w-20*mm, 15*mm, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.save()
    return buf.getvalue()


def gerar_pdf_escala_dia(data: str, df_raw: pd.DataFrame, df_util: pd.DataFrame = None) -> bytes:
    """Gera PDF da escala diaria em A4 retrato usando reportlab - layout original."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white, black
    from datetime import datetime as _dt

    if df_util is None:
        df_util = pd.DataFrame()

    def fmt_id(txt):
        t = str(txt)
        if "\U0001f504" in t:
            parts = t.split("\U0001f504")
            return f"{parts[0].strip()} (Troca c/{parts[1].strip()})"
        return t

    df_raw = df_raw.copy()
    df_raw["servico_col"] = df_raw["serviço"].apply(norm)
    df_raw["id_fmt"] = df_raw["id_disp"].apply(fmt_id)
    df_raw_com = df_raw[df_raw["id"].astype(str).str.strip().str.len() > 0].copy()

    def filtrar(pat, df):
        mask = df["servico_col"].str.contains(pat, na=False)
        return df[mask].copy(), df[~mask].copy()

    df_aus,  df_rest = filtrar(r"ferias|licen|doente|folga|baixa", df_raw_com)
    df_adm,  df_rest = filtrar(r"pronto|secretaria|inquer|comando|dilig", df_rest)
    df_ap,   df_rest = filtrar(r"apoio", df_rest)
    df_at,   df_rest = filtrar(r"atendimento", df_rest)
    df_pat,  df_rest = filtrar(r"po|patrulha|ronda|vtr|giro", df_rest)
    df_rem,  df_rest = filtrar(r"remu|grat", df_rest)
    df_outros = df_rest

    # Agrupar patrulha ocorrencias por horario
    df_ocorr = df_pat[df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()
    df_outras_pat = df_pat[~df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()

    AZUL_ESC  = HexColor("#1a1a1a")
    AZUL_MED  = HexColor("#c8c8c8")
    FILL_ALT  = HexColor("#f0f0f0")
    CINZA_LN  = HexColor("#999999")
    CINZA_TXT = HexColor("#444444")

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    # ---- Barra lateral ----
    SB_W = 24*mm
    SB_X = 5*mm    # mais afastado da margem esquerda
    SB_TM = 10*mm  # mais afastado do topo

    # Recolher todos os militares únicos com iniciais
    def _iniciais(mid):
        row_u = df_util[df_util['id'].astype(str).str.strip() == str(mid).strip()] if not df_util.empty else pd.DataFrame()
        if row_u.empty:
            return str(mid)
        nome = str(row_u.iloc[0].get('nome', '')).strip()
        partes = nome.split()
        if len(partes) >= 2:
            return f"{partes[0][0]}.{partes[-1]}"
        elif len(partes) == 1:
            return partes[0]
        return str(mid)

    # Efetivo -- ordem da aba utilizadores
    if not df_util.empty and 'id' in df_util.columns:
        todos_ids = [str(r).strip() for r in df_util['id'] if str(r).strip() and str(r).strip() != 'nan']
    else:
        todos_ids = sorted(set(
            str(r).strip() for r in df_raw['id']
            if str(r).strip() and str(r).strip() != 'nan'
        ), key=lambda x: int(x) if x.isdigit() else 0)

    def draw_sidebar(y_top=None):
        """Desenha barra lateral com IDs e iniciais."""
        if y_top is None:
            y_top = H - SB_TM
        # Fundo branco
        c.setFillColor(white)
        c.rect(SB_X, SB_TM, SB_W, y_top - SB_TM, fill=1, stroke=0)
        # Cabeçalho EFETIVO -- fundo escuro, letra branca
        c.setFillColor(HexColor("#1a1a1a"))
        c.rect(SB_X, y_top - 8*mm, SB_W, 8*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(SB_X + SB_W/2, y_top - 5.5*mm, "EFETIVO")
        # IDs e iniciais
        linha_h = min(5.5*mm, (y_top - SB_TM - 12*mm) / max(len(todos_ids), 1))
        y_sb = y_top - 12*mm
        for idx_sb, mid in enumerate(todos_ids):
            ini = _iniciais(mid)
            if idx_sb % 2 == 0:
                c.setFillColor(HexColor("#efefef"))
                c.rect(SB_X, y_sb - linha_h, SB_W, linha_h, fill=1, stroke=0)
            c.setFillColor(HexColor("#1a1a1a"))
            c.setFont("Helvetica-Bold", 7)
            c.drawString(SB_X + 1.5*mm, y_sb - linha_h/2 - 1.5*mm, str(mid))
            c.setFont("Helvetica", 7)
            c.drawString(SB_X + 9*mm, y_sb - linha_h/2 - 1.5*mm, ini)
            c.setStrokeColor(HexColor("#cccccc"))
            c.setLineWidth(0.2)
            c.line(SB_X, y_sb - linha_h, SB_X + SB_W, y_sb - linha_h)
            y_sb -= linha_h
            if y_sb < SB_TM + 3*mm:
                break
        # Borda direita subtil
        c.setStrokeColor(HexColor("#999999"))
        c.setLineWidth(0.5)
        c.line(SB_X + SB_W, SB_TM, SB_X + SB_W, y_top)

    # ---- helpers ----
    LM = SB_X + SB_W + 3*mm  # margem esquerda com folga
    RM = 12*mm                 # margem direita maior
    TW = W - LM - RM          # largura total

    def new_page():
        draw_sidebar(y_top=H - SB_TM)
        c.showPage()
        draw_sidebar(y_top=H - SB_TM)
        return H - 10*mm

    def draw_header(y):
        box_w = 50*mm
        box_h = 20*mm
        header_w = TW - box_w - 2*mm

        # Cabeçalho sem fundo -- borda simples, texto a preto
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.rect(LM, y-box_h, header_w, box_h, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(LM + header_w/2, y-8*mm, "POSTO TERRITORIAL DE VILA NOVA DE FAMALICÃO")
        try:
            dt_obj   = _dt.strptime(data, "%d/%m/%Y")
            dias_pt  = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
                        "Sexta-feira","Sábado","Domingo"]
            meses_pt = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
            titulo = f"ESCALA DE SERVIÇO  |  {dias_pt[dt_obj.weekday()]}  {dt_obj.day} de {meses_pt[dt_obj.month]} de {dt_obj.year}"
        except:
            titulo = f"ESCALA DE SERVIÇO  |  {data}"
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(LM + header_w/2, y-15*mm, titulo)

        # Caixa de assinatura -- canto superior direito
        box_x = LM + header_w + 2*mm
        box_y = y - box_h
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.rect(box_x, box_y, box_w, box_h, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(box_x + box_w/2, box_y + box_h - 4*mm, "O COMANDANTE")
        c.setFillColor(CINZA_TXT)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(box_x + box_w/2, box_y + 3.5*mm, "Hugo Alexandre Ferreira do Carmo")
        c.drawCentredString(box_x + box_w/2, box_y + 1*mm, "Sargento-Ajudante")
        c.setLineWidth(0.5)

        return y - box_h - 2*mm

    def sec_title(y, label, x=LM, w=TW):
        # Borda simples com texto a negrito -- sem fundo escuro (poupa toner)
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.rect(x, y-5.5*mm, w, 5.5*mm, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x+2*mm, y-4*mm, f"  {label.upper()}")
        return y - 6.5*mm

    def tbl_header(y, cols, widths, x=LM):
        # Fundo cinza claro com texto escuro
        c.setFillColor(HexColor("#e0e0e0"))
        c.rect(x, y-5*mm, sum(widths), 5*mm, fill=1, stroke=0)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 8.5)
        xi = x
        for col, w in zip(cols, widths):
            c.drawCentredString(xi + w/2, y-3.5*mm, col)
            xi += w
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.line(x, y-5*mm, x+sum(widths), y-5*mm)
        return y - 5*mm

    def tbl_row(y, vals, widths, fill=False, x=LM, h=None):
        # Calcular altura necessária com wrap
        c.setFont("Helvetica", 8.5)
        linhas_por_cel = []
        for val, w in zip(vals, widths):
            txt = str(val)
            max_pts = w - 3*mm
            words = txt.split(', ')
            curr, linhas = '', []
            for word in words:
                test = (curr + ', ' + word).strip(', ') if curr else word
                if c.stringWidth(test, "Helvetica", 8.5) < max_pts:
                    curr = test
                else:
                    if curr: linhas.append(curr)
                    curr = word
            if curr: linhas.append(curr)
            linhas_por_cel.append(linhas if linhas else [''])
        row_h = h if h else max(5*mm, max(len(l) for l in linhas_por_cel) * 5*mm)
        if fill:
            c.setFillColor(FILL_ALT)
            c.rect(x, y-row_h, sum(widths), row_h, fill=1, stroke=0)
        c.setFillColor(black)
        c.setFont("Helvetica", 8.5)
        xi = x
        for linhas, w in zip(linhas_por_cel, widths):
            for li, ln in enumerate(linhas):
                c.drawCentredString(xi + w/2, y-(li*5*mm)-3.5*mm, ln)
            xi += w
        c.setStrokeColor(CINZA_LN)
        c.line(x, y-row_h, x+sum(widths), y-row_h)
        return y - row_h

    def draw_ids_line(y, label, ids, x=LM, w=TW):
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(AZUL_ESC)
        c.drawString(x+2*mm, y-3.5*mm, f"  {label}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(black)
        ids_txt = ", ".join(ids)
        c.drawString(x+35*mm, y-3.5*mm, ids_txt[:80])
        return y - 5*mm

    def rodape():
        pass  # rodapé removido

    # ======= INÍCIO =======
    y = H - 15*mm
    y = draw_header(y)
    y -= 2*mm
    draw_sidebar(y_top=y)  # barra lateral começa alinhada com as ausências

    # ---- AUSÊNCIAS e ADM lado a lado ----
    CW_ESQ = TW * 0.60 - 1*mm   # ausências -- 60%
    CW_DIR = TW * 0.40 - 1*mm   # ADM -- 40%
    CW2 = TW/2 - 1*mm           # atendimento/apoio -- 50/50
    GAP = 2*mm

    # Recolher grupos
    grupos_aus = {}
    for _, row in df_aus.iterrows():
        serv = str(row.get("serviço", "")).strip()
        mid  = str(row.get("id_fmt", row.get("id", ""))).strip()
        grupos_aus.setdefault(serv, []).append(mid)

    grupos_adm = {}
    for _, row in df_adm.iterrows():
        serv = str(row.get("serviço", "")).strip()
        mid  = str(row.get("id_fmt", row.get("id", ""))).strip()
        grupos_adm.setdefault(serv, []).append(mid)

    # Títulos das duas colunas
    y_col = y
    sec_title(y_col, "Ausências, Folgas e Licenças", x=LM, w=CW_ESQ)
    if grupos_adm:
        sec_title(y_col, "Outras Situações / ADM", x=LM+CW_ESQ+GAP, w=CW_DIR)
    y_col -= 6.5*mm

    # Linhas esquerda
    y_esq = y_col
    max_pts_esq = CW_ESQ - 37*mm
    label_w_esq = 35*mm
    idx_aus = 0
    for serv, ids in grupos_aus.items():
        ids_txt = ", ".join(ids)
        words = ids_txt.split(", ")
        curr_line, curr_w = [], 0
        linhas_ids = []
        for w_id in words:
            tw = c.stringWidth(w_id + ", ", "Helvetica", 8.5)
            if curr_w + tw < max_pts_esq:
                curr_line.append(w_id)
                curr_w += tw
            else:
                if curr_line: linhas_ids.append(", ".join(curr_line))
                curr_line, curr_w = [w_id], tw
        if curr_line: linhas_ids.append(", ".join(curr_line))
        row_h = len(linhas_ids) * 5*mm
        # Fundo alternado cobre toda a largura da coluna
        if idx_aus % 2 == 0:
            c.setFillColor(FILL_ALT)
            c.rect(LM, y_esq-row_h, CW_ESQ, row_h, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(AZUL_ESC)
        c.drawString(LM+2*mm, y_esq-3.5*mm, f"  {serv}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(black)
        for li, ln in enumerate(linhas_ids):
            indent = LM+label_w_esq if li == 0 else LM+5*mm
            c.drawString(indent, y_esq-3.5*mm, ln)
            y_esq -= 5*mm
        idx_aus += 1

    # Linhas direita
    y_dir = y_col
    x_dir = LM + CW_ESQ + GAP
    max_pts_dir = CW_DIR - 37*mm
    idx_adm = 0
    for serv, ids in grupos_adm.items():
        ids_txt = ", ".join(ids)
        words = ids_txt.split(", ")
        curr_line, curr_w = [], 0
        linhas_ids = []
        for w_id in words:
            tw = c.stringWidth(w_id + ", ", "Helvetica", 8.5)
            if curr_w + tw < max_pts_dir:
                curr_line.append(w_id)
                curr_w += tw
            else:
                if curr_line: linhas_ids.append(", ".join(curr_line))
                curr_line, curr_w = [w_id], tw
        if curr_line: linhas_ids.append(", ".join(curr_line))
        row_h = len(linhas_ids) * 5*mm
        if idx_adm % 2 == 0:
            c.setFillColor(FILL_ALT)
            c.rect(x_dir, y_dir-row_h, CW_DIR, row_h, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(AZUL_ESC)
        c.drawString(x_dir+2*mm, y_dir-3.5*mm, f"  {serv}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(black)
        for li, ln in enumerate(linhas_ids):
            indent = x_dir+label_w_esq if li == 0 else x_dir+5*mm
            c.drawString(indent, y_dir-3.5*mm, ln)
            y_dir -= 5*mm
        idx_adm += 1

    # Avançar y para o máximo das duas colunas
    y = min(y_esq, y_dir) - 2*mm

    # ---- ATENDIMENTO e APOIO lado a lado ----
    if not df_at.empty or not df_ap.empty:
        y_at = y
        # Títulos
        if not df_at.empty:
            sec_title(y_at, "Atendimento", x=LM, w=CW2)
        if not df_ap.empty:
            sec_title(y_at, "Apoio ao Atendimento", x=LM+CW2+GAP, w=CW2)
        y_at -= 6.5*mm

        cols_at = ["Horário", "Militar(es)"]

        # Coluna esquerda -- Atendimento
        y_esq2 = y_at
        if not df_at.empty:
            wids_at_l = [20*mm, CW2-20*mm]
            y_esq2 = tbl_header(y_at, cols_at, wids_at_l, x=LM)
            fill = False
            for hor, grp in df_at.groupby("horário", sort=False):
                ids = ", ".join(grp["id_fmt"].tolist())
                y_esq2 = tbl_row(y_esq2, [hor, ids], wids_at_l, fill, x=LM)
                fill = not fill

        # Coluna direita -- Apoio
        y_dir2 = y_at
        if not df_ap.empty:
            wids_at_r = [20*mm, CW2-20*mm]
            x_dir2 = LM+CW2+GAP
            y_dir2 = tbl_header(y_at, cols_at, wids_at_r, x=x_dir2)
            fill = False
            for hor, grp in df_ap.groupby("horário", sort=False):
                ids = ", ".join(grp["id_fmt"].tolist())
                y_dir2 = tbl_row(y_dir2, [hor, ids], wids_at_r, fill, x=x_dir2)
                fill = not fill

        y = min(y_esq2, y_dir2) - 2*mm

    # ---- PATRULHA OCORRÊNCIAS ----
    if not df_ocorr.empty:
        y = sec_title(y, "Patrulha Ocorrências")
        cols_oc = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"]
        _w = TW - 16*mm - 32*mm - 40*mm
        wids_oc = [16*mm, 32*mm, 40*mm, _w/3, _w/3, _w/3]
        y = tbl_header(y, cols_oc, wids_oc)
        fill = False
        for hor, grp in df_ocorr.groupby("horário", sort=False):
            ids  = ", ".join(grp["id_fmt"].tolist())
            serv = grp["serviço"].iloc[0]
            ind  = grp["indicativo rádio"].iloc[0] if "indicativo rádio" in grp.columns else ""
            rad  = grp["rádio"].iloc[0] if "rádio" in grp.columns else ""
            vtr  = grp["viatura"].iloc[0] if "viatura" in grp.columns else ""
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr], wids_oc, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        y -= 2*mm

    # ---- PATRULHAS E POLICIAMENTO ----
    if not df_outras_pat.empty:
        y = sec_title(y, "Patrulhas e Policiamento")
        cols_pp = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura", "Giro"]
        _wp = TW - 16*mm - 32*mm - 34*mm - 14*mm
        wids_pp = [16*mm, 32*mm, 34*mm, _wp/3, _wp/3, _wp/3, 14*mm]
        y = tbl_header(y, cols_pp, wids_pp)
        fill = False
        for hor, grp in df_outras_pat.groupby("horário", sort=False):
            ids  = ", ".join(grp["id_fmt"].tolist())
            serv = grp["serviço"].iloc[0]
            ind  = grp["indicativo rádio"].iloc[0] if "indicativo rádio" in grp.columns else ""
            rad  = grp["rádio"].iloc[0] if "rádio" in grp.columns else ""
            vtr  = grp["viatura"].iloc[0] if "viatura" in grp.columns else ""
            giro = grp["giro"].iloc[0] if "giro" in grp.columns else ""
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr, giro], wids_pp, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        y -= 2*mm

    # ---- OUTROS SERVIÇOS ----
    if not df_outros.empty:
        y = sec_title(y, "Outros Serviços")
        cols_ot = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"]
        _wo = TW - 16*mm - 32*mm - 40*mm
        wids_ot = [16*mm, 32*mm, 40*mm, _wo/3, _wo/3, _wo/3]
        y = tbl_header(y, cols_ot, wids_ot)
        fill = False
        for (hor, serv), grp in df_outros.groupby(["horário", "serviço"], sort=False):
            ids = ", ".join(grp["id_fmt"].tolist())
            ind = str(grp["indicativo rádio"].iloc[0]) if "indicativo rádio" in grp.columns else ""
            rad = str(grp["rádio"].iloc[0]) if "rádio" in grp.columns else ""
            vtr = str(grp["viatura"].iloc[0]) if "viatura" in grp.columns else ""
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr], wids_ot, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        y -= 2*mm

    # ---- helper wrap ----
    def wrap_text(txt, max_pts):
        lines = []
        for paragrafo in str(txt).split('\n'):
            words = paragrafo.split()
            curr = ""
            for word in words:
                test = (curr + " " + word).strip()
                if c.stringWidth(test, "Helvetica", 8.5) < max_pts:
                    curr = test
                else:
                    if curr: lines.append(curr)
                    curr = word
            if curr: lines.append(curr)
        return lines if lines else [""]

    # ---- REMUNERADOS ----
    if not df_rem.empty:
        y = sec_title(y, "Serviços Remunerados / Gratificados")
        _vtr_w = 20*mm if 'viatura' in df_rem.columns else 0
        wids_rm = [15*mm, 35*mm, _vtr_w, TW-50*mm-_vtr_w]
        _obs_w = wids_rm[3]  # largura real da coluna obs
        cols_rm = ["Horário", "Militares"] + (["Viatura"] if _vtr_w else []) + ["Observação"]
        y = tbl_header(y, cols_rm, wids_rm)
        fill = False

        x_obs_start = LM + wids_rm[0] + wids_rm[1] + _vtr_w + 2*mm
        x_obs_end   = LM + TW - 2*mm
        max_pts_rm  = x_obs_end - x_obs_start
        x_obs_col   = LM + wids_rm[0] + wids_rm[1] + _vtr_w

        # Agrupar linhas por obs para fundir célula -- preservar ordem original
        linhas_rem = []
        vistos = {}  # hor -> já processado
        for _, row in df_rem.iterrows():
            hor = str(row.get('horário', '')).strip()
            if hor in vistos:
                continue
            vistos[hor] = True
            grp = df_rem[df_rem['horário'] == hor]
            ids = ", ".join(grp["id_fmt"].tolist())
            obs = str(row.get("observações", "")) if "observações" in df_rem.columns else ""
            if obs == 'nan': obs = ""
            # Viatura -- procurar coluna independentemente de maiúsculas/minúsculas
            vtr = ""
            col_vtr = next((c for c in df_rem.columns if norm(c) == 'viatura'), None)
            if col_vtr:
                vtr_vals = grp[col_vtr].dropna().astype(str)
                vtr_vals = vtr_vals[vtr_vals.str.strip().str.len() > 0]
                vtr = vtr_vals.iloc[0].strip() if not vtr_vals.empty else ""
            linhas_rem.append({'hor': hor, 'ids': ids, 'obs': obs, 'vtr': vtr})

        # Calcular alturas e grupos de obs
        alturas = []
        for r in linhas_rem:
            obs_lines = wrap_text(r['obs'], max_pts_rm) if r['obs'] else [""]
            ids_lines = wrap_text(r['ids'], wids_rm[1] - 2*mm)
            alturas.append(max(5*mm, max(len(obs_lines), len(ids_lines)) * 5*mm))

        # Identificar spans de obs iguais CONSECUTIVAS
        obs_spans = {}  # idx_inicio -> (obs, count, altura_total)
        i = 0
        while i < len(linhas_rem):
            obs_atual = linhas_rem[i]['obs']
            j = i + 1
            # Só agrupas se consecutivas E obs não vazia
            while j < len(linhas_rem) and linhas_rem[j]['obs'] == obs_atual and obs_atual:
                j += 1
            altura_total = sum(alturas[i:j])
            obs_spans[i] = (obs_atual, j - i, altura_total)
            i = j

        # Desenhar primeiro todas as linhas de horário+militares, registar posições y
        y_posicoes = []  # y antes de cada linha
        obs_desenhadas = set()
        y_grupo = {}

        for idx, r in enumerate(linhas_rem):
            row_h = alturas[idx]
            if y - row_h < 20*mm: y = new_page()
            if idx in obs_spans:
                y_grupo[idx] = y
            y_posicoes.append((y, row_h))

            # Fundo linha horário + militares -- primeira branca, depois alterna
            if idx > 0 and idx % 2 == 1:
                c.setFillColor(FILL_ALT)
                c.rect(LM, y-row_h, wids_rm[0]+wids_rm[1]+_vtr_w, row_h, fill=1, stroke=0)
            c.setFillColor(black)
            c.setFont("Helvetica", 8.5)
            ids_lines = wrap_text(r['ids'], wids_rm[1] - 2*mm)
            total_ids_h = len(ids_lines) * 5*mm
            row_h_real = max(row_h, 5*mm)
            # Horário centrado verticalmente (meio da célula menos meia altura do texto ~2mm)
            y_centro = y - row_h_real/2 - 1.5*mm
            c.drawCentredString(LM+wids_rm[0]/2, y_centro, str(r['hor']))
            # Militares centrados verticalmente
            y_ids_start = y - (row_h_real - total_ids_h) / 2 - 3.5*mm
            for li, id_l in enumerate(ids_lines):
                c.drawCentredString(LM+wids_rm[0]+wids_rm[1]/2, y_ids_start - (li*5*mm), id_l)
            # Viatura centrada verticalmente
            if _vtr_w:
                c.drawCentredString(LM+wids_rm[0]+wids_rm[1]+_vtr_w/2, y_centro, r.get('vtr', ''))
            c.setStrokeColor(CINZA_LN)
            c.rect(LM, y-row_h, wids_rm[0]+wids_rm[1]+_vtr_w, row_h, fill=0, stroke=1)
            c.line(LM+wids_rm[0], y, LM+wids_rm[0], y-row_h)
            if _vtr_w:
                c.line(LM+wids_rm[0]+wids_rm[1], y, LM+wids_rm[0]+wids_rm[1], y-row_h)
            y -= row_h

        # Agora desenhar as células de observação fundidas por cima
        for idx, (obs_txt, span_count, span_h) in obs_spans.items():
            if idx not in y_grupo:
                continue
            y_ini = y_grupo[idx]
            obs_lines_span = wrap_text(obs_txt, max_pts_rm) if obs_txt else [""]
            # Fundo branco da célula obs
            c.setFillColor(white)
            c.rect(x_obs_col, y_ini-span_h, _obs_w, span_h, fill=1, stroke=0)
            # Centrar texto verticalmente na célula fundida
            total_txt_h = len(obs_lines_span) * 5*mm
            y_texto = y_ini - (span_h - total_txt_h) / 2 - 3.5*mm
            c.setFillColor(black)
            c.setFont("Helvetica", 8.5)
            for li, obs_l in enumerate(obs_lines_span):
                c.drawString(x_obs_start, y_texto - (li * 5*mm), obs_l)
            # Borda da célula fundida
            c.setStrokeColor(CINZA_LN)
            c.rect(x_obs_col, y_ini-span_h, _obs_w, span_h, fill=0, stroke=1)
        y -= 2*mm

    # ---- OBSERVAÇÕES (todos exceto remunerados) ----
    obs_por_ind = {}  # label -> {obs -> set(hors)}
    for df_sec in [df_pat, df_at, df_ap, df_outros]:
        if df_sec.empty or "observações" not in df_sec.columns:
            continue
        for _, row in df_sec.iterrows():
            obs = str(row.get("observações", "")).strip()
            ind = str(row.get("indicativo rádio", "")).strip() if "indicativo rádio" in df_sec.columns else ""
            serv = str(row.get("serviço", "")).strip()
            hor  = str(row.get("horário", "")).strip()
            label = ind if ind else serv
            if label not in obs_por_ind:
                obs_por_ind[label] = {}
            obs_key = obs if (obs and obs != 'nan') else ""
            if obs_key not in obs_por_ind[label]:
                obs_por_ind[label][obs_key] = set()
            obs_por_ind[label][obs_key].add(hor)  # set evita duplicados

    obs_lista = []
    for label, obs_map in obs_por_ind.items():
        obs_com = {k: v for k, v in obs_map.items() if k}
        obs_sem = {k: v for k, v in obs_map.items() if not k}
        tem_multiplas = len(obs_com) > 1 or (obs_com and obs_sem)
        for obs_txt, hors in obs_com.items():
            if tem_multiplas:
                hors_unicos = sorted(hors)  # já é set, sem duplicados
                lbl = f"{label}\n{', '.join(hors_unicos)}"
            else:
                lbl = label
            obs_lista.append((lbl, obs_txt))

    if obs_lista:
        if y < 40*mm: y = new_page()
        y = sec_title(y, "Observações")
        cols_ob = ["Indicativo / Serviço", "Detalhe"]
        wids_ob = [35*mm, TW-35*mm]
        y = tbl_header(y, cols_ob, wids_ob)
        fill = False
        max_pts_ob = (wids_ob[1] - 3*mm)
        for lbl, obs in obs_lista:
            label_lines = lbl.split('\n')
            obs_lines = wrap_text(obs, max_pts_ob)
            row_h = max(5*mm, max(len(obs_lines), len(label_lines)) * 5*mm)
            if y - row_h < 20*mm: y = new_page()
            if fill:
                c.setFillColor(FILL_ALT)
                c.rect(LM, y-row_h, TW, row_h, fill=1, stroke=0)
            c.setFillColor(black)
            c.setFont("Helvetica", 8.5)
            for li, l in enumerate(label_lines):
                c.drawCentredString(LM+wids_ob[0]/2, y-(li*5*mm)-3.5*mm, l)
            for li, obs_l in enumerate(obs_lines):
                c.drawString(LM+wids_ob[0]+2*mm, y-(li*5*mm)-3.5*mm, obs_l)
            c.setStrokeColor(CINZA_LN)
            c.rect(LM, y-row_h, TW, row_h, fill=0, stroke=1)
            c.line(LM+wids_ob[0], y, LM+wids_ob[0], y-row_h)
            y -= row_h
            fill = not fill
        y -= 2*mm

    rodape()
    c.save()
    return buf.getvalue()


def get_nome_militar(df_util: pd.DataFrame, id_m) -> str:
    if df_util.empty or 'id' not in df_util.columns:
        return f"ID {id_m}"
    res = df_util[df_util['id'].astype(str) == str(id_m)]
    return f"{res.iloc[0]['posto']} {res.iloc[0]['nome']}" if not res.empty else f"ID {id_m}"

def get_nome_curto(df_util: pd.DataFrame, id_m) -> str:
    """Posto + primeiro e último nome."""
    if df_util.empty or 'id' not in df_util.columns:
        return f"ID {id_m}"
    res = df_util[df_util['id'].astype(str) == str(id_m)]
    if res.empty:
        return f"ID {id_m}"
    posto = res.iloc[0]['posto']
    nomes = res.iloc[0]['nome'].strip().split()
    nome_curto = f"{nomes[0]} {nomes[-1]}" if len(nomes) > 1 else nomes[0]
    return f"{posto} {nome_curto}"

def filtrar_secao(keys: list, df_f: pd.DataFrame) -> tuple:
    """Filtra linhas pelo padrão de keys. Devolve (df_secção, df_restante)."""
    pattern = '|'.join(k for k in keys if k).lower()
    if not pattern:
        return pd.DataFrame(), df_f
    mask = df_f['serviço'].str.lower().str.contains(pattern, na=False)
    return df_f[mask].copy(), df_f[~mask].copy()

def _limpar_sem_militar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas onde id está vazio -- serviços sem militar escalado."""
    if 'id' not in df.columns:
        return df
    return df[df['id'].astype(str).str.strip().str.len() > 0].copy()

def _cel_expandivel(val: str, limite: int = 60) -> str:
    """Renderiza texto diretamente sem truncar."""
    return str(val).replace('\n', '<br>')

AZUL = "#14285f"
AZUL_MED = "#cdd7f2"
AZUL_CLARO = "#ebf1ff"

def _sec_header(titulo):
    return f"""<div style='background:{AZUL};color:white;padding:5px 10px;
        font-size:0.8rem;font-weight:700;letter-spacing:0.05em;
        margin-top:10px;margin-bottom:0;border-radius:4px 4px 0 0'>
        {titulo.upper()}</div>"""

def _render_tabela(df: pd.DataFrame, expandivel: bool = False) -> str:
    def _cel(val):
        txt = str(val).replace('\n', '<br>')
        return txt

    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;white-space:nowrap;border-bottom:2px solid {AZUL};"
    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:top;border-bottom:1px solid #dde6f7;word-break:break-word;"
    td_a = td_s + f"background:{AZUL_CLARO};"
    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;margin-bottom:2px'>"
    html += "<table style='width:100%;border-collapse:collapse;'><thead><tr>"
    for col in df.columns:
        html += f"<th style='{th_s}'>{str(col).capitalize()}</th>"
    html += "</tr></thead><tbody>"
    for i, (_, row) in enumerate(df.iterrows()):
        td = td_a if i % 2 == 0 else td_s
        html += "<tr>"
        for val in row:
            html += f"<td style='{td}'>{_cel(str(val))}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html

def _render_ids_linha(grupos: dict) -> str:
    """Renderiza ausências/ADM em formato compacto: Tipo: id1, id2"""
    html = f"<div style='border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;padding:6px 10px;margin-bottom:2px;background:white;font-size:0.8rem;'>"
    for serv, ids in grupos.items():
        html += f"<div style='margin-bottom:3px'><span style='color:{AZUL};font-weight:700'>{serv}:</span> <span style='color:#1E293B'>{', '.join(ids)}</span></div>"
    html += "</div>"
    return html

def mostrar_secao(titulo: str, df_sec: pd.DataFrame, mostrar_extras: bool = False, excluir_cols: list = [], esconder_servico: bool = False):
    """Renderiza uma secção da escala com estilo próximo do PDF."""
    if df_sec.empty:
        return
    st.markdown(_sec_header(titulo), unsafe_allow_html=True)
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
                                        # Verificar PIN -- suporta texto simples e hash
                                        user = None
                                        for _, row_u in df_u.iterrows():
                                            if verificar_pin(new, str(row_u.get('pin', ''))):
                                                user = row_u
                                                break
                                        if user is not None:
                                            # Migrar PIN para hash se ainda for texto simples
                                            pin_guardado = str(user.get('pin', '')).strip()
                                            if ':' not in pin_guardado or len(pin_guardado) <= 10:
                                                migrar_pin_para_hash(str(user.get('email', '')), new)
                                            fazer_login(user, user['email'])
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

    # ── MODO EMAIL/PASSWORD ── (removido -- login só por PIN)
    # ── MODO REGISTAR PIN ── (removido -- PINs criados pelos admins)



# ============================================================
# 8. APP PRINCIPAL (pós-login)
# ============================================================
else:
    # Carregar dados globais uma vez por sessão de render
    df_trocas = load_trocas()
    df_util   = load_utilizadores()
    ano_atual = datetime.now().year
    df_ferias  = load_ferias(ano_atual)
    feriados   = load_feriados(ano_atual)
    df_folgas  = load_folgas(ano_atual)
    grupos_folga = load_grupos_folga()
    df_licencas = load_licencas(ano_atual)

    u_id      = str(st.session_state['user_id'])
    u_nome    = st.session_state['user_nome']
    is_admin  = st.session_state.get("is_admin", False)

    # Carregar dias publicados uma vez (não-admins precisam disto em vários menus)
    _dias_pub_global = load_dias_publicados() if not is_admin else set()

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
            "🔄 Trocas",
            "🔍 Escala Geral",
            "🔄 Giros",
            "👥 Efetivo",
        ]
        menu_admin = ["🏖️ Férias", "📊 Estatísticas", "⚖️ Validar Trocas", "📜 Trocas Validadas", "🚨 Alertas", "⚙️ Gerar Escala", "👤 Gerir Utilizadores"]

        st.markdown("<p style='font-size:0.75rem;letter-spacing:0.08em;color:#94A3B8;margin:0 0 4px 0;'>MENU</p>", unsafe_allow_html=True)

        menu_opt = [
            "📅 Minha Escala",
            "🔄 Trocas",
            "🔍 Escala Geral",
            "🔄 Giros",
            "👥 Efetivo",
        ]
        if is_admin:
            menu_opt += ["", "🏖️ Férias", "🏥 Dispensas", "📊 Estatísticas", "⚖️ Validar Trocas", "📜 Trocas Validadas", "🚨 Alertas", "⚙️ Gerar Escala", "📢 Publicar Escala", "👤 Gerir Utilizadores"]

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

        if is_admin:
            tab_escala, = st.tabs(["📅 Escala"])
        else:
            tab_escala, tab_stats, tab_ferias = st.tabs(["📅 Escala", "📊 Estatísticas", "🏖️ Férias"])

        with tab_escala:

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
                                <div style='color:#92400E;font-size:0.82rem'>Completa {idade} anos -- Parabéns! 🎉</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            vista = st.radio("Vista:", ["📋 Próximos Serviços", "📅 Calendário Mensal"], horizontal=True, label_visibility="collapsed")

            # ── Exportar para Calendário ──
            with st.expander("📆 Exportar para Calendário", expanded=False):
                st.caption("Gera um ficheiro .ics com os teus próximos serviços para importar no iPhone, Android ou Outlook.")
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    dias_exp = st.slider("Dias a incluir:", 7, 90, 30)
                with col_exp2:
                    incl_folgas_exp = st.checkbox("Incluir folgas", value=True, key="exp_incl_folgas")
                    incl_ferias_exp = st.checkbox("Incluir férias", value=True, key="exp_incl_ferias")
                if st.button("📥 Gerar ficheiro .ics", use_container_width=True):
                    ics_lines = [
                        "BEGIN:VCALENDAR",
                        "VERSION:2.0",
                        "PRODID:-//GNR Famalicão//Escala//PT",
                        "CALSCALE:GREGORIAN",
                        "METHOD:PUBLISH",
                        "X-WR-CALNAME:Escala GNR Famalicão",
                        "X-WR-TIMEZONE:Europe/Lisbon",
                    ]
                    hj_exp = datetime.now()
                    eventos = 0
                    dias_pub_exp = load_dias_publicados()

                    for i_exp in range(dias_exp):
                        dt_exp = hj_exp + timedelta(days=i_exp)
                        aba_exp = dt_exp.strftime("%d-%m")

                        # Só dias publicados para todos
                        if aba_exp not in dias_pub_exp:
                            continue

                        df_exp = load_data(aba_exp)
                        if df_exp.empty:
                            continue

                        meu_exp = df_exp[df_exp['id'].astype(str).str.strip() == u_id]
                        if meu_exp.empty:
                            continue

                        for _, row_exp in meu_exp.iterrows():
                            serv_exp = str(row_exp.get('serviço', '')).strip()
                            hor_exp  = str(row_exp.get('horário', '')).strip()
                            obs_exp  = str(row_exp.get('observações', '')).strip()
                            if not serv_exp:
                                continue
                            # Filtrar folgas e férias conforme opção do utilizador
                            s_n_skip = norm(serv_exp)
                            if not incl_folgas_exp and any(x in s_n_skip for x in ['folga']):
                                continue
                            if not incl_ferias_exp and any(x in s_n_skip for x in ['ferias']):
                                continue

                            # Emoji por tipo de serviço
                            s_n = norm(serv_exp)
                            if any(x in s_n for x in ['remu', 'grat']):
                                emoji = "💰"
                            elif 'patrulha' in s_n or 'ocorr' in s_n:
                                emoji = "🚔"
                            elif 'atendimento' in s_n:
                                emoji = "🖥️"
                            elif 'apoio' in s_n:
                                emoji = "🤝"
                            elif any(x in s_n for x in ['ferias', 'licen']):
                                emoji = "🏖️"
                            elif 'folga' in s_n:
                                emoji = "😴"
                            elif any(x in s_n for x in ['tribunal', 'dilig']):
                                emoji = "⚖️"
                            else:
                                emoji = "🛡️"

                            # Calcular horas início/fim
                            dt_inicio = dt_exp
                            dt_fim    = dt_exp
                            if hor_exp and '-' in hor_exp:
                                try:
                                    h_ini, h_fim = hor_exp.split('-')
                                    hi = int(h_ini.strip().replace('H','').replace('h',''))
                                    hf = int(h_fim.strip().replace('H','').replace('h',''))
                                    dt_inicio = dt_exp.replace(hour=hi, minute=0, second=0, microsecond=0)
                                    if hf <= hi:
                                        dt_fim = (dt_exp + timedelta(days=1)).replace(hour=hf, minute=0, second=0, microsecond=0)
                                    else:
                                        dt_fim = dt_exp.replace(hour=hf, minute=0, second=0, microsecond=0)
                                except:
                                    dt_inicio = dt_exp.replace(hour=0, minute=0, second=0, microsecond=0)
                                    dt_fim    = dt_exp.replace(hour=23, minute=59, second=0, microsecond=0)
                            else:
                                dt_inicio = dt_exp.replace(hour=0, minute=0, second=0, microsecond=0)
                                dt_fim    = dt_exp.replace(hour=23, minute=59, second=0, microsecond=0)

                            uid_evt  = f"{dt_exp.strftime('%Y%m%d')}-{u_id}-{eventos}"
                            summary  = f"{emoji} {serv_exp}" + (f" ({hor_exp})" if hor_exp else "")
                            desc     = obs_exp if obs_exp and obs_exp != 'nan' else ""

                            ics_lines += [
                                "BEGIN:VEVENT",
                                f"UID:{uid_evt}@gnr.famalicao",
                                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                                f"DTSTART:{dt_inicio.strftime('%Y%m%dT%H%M%S')}",
                                f"DTEND:{dt_fim.strftime('%Y%m%dT%H%M%S')}",
                                f"SUMMARY:{summary}",
                                f"DESCRIPTION:{desc}",
                                "LOCATION:Posto Territorial de Vila Nova de Famalicão",
                                "END:VEVENT",
                            ]
                            eventos += 1

                    ics_lines.append("END:VCALENDAR")
                    ics_content = "\r\n".join(ics_lines)

                    if eventos > 0:
                        st.download_button(
                            f"⬇️ Descarregar ({eventos} serviços)",
                            data=ics_content.encode('utf-8'),
                            file_name=f"escala_gnr_{u_id}.ics",
                            mime="text/calendar",
                            use_container_width=True,
                        )
                    else:
                        st.info("Não encontrei serviços para os próximos dias.")

            with st.expander("🏖️ Exportar Mapa de Folgas", expanded=False):
                st.caption("Gera um ficheiro .ics com todas as tuas folgas do ano.")
                if st.button("📥 Gerar mapa de folgas", use_container_width=True, key="btn_ics_folgas"):
                    with st.spinner("A calcular folgas..."):
                        ano_fme = datetime.now().year
                        df_folgas_me = load_folgas(ano_fme)
                        grupos_me    = load_grupos_folga()
                        from calendar import monthrange as _mr
                        ics_f = ["BEGIN:VCALENDAR","VERSION:2.0",
                                 "PRODID:-//GNR Famalicão//Folgas//PT",
                                 "CALSCALE:GREGORIAN","METHOD:PUBLISH",
                                 "X-WR-CALNAME:Folgas GNR Famalicão"]
                        n_folgas = 0
                        for m in range(1, 13):
                            _, n_dias = _mr(ano_fme, m)
                            for d in range(1, n_dias+1):
                                dt = datetime(ano_fme, m, d).date()
                                tipo = militar_de_folga(u_id, dt, df_folgas_me, grupos_me, feriados)
                                if tipo:
                                    dtstr = dt.strftime('%Y%m%d')
                                    dtend = (dt + timedelta(days=1)).strftime('%Y%m%d')
                                    ics_f += ["BEGIN:VEVENT",
                                              f"UID:folga-{u_id}-{dtstr}@gnr",
                                              f"DTSTART;VALUE=DATE:{dtstr}",
                                              f"DTEND;VALUE=DATE:{dtend}",
                                              f"SUMMARY:{'😴' if 'Semanal' in tipo else '🌿'} {tipo}",
                                              "END:VEVENT"]
                                    n_folgas += 1
                        ics_f.append("END:VCALENDAR")
                        if n_folgas > 0:
                            st.download_button(f"⬇️ Descarregar ({n_folgas} folgas)",
                                               data="\r\n".join(ics_f).encode('utf-8'),
                                               file_name=f"folgas_{u_id}_{ano_fme}.ics",
                                               mime="text/calendar",
                                               use_container_width=True, key="dl_folgas_ics")
                        else:
                            st.info("Não tens folgas configuradas.")

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
                dias_publicados_cal = _dias_pub_global  # todos filtram por publicados
                for d in range(1, n_dias + 1):
                    dt_cal = datetime(ano_sel, mes_sel, d)
                    aba = dt_cal.strftime("%d-%m")
                    # Só mostrar dias publicados
                    if aba not in dias_publicados_cal:
                        continue
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
                            rem_cal = rem_cal[rem_cal['serviço'].apply(norm).str.contains('remu|grat', na=False)]
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
                            s_n = norm(info['serviço'])
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
                dias_publicados = _dias_pub_global

                # Percorre dias a partir de hoje até não encontrar mais abas com dados
                dias_sem_dados = 0
                i = 0
                encontrou_algum = False

                while dias_sem_dados < 5:  # Para após 5 dias consecutivos sem dados
                    dt  = hj + timedelta(days=i)
                    d_s = dt.strftime('%d/%m/%Y')
                    aba_dt = dt.strftime('%d-%m')
                    lbl = "🟢 HOJE" if i == 0 else ("🔵 AMANHÃ" if i == 1 else dt.strftime("%d/%m (%a)").upper())

                    # Para não-admins: só mostrar dias publicados
                    if not is_admin and aba_dt not in dias_publicados:
                        i += 1
                        if i > 60: break
                        continue

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
                        df_d_rem = df_d  # já carregado acima
                        if not df_d_rem.empty and 'serviço' in df_d_rem.columns:
                            rem_mil_t = df_d_rem[df_d_rem['id'].astype(str) == u_id]
                            rem_mil_t = rem_mil_t[rem_mil_t['serviço'].apply(norm).str.contains('remu|grat', na=False)]
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
                                s_norm = norm(row['serviço'])
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
                                df_rem_dia = df_d  # já carregado acima
                                if not df_rem_dia.empty and 'serviço' in df_rem_dia.columns:
                                    # Remunerados escalados diretamente
                                    rem_mil = df_rem_dia[df_rem_dia['id'].astype(str) == u_id]
                                    rem_mil = rem_mil[rem_mil['serviço'].apply(norm).str.contains('remu|grat', na=False)]
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
                                if militar_de_ferias(u_id, dt.date(), df_ferias, feriados):
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

        if not is_admin:
            with tab_stats:
                _gsheet_url = st.secrets["gsheet_url"]
                _sheet_id   = _gsheet_url.split("/d/")[1].split("/")[0]
                with st.spinner("A carregar histórico..."):
                    df_stats_t = contar_servicos_historico(u_id, _sheet_id)
                if df_stats_t.empty:
                    st.info("Não foram encontrados serviços no histórico.")
                else:
                    hoje_s = datetime.now()
                    meses_pt_s = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                                  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
                    periodo_s = st.radio("Período:", ["📅 Mensal", "📆 Anual"], horizontal=True, key="stats_tab_periodo")
                    if periodo_s == "📅 Mensal":
                        meses_d = sorted(df_stats_t['mes'].unique(),
                                        key=lambda x: (int(x.split('/')[1]), int(x.split('/')[0])))
                        mes_a = f"{hoje_s.month:02d}/{hoje_s.year}"
                        idx_d = meses_d.index(mes_a) if mes_a in meses_d else len(meses_d)-1
                        mes_s = st.selectbox("Mês:", meses_d, index=idx_d,
                                            format_func=lambda m: f"{meses_pt_s[int(m.split('/')[0])-1]} {m.split('/')[1]}")
                        df_f2 = df_stats_t[df_stats_t['mes'] == mes_s]
                    else:
                        anos_d = sorted(df_stats_t['mes'].apply(lambda x: x.split('/')[1]).unique(), reverse=True)
                        ano_s = st.selectbox("Ano:", anos_d, key="stats_tab_ano")
                        df_f2 = df_stats_t[df_stats_t['mes'].str.endswith(f"/{ano_s}")]
                    col1s, col2s = st.columns(2)
                    with col1s:
                        st.markdown("**Por categoria**")
                        if 'categoria' in df_f2.columns:
                            st.dataframe(df_f2.groupby('categoria').size().reset_index(name='total').sort_values('total', ascending=False), use_container_width=True, hide_index=True)
                        else:
                            st.info("Sem dados de categoria.")
                    with col2s:
                        st.markdown("**Detalhe por serviço**")
                        if 'serviço' in df_f2.columns:
                            st.dataframe(df_f2.groupby('serviço').size().reset_index(name='vezes').sort_values('vezes', ascending=False), use_container_width=True, hide_index=True)
                        else:
                            st.info("Sem dados de serviço.")

            with tab_ferias:
                ano_tf = datetime.now().year
                df_ftab = load_ferias(ano_tf)
                fer_tab = load_feriados(ano_tf)
                meses_pt_f = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                              "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
                def fmt_data_f(d):
                    return f"{d.day} de {meses_pt_f[d.month]} de {d.year}"
                if df_ftab.empty:
                    st.info(f"Não há plano de férias para {ano_tf}.")
                else:
                    cols_ft = df_ftab.columns.tolist()
                    id_col_ft = 'id' if 'id' in cols_ft else cols_ft[0]
                    ini_cols_ft = [c for c in cols_ft if 'ini' in c.lower()]
                    fim_cols_ft  = [c for c in cols_ft if 'fim' in c.lower()]
                    total_col_ft = next((c for c in cols_ft if 'total' in c.lower()), None)
                    mil_ft = df_ftab[df_ftab[id_col_ft].astype(str).str.strip() == u_id]
                    if mil_ft.empty:
                        st.info("Não tens férias planeadas para este ano.")
                    else:
                        row_ft = mil_ft.iloc[0]
                        periodos_ft = []
                        for ini_c, fim_c in zip(ini_cols_ft, fim_cols_ft):
                            ini_v = str(row_ft.get(ini_c, '')).strip()
                            fim_v = str(row_ft.get(fim_c, '')).strip()
                            if not ini_v or ini_v == 'nan': continue
                            ini_d = _parse_data_ferias(ini_v, ano_tf)
                            fim_d = _parse_data_ferias(fim_v, ano_tf)
                            if not ini_d or not fim_d: continue
                            du = sum(1 for n in range((fim_d - ini_d).days + 1)
                                    if (ini_d + timedelta(days=n)).weekday() < 5
                                    and (ini_d + timedelta(days=n)) not in fer_tab)
                            fim_ext = ini_d
                            while True:
                                prox = fim_ext + timedelta(days=1)
                                if prox.weekday() >= 5 or prox in fer_tab: fim_ext = prox
                                else: break
                            dc = (fim_ext - ini_d).days + 1
                            periodos_ft.append((ini_d, fim_d, du, dc))
                        total_du_ft = sum(p[2] for p in periodos_ft)

                        # Exportar férias para calendário — em cima
                        with st.expander("📆 Exportar Mapa de Férias", expanded=False):
                            st.caption("Gera um ficheiro .ics com as tuas férias para importar no calendário.")
                            if st.button("📥 Gerar mapa de férias", use_container_width=True, key="btn_ics_ferias"):
                                ics_fer = ["BEGIN:VCALENDAR","VERSION:2.0",
                                           "PRODID:-//GNR Famalicão//Ferias//PT",
                                           "CALSCALE:GREGORIAN","METHOD:PUBLISH",
                                           "X-WR-CALNAME:Férias GNR Famalicão"]
                                for i, (ini_d, fim_d, du, dc) in enumerate(periodos_ft, 1):
                                    dtstr = ini_d.strftime('%Y%m%d')
                                    dtend = (fim_d + timedelta(days=1)).strftime('%Y%m%d')
                                    ics_fer += ["BEGIN:VEVENT",
                                                f"UID:ferias-{u_id}-{i}-{dtstr}@gnr",
                                                f"DTSTART;VALUE=DATE:{dtstr}",
                                                f"DTEND;VALUE=DATE:{dtend}",
                                                f"SUMMARY:🏖️ Férias ({du} dias úteis)",
                                                "END:VEVENT"]
                                ics_fer.append("END:VCALENDAR")
                                st.download_button(
                                    f"⬇️ Descarregar ({len(periodos_ft)} períodos)",
                                    data="\r\n".join(ics_fer).encode('utf-8'),
                                    file_name=f"ferias_{u_id}_{ano_tf}.ics",
                                    mime="text/calendar",
                                    use_container_width=True,
                                    key="dl_ferias_ics"
                                )
                        st.markdown("---")
                        total_du_ft = sum(p[2] for p in periodos_ft)
                        st.markdown(
                            f'<div style="background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border-radius:12px;'
                            f'padding:16px 20px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">'
                            f'<div><div style="font-size:0.8rem;color:#065F46;font-weight:600">PLANO DE FÉRIAS {ano_tf}</div>'
                            f'<div style="font-size:1.1rem;font-weight:800;color:#064E3B">{u_nome}</div></div>'
                            f'<div style="text-align:right"><div style="font-size:1.8rem;font-weight:900;color:#059669">{total_du_ft}</div>'
                            f'<div style="font-size:0.75rem;color:#065F46">dias úteis</div></div></div>',
                            unsafe_allow_html=True
                        )
                        for i, (ini_d, fim_d, du, dc) in enumerate(periodos_ft, 1):
                            st.markdown(
                                f'<div style="background:#F0FDF4;border-left:4px solid #16A34A;border-radius:10px;'
                                f'padding:14px 18px;margin-bottom:10px">'
                                f'<div style="font-size:0.72rem;color:#16A34A;font-weight:700;margin-bottom:6px">PERÍODO {i}</div>'
                                f'<div style="font-size:1rem;font-weight:700;color:#14532D">🏖️ {fmt_data_f(ini_d)}</div>'
                                f'<div style="font-size:0.85rem;color:#166534;margin:2px 0 10px 0">até {fmt_data_f(fim_d)}</div>'
                                f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                                f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">📅 {dc} dias corridos</span>'
                                f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">💼 {du} dias úteis</span>'
                                f'</div></div>',
                                unsafe_allow_html=True
                            )

    elif menu == "📊 Estatísticas":
        st.title("📊 Estatísticas de Serviço")

        if is_admin:
            militares_opts = {f"{r['posto']} {r['nome']} (ID: {r['id']})": str(r['id']) for _, r in df_util.iterrows()}
            sel_mil = st.selectbox("Selecionar militar:", ["-- O meu próprio --"] + list(militares_opts.keys()))
            alvo_id   = u_id if sel_mil == "-- O meu próprio --" else militares_opts[sel_mil]
            alvo_nome = u_nome if sel_mil == "-- O meu próprio --" else sel_mil
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

        meses_pt = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

        def fmt_data_ext(d):
            return f"{d.day} de {meses_pt[d.month]} de {d.year}"

        if df_f.empty:
            st.info(f"Não há plano de férias para {ano_sel_f}.")
        else:
            cols_f = df_f.columns.tolist()
            id_col_f = 'id' if 'id' in cols_f else cols_f[0]
            ini_cols_f = [c for c in cols_f if 'ini' in c.lower()]
            fim_cols_f  = [c for c in cols_f if 'fim' in c.lower()]
            dias_cols_f = [c for c in cols_f if 'dias' in c.lower() and 'total' not in c.lower()]
            total_col_f = next((c for c in cols_f if 'total' in c.lower()), None)

            def render_periodos(row_f, fer_f):
                periodos = []
                def parse_data(s):
                    s = str(s).strip()
                    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d', '%m/%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                        try:
                            d = datetime.strptime(s, fmt).date()
                            if fmt == '%m/%d':
                                d = d.replace(year=ano_sel_f)
                            return d
                        except:
                            pass
                    return None

                def dias_corridos_reais(ini_d, fim_d, fer_f):
                    # Estender fim_d para incluir fins de semana e feriados subsequentes
                    fim_ext = fim_d
                    while True:
                        proximo = fim_ext + timedelta(days=1)
                        if proximo.weekday() >= 5 or proximo in fer_f:
                            fim_ext = proximo
                        else:
                            break
                    return (fim_ext - ini_d).days + 1
                for ini_c, fim_c in zip(ini_cols_f, fim_cols_f):
                    ini_v = str(row_f.get(ini_c, '')).strip()
                    fim_v = str(row_f.get(fim_c, '')).strip()
                    if not ini_v or ini_v == 'nan': continue
                    ini_d = parse_data(ini_v)
                    fim_d = parse_data(fim_v)
                    if not ini_d or not fim_d: continue
                    du = sum(1 for n in range((fim_d - ini_d).days + 1)
                            if (ini_d + timedelta(days=n)).weekday() < 5
                            and (ini_d + timedelta(days=n)) not in fer_f)
                    dc = dias_corridos_reais(ini_d, fim_d, fer_f)
                    periodos.append((ini_d, fim_d, du, dc))
                return periodos

            if is_admin:
                militares_opts_f = {f"{r['posto']} {r['nome']} (ID: {r['id']})": str(r['id']) for _, r in df_util.iterrows()}
                sel_mil_f = st.selectbox("Selecionar militar:", ["-- O meu próprio --"] + list(militares_opts_f.keys()))
                alvo_id_f = u_id if sel_mil_f == "-- O meu próprio --" else militares_opts_f[sel_mil_f]
            else:
                alvo_id_f = u_id

            mil_f = df_f[df_f[id_col_f].astype(str).str.strip() == alvo_id_f]
            if mil_f.empty:
                st.info("Não há férias planeadas para este militar.")
            else:
                row_f = mil_f.iloc[0]
                nome_exibir = get_nome_militar(df_util, alvo_id_f)
                total_f = str(row_f.get(total_col_f, '')).strip() if total_col_f else ''
                periodos = render_periodos(row_f, fer_f)
                total_du = sum(p[2] for p in periodos)
                total_dc = sum(p[3] for p in periodos)

                # Resumo no topo
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border-radius:12px;'
                    f'padding:16px 20px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">'
                    f'<div><div style="font-size:0.8rem;color:#065F46;font-weight:600">PLANO DE FÉRIAS {ano_sel_f}</div>'
                    f'<div style="font-size:1.1rem;font-weight:800;color:#064E3B">{nome_exibir}</div></div>'
                    f'<div style="text-align:right">'
                    f'<div style="font-size:1.8rem;font-weight:900;color:#059669">{total_du}</div>'
                    f'<div style="font-size:0.75rem;color:#065F46">dias úteis</div>'
                    f'</div></div>',
                    unsafe_allow_html=True
                )

                for i, (ini_d, fim_d, du, dc) in enumerate(periodos, 1):
                    st.markdown(
                        f'<div style="background:#F0FDF4;border-left:4px solid #16A34A;border-radius:10px;'
                        f'padding:14px 18px;margin-bottom:10px">'
                        f'<div style="font-size:0.72rem;color:#16A34A;font-weight:700;letter-spacing:0.08em;margin-bottom:6px">PERÍODO {i}</div>'
                        f'<div style="font-size:1rem;font-weight:700;color:#14532D">🏖️ {fmt_data_ext(ini_d)}</div>'
                        f'<div style="font-size:0.85rem;color:#166534;margin:2px 0 10px 0">até {fmt_data_ext(fim_d)}</div>'
                        f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                        f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">📅 {dc} dias corridos</span>'
                        f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">💼 {du} dias úteis</span>'
                        f'</div></div>',
                        unsafe_allow_html=True
                    )

    # --- 🔍 ESCALA GERAL ---
    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")

        if is_admin:
            tab_eg, tab_hist_serv = st.tabs(["📅 Escala do Dia", "🔎 Historial por Serviço"])
        else:
            tab_eg = st.container()
            tab_hist_serv = None

        with tab_eg:
            d_sel  = st.date_input("Seleciona a data:", format="DD/MM/YYYY")
            aba_sel = d_sel.strftime("%d-%m")

        # Não-admins: só ver dias publicados
        if not is_admin and aba_sel not in _dias_pub_global:
            st.info("A escala para este dia ainda não foi publicada.")
        else:
            df_dia = load_data(aba_sel)

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

                    # Aplicar matar remunerado -- mesmo formato que trocas normais
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
                        # Linha do cedente -- substitui pelo novo titular
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
                        if militar_de_ferias(mid_f, d_sel, df_ferias, feriados):
                            nova_linha = {c: '' for c in df_at.columns}
                            nova_linha['id'] = mid_f
                            nova_linha['id_disp'] = mid_f
                            nova_linha['serviço'] = 'Férias'
                            nova_linha['horário'] = ''
                            df_at = pd.concat([df_at, pd.DataFrame([nova_linha])], ignore_index=True)

                pdf_bytes = gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at, df_util)
                col_pdf, col_full, _ = st.columns([1, 1, 3])
                with col_pdf:
                    st.download_button(
                        "📥 Escala do Dia",
                        pdf_bytes,
                        file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf",
                        mime="application/pdf"
                    )
                with col_full:
                    if st.button("📥 Escala Completa", use_container_width=True):
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
                                            if militar_de_ferias(mid_f2, dt2.date(), df_ferias, feriados):
                                                nl2 = {c: '' for c in df_d2.columns}
                                                nl2['id'] = mid_f2
                                                nl2['id_disp'] = mid_f2
                                                nl2['serviço'] = 'Férias'
                                                nl2['horário'] = ''
                                                df_d2 = pd.concat([df_d2, pd.DataFrame([nl2])], ignore_index=True)
                                    pb2 = gerar_pdf_escala_dia(dt2.strftime("%d/%m/%Y"), df_d2, df_util)
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
                                with col_full:
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
                df_aus, df_res = filtrar_secao(["férias", "licença", "doente", "baixa"], df_at)

                # Extrair cada grupo do df_res por ordem
                df_cmd,  df_res = filtrar_secao(["pronto", "secretaria", "inquérito", "diligência"],    df_res)
                df_apoi, df_res = filtrar_secao(["apoio"],                                 df_res)
                df_aten, df_res = filtrar_secao(["atendimento"],                           df_res)
                df_pat,  df_res = filtrar_secao(["po", "patrulha", "ronda", "vtr", "giro"], df_res)
                df_remu, df_res = filtrar_secao(["remu", "grat"],                            df_res)
                df_folga,df_res = filtrar_secao(["folga"],                                   df_res)
                df_outros       = df_res
                df_pat_ocorr, df_pat_outras = filtrar_secao(["ocorr"], df_pat)

                # 1. Ausências e ADM lado a lado no topo (igual ao PDF)
                col_aus, col_adm = st.columns(2)
                with col_aus:
                    grupos_aus = {}
                    for _, row in df_aus.iterrows():
                        serv = str(row.get('serviço', '')).strip()
                        mid  = str(row.get('id_disp', row.get('id', ''))).strip()
                        grupos_aus.setdefault(serv, []).append(mid)
                    for _, row in df_folga.iterrows():
                        serv = str(row.get('serviço', '')).strip()
                        mid  = str(row.get('id_disp', row.get('id', ''))).strip()
                        grupos_aus.setdefault(serv, []).append(mid)
                    if grupos_aus:
                        st.markdown(_sec_header("Ausências, Folgas e Licenças"), unsafe_allow_html=True)
                        st.markdown(_render_ids_linha(grupos_aus), unsafe_allow_html=True)
                with col_adm:
                    grupos_adm = {}
                    for _, row in df_cmd.iterrows():
                        serv = str(row.get('serviço', '')).strip()
                        mid  = str(row.get('id_disp', row.get('id', ''))).strip()
                        grupos_adm.setdefault(serv, []).append(mid)
                    if grupos_adm:
                        st.markdown(_sec_header("Outras Situações / ADM"), unsafe_allow_html=True)
                        st.markdown(_render_ids_linha(grupos_adm), unsafe_allow_html=True)

                # 2. Atendimento e Apoio
                mostrar_secao("Atendimento",               df_aten,       esconder_servico=True)
                mostrar_secao("Apoio ao Atendimento",      df_apoi,       esconder_servico=True)

                # 3. Patrulhas
                mostrar_secao("Patrulha Ocorrências",      df_pat_ocorr,  mostrar_extras=True, esconder_servico=True)
                mostrar_secao("Patrulhas",                 df_pat_outras, mostrar_extras=True)

                # 4. Outros Serviços
                mostrar_secao("Outros Serviços",           df_outros,     mostrar_extras=True, excluir_cols=['giro'])

                # 5. Remunerados -- obs igual com rowspan (células fundidas)
                if not df_remu.empty:
                    st.markdown(_sec_header("Serviços Remunerados / Gratificados"), unsafe_allow_html=True)
                    # Preparar linhas por horário
                    rows_rem = []
                    for hor, grp in df_remu.groupby('horário', sort=False):
                        ids = ', '.join(grp['id_disp'].tolist())
                        obs = str(grp['observações'].iloc[0]).strip() if 'observações' in grp.columns else ''
                        if obs == 'nan': obs = ''
                        vtr = str(grp['viatura'].iloc[0]).strip() if 'viatura' in grp.columns else ''
                        if vtr == 'nan': vtr = ''
                        rows_rem.append({'horário': hor, 'militares': ids, 'vtr': vtr, 'obs': obs})

                    # Calcular rowspans por obs
                    obs_spans = {}
                    for i, r in enumerate(rows_rem):
                        obs = r['obs']
                        if obs not in obs_spans:
                            obs_spans[obs] = {'start': i, 'count': 0}
                        obs_spans[obs]['count'] += 1
                    obs_first = {v['start']: (k, v['count']) for k, v in obs_spans.items()}

                    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;border-bottom:2px solid {AZUL};"
                    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-bottom:1px solid #dde6f7;"
                    td_a = td_s + f"background:{AZUL_CLARO};"

                    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;margin-bottom:2px'>"
                    html += "<table style='width:100%;border-collapse:collapse;'><thead><tr>"
                    html += f"<th style='{th_s}'>Horário</th><th style='{th_s}'>Militares</th><th style='{th_s}'>Viatura</th><th style='{th_s}'>Observação</th>"
                    html += "</tr></thead><tbody>"
                    for i, r in enumerate(rows_rem):
                        td = td_a if i % 2 == 0 else td_s
                        html += "<tr>"
                        html += f"<td style='{td}'>{r['horário']}</td>"
                        html += f"<td style='{td}'>{r['militares']}</td>"
                        html += f"<td style='{td}'>{r.get('vtr', '')}</td>"
                        if i in obs_first:
                            obs_txt, span = obs_first[i]
                            html += f"<td style='{td}border-left:2px solid {AZUL_MED};' rowspan='{span}'>{obs_txt}</td>"
                        html += "</tr>"
                    html += "</tbody></table></div>"
                    st.markdown(html, unsafe_allow_html=True)

        # ── Tab Historial por Serviço (só admins) ──
        if is_admin and tab_hist_serv is not None:
            with tab_hist_serv:
                st.markdown("#### 🔎 Historial por Serviço")
                st.caption("Seleciona um serviço e um militar para ver quando fez esse serviço.")

                # Recolher todos os serviços únicos de todas as abas em cache
                # Usar os serviços da aba "serviços"
                try:
                    ws_serv_h = get_sheet().worksheet("serviços")
                    serv_vals_h = ws_serv_h.get_all_values()
                    servicos_disponiveis = [str(h).strip() for h in serv_vals_h[0] if str(h).strip()]
                except:
                    servicos_disponiveis = []

                if not servicos_disponiveis:
                    st.info("Não foi possível carregar a lista de serviços.")
                else:
                    col_sh1, col_sh2, col_sh3 = st.columns(3)
                    with col_sh1:
                        serv_sel_h = st.selectbox("Serviço:", servicos_disponiveis, key="serv_sel_hist")
                    with col_sh2:
                        # Coluna id pode ser 'id' ou 'id_militar'
                        col_id_u = 'id_militar' if 'id_militar' in df_util.columns else 'id'
                        col_nome_u = 'nome' if 'nome' in df_util.columns else col_id_u
                        mil_opts_h = {}
                        for _, r in df_util.iterrows():
                            mid = str(r.get(col_id_u, '')).strip()
                            nome = str(r.get(col_nome_u, '')).strip()
                            if mid and mid != 'nan':
                                mil_opts_h[f"{mid} -- {nome}"] = mid
                        mil_sel_h = st.selectbox("Militar:", list(mil_opts_h.keys()), key="mil_sel_hist")
                    with col_sh3:
                        hor_sel_h = st.text_input("Horário:", placeholder="ex: 00-08", key="hor_sel_hist")

                    if st.button("🔍 Pesquisar último", key="btn_hist_serv", use_container_width=True):
                        mid_h = str(mil_opts_h[mil_sel_h]).strip()
                        with st.spinner("A pesquisar..."):
                            sh_h = get_sheet()
                            # Ordenar abas do mais recente para o mais antigo
                            abas_h = sorted(
                                [ws.title for ws in sh_h.worksheets() if re.match(r'^\d{2}-\d{2}$', ws.title)],
                                reverse=True
                            )
                            resultado_h = None
                            for aba_h in abas_h:
                                df_h = load_data(aba_h)
                                if df_h.empty:
                                    continue
                                mask_mil  = df_h['id'].astype(str).str.strip() == mid_h
                                mask_serv = df_h['serviço'].astype(str).str.strip().str.lower() == serv_sel_h.lower()
                                mask_hor  = df_h['horário'].astype(str).str.strip() == hor_sel_h.strip() if hor_sel_h.strip() else pd.Series([True]*len(df_h), index=df_h.index)
                                linhas = df_h[mask_mil & mask_serv & mask_hor]
                                if not linhas.empty:
                                    row_h = linhas.iloc[0]
                                    try:
                                        ano_h = datetime.now().year
                                        dt_h  = datetime.strptime(f"{aba_h}-{ano_h}", "%d-%m-%Y")
                                        # Se data futura, tentar ano anterior
                                        if dt_h.date() > datetime.now().date():
                                            dt_h = datetime.strptime(f"{aba_h}-{ano_h-1}", "%d-%m-%Y")
                                        dia_sem_h = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"][dt_h.weekday()]
                                        data_fmt_h = f"{dt_h.strftime('%d/%m/%Y')} ({dia_sem_h})"
                                    except:
                                        data_fmt_h = aba_h
                                    resultado_h = {
                                        'data': data_fmt_h,
                                        'horario': str(row_h.get('horário', '')),
                                        'obs': str(row_h.get('observações', '') or ''),
                                    }
                                    break  # parar ao primeiro encontrado

                        if resultado_h:
                            nome_mil = mil_sel_h.split('--')[1].strip() if '--' in mil_sel_h else mil_sel_h
                            st.success(f"✅ Último serviço encontrado:")
                            st.markdown(f"""
                            | Campo | Valor |
                            |-------|-------|
                            | **Militar** | {nome_mil} |
                            | **Serviço** | {serv_sel_h} |
                            | **Data** | {resultado_h['data']} |
                            | **Horário** | {resultado_h['horario']} |
                            | **Observações** | {resultado_h['obs']} |
                            """)
                        else:
                            st.info(f"Nenhum registo encontrado para **{serv_sel_h}** com este militar.")

    # --- 🔄 SOLICITAR TROCA ---
    # --- 🔄 TROCAS ---
    elif menu == "🔄 Trocas":
        st.title("🔄 Trocas")
        tab_sol, tab_ped, tab_hist = st.tabs(["📨 Solicitar", "📥 Pedidos Recebidos", "📋 Histórico"])

        with tab_sol:
            st.title("🔄 Solicitar Troca de Serviço")

            tipo_troca = st.radio(
                "Tipo de pedido:",
                ["🔄 Troca Simples", "💶 Fazer Remunerado", "💶 Dar Remunerado", "📅 Mudar Folga"],
                horizontal=True
            )
            st.markdown("---")

            dt_s = st.date_input("Data:", format="DD/MM/YYYY")
            df_d = load_data(dt_s.strftime("%d-%m"))

            if df_d.empty:
                st.info("Não existem dados para esta data.")
            else:
                df_d = df_d.copy()
                df_ant = load_data((dt_s - timedelta(days=1)).strftime("%d-%m"))
                df_seg = load_data((dt_s + timedelta(days=1)).strftime("%d-%m"))
                df_ant = df_ant.copy() if not df_ant.empty else df_ant
                df_seg = df_seg.copy() if not df_seg.empty else df_seg

                # Aplicar trocas aprovadas a df_d, df_ant e df_seg
                def _aplicar_trocas_df(df_alvo, data_str):
                    if df_alvo.empty or df_trocas.empty:
                        return df_alvo
                    tr = df_trocas[
                        (df_trocas['data'] == data_str) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                    ]
                    mask_rem = df_alvo['serviço'].str.lower().str.contains('remu|grat', na=False)
                    for _, t in tr.iterrows():
                        id_o   = str(t['id_origem']).strip()
                        id_d2  = str(t['id_destino']).strip()
                        s_o    = t['servico_origem']; s_d2 = t['servico_destino']
                        serv_o  = s_o.rsplit('(', 1)[0].strip()
                        hor_o   = s_o.rsplit('(', 1)[1].rstrip(')') if '(' in s_o else ''
                        serv_d2 = s_d2.rsplit('(', 1)[0].strip()
                        hor_d2  = s_d2.rsplit('(', 1)[1].rstrip(')') if '(' in s_d2 else ''
                        m_o = (df_alvo['id'].astype(str).str.strip() == id_o) & ~mask_rem
                        if m_o.any():
                            df_alvo.loc[m_o, 'serviço'] = serv_d2
                            if hor_d2: df_alvo.loc[m_o, 'horário'] = hor_d2
                        m_d = (df_alvo['id'].astype(str).str.strip() == id_d2) & ~mask_rem
                        if m_d.any():
                            df_alvo.loc[m_d, 'serviço'] = serv_o
                            if hor_o: df_alvo.loc[m_d, 'horário'] = hor_o
                    return df_alvo

                servico_override = None
                if not df_trocas.empty:
                    data_str_d   = dt_s.strftime('%d/%m/%Y')
                    data_str_ant = (dt_s - timedelta(days=1)).strftime('%d/%m/%Y')
                    data_str_seg = (dt_s + timedelta(days=1)).strftime('%d/%m/%Y')
                    df_d   = _aplicar_trocas_df(df_d,   data_str_d)
                    df_ant = _aplicar_trocas_df(df_ant, data_str_ant)
                    df_seg = _aplicar_trocas_df(df_seg, data_str_seg)
                    # Registar override do próprio utilizador
                    tr_dia = df_trocas[
                        (df_trocas['data'] == data_str_d) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
                    ]
                    for _, t in tr_dia.iterrows():
                        if str(t['id_origem']).strip() == u_id.strip():
                            servico_override = t['servico_destino']
                        elif str(t['id_destino']).strip() == u_id.strip():
                            servico_override = t['servico_origem']

                meu = df_d[df_d['id'].astype(str) == u_id]

                # IDs que já têm troca pendente nesse dia -- excluir das listas
                ids_com_troca = set()
                if not df_trocas.empty:
                    tr_ocupados = df_trocas[
                        (df_trocas['data'] == dt_s.strftime('%d/%m/%Y')) &
                        (df_trocas['status'].isin(['Pendente_Militar', 'Pendente_Admin']))
                    ]
                    ids_com_troca = set(tr_ocupados['id_origem'].astype(str).tolist() +
                                        tr_ocupados['id_destino'].astype(str).tolist())
                    ids_com_troca.discard(u_id)  # não excluir o próprio

                # IDs a excluir só do fazer remunerado (cedentes aprovados)
                ids_sem_remunerado = set()
                if not df_trocas.empty:
                    rem_apr = df_trocas[
                        (df_trocas['data'] == dt_s.strftime('%d/%m/%Y')) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] == 'MATAR_REMUNERADO')
                    ]
                    ids_sem_remunerado.update(rem_apr['id_destino'].astype(str).tolist())

                # Função auxiliar -- remunerado não cedido é impedimento
                def _tem_rem_nao_cedido(mid):
                    mid = str(mid).strip()
                    rows_rem = df_d[(df_d['id'].astype(str).str.strip() == mid) &
                                    (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))]
                    if rows_rem.empty:
                        return False
                    if mid in ids_sem_remunerado:
                        return False
                    return True

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
                            (~df_d['id'].astype(str).str.strip().isin(ids_com_troca)) &
                            ~((df_d['serviço'] == meu_serv_orig) & (df_d['horário'] == meu_hor_orig)) &
                            ~(estou_de_folga & df_d['serviço'].str.lower().str.contains('folga', na=False))
                        )
                        # Folgas: disponíveis sempre (sem verificação de descanso)
                        mask_folga = df_d['serviço'].str.lower().str.contains('folga', na=False)
                        mask_imp   = df_d['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False)
                        # Remunerados que NÃO foram cedidos -- são impedimento
                        mask_rem_nao_cedido = df_d['id'].astype(str).apply(_tem_rem_nao_cedido)
                        # Debug
                        cols_folga = df_d[base_mask & mask_folga]
                        cols = df_d[base_mask & ~mask_folga & ~mask_imp & ~mask_rem_nao_cedido]
                        if cols.empty and cols_folga.empty:
                            st.warning("Não há militares disponíveis para troca neste dia.")
                        else:
                            meu_serv_nome = meu_s.rsplit('(', 1)[0].strip()
                            meu_hor_val   = meu_s.rsplit('(', 1)[1].rstrip(')') if '(' in meu_s else meu.iloc[0]['horário']
                            opts = []
                            # Folgas -- verificar só o descanso do militar de folga (destino)
                            for _, row_c in cols_folga.iterrows():
                                id_c   = str(row_c['id'])
                                serv_c = str(row_c['serviço'])
                                hor_c  = str(row_c['horário'])
                                erros_destino = verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg)
                                erros_dest_only = [e for e in erros_destino if e.startswith("O militar de destino")]
                                if not erros_dest_only:
                                    nome_c = get_nome_curto(df_util, id_c)
                                    opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")
                            # Restantes -- com verificação de descanso
                            for _, row_c in cols.iterrows():
                                id_c   = str(row_c['id'])
                                serv_c = str(row_c['serviço'])
                                hor_c  = str(row_c['horário'])
                                if not verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg):
                                    nome_c = get_nome_curto(df_util, id_c)
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

                # ── Dar Remunerado ──
                elif tipo_troca == "💶 Dar Remunerado":
                    # Verificar se tenho remunerado escalado nesse dia
                    meu_rem = df_d[
                        (df_d['id'].astype(str).str.strip() == u_id) &
                        (df_d['serviço'].str.lower().str.contains('remu|grat', na=False))
                    ]
                    if meu_rem.empty:
                        st.warning("Não tens nenhum remunerado escalado nesse dia.")
                    else:
                        rem_row = meu_rem.iloc[0]
                        rem_serv = str(rem_row.get('serviço', '')).strip()
                        rem_hor  = str(rem_row.get('horário', '')).strip()
                        st.info(f"📋 O teu remunerado: **{rem_serv} ({rem_hor})**")

                        # Mostrar militares disponíveis para ceder
                        _imp_dar = r'ferias|licen|doente|baixa|dilig|tribunal|inquer|secretaria|pronto'
                        outros_dar = df_d[
                            (df_d['id'].astype(str).str.strip() != u_id) &
                            (df_d['id'].astype(str).str.strip() != '') &
                            (df_d['id'].astype(str).str.strip() != 'nan')
                        ]
                        outros_dar = outros_dar[~outros_dar['serviço'].str.lower().apply(norm).str.contains(_imp_dar, na=False)]
                        outros_dar = outros_dar[~outros_dar['id'].astype(str).apply(
                            lambda mid: militar_de_ferias(mid, dt_s, df_ferias, feriados)
                        )]
                        # Verificar sobreposição de horário
                        opts_dar = []
                        ini_rem, fim_rem = _parse_horario(rem_hor)
                        for _, r_dar in outros_dar.iterrows():
                            mid_dar = str(r_dar['id']).strip()
                            hor_dar = str(r_dar.get('horário', '')).strip()
                            if ini_rem is not None and hor_dar:
                                ini_d, fim_d = _parse_horario(hor_dar)
                                if ini_d is not None and not (fim_rem <= ini_d or ini_rem >= fim_d):
                                    continue  # sobreposição
                            nome_dar = get_nome_curto(df_util, mid_dar)
                            opts_dar.append(f"{mid_dar} {nome_dar} -- {r_dar['serviço']} ({hor_dar})")

                        if not opts_dar:
                            st.warning("Não há militares disponíveis para ceder o remunerado.")
                        else:
                            with st.form("dar_rem"):
                                st.info("Seleciona o militar a quem queres ceder o remunerado.")
                                dar_sel = st.selectbox("Militar:", opts_dar)
                                if st.form_submit_button("💶 CEDER REMUNERADO", use_container_width=True):
                                    id_dest_dar = dar_sel.split(" ")[0]
                                    serv_completo = f"{rem_serv} ({rem_hor})"
                                    if salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), id_dest_dar, "MATAR_REMUNERADO", u_id, serv_completo, "Pendente_Militar", ""]):
                                        st.success("✅ Pedido enviado! Aguarda aceitação do militar.")

                # ── Fazer Remunerado ──
                elif tipo_troca == "💶 Fazer Remunerado":
                    _imp_rem = r'ferias|licen|doente|dilig|tribunal|pronto|secretaria|inquer'
                    _motivo_imp = ''
                    if not meu.empty and re.search(_imp_rem, norm(meu.iloc[0]['serviço'])):
                        _motivo_imp = meu.iloc[0]['serviço']
                    elif militar_de_ferias(u_id, dt_s, df_ferias, feriados):
                        _motivo_imp = 'Férias'
                    if _motivo_imp:
                        st.warning(f"Não podes fazer remunerados -- estás com **{_motivo_imp}**.")
                    else:
                        rem_dia = df_d[
                            (df_d['id'].astype(str).str.strip() != u_id) &
                            (df_d['id'].astype(str).str.strip() != '') &
                            (df_d['id'].astype(str).str.strip() != 'nan') &
                            (~df_d['id'].astype(str).str.strip().isin(ids_com_troca)) &
                            (~df_d['id'].astype(str).str.strip().isin(ids_sem_remunerado)) &
                            (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))
                        ]
                        if rem_dia.empty:
                            st.info("Não há serviços remunerados escalados neste dia.")
                        else:
                            # Verificar sobreposição -- usar horário real após trocas aprovadas
                            meu_ini, meu_fim = (None, None)
                            meu_hor_real = None
                            if servico_override and '(' in servico_override:
                                meu_hor_real = servico_override.rsplit('(', 1)[1].rstrip(')')
                            elif not meu.empty and meu.iloc[0]['horário']:
                                meu_hor_real = meu.iloc[0]['horário']
                            if meu_hor_real:
                                meu_ini, meu_fim = _parse_horario(meu_hor_real)

                            opts_rem = []
                            for _, r in rem_dia.iterrows():
                                hor_rem = str(r['horário']).strip()
                                if meu_ini is not None and hor_rem:
                                    ini_r, fim_r = _parse_horario(hor_rem)
                                    if ini_r is not None:
                                        if not (fim_r <= meu_ini or ini_r >= meu_fim):
                                            continue
                                nome_r = get_nome_curto(df_util, str(r["id"]))
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

                # ── Troca de Folga ──
                elif tipo_troca == "📅 Mudar Folga":
                    ano_tf = datetime.now().year
                    df_folgas_tf = load_folgas(ano_tf)
                    grupos_tf    = load_grupos_folga()

                    # Calcular os meus dias de folga (próximos 60 dias)
                    meus_dias_folga = []
                    for i_tf in range(60):
                        dt_tf = datetime.now().date() + timedelta(days=i_tf)
                        tipo_tf = militar_de_folga(u_id, dt_tf, df_folgas_tf, grupos_tf, feriados)
                        if tipo_tf:
                            meus_dias_folga.append((dt_tf, tipo_tf))

                    if not meus_dias_folga:
                        st.warning("Não tens dias de folga nos próximos 60 dias.")
                    else:
                        opts_meus = {f"{d.strftime('%d/%m/%Y')} -- {t}": (d, t) for d, t in meus_dias_folga}
                        meu_dia_sel = st.selectbox("Folga que queres mudar:", list(opts_meus.keys()), key="tf_meu_dia")
                        meu_dia_tf, meu_tipo_tf = opts_meus[meu_dia_sel]

                        # Escolher qualquer dia que não seja dia de folga
                        novo_dia_tf = st.date_input("Novo dia de folga:", format="DD/MM/YYYY", key="tf_novo_dia",
                                                     value=meu_dia_tf + timedelta(days=1))

                        # Verificar que o novo dia não é já folga
                        tipo_novo = militar_de_folga(u_id, novo_dia_tf, df_folgas_tf, grupos_tf, feriados)
                        if tipo_novo:
                            st.warning(f"Já estás de {tipo_novo} nesse dia.")
                        else:
                            st.info(f"📋 Mover folga de **{meu_dia_tf.strftime('%d/%m/%Y')}** ({meu_tipo_tf}) para **{novo_dia_tf.strftime('%d/%m/%Y')}**")
                            if st.button("📅 SOLICITAR MUDANÇA DE FOLGA", use_container_width=True, key="btn_tf"):
                                serv_orig_tf = f"Folga {meu_dia_tf.strftime('%d/%m/%Y')} ({meu_tipo_tf})"
                                serv_dest_tf = f"Folga {novo_dia_tf.strftime('%d/%m/%Y')} ({meu_tipo_tf})"
                                if salvar_troca_gsheet([meu_dia_tf.strftime('%d/%m/%Y'), u_id, serv_orig_tf, u_id, serv_dest_tf, "Pendente_Admin", ""]):
                                    st.success("✅ Pedido enviado para validação!")

        # --- 📥 PEDIDOS RECEBIDOS ---
        with tab_ped:
            st.title("📥 Pedidos de Troca Recebidos")

            # Processar ação pendente ANTES de renderizar
            acao_ped = st.session_state.pop('pedido_acao', None)
            if acao_ped:
                atualizar_status_gsheet(acao_ped['idx'], acao_ped['status'])
                invalidar_trocas()
                st.rerun()

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
                            st.session_state['pedido_acao'] = {'idx': idx, 'status': 'Pendente_Admin'}
                            st.rerun()
                        if c2.button("❌ RECUSAR", key=f"re_{idx}", use_container_width=True):
                            st.session_state['pedido_acao'] = {'idx': idx, 'status': 'Recusada'}
                            st.rerun()

        # --- ⚖️ VALIDAR TROCAS (ADMIN) ---
    # --- 📋 HISTÓRICO DE TROCAS DO PRÓPRIO ---
        with tab_hist:
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
                            titulo = f"{cor} {r['data']} -- Fazer Remunerado: {outro_serv} ({status})"
                        else:
                            papel = "Requerente" if fui_origem else "Substituto"
                            titulo = f"{cor} {r['data']} -- {meu_serv} ↔ {outro_serv} ({status})"

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
                                        invalidar_trocas()
                                        st.success("Pedido cancelado.")
                                        st.rerun()

    elif menu == "⚖️ Validar Trocas":
        st.title("⚖️ Validação Superior de Trocas")

        # Processar ação pendente ANTES de renderizar os botões
        acao_val = st.session_state.pop('validar_acao', None)
        if acao_val:
            atualizar_status_gsheet(acao_val['idx'], acao_val['status'], u_nome)
            invalidar_trocas()
            st.rerun()

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
                    is_matar_v = str(r['servico_origem']) == 'MATAR_REMUNERADO'
                    titulo = f"📅 {r['data']}  |  💶 {n_o} faz remunerado de {n_d}" if is_matar_v else f"📅 {r['data']}  |  {n_o} ↔️ {n_d}"
                    with st.expander(titulo, expanded=True):
                        col1, col2 = st.columns(2)
                        if is_matar_v:
                            with col1:
                                st.info(f"**Requerente:**\n\n{n_o}")
                            with col2:
                                st.success(f"**Cedente:**\n\n{n_d}\n\n`{r['servico_destino']}`")
                        else:
                            with col1:
                                st.info(f"**{n_o}**\n\n`{r['servico_origem']}`")
                            with col2:
                                st.success(f"**{n_d}**\n\n`{r['servico_destino']}`")
                        c1, c2 = st.columns(2)
                        if c1.button("✔️ VALIDAR",  key=f"ok_{idx}", use_container_width=True):
                            st.session_state['validar_acao'] = {'idx': idx, 'status': 'Aprovada'}
                            st.rerun()
                        if c2.button("🚫 REJEITAR", key=f"no_{idx}", use_container_width=True):
                            st.session_state['validar_acao'] = {'idx': idx, 'status': 'Rejeitada'}
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
                                st.markdown("**Ação:** Fazer Remunerado")
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
                        else:
                            dados_pdf_rem = {
                                "data":            r['data'],
                                "id_requerente":   r['id_origem'],  "nome_requerente": n_o,
                                "id_cedente":      r['id_destino'], "nome_cedente":    n_d,
                                "remunerado":      r['servico_destino'],
                                "validador":       val_por,         "data_val":        val_em,
                            }
                            st.download_button(
                                label="📥 Descarregar Comprovativo",
                                data=gerar_pdf_fazer_remunerado(dados_pdf_rem),
                                file_name=f"Remunerado_{r['data'].replace('/','-')}.pdf",
                                mime="application/pdf",
                                key=f"rem_pdf_{idx}"
                            )

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

        hoje_a = datetime.now()
        alertas_trocas     = []
        alertas_duplos     = []
        alertas_descanso   = []
        alertas_esquecidos = []

        ids_ativos = set(df_util['id'].astype(str).str.strip().tolist()) if not df_util.empty else set()

        # Pré-calcular IDs de férias a partir do df_ferias (sem chamar militar_de_ferias por dia)
        def _ids_de_ferias_no_dia(dt):
            """Devolve set de IDs em férias numa data, sem iterar por militar."""
            em_ferias = set()
            if df_ferias.empty:
                return em_ferias
            cols = df_ferias.columns.tolist()
            ini_cols = [c for c in cols if 'ini' in c.lower()]
            fim_cols  = [c for c in cols if 'fim' in c.lower()]
            id_col = 'id' if 'id' in cols else cols[0]
            data = dt.date() if hasattr(dt, 'date') else dt
            for _, row in df_ferias.iterrows():
                mid = str(row.get(id_col, '')).strip()
                if not mid or mid == 'nan':
                    continue
                for ini_c, fim_c in zip(ini_cols, fim_cols):
                    ini_s = str(row.get(ini_c, '')).strip()
                    fim_s = str(row.get(fim_c, '')).strip()
                    if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan':
                        continue
                    ini_d = _parse_data_ferias(ini_s, data.year)
                    fim_d = _parse_data_ferias(fim_s, data.year)
                    if not ini_d or not fim_d:
                        continue
                    fim_real = _fim_ferias_real(fim_d, feriados)
                    if ini_d <= data <= fim_real:
                        em_ferias.add(mid)
                        break
            return em_ferias

        with st.spinner("A verificar escalas..."):
            dias_sem = 0
            j = 0
            df_ant_cache = {}

            while dias_sem < 3 and j < 20:
                dt_a = hoje_a + timedelta(days=j)
                aba_a = dt_a.strftime('%d-%m')
                df_a = load_data(aba_a)
                j += 1
                if df_a.empty:
                    dias_sem += 1
                    continue
                dias_sem = 0
                d_s_a = dt_a.strftime('%d/%m/%Y')

                # ── Alerta 2: Militar em 2 serviços ──
                df_a_serv = df_a[~df_a['serviço'].apply(norm).str.contains('remu|grat', na=False)]
                contagem = df_a_serv[df_a_serv['id'].astype(str).str.strip() != ''].groupby('id').size()
                for mid, count in contagem.items():
                    if count > 1:
                        n = get_nome_militar(df_util, mid)
                        servs = df_a_serv[df_a_serv['id'].astype(str) == str(mid)][['serviço','horário']].values.tolist()
                        alertas_duplos.append(f"**{d_s_a}** -- {n}: {' / '.join([f'{s} ({h})' for s,h in servs])}")

                # ── Alerta 3: Menos de 8h descanso ──
                aba_ant = (dt_a - timedelta(days=1)).strftime('%d-%m')
                if aba_ant not in df_ant_cache:
                    df_ant_cache[aba_ant] = load_data(aba_ant)
                df_ant_a = df_ant_cache[aba_ant]
                if not df_ant_a.empty:
                    df_ant_serv = df_ant_a[~df_ant_a['serviço'].apply(norm).str.contains('remu|grat|folga|ferias|licen|doente', na=False)]
                    ids_hoje = set(df_a_serv[df_a_serv['id'].astype(str).str.strip() != '']['id'].astype(str))
                    ids_ant  = set(df_ant_serv[df_ant_serv['id'].astype(str).str.strip() != '']['id'].astype(str))
                    for mid in ids_hoje & ids_ant:  # só militares em ambos os dias
                        rows_h = df_a_serv[df_a_serv['id'].astype(str) == mid]
                        rows_a = df_ant_serv[df_ant_serv['id'].astype(str) == mid]
                        for _, rh in rows_h.iterrows():
                            ini_h, _ = _parse_horario(rh['horário'])
                            if ini_h is None or _e_atendimento(rh['serviço']): continue
                            for _, ra in rows_a.iterrows():
                                _, fim_a = _parse_horario(ra['horário'])
                                if fim_a is None or _e_atendimento(ra['serviço']): continue
                                descanso = (ini_h + 1440) - fim_a
                                if 0 <= descanso < 480:
                                    n = get_nome_militar(df_util, mid)
                                    h2, m2 = descanso//60, descanso%60
                                    alertas_descanso.append(f"**{d_s_a}** -- {n}: {h2}h{m2:02d}m entre `{ra['serviço']} ({ra['horário']})` e `{rh['serviço']} ({rh['horário']})`")

                # ── Alerta 4: Não escalado ──
                ids_na_escala = set(df_a[df_a['id'].astype(str).str.strip() != '']['id'].astype(str).str.strip())
                em_ferias_hoje = _ids_de_ferias_no_dia(dt_a)
                for mid in sorted(ids_ativos - ids_na_escala - em_ferias_hoje):
                    n = get_nome_militar(df_util, mid)
                    alertas_esquecidos.append(f"**{d_s_a}** -- {n} ({mid})")
        with st.expander(f"👥 Militar escalado 2x ({len(alertas_duplos)})", expanded=len(alertas_duplos) > 0):
            if alertas_duplos:
                for a in alertas_duplos: st.warning(a)
            else:
                st.success("✅ Sem alertas")

        with st.expander(f"😴 Menos de 8h descanso ({len(alertas_descanso)})", expanded=len(alertas_descanso) > 0):
            if alertas_descanso:
                for a in alertas_descanso: st.warning(a)
            else:
                st.success("✅ Sem alertas")

        with st.expander(f"🔍 Não escalados ({len(alertas_esquecidos)})", expanded=len(alertas_esquecidos) > 0):
            if alertas_esquecidos:
                for a in alertas_esquecidos: st.warning(a)
            else:
                st.success("✅ Sem alertas")

        # --- ⚙️ GERAR ESCALA (ADMIN) ---
    elif menu == "⚙️ Gerar Escala":
        st.title("⚙️ Gerar Escala Automática")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()

        # ── Processar confirmação (executar antes dos widgets) ──
        if st.session_state.get('confirmar_escala', False) and 'escala_gerada_multi' in st.session_state:
            st.session_state['confirmar_escala'] = False
            dados_multi_c = st.session_state['escala_gerada_multi']
            resultados_c  = dados_multi_c['resultados']
            ordem_headers_c = dados_multi_c['ordem_headers']
            try:
                sh2 = get_sheet()
                from collections import defaultdict
                for idx_res, res in enumerate(resultados_c):
                    # Pausa entre dias para evitar quota
                    if idx_res > 0:
                        import time as _time
                        _time.sleep(8)
                    aba_r = res['aba']
                    escalados_r = res['escalados']
                    ordem_r = res['ordem_atualizada']
                    data_r = res['data']

                    # Retry em caso de quota
                    for _t in range(3):
                        try:
                            ws_dia_r = sh2.worksheet(aba_r)
                            break
                        except Exception as _e:
                            if _t < 2:
                                import time as _time2; _time2.sleep(20)
                            else:
                                raise _e
                    todas_linhas_r = ws_dia_r.get_all_values()
                    hdrs_r = [h.strip().lower() for h in todas_linhas_r[0]]
                    ix_id_r   = hdrs_r.index('id')      if 'id'      in hdrs_r else 0
                    ix_serv_r = hdrs_r.index('serviço') if 'serviço' in hdrs_r else 1
                    ix_hor_r  = hdrs_r.index('horário') if 'horário' in hdrs_r else 2

                    agrupados_r = defaultdict(list)
                    simples_r = []
                    for mid, serv, hor in escalados_r:
                        if serv == "Patrulha Ocorrências":
                            agrupados_r[(serv, hor)].append(mid)
                        else:
                            simples_r.append((mid, serv, hor))
                    emap_r = {}
                    for (serv, hor), ids in agrupados_r.items():
                        emap_r[(norm(serv), hor.strip())] = ';'.join(ids)
                    for mid, serv, hor in simples_r:
                        emap_r[(norm(serv), hor.strip())] = mid

                    upds_r = []
                    for i, row in enumerate(todas_linhas_r[1:], start=2):
                        sc = norm(row[ix_serv_r].strip()) if ix_serv_r < len(row) else ''
                        hc = str(row[ix_hor_r]).strip()  if ix_hor_r < len(row) else ''
                        ic = str(row[ix_id_r]).strip()   if ix_id_r  < len(row) else ''
                        ch = (sc, hc)
                        if ch in emap_r and not ic:
                            cl = chr(ord('A') + ix_id_r)
                            upds_r.append({'range': f'{cl}{i}', 'values': [[emap_r[ch]]]})
                            del emap_r[ch]
                    if upds_r:
                        ws_dia_r.batch_update(upds_r)

                    # Escrever disponíveis na linha "Disponíveis" da aba
                    disp_r = res.get('disponiveis', [])
                    if disp_r:
                        ids_disp_str = ';'.join(disp_r)
                        for i, row in enumerate(todas_linhas_r[1:], start=2):
                            sc_d = norm(row[ix_serv_r].strip()) if ix_serv_r < len(row) else ''
                            ic_d = str(row[ix_id_r]).strip() if ix_id_r < len(row) else ''
                            if sc_d == norm('Disponíveis') or sc_d == norm('Disponiveis'):
                                cl_d = chr(ord('A') + ix_id_r)
                                ws_dia_r.update(f'{cl_d}{i}', [[ids_disp_str]])
                                break

                    # ── Atualizar ordem_escala do dia seguinte ──
                    # Sempre parte do ordem_escala do dia atual (que vem da geração)
                    # ignorando qualquer ordem_escala existente para o dia seguinte
                    nome_prox = f"ordem_escala {(data_r + timedelta(days=1)).strftime('%d-%m')}"
                    abas_existentes = [ws.title for ws in sh2.worksheets()]

                    _slots_map_r = {
                        (norm("Atendimento"),          "00-08"): "Atendimento 00-08",
                        (norm("Atendimento"),          "08-16"): "Atendimento 08-16",
                        (norm("Atendimento"),          "16-24"): "Atendimento 16-24",
                        (norm("Patrulha Ocorrências"), "00-08"): "Patrulha Ocorrências 00-08",
                        (norm("Patrulha Ocorrências"), "08-16"): "Patrulha Ocorrências 08-16",
                        (norm("Patrulha Ocorrências"), "16-24"): "Patrulha Ocorrências 16-24",
                        (norm("Apoio Atendimento"),    "08-16"): "Apoio Atendimento 08-16",
                        (norm("Apoio Atendimento"),    "16-24"): "Apoio Atendimento 16-24",
                    }

                    # Usar ordem_r que já vem do dia anterior com os escalados movidos
                    ordem_base = {h: list(v) for h, v in ordem_r.items()}
                    hdrs_prox  = ordem_headers_c

                    # Mover militares escalados automaticamente para o fim
                    ids_auto_r = set(m for m, _, _ in escalados_r)
                    for col_key_p, lista_p in ordem_base.items():
                        for mid_p in list(ids_auto_r):
                            if mid_p in lista_p:
                                lista_p.remove(mid_p)
                                lista_p.append(mid_p)

                    # Mover militares manuais para o fim também
                    for row_m in todas_linhas_r[1:]:
                        serv_m = norm(row_m[ix_serv_r].strip()) if ix_serv_r < len(row_m) else ''
                        hor_m  = str(row_m[ix_hor_r]).strip()   if ix_hor_r  < len(row_m) else ''
                        id_m   = str(row_m[ix_id_r]).strip()    if ix_id_r   < len(row_m) else ''
                        if not id_m or id_m == 'nan':
                            continue
                        col_key_m = _slots_map_r.get((serv_m, hor_m))
                        if not col_key_m or col_key_m not in ordem_base:
                            continue
                        for mid_m in re.split(r'[;,]', id_m):
                            mid_m = mid_m.strip()
                            if not mid_m or mid_m in ids_auto_r:
                                continue
                            if mid_m in ordem_base[col_key_m]:
                                ordem_base[col_key_m].remove(mid_m)
                                ordem_base[col_key_m].append(mid_m)

                    # Escrever ordem -- substituir sempre
                    nova_o_r = [hdrs_prox]
                    ml_r = max((len(v) for v in ordem_base.values()), default=1)
                    for i in range(ml_r):
                        nova_o_r.append([ordem_base[h][i] if i < len(ordem_base[h]) else '' for h in hdrs_prox])

                    if nome_prox in abas_existentes:
                        ws_prox_exist = sh2.worksheet(nome_prox)
                        ws_prox_exist.clear()
                        ws_prox_exist.update('A1', nova_o_r)
                        ws_prox_exist.hide()
                    else:
                        ws_prox = sh2.add_worksheet(title=nome_prox, rows=100, cols=len(hdrs_prox))
                        ws_prox.update('A1', nova_o_r)
                        ws_prox.hide()

                load_data.clear()
                del st.session_state['escala_gerada_multi']
                st.session_state['escala_ok'] = True
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao escrever: {e}")

        # ── Selecionar data(s) ──
        tab_auto, tab_editar, tab_rem = st.tabs(["⚙️ Escala Automática", "✏️ Editar Escala", "💶 Nomear para Remunerado"])

        with tab_auto:
            d_gerar = st.date_input("Data a escalar:", format="DD/MM/YYYY", key="d_gerar_input")
            aba_dia = d_gerar.strftime("%d-%m")

            # ── Carregar serviços por militar ──
            militares_servicos = load_servicos()
            serv_headers = list(set(s for servs in militares_servicos.values() for s in servs))
            todos_servicos = [''] + sorted(set(serv_headers))

            # ── Botão para carregar/resetar tabela ──
            if st.button("📋 Carregar tabela do dia", key="btn_carregar_tabela", use_container_width=True):
                sh_tab = get_sheet()
                # Criar aba do dia se não existir, copiando estrutura de outra aba
                abas_existentes_tab = [ws.title for ws in sh_tab.worksheets()]
                if aba_dia not in abas_existentes_tab:
                    # Encontrar aba modelo (outro dia)
                    aba_modelo = None
                    for ws_t in sh_tab.worksheets():
                        if re.match(r'^\d{2}-\d{2}$', ws_t.title):
                            aba_modelo = ws_t
                            break
                    if aba_modelo:
                        # Copiar só os cabeçalhos
                        hdrs_modelo = aba_modelo.row_values(1)
                        ws_nova = sh_tab.add_worksheet(title=aba_dia, rows=200, cols=len(hdrs_modelo))
                        ws_nova.update('A1', [hdrs_modelo])
                    else:
                        # Criar com cabeçalhos padrão
                        hdrs_pad = ['id','serviço','horário','indicativo rádio','rádio','viatura','giro','observações']
                        ws_nova = sh_tab.add_worksheet(title=aba_dia, rows=200, cols=len(hdrs_pad))
                        ws_nova.update('A1', [hdrs_pad])

                # Ler aba do dia diretamente para apanhar IDs múltiplos
                mapa_existente = {}
                try:
                    ws_dia_tab = sh_tab.worksheet(aba_dia)
                    vals_tab = ws_dia_tab.get_all_values()
                    if vals_tab and len(vals_tab) > 1:
                        hdrs_tab = [h.strip().lower() for h in vals_tab[0]]
                        ix_id_t  = hdrs_tab.index('id')      if 'id'      in hdrs_tab else 0
                        ix_sv_t  = hdrs_tab.index('serviço') if 'serviço' in hdrs_tab else 1
                        ix_hr_t  = hdrs_tab.index('horário') if 'horário' in hdrs_tab else 2
                        ix_in_t  = hdrs_tab.index('indicativo rádio') if 'indicativo rádio' in hdrs_tab else (hdrs_tab.index('indicativo') if 'indicativo' in hdrs_tab else None)
                        ix_ra_t  = hdrs_tab.index('rádio') if 'rádio' in hdrs_tab else None
                        ix_gi_t  = hdrs_tab.index('giro') if 'giro' in hdrs_tab else None
                        ix_ob_t  = hdrs_tab.index('observações') if 'observações' in hdrs_tab else None
                        ix_vt_t  = hdrs_tab.index('viatura') if 'viatura' in hdrs_tab else None
                        def _gt(row, ix):
                            return str(row[ix]).strip().replace('nan','') if ix is not None and ix < len(row) else ''
                        for row_t in vals_tab[1:]:
                            id_raw = _gt(row_t, ix_id_t)
                            if not id_raw: continue
                            dados_t = {
                                'serviço':    _gt(row_t, ix_sv_t),
                                'horário':    _gt(row_t, ix_hr_t),
                                'indicativo': _gt(row_t, ix_in_t),
                                'rádio':      _gt(row_t, ix_ra_t),
                                'giro':       _gt(row_t, ix_gi_t),
                                'viatura':    _gt(row_t, ix_vt_t),
                                'observações':_gt(row_t, ix_ob_t),
                            }
                            for mid in re.split(r'[;,\n]+', id_raw):
                                mid = mid.strip()
                                if mid:
                                    mapa_existente[mid] = dados_t
                except:
                    pass

                linhas = []
                for _, row_u in df_util.iterrows():
                    mid = str(row_u.get('id', '')).strip()
                    if not mid or mid == 'nan':
                        continue
                    nome  = str(row_u.get('nome', '')).strip()
                    posto = str(row_u.get('posto', '')).strip()
                    # Filtrar militares de férias (não mostrar na tabela)
                    if militar_de_ferias(mid, d_gerar, df_ferias, feriados):
                        continue
                    # Dados existentes, licenças, folgas, serviço por defeito ou vazio
                    if mid in mapa_existente:
                        dados = mapa_existente[mid]
                    else:
                        tipo_lic = militar_de_licenca(mid, d_gerar, df_licencas)
                        if tipo_lic:
                            dados = {'serviço': tipo_lic, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        else:
                            tipo_folga = militar_de_folga(mid, d_gerar, df_folgas, grupos_folga, feriados)
                            if tipo_folga:
                                dados = {'serviço': tipo_folga, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                            else:
                                # Serviço por defeito da coluna 'serviço' em folgas_2026
                                serv_defeito = ''
                                if not df_folgas.empty and 'serviço' in df_folgas.columns:
                                    col_id_f = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
                                    linha_f = df_folgas[df_folgas[col_id_f].astype(str).str.strip() == mid]
                                    if not linha_f.empty:
                                        sv_f = str(linha_f.iloc[0].get('serviço', '')).strip()
                                        if sv_f and sv_f != 'nan': serv_defeito = sv_f
                                dados = {'serviço': serv_defeito, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}

                    linhas.append({
                        'id': mid,
                        'nome': f"{posto} {nome}".strip(),
                        'serviço':     dados['serviço'],
                        'horário':     dados['horário'],
                        'indicativo':  dados['indicativo'],
                        'rádio':       dados['rádio'],
                        'giro':        dados['giro'],
                        'observações': dados['observações'],
                    })

                st.session_state['tabela_escala'] = linhas
                st.session_state['tabela_dia'] = aba_dia
                st.rerun()

            # ── Mostrar tabela editável ──
            if 'tabela_escala' in st.session_state and st.session_state.get('tabela_dia') == aba_dia:
                linhas = st.session_state['tabela_escala']

                st.markdown(f"**{len(linhas)} militares -- {d_gerar.strftime('%d/%m/%Y')}**")
                st.caption("Preenche os serviços, gera a escala automática e edita conforme necessário.")

                # Filtro de pesquisa
                pesq = st.text_input("🔍 Pesquisar por ID ou nome:", placeholder="ex: 507 ou Silva", key="pesq_tabela", label_visibility="collapsed")

                # Construir df editável
                df_edit = pd.DataFrame(linhas)

                # Carregar listas para dropdowns
                _listas_auto = load_listas()
                _hor_auto = _listas_auto.get('Horário', ['', '00-08', '08-16', '16-24'])
                _ind_auto = _listas_auto.get('Indicativo', [''])
                _rad_auto = _listas_auto.get('Rádio', [''])
                _vtr_auto = _listas_auto.get('Viatura', [''])
                _gir_auto = _listas_auto.get('Giro', [''])
                if len(_hor_auto) <= 1: _hor_auto = ['', '00-08', '08-16', '16-24']

                # Mapeamento de abreviaturas para o gerar escala
                _abrev = {
                    'Atendimento 00-08':          'A1', 'Atendimento 08-16':          'A2', 'Atendimento 16-24':          'A3',
                    'Patrulha Ocorrências 00-08':  'PO1','Patrulha Ocorrências 08-16':  'PO2','Patrulha Ocorrências 16-24':  'PO3',
                    'Apoio Atendimento 08-16':     'AA2','Apoio Atendimento 16-24':     'AA3',
                }

                # Opções de serviço -- abreviaturas + extras das listas
                _extras_listas = [s for s in (_listas_auto.get('Serviço', []) or [])
                                  if s and s not in ('','Atendimento','Patrulha Ocorrências','Apoio Atendimento')]
                _sv_opts_abrev = ['', 'A1','A2','A3','PO1','PO2','PO3','AA2','AA3'] + _extras_listas

                # Aplicar abreviaturas no df_edit para display
                # Mapeamento normalizado para converter serviço+horário → abreviatura
                _abrev_norm = {f"{norm(k.rsplit(' ',1)[0])} {k.rsplit(' ',1)[1]}": v for k, v in _abrev.items()}
                def _to_abrev(serv, hor):
                    chave_norm = f"{norm(serv)} {hor}".strip()
                    return _abrev_norm.get(chave_norm, serv)
                df_edit_abrev = df_edit.copy()
                df_edit_abrev['serviço'] = df_edit.apply(lambda r: _to_abrev(str(r['serviço']).strip(), str(r['horário']).strip()), axis=1)
                # Não limpar horário — fica visível para edição

                if pesq.strip():
                    mask_pesq = (
                        df_edit_abrev['id'].astype(str).str.contains(pesq.strip(), case=False, na=False) |
                        df_edit_abrev['nome'].astype(str).str.contains(pesq.strip(), case=False, na=False)
                    )
                    df_edit_show = df_edit_abrev[mask_pesq].copy()
                else:
                    df_edit_show = df_edit_abrev.copy()

                # Serviços disponíveis por militar para dropdown
                opcoes_servico = {}
                for row in df_edit.itertuples():
                    mid = str(row.id)
                    servs_mil = militares_servicos.get(mid, [])
                    opcoes_servico[mid] = [''] + servs_mil

                # Usar st.data_editor
                df_editado_show = st.data_editor(
                    df_edit_show,
                    column_config={
                        'id':          st.column_config.TextColumn('ID', disabled=True, width='small'),
                        'nome':        st.column_config.TextColumn('Nome', disabled=True, width='medium'),
                        'serviço':     st.column_config.SelectboxColumn('Serviço', options=_sv_opts_abrev, width='small'),
                        'horário':     st.column_config.SelectboxColumn('Horário', options=_hor_auto, width='small'),
                        'indicativo':  st.column_config.SelectboxColumn('Indicativo', options=_ind_auto, width='small'),
                        'rádio':       st.column_config.SelectboxColumn('Rádio', options=_rad_auto, width='small'),
                        'giro':        st.column_config.SelectboxColumn('Giro', options=_gir_auto, width='small'),
                        'viatura':     st.column_config.SelectboxColumn('Viatura', options=_vtr_auto, width='small'),
                        'observações': st.column_config.TextColumn('Observações', width='large'),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_escala",
                    num_rows="fixed",
                )
                # Converter abreviaturas de volta e construir df_editado completo
                _abrev_hor = {
                    'A1': ('Atendimento', '00-08'), 'A2': ('Atendimento', '08-16'), 'A3': ('Atendimento', '16-24'),
                    'PO1': ('Patrulha Ocorrências', '00-08'), 'PO2': ('Patrulha Ocorrências', '08-16'), 'PO3': ('Patrulha Ocorrências', '16-24'),
                    'AA2': ('Apoio Atendimento', '08-16'), 'AA3': ('Apoio Atendimento', '16-24'),
                }
                # Partir do df_edit original (com serviços por extenso e horários)
                df_editado = df_edit.copy()
                # Aplicar edições do data_editor
                for _, row_ed in df_editado_show.iterrows():
                    mid_ed = str(row_ed['id']).strip()
                    idx_ed = df_editado[df_editado['id'].astype(str).str.strip() == mid_ed].index
                    if len(idx_ed) == 0:
                        continue
                    i = idx_ed[0]
                    sv_ed  = str(row_ed.get('serviço', '')).strip()
                    hor_ed = str(row_ed.get('horário', '')).strip()
                    # Converter abreviatura
                    if sv_ed in _abrev_hor:
                        serv_real, hor_real = _abrev_hor[sv_ed]
                        df_editado.at[i, 'serviço'] = serv_real
                        if not hor_ed or hor_ed == 'nan':
                            df_editado.at[i, 'horário'] = hor_real
                        else:
                            df_editado.at[i, 'horário'] = hor_ed
                    else:
                        df_editado.at[i, 'serviço'] = sv_ed
                        df_editado.at[i, 'horário'] = hor_ed
                    # Restantes campos
                    for col_ed in ['indicativo', 'rádio', 'giro', 'viatura', 'observações']:
                        if col_ed in row_ed.index:
                            df_editado.at[i, col_ed] = row_ed[col_ed]

                col_g1, col_g2, col_g3 = st.columns(3)

                # ── Botão Limpar ──
                with col_g3:
                    if st.button("🗑️ Limpar escala", use_container_width=True, key="btn_limpar_escala"):
                        linhas_atuais = st.session_state.get('tabela_escala', [])
                        _serv_manter = {'férias', 'folga semanal', 'folga complementar'}
                        linhas_limpas = []
                        for row_l in linhas_atuais:
                            sv_l = str(row_l.get('serviço', '')).strip().lower()
                            mid_l = str(row_l.get('id', '')).strip()
                            if sv_l in _serv_manter:
                                # já tem folga/férias -- manter
                                linhas_limpas.append(row_l)
                            else:
                                # Recalcular folga para este militar
                                tipo_folga_l = militar_de_folga(mid_l, d_gerar, df_folgas, grupos_folga, feriados)
                                if tipo_folga_l:
                                    linhas_limpas.append({**row_l, 'serviço': tipo_folga_l, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''})
                                else:
                                    linhas_limpas.append({**row_l, 'serviço': '', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''})
                        st.session_state['tabela_escala'] = linhas_limpas
                        st.session_state.pop('ordem_gerada', None)
                        st.rerun()

                # ── Botão Gerar Escala Automática ──
                with col_g1:
                    if st.button("⚙️ Gerar escala automática", use_container_width=True, key="btn_gerar_auto"):
                        with st.spinner("A gerar..."):
                            try:
                                sh_g = get_sheet()

                                # Aplicar horários das abreviaturas no df_editado ANTES de calcular slots
                                _abrev_hor = {
                                    'A1': ('Atendimento', '00-08'),
                                    'A2': ('Atendimento', '08-16'),
                                    'A3': ('Atendimento', '16-24'),
                                    'PO1': ('Patrulha Ocorrências', '00-08'),
                                    'PO2': ('Patrulha Ocorrências', '08-16'),
                                    'PO3': ('Patrulha Ocorrências', '16-24'),
                                    'AA2': ('Apoio Atendimento', '08-16'),
                                    'AA3': ('Apoio Atendimento', '16-24'),
                                }
                                for idx_ab, row_ab in df_editado.iterrows():
                                    sv_ab = str(row_ab['serviço']).strip()
                                    hor_ab = str(row_ab['horário']).strip()
                                    if sv_ab in _abrev_hor:
                                        serv_real, hor_real = _abrev_hor[sv_ab]
                                        df_editado.at[idx_ab, 'serviço'] = serv_real
                                        if not hor_ab or hor_ab == 'nan':
                                            df_editado.at[idx_ab, 'horário'] = hor_real

                                # Indisponíveis = quem já tem serviço preenchido (após converter abreviaturas)
                                ids_indisponiveis = set()
                                for _, row_e in df_editado.iterrows():
                                    mid = str(row_e['id']).strip()
                                    serv = str(row_e['serviço']).strip()
                                    if serv and serv != 'nan':
                                        ids_indisponiveis.add(mid)

                                # Carregar ordem_escala
                                aba_ordem = f"ordem_escala {aba_dia}"
                                aba_ordem_ant = f"ordem_escala {(d_gerar - timedelta(days=1)).strftime('%d-%m')}"
                                try:
                                    ws_ordem_g = sh_g.worksheet(aba_ordem)
                                except:
                                    try:
                                        ws_ordem_g = sh_g.worksheet(aba_ordem_ant)
                                    except:
                                        # Listar abas disponíveis para debug
                                        abas_disp = [ws.title for ws in sh_g.worksheets()]
                                        abas_ord = [a for a in abas_disp if 'ordem' in a.lower()]
                                        st.error(f"Não encontrei ordem_escala. A procurar: '{aba_ordem}' ou '{aba_ordem_ant}'. Abas ordem disponíveis: {abas_ord}")
                                        st.stop()

                                ordem_vals_g = ws_ordem_g.get_all_values()
                                ordem_headers_g = [str(h).strip() for h in ordem_vals_g[0]]
                                ordem_g = {h: [] for h in ordem_headers_g}
                                for row_o in ordem_vals_g[1:]:
                                    for i, h in enumerate(ordem_headers_g):
                                        val = str(row_o[i]).strip() if i < len(row_o) else ''
                                        if val:
                                            ordem_g[h].append(val)

                                df_ant_g2 = load_data_direto(sh_g, (d_gerar - timedelta(days=1)).strftime("%d-%m"))

                                SLOTS = [
                                    ("Atendimento",         "00-08", 1),
                                    ("Atendimento",         "08-16", 1),
                                    ("Atendimento",         "16-24", 1),
                                    ("Patrulha Ocorrências","00-08", 2),
                                    ("Patrulha Ocorrências","08-16", 2),
                                    ("Patrulha Ocorrências","16-24", 2),
                                    ("Apoio Atendimento",   "08-16", 1),
                                    ("Apoio Atendimento",   "16-24", 1),
                                ]

                                # Contar quantos já estão manualmente preenchidos por slot
                                slots_preenchidos_g = {}
                                for _, row_e in df_editado.iterrows():
                                    sv_e = str(row_e['serviço']).strip()
                                    hr_e = str(row_e['horário']).strip()
                                    if sv_e and sv_e != 'nan' and hr_e and hr_e != 'nan':
                                        chave_s = (norm(sv_e), hr_e)
                                        slots_preenchidos_g[chave_s] = slots_preenchidos_g.get(chave_s, 0) + 1

                                SLOTS_AJUSTADOS = []
                                for sv_s, hr_s, num_s in SLOTS:
                                    ja = slots_preenchidos_g.get((norm(sv_s), hr_s), 0)
                                    vagas = max(0, num_s - ja)
                                    if vagas > 0:
                                        SLOTS_AJUSTADOS.append((sv_s, hr_s, vagas))

                                # Debug
                                st.info(f"🔍 Slots preenchidos: {slots_preenchidos_g}")
                                st.info(f"🔍 SLOTS_AJUSTADOS: {SLOTS_AJUSTADOS}")

                                ids_escalados_g = set()
                                novas_linhas = {str(row_e['id']): dict(row_e) for _, row_e in df_editado.iterrows()}

                                for servico, horario, num in SLOTS_AJUSTADOS:
                                    col_key = f"{servico} {horario}"
                                    if col_key not in ordem_g:
                                        if servico == "Atendimento" and horario == "00-08":
                                            st.warning(f"⚠️ A1: coluna '{col_key}' não existe. Colunas: {list(ordem_g.keys())}")
                                        continue
                                    colocados = []
                                    _debug_a1 = []
                                    for mid in ordem_g[col_key]:
                                        if len(colocados) >= num: break
                                        motivo = None
                                        if mid in ids_indisponiveis: motivo = 'indisponivel'
                                        elif mid in ids_escalados_g: motivo = 'ja_escalado'
                                        elif servico not in militares_servicos.get(mid, []): motivo = f'sem_servico:{militares_servicos.get(mid,[])}'
                                        else:
                                            if not df_ant_g2.empty:
                                                rows_ant = df_ant_g2[df_ant_g2['id'].astype(str).str.strip() == mid]
                                                ini_novo, _ = _parse_horario(horario)
                                                ok = True
                                                for _, r_ant in rows_ant.iterrows():
                                                    _, fim_ant = _parse_horario(str(r_ant.get('horário','')))
                                                    if fim_ant and ini_novo is not None:
                                                        if (1440 - fim_ant) + ini_novo < 480:
                                                            ok = False; break
                                                if not ok: motivo = 'descanso'
                                        if motivo:
                                            _debug_a1.append(f"{mid}:{motivo}")
                                        else:
                                            colocados.append(mid)
                                            ids_escalados_g.add(mid)
                                    if servico == "Atendimento" and horario == "00-08":
                                        st.info(f"🔍 A1 fila: {ordem_g[col_key][:8]} | colocados: {colocados} | saltados: {_debug_a1[:5]}")

                                    for mid in colocados:
                                        if mid not in novas_linhas:
                                            continue
                                        novas_linhas[mid]['serviço'] = servico
                                        novas_linhas[mid]['horário'] = horario
                                        if servico == 'Patrulha Ocorrências':
                                            novas_linhas[mid]['indicativo'] = '031.6A'
                                        # Rodar na ordem
                                        ordem_g[col_key].remove(mid)
                                        ordem_g[col_key].append(mid)

                                st.session_state['tabela_escala'] = list(novas_linhas.values())
                                st.session_state['ordem_gerada'] = ordem_g
                                st.session_state['ordem_headers_gerada'] = ordem_headers_g
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao gerar: {e}")

                # ── Botão Confirmar ──
                with col_g2:
                    if st.button("✅ CONFIRMAR E GUARDAR", use_container_width=True, type="primary", key="btn_confirmar_tabela"):
                        with st.spinner("A guardar..."):
                            try:
                                # Aplicar horários das abreviaturas
                                _abrev_hor_c = {
                                    'A1': ('Atendimento', '00-08'), 'A2': ('Atendimento', '08-16'), 'A3': ('Atendimento', '16-24'),
                                    'PO1': ('Patrulha Ocorrências', '00-08'), 'PO2': ('Patrulha Ocorrências', '08-16'), 'PO3': ('Patrulha Ocorrências', '16-24'),
                                    'AA2': ('Apoio Atendimento', '08-16'), 'AA3': ('Apoio Atendimento', '16-24'),
                                }
                                for idx_c, row_c2 in df_editado.iterrows():
                                    sv_c2  = str(row_c2['serviço']).strip()
                                    hor_c2 = str(row_c2['horário']).strip()
                                    if sv_c2 in _abrev_hor_c:
                                        serv_c2, hor_def = _abrev_hor_c[sv_c2]
                                        df_editado.at[idx_c, 'serviço'] = serv_c2
                                        if not hor_c2 or hor_c2 == 'nan':
                                            df_editado.at[idx_c, 'horário'] = hor_def
                                sh_c = get_sheet()
                                ws_dia_c = sh_c.worksheet(aba_dia)
                                todas_linhas_c = ws_dia_c.get_all_values()
                                hdrs_c = [h.strip().lower() for h in todas_linhas_c[0]]
                                ix_id_c   = hdrs_c.index('id')      if 'id'      in hdrs_c else 0
                                ix_serv_c = hdrs_c.index('serviço') if 'serviço' in hdrs_c else 1
                                ix_hor_c  = hdrs_c.index('horário') if 'horário' in hdrs_c else 2
                                ix_ind_c  = hdrs_c.index('indicativo rádio') if 'indicativo rádio' in hdrs_c else (hdrs_c.index('indicativo') if 'indicativo' in hdrs_c else None)
                                ix_rad_c  = hdrs_c.index('rádio') if 'rádio' in hdrs_c else (hdrs_c.index('radio') if 'radio' in hdrs_c else None)
                                ix_giro_c = hdrs_c.index('giro') if 'giro' in hdrs_c else None
                                ix_obs_c  = hdrs_c.index('observações') if 'observações' in hdrs_c else (hdrs_c.index('observacoes') if 'observacoes' in hdrs_c else None)

                                # Construir mapa de edições -- só militares com serviço preenchido
                                edit_map = {}
                                for _, row_e in df_editado.iterrows():
                                    mid_e = str(row_e['id']).strip()
                                    sv_e  = str(row_e.get('serviço','')).strip()
                                    if mid_e and sv_e and sv_e != 'nan':
                                        edit_map[mid_e] = row_e

                                upds_c = []
                                for i, row_c in enumerate(todas_linhas_c[1:], start=2):
                                    mid_c = str(row_c[ix_id_c]).strip() if ix_id_c < len(row_c) else ''
                                    if not mid_c or mid_c == 'nan':
                                        continue
                                    ids_c = [m.strip() for m in re.split(r'[;,]', mid_c) if m.strip()]
                                    # Só atualizar se TODOS os IDs desta linha estão no edit_map com o mesmo serviço
                                    # Ou se é uma linha de um só militar
                                    if len(ids_c) == 1:
                                        mid_s = ids_c[0]
                                        if mid_s not in edit_map:
                                            continue
                                        row_e = edit_map[mid_s]
                                        def _upd(ix, val):
                                            if ix is not None and str(val).strip() and str(val).strip() != 'nan':
                                                cl = chr(ord('A') + ix)
                                                upds_c.append({'range': f'{cl}{i}', 'values': [[str(val).strip()]]})
                                        _upd(ix_serv_c, row_e['serviço'])
                                        _upd(ix_hor_c,  row_e['horário'])
                                        _upd(ix_ind_c,  row_e.get('indicativo',''))
                                        _upd(ix_rad_c,  row_e.get('rádio',''))
                                        _upd(ix_giro_c, row_e.get('giro',''))
                                        _upd(ix_obs_c,  row_e.get('observações',''))
                                    else:
                                        # Linha com múltiplos IDs (ex: Patrulha) -- só atualizar se algum está no edit_map
                                        for mid_s in ids_c:
                                            if mid_s in edit_map:
                                                row_e = edit_map[mid_s]
                                                sv_linha = str(row_c[ix_serv_c]).strip() if ix_serv_c < len(row_c) else ''
                                                # Só atualizar se o serviço bate com o que está na linha
                                                if norm(str(row_e['serviço'])) == norm(sv_linha) or not sv_linha:
                                                    def _upd2(ix, val):
                                                        if ix is not None and str(val).strip() and str(val).strip() != 'nan':
                                                            cl = chr(ord('A') + ix)
                                                            upds_c.append({'range': f'{cl}{i}', 'values': [[str(val).strip()]]})
                                                    _upd2(ix_hor_c,  row_e['horário'])
                                                    _upd2(ix_ind_c,  row_e.get('indicativo',''))
                                                break

                                if upds_c:
                                    ws_dia_c.batch_update(upds_c)

                                # Atualizar ordem_escala
                                _atualizar_ordem_escala_dia(sh_c, aba_dia, d_gerar)

                                load_data.clear()
                                del st.session_state['tabela_escala']
                                st.session_state.pop('ordem_gerada', None)
                                st.session_state.pop('tabela_dia', None)
                                st.success("✅ Escala guardada!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao guardar: {e}")

        with tab_editar:
            st.markdown("#### ✏️ Editar Escala")
            st.caption("Seleciona até 3 dias para ver e editar em simultâneo.")

            # ── Carregar serviços e listas ──
            _listas = load_listas()
            _mil_servicos = load_servicos()
            _extras_e = ['Férias', 'Folga Semanal', 'Folga Complementar', 'Outras Licenças',
                         'Doente', 'Baixa', 'Diligência', 'Inquéritos', 'Secretaria',
                         'Pronto', 'Tribunal', 'Disponível',
                         'Patrulha Auto', 'Patrulha Apeada', 'EG', 'Tiro']
            _hdrs_e = list(set(s for servs in _mil_servicos.values() for s in servs))
            todos_servicos_e = [''] + sorted(set(_hdrs_e + _extras_e))
            opts_hor_e = _listas.get('Horário', ['', '00-08', '08-16', '16-24'])
            opts_rad_e = _listas.get('Rádio', [''])
            opts_ind_e = _listas.get('Indicativo', [''])
            opts_vtr_e = _listas.get('Viatura', [''])
            opts_gir_e = _listas.get('Giro', [''])
            opts_sv_e  = _listas.get('Serviço', todos_servicos_e) or todos_servicos_e
            # Garantir que horário tem sempre as opções base
            if len(opts_hor_e) <= 1:
                opts_hor_e = ['', '00-08', '08-16', '16-24']

            def _adicionar_lista(campo, valor):
                """Adiciona valor novo à aba listas se não existir."""
                try:
                    sh_l = get_sheet()
                    ws_l = sh_l.worksheet("listas")
                    vals_l = ws_l.get_all_values()
                    if not vals_l: return
                    hdrs_l = [h.strip() for h in vals_l[0]]
                    if campo not in hdrs_l: return
                    col_idx = hdrs_l.index(campo)
                    col_vals = [str(row[col_idx]).strip() for row in vals_l[1:] if col_idx < len(row)]
                    if valor not in col_vals:
                        # Encontrar próxima linha vazia nesta coluna
                        next_row = len([v for v in col_vals if v]) + 2  # +2 para header
                        cl = chr(ord('A') + col_idx)
                        ws_l.update(f'{cl}{next_row}', [[valor]])
                        load_listas.clear()
                except:
                    pass

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                d_e1 = st.date_input("Dia 1:", format="DD/MM/YYYY", key="d_edit1")
            with col_e2:
                d_e2 = st.date_input("Dia 2:", format="DD/MM/YYYY", key="d_edit2", value=None)

            dias_editar = [d for d in [d_e1, d_e2] if d is not None]

            if st.button("📋 Carregar dias", key="btn_carregar_editar", use_container_width=True):
                sh_e = get_sheet()
                abas_existentes_e = [ws.title for ws in sh_e.worksheets()]
                # Criar abas que não existam
                aba_modelo_e = next((ws for ws in sh_e.worksheets() if re.match(r'^\d{2}-\d{2}$', ws.title)), None)
                hdrs_modelo_e = aba_modelo_e.row_values(1) if aba_modelo_e else ['id','serviço','horário','indicativo rádio','rádio','viatura','giro','observações']
                for d_e_chk in dias_editar:
                    aba_chk = d_e_chk.strftime("%d-%m")
                    if aba_chk not in abas_existentes_e:
                        ws_chk = sh_e.add_worksheet(title=aba_chk, rows=200, cols=len(hdrs_modelo_e))
                        ws_chk.update('A1', [hdrs_modelo_e])
                # Pré-calcular férias uma vez para todos os dias/militares
                ferias_cache_e = {}
                for d_e in dias_editar:
                    em_ferias = set()
                    for mid in df_util['id'].astype(str).str.strip():
                        if militar_de_ferias(mid, d_e, df_ferias, feriados):
                            em_ferias.add(mid)
                    ferias_cache_e[d_e] = em_ferias

                dados_editar = {}
                for d_e in dias_editar:
                    aba_e = d_e.strftime("%d-%m")
                    # Ler aba diretamente sem explodir IDs
                    mapa_e = {}
                    try:
                        ws_e_raw = sh_e.worksheet(aba_e)
                        vals_e_raw = ws_e_raw.get_all_values()
                        if vals_e_raw and len(vals_e_raw) > 1:
                            hdrs_e_raw = [h.strip().lower() for h in vals_e_raw[0]]
                            ix_id_r  = hdrs_e_raw.index('id')      if 'id'      in hdrs_e_raw else 0
                            ix_sv_r  = hdrs_e_raw.index('serviço') if 'serviço' in hdrs_e_raw else 1
                            ix_hr_r  = hdrs_e_raw.index('horário') if 'horário' in hdrs_e_raw else 2
                            ix_in_r  = hdrs_e_raw.index('indicativo rádio') if 'indicativo rádio' in hdrs_e_raw else (hdrs_e_raw.index('indicativo') if 'indicativo' in hdrs_e_raw else None)
                            ix_ra_r  = hdrs_e_raw.index('rádio') if 'rádio' in hdrs_e_raw else None
                            ix_gi_r  = hdrs_e_raw.index('giro') if 'giro' in hdrs_e_raw else None
                            ix_vt_r  = hdrs_e_raw.index('viatura') if 'viatura' in hdrs_e_raw else None
                            ix_ob_r  = hdrs_e_raw.index('observações') if 'observações' in hdrs_e_raw else None
                            def _get(row, ix):
                                return str(row[ix]).strip().replace('nan','') if ix is not None and ix < len(row) else ''
                            # Recolher opções de TODAS as linhas (não só as com ID)
                            opts_hor_e  = set(opts_hor_e)   # já vem das listas
                            opts_ind_e  = set(opts_ind_e)   # já vem das listas
                            opts_rad_e  = set(opts_rad_e)   # já vem das listas
                            opts_gir_e  = set(opts_gir_e)   # já vem das listas
                            opts_vtr_e  = set(opts_vtr_e)   # já vem das listas
                            opts_sv_dia = set(opts_sv_e)    # começar com as listas
                            for row_r in vals_e_raw[1:]:
                                v_sv = _get(row_r, ix_sv_r)
                                v_hr = _get(row_r, ix_hr_r)
                                v_in = _get(row_r, ix_in_r)
                                v_ra = _get(row_r, ix_ra_r)
                                v_gi = _get(row_r, ix_gi_r)
                                v_vt = _get(row_r, ix_vt_r)
                                if v_sv: opts_sv_dia.add(v_sv)
                                if v_hr: opts_hor_e.add(v_hr)
                                if v_in: opts_ind_e.add(v_in)
                                if v_ra: opts_rad_e.add(v_ra)
                                if v_gi: opts_gir_e.add(v_gi)
                                if v_vt: opts_vtr_e.add(v_vt)
                                v_hr = _get(row_r, ix_hr_r)
                                v_in = _get(row_r, ix_in_r)
                                v_ra = _get(row_r, ix_ra_r)
                                v_gi = _get(row_r, ix_gi_r)
                                v_vt = _get(row_r, ix_vt_r)
                                if v_hr: opts_hor_e.add(v_hr)
                                if v_in: opts_ind_e.add(v_in)
                                if v_ra: opts_rad_e.add(v_ra)
                                if v_gi: opts_gir_e.add(v_gi)
                                if v_vt: opts_vtr_e.add(v_vt)
                                id_raw = _get(row_r, ix_id_r)
                                if not id_raw: continue
                                dados_r = {
                                    'serviço':     _get(row_r, ix_sv_r),
                                    'horário':     _get(row_r, ix_hr_r),
                                    'indicativo':  _get(row_r, ix_in_r),
                                    'rádio':       _get(row_r, ix_ra_r),
                                    'giro':        _get(row_r, ix_gi_r),
                                    'viatura':     _get(row_r, ix_vt_r),
                                    'observações': _get(row_r, ix_ob_r),
                                }
                                for mid in re.split(r'[;,\n]+', id_raw):
                                    mid = mid.strip()
                                    if mid:
                                        mapa_e[mid] = dados_r
                            # Combinar com opts base das listas (garantir que ficam sempre disponíveis)
                            st.session_state['opts_hor_e'] = [''] + sorted(opts_hor_e - {''})
                            st.session_state['opts_ind_e'] = [''] + sorted(opts_ind_e - {''})
                            st.session_state['opts_rad_e'] = [''] + sorted(opts_rad_e - {''})
                            st.session_state['opts_gir_e'] = [''] + sorted(opts_gir_e - {''})
                            st.session_state['opts_vtr_e'] = [''] + sorted(opts_vtr_e - {''})
                            st.session_state['opts_sv_e']  = [''] + sorted(opts_sv_dia - {''})
                    except Exception as _err_e:
                        st.warning(f"Erro ao ler {aba_e}: {_err_e}")
                    em_ferias_e = ferias_cache_e[d_e]
                    linhas_e = []
                    for _, row_u in df_util.iterrows():
                        mid = str(row_u.get('id', '')).strip()
                        if not mid or mid == 'nan': continue
                        nome  = str(row_u.get('nome', '')).strip()
                        posto = str(row_u.get('posto', '')).strip()
                        # Abreviar nome: inicial + apelido
                        partes_nome = nome.split()
                        nome_curto = f"{partes_nome[0][0]}.{partes_nome[-1]}" if len(partes_nome) >= 2 else nome
                        if mid in mapa_e:
                            dados = mapa_e[mid]
                        elif mid in em_ferias_e:
                            dados = {'serviço': 'Férias', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        else:
                            dados = {'serviço': 'Disponível', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        linhas_e.append({'id': mid, 'nome': f"{posto} {nome_curto}".strip(),
                                         'serviço': dados.get('serviço',''), 'horário': dados.get('horário',''),
                                         'indicativo': dados.get('indicativo',''), 'rádio': dados.get('rádio',''),
                                         'giro': dados.get('giro',''), 'viatura': dados.get('viatura',''),
                                         'observações': dados.get('observações','')})
                    dados_editar[aba_e] = {'linhas': linhas_e, 'data': d_e}
                st.session_state['editar_escala'] = dados_editar
                st.session_state['editar_escala_original'] = {
                    aba: {mid: dict(r) for r in info['linhas'] for mid in [str(r['id']).strip()]}
                    for aba, info in dados_editar.items()
                }
                st.rerun()

            if 'debug_upds' in st.session_state:
                st.info(st.session_state.pop('debug_upds'))

            # ── Mostrar tabelas por dia ──
            if 'editar_escala' in st.session_state:
                dados_editar = st.session_state['editar_escala']
                abas_lista = list(dados_editar.items())

                def _guardar_sheets(editados_dict):
                    sh_gc = get_sheet()
                    for aba_g, df_g in editados_dict.items():
                        ws_g = sh_gc.worksheet(aba_g)
                        todas_g = ws_g.get_all_values()
                        if not todas_g: continue
                        hdrs_g = [h.strip().lower() for h in todas_g[0]]
                        ix_id_g  = hdrs_g.index('id')      if 'id'      in hdrs_g else 0
                        ix_sv_g  = hdrs_g.index('serviço') if 'serviço' in hdrs_g else 1
                        ix_hr_g  = hdrs_g.index('horário') if 'horário' in hdrs_g else 2

                        # Estado original (antes de editar) -- do session_state
                        original = st.session_state.get('editar_escala_original', {}).get(aba_g, {})

                        # Converter editor para dict id -> {serviço, horário, ...}
                        editor_map = {}
                        for _, r in df_g.iterrows():
                            mid = str(r['id']).strip()
                            if mid and mid != 'nan':
                                editor_map[mid] = {
                                    'serviço':     str(r.get('serviço','') or '').strip(),
                                    'horário':     str(r.get('horário','') or '').strip(),
                                    'indicativo':  str(r.get('indicativo','') or '').strip(),
                                    'rádio':       str(r.get('rádio','') or '').strip(),
                                    'giro':        str(r.get('giro','') or '').strip(),
                                    'viatura':     str(r.get('viatura','') or '').strip(),
                                    'observações': str(r.get('observações','') or '').strip(),
                                }

                        # Construir mapa de linhas do Sheets: (norm_serv, horário) -> índice linha (1-based)
                        linhas_sheet = {}
                        for i, row in enumerate(todas_g[1:], start=1):
                            sv = norm(str(row[ix_sv_g]).strip()) if ix_sv_g < len(row) else ''
                            hr = str(row[ix_hr_g]).strip() if ix_hr_g < len(row) else ''
                            if sv:
                                linhas_sheet[(sv, hr)] = i  # índice na lista todas_g

                        # Construir novo estado das linhas
                        # Para cada linha do Sheets, recalcular quem está lá
                        novas_linhas = {}  # (sv,hr) -> lista de IDs
                        for (sv, hr), idx in linhas_sheet.items():
                            row = todas_g[idx]
                            ids_atuais = [m.strip() for m in re.split(r'[;,]+', str(row[ix_id_g]).strip()) if m.strip()]
                            novas_linhas[(sv, hr)] = ids_atuais[:]

                        # Aplicar mudanças do editor
                        for mid, dados in editor_map.items():
                            sv_novo = norm(dados['serviço'])
                            hr_novo = dados['horário']
                            sv_orig = norm(original.get(mid, {}).get('serviço', ''))
                            hr_orig = original.get(mid, {}).get('horário', '')

                            # Remover da linha original se mudou
                            if sv_orig and (sv_orig != sv_novo or hr_orig != hr_novo):
                                chave_orig = (sv_orig, hr_orig)
                                if chave_orig in novas_linhas and mid in novas_linhas[chave_orig]:
                                    novas_linhas[chave_orig].remove(mid)

                            # Adicionar à linha nova
                            if sv_novo:
                                chave_nova = (sv_novo, hr_novo)
                                if chave_nova in novas_linhas:
                                    if mid not in novas_linhas[chave_nova]:
                                        novas_linhas[chave_nova].append(mid)
                                else:
                                    novas_linhas[chave_nova] = [mid]

                        # Escrever updates no Sheets
                        upds_g = []
                        cl_id = chr(ord('A') + ix_id_g)
                        for (sv, hr), idx in linhas_sheet.items():
                            ids_novos = novas_linhas.get((sv, hr), [])
                            ids_str = ';'.join(ids_novos)
                            linha_sheet = idx + 1  # +1 porque todas_g[0] é header
                            upds_g.append({'range': f'{cl_id}{linha_sheet}', 'values': [[ids_str]]})

                        # Linhas novas (serviços que não existiam no Sheets)
                        for (sv, hr), ids in novas_linhas.items():
                            if (sv, hr) not in linhas_sheet and ids:
                                # Encontrar nome real do serviço
                                sv_real = ids[0]  # fallback
                                for mid in ids:
                                    sv_real_r = editor_map.get(mid, {}).get('serviço', '')
                                    if sv_real_r:
                                        sv_real = sv_real_r
                                        break
                                nova_linha = [''] * len(hdrs_g)
                                nova_linha[ix_id_g] = ';'.join(ids)
                                nova_linha[ix_sv_g] = sv_real
                                nova_linha[ix_hr_g] = hr
                                ws_g.append_row(nova_linha)

                        if upds_g:
                            ws_g.batch_update(upds_g)

                        # Atualizar ordem_escala -- usando função central
                        try:
                            aba_data_g = datetime.strptime(f"{aba_g}-{datetime.now().year}", "%d-%m-%Y")
                            _atualizar_ordem_escala_dia(sh_gc, aba_g, aba_data_g)
                        except:
                            pass

                dias_pt = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']

                if len(abas_lista) == 2:
                    aba_1, info_1 = abas_lista[0]
                    aba_2, info_2 = abas_lista[1]
                    d1, d2 = info_1['data'], info_2['data']
                    label_1  = f"Serviço {d1.strftime('%d/%m')} {dias_pt[d1.weekday()]}"
                    label_h1 = f"Horário {d1.strftime('%d/%m')}"
                    label_2  = f"Serviço {d2.strftime('%d/%m')} {dias_pt[d2.weekday()]}"
                    label_h2 = f"Horário {d2.strftime('%d/%m')}"
                    mapa_1 = {r['id']: r for r in info_1['linhas']}
                    mapa_2 = {r['id']: r for r in info_2['linhas']}
                    linhas_uni = []
                    for mid in [r['id'] for r in info_1['linhas']]:
                        r1 = mapa_1.get(mid, {})
                        r2 = mapa_2.get(mid, {})
                        linhas_uni.append({'id': mid, 'nome': r1.get('nome',''), label_1: r1.get('serviço',''), label_h1: r1.get('horário',''), label_2: r2.get('serviço',''), label_h2: r2.get('horário','')})
                    df_uni = pd.DataFrame(linhas_uni)
                    df_editado_uni = st.data_editor(
                        df_uni,
                        column_config={
                            'id':     st.column_config.TextColumn('ID', disabled=True, width='small'),
                            'nome':   st.column_config.TextColumn('Nome', disabled=True, width='small'),
                            label_1:  st.column_config.SelectboxColumn(label_1, options=st.session_state.get('opts_sv_e', opts_sv_e), width='medium'),
                            label_h1: st.column_config.SelectboxColumn(label_h1, options=opts_hor_e, width='small'),
                            label_2:  st.column_config.SelectboxColumn(label_2, options=st.session_state.get('opts_sv_e', opts_sv_e), width='medium'),
                            label_h2: st.column_config.SelectboxColumn(label_h2, options=opts_hor_e, width='small'),
                        },
                        hide_index=True, use_container_width=True,
                        key="editor_unificado", num_rows="fixed",
                    )
                    if st.button("✅ GUARDAR ALTERAÇÕES", use_container_width=True, type="primary", key="btn_guardar_editar"):
                        with st.spinner("A guardar..."):
                            try:
                                rows_1, rows_2 = [], []
                                for _, row_u in df_editado_uni.iterrows():
                                    mid = str(row_u['id'])
                                    r1o = dict(mapa_1.get(mid, {'id':mid,'nome':'','serviço':'','horário':'','indicativo':'','rádio':'','giro':'','observações':''}))
                                    r2o = dict(mapa_2.get(mid, {'id':mid,'nome':'','serviço':'','horário':'','indicativo':'','rádio':'','giro':'','observações':''}))
                                    r1o['id'] = mid; r2o['id'] = mid
                                    r1o['serviço'] = str(row_u.get(label_1) or '')
                                    r1o['horário'] = str(row_u.get(label_h1) or '')
                                    r2o['serviço'] = str(row_u.get(label_2) or '')
                                    r2o['horário'] = str(row_u.get(label_h2) or '')
                                    rows_1.append(r1o); rows_2.append(r2o)
                                _guardar_sheets({aba_1: pd.DataFrame(rows_1), aba_2: pd.DataFrame(rows_2)})
                                del st.session_state['editar_escala']
                                st.session_state.pop('editar_escala_original', None)
                                st.success("✅ Guardado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

                else:
                    aba_e, info_e = abas_lista[0]
                    d_e = info_e['data']
                    st.markdown(f"**📅 {d_e.strftime('%d/%m/%Y')} -- {dias_pt[d_e.weekday()]}**")
                    df_s = pd.DataFrame(info_e['linhas'])
                    df_editado_s = st.data_editor(
                        df_s,
                        column_config={
                            'id':          st.column_config.TextColumn('ID', disabled=True, width='small'),
                            'nome':        st.column_config.TextColumn('Nome', disabled=True, width='small'),
                            'serviço':     st.column_config.SelectboxColumn('Serviço', options=st.session_state.get('opts_sv_e', opts_sv_e), width='medium'),
                            'horário':     st.column_config.SelectboxColumn('Horário', options=opts_hor_e, width='small'),
                            'indicativo':  st.column_config.SelectboxColumn('Indicativo', options=opts_ind_e, width='small'),
                            'rádio':       st.column_config.SelectboxColumn('Rádio', options=opts_rad_e, width='small'),
                            'giro':        st.column_config.SelectboxColumn('Giro', options=opts_gir_e, width='small'),
                            'viatura':     st.column_config.SelectboxColumn('Viatura', options=opts_vtr_e, width='small'),
                            'observações': st.column_config.TextColumn('Observações', width='medium'),
                        },
                        hide_index=True, use_container_width=True,
                        key=f"editor_{aba_e}", num_rows="fixed",
                    )
                    if st.button("✅ GUARDAR ALTERAÇÕES", use_container_width=True, type="primary", key="btn_guardar_editar"):
                        with st.spinner("A guardar..."):
                            try:
                                # Adicionar novos valores às listas
                                for _, row_e in df_editado_s.iterrows():
                                    for campo, col in [('Horário','horário'),('Indicativo','indicativo'),('Rádio','rádio'),('Giro','giro'),('Viatura','viatura')]:
                                        val = str(row_e.get(col, '') or '').strip()
                                        if val:
                                            opts = {'Horário': opts_hor_e, 'Indicativo': opts_ind_e, 'Rádio': opts_rad_e, 'Giro': opts_gir_e, 'Viatura': opts_vtr_e}[campo]
                                            if val not in opts:
                                                _adicionar_lista(campo, val)
                                _guardar_sheets({aba_e: df_editado_s})
                                del st.session_state['editar_escala']
                                st.session_state.pop('editar_escala_original', None)
                                st.success("✅ Guardado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

        with tab_rem:
            st.markdown("#### 💶 Nomear para Remunerado")

            # Carregar ordem_remunerados
            try:
                sh_rem = get_sheet()
                ws_ord_rem = sh_rem.worksheet("ordem_remunerados")
                df_ord_rem = pd.DataFrame(ws_ord_rem.get_all_records())
                df_ord_rem.columns = [c.strip().lower() for c in df_ord_rem.columns]
            except Exception as e:
                st.error(f"Aba 'ordem_remunerados' não encontrada: {e}")
                st.stop()

            if df_ord_rem.empty:
                st.info("Sem dados na aba 'ordem_remunerados'.")
            else:
                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                with col_r1:
                    d_rem = st.date_input("Data:", format="DD/MM/YYYY", key="d_rem")
                with col_r2:
                    tab_rem_sel = st.selectbox("Tabela:", ["A", "B"], key="tab_rem_sel")
                with col_r3:
                    hor_rem = st.text_input("Horário:", placeholder="ex: 09-13", key="hor_rem")
                with col_r4:
                    n_rem = st.number_input("Nº militares:", min_value=1, max_value=10, value=2, key="n_rem")

                obs_rem = st.text_input("Observação do remunerado:", placeholder="ex: Reg. Trânsito - Rua X", key="obs_rem")

                if st.button("🔍 Calcular Nomeação", use_container_width=True, key="btn_calc_rem"):
                    aba_rem = d_rem.strftime("%d-%m")
                    df_dia_rem = load_data(aba_rem)
                    data_str_rem = d_rem.strftime("%d/%m/%Y")

                    # Colunas da tabela selecionada
                    col_ultima = f"ultima_vez_{tab_rem_sel.lower()}"
                    col_total  = f"total_ano_{tab_rem_sel.lower()}"

                    # Garantir colunas existem
                    for col in [col_ultima, col_total, 'voluntario', 'prescinde_descanso']:
                        if col not in df_ord_rem.columns:
                            df_ord_rem[col] = ''

                    # Converter tipos
                    df_ord_rem['voluntario']         = df_ord_rem['voluntario'].astype(str).str.strip().str.lower().isin(['true','1','sim','yes'])
                    df_ord_rem['prescinde_descanso'] = df_ord_rem['prescinde_descanso'].astype(str).str.strip().str.lower().isin(['true','1','sim','yes'])
                    df_ord_rem[col_total] = pd.to_numeric(df_ord_rem[col_total], errors='coerce').fillna(0)
                    df_ord_rem[col_ultima] = pd.to_datetime(df_ord_rem[col_ultima], dayfirst=True, errors='coerce')

                    # Horário do remunerado a nomear
                    hi_rem, hf_rem = None, None
                    if hor_rem and '-' in hor_rem:
                        try:
                            hi_rem = int(hor_rem.split('-')[0].strip())
                            hf_rem = int(hor_rem.split('-')[1].strip())
                        except:
                            pass

                    def _sobreposicao(h1_ini, h1_fim, h2_ini, h2_fim):
                        """Verifica sobreposição parcial entre dois horários."""
                        if None in (h1_ini, h1_fim, h2_ini, h2_fim):
                            return False
                        # Converter para minutos desde meia-noite (considerar passagem de dia)
                        def to_min(h, base=0):
                            return h * 60 + (1440 if h < base else 0)
                        s1 = to_min(h1_ini); e1 = to_min(h1_fim, h1_ini)
                        s2 = to_min(h2_ini); e2 = to_min(h2_fim, h2_ini)
                        return s1 < e2 and s2 < e1

                    def _verif_descanso(hi_serv, hf_serv, hi_novo, hf_novo):
                        """Verifica 8h de descanso antes e depois."""
                        if None in (hi_serv, hf_serv, hi_novo, hf_novo):
                            return True
                        # Converter tudo para minutos
                        def to_min(h, base=0):
                            return h * 60 + (1440 if h < base else 0)
                        fim_serv = to_min(hf_serv, hi_serv)
                        ini_novo = to_min(hi_novo)
                        ini_serv = to_min(hi_serv)
                        fim_novo = to_min(hf_novo, hi_novo)
                        descanso_antes = abs(ini_novo - fim_serv) >= 480
                        descanso_depois = abs(ini_serv - fim_novo) >= 480
                        return descanso_antes and descanso_depois

                    # Serviços do dia por militar
                    servicos_dia = {}
                    if not df_dia_rem.empty:
                        df_serv_dia = df_dia_rem[~df_dia_rem['serviço'].apply(norm).str.contains('remu|grat', na=False)]
                        for _, row_sd in df_serv_dia.iterrows():
                            mid_sd = str(row_sd['id']).strip()
                            if not mid_sd:
                                continue
                            hor_sd = str(row_sd.get('horário', '')).strip()
                            hi_sd, hf_sd = None, None
                            if '-' in hor_sd:
                                try:
                                    hi_sd = int(hor_sd.split('-')[0].strip())
                                    hf_sd = int(hor_sd.split('-')[1].strip())
                                except:
                                    pass
                            servicos_dia.setdefault(mid_sd, []).append((hi_sd, hf_sd, str(row_sd.get('serviço',''))))

                    # Ausentes no dia
                    ausentes_dia = set()
                    if not df_dia_rem.empty:
                        aus_mask = df_dia_rem['serviço'].apply(norm).str.contains('ferias|licen|doente|baixa|dilig|tribunal', na=False)
                        for mid_a in df_dia_rem[aus_mask]['id'].astype(str).str.strip().tolist():
                            if mid_a:
                                ausentes_dia.add(mid_a)
                    # Verificar férias
                    for _, row_u in df_ord_rem.iterrows():
                        mid_u = str(row_u.get('id', '')).strip()
                        if mid_u and militar_de_ferias(mid_u, d_rem, df_ferias, feriados):
                            ausentes_dia.add(mid_u)

                    # Ordenar por ultima_vez (mais antigo primeiro), desempate total_ano
                    df_ord_rem_sorted = df_ord_rem.sort_values(
                        [col_ultima, col_total],
                        ascending=[True, True],
                        na_position='first'
                    )

                    nomeados = []
                    avisos   = []
                    skipped  = []

                    # 1ª passagem: voluntários
                    # 2ª passagem: não voluntários (se não chegou)
                    for fase in ['voluntarios', 'nao_voluntarios']:
                        if len(nomeados) >= n_rem:
                            break
                        for _, row_r in df_ord_rem_sorted.iterrows():
                            if len(nomeados) >= n_rem:
                                break
                            mid_r = str(row_r.get('id', '')).strip()
                            if not mid_r or mid_r in [n['id'] for n in nomeados]:
                                continue
                            is_vol = bool(row_r['voluntario'])
                            if fase == 'voluntarios' and not is_vol:
                                continue
                            if fase == 'nao_voluntarios' and is_vol:
                                continue

                            # Verificar ausente
                            if mid_r in ausentes_dia:
                                skipped.append(f"{mid_r} -- ausente")
                                continue

                            # Verificar sobreposição
                            sobreposto = False
                            for hi_s, hf_s, serv_s in servicos_dia.get(mid_r, []):
                                if _sobreposicao(hi_rem, hf_rem, hi_s, hf_s):
                                    skipped.append(f"{mid_r} -- sobreposição com {serv_s} ({hi_s}-{hf_s})")
                                    sobreposto = True
                                    break
                            if sobreposto:
                                continue

                            # Verificar descanso (só quem não prescinde)
                            if not bool(row_r['prescinde_descanso']):
                                descanso_ok = True
                                for hi_s, hf_s, serv_s in servicos_dia.get(mid_r, []):
                                    if not _verif_descanso(hi_s, hf_s, hi_rem, hf_rem):
                                        skipped.append(f"{mid_r} -- menos de 8h descanso com {serv_s}")
                                        descanso_ok = False
                                        break
                                if not descanso_ok:
                                    continue

                            # ✅ Nomear
                            if fase == 'nao_voluntarios':
                                avisos.append(f"⚠️ **{get_nome_curto(df_util, mid_r)} ({mid_r})** nomeado fora da lista de voluntários")
                            nomeados.append({
                                'id': mid_r,
                                'nome': get_nome_curto(df_util, mid_r),
                                'voluntario': is_vol,
                                'prescinde': bool(row_r['prescinde_descanso']),
                                'ultima_vez': row_r[col_ultima],
                                'total': int(row_r[col_total]),
                            })

                    # Mostrar resultado
                    if nomeados:
                        st.success(f"✅ {len(nomeados)} militar(es) nomeado(s) para Tabela {tab_rem_sel} -- {hor_rem}:")
                        for n in nomeados:
                            ul = n['ultima_vez'].strftime('%d/%m/%Y') if pd.notna(n['ultima_vez']) else "Nunca"
                            st.markdown(f"- **{n['nome']} ({n['id']})** -- último: {ul} | total ano: {n['total']}")
                        for av in avisos:
                            st.warning(av)
                        if skipped:
                            with st.expander(f"ℹ️ {len(skipped)} militar(es) ignorado(s)"):
                                for s in skipped:
                                    st.caption(s)

                        # Guardar em session_state para confirmar
                        st.session_state['rem_nomeados'] = {
                            'nomeados': nomeados,
                            'data': data_str_rem,
                            'aba': aba_rem,
                            'horario': hor_rem,
                            'tabela': tab_rem_sel,
                            'observacao': obs_rem,
                            'col_ultima': col_ultima,
                            'col_total': col_total,
                        }
                    else:
                        st.warning("Não foi possível nomear militares suficientes.")
                        if skipped:
                            with st.expander("ℹ️ Militares ignorados"):
                                for s in skipped:
                                    st.caption(s)

                # Confirmar nomeação
                if 'rem_nomeados' in st.session_state:
                    dados_rem = st.session_state['rem_nomeados']
                    if st.button("✅ CONFIRMAR NOMEAÇÃO E ESCREVER NA ESCALA", use_container_width=True, type="primary", key="btn_conf_rem"):
                        try:
                            sh_conf = get_sheet()
                            ws_dia_rem = sh_conf.worksheet(dados_rem['aba'])
                            ids_nomeados = [n['id'] for n in dados_rem['nomeados']]
                            ids_str = ", ".join(ids_nomeados)
                            # Escrever linha na aba do dia
                            ws_dia_rem.append_row([
                                ids_str,
                                f"Svç Remunerado - Tabela {dados_rem['tabela']}",
                                dados_rem['horario'],
                                "", "", "",  # indicativo, radio, viatura
                                dados_rem['observacao'],
                            ])
                            # Atualizar ordem_remunerados
                            ws_ord = sh_conf.worksheet("ordem_remunerados")
                            todos_vals = ws_ord.get_all_values()
                            hdrs_ord = [h.strip().lower() for h in todos_vals[0]]
                            col_id_idx    = hdrs_ord.index('id') if 'id' in hdrs_ord else 0
                            col_ul_idx    = hdrs_ord.index(dados_rem['col_ultima']) if dados_rem['col_ultima'] in hdrs_ord else None
                            col_tot_idx   = hdrs_ord.index(dados_rem['col_total'])  if dados_rem['col_total']  in hdrs_ord else None
                            upds_ord = []
                            for i, row_o in enumerate(todos_vals[1:], start=2):
                                mid_o = str(row_o[col_id_idx]).strip() if col_id_idx < len(row_o) else ''
                                if mid_o in ids_nomeados:
                                    if col_ul_idx is not None:
                                        cl = chr(ord('A') + col_ul_idx)
                                        upds_ord.append({'range': f'{cl}{i}', 'values': [[dados_rem['data']]]})
                                    if col_tot_idx is not None:
                                        total_atual = int(str(row_o[col_tot_idx]).strip() or 0) if col_tot_idx < len(row_o) else 0
                                        cl2 = chr(ord('A') + col_tot_idx)
                                        upds_ord.append({'range': f'{cl2}{i}', 'values': [[total_atual + 1]]})
                            if upds_ord:
                                ws_ord.batch_update(upds_ord)
                            load_data.clear()
                            del st.session_state['rem_nomeados']
                            st.success("✅ Nomeação confirmada e escala atualizada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

    # --- 🏥 LICENÇAS (ADMIN) ---
    elif menu == "🏥 Dispensas":
        st.title("🏥 Dispensas")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()

        # Mostrar registos existentes
        df_lic_all = load_licencas(ano_atual)
        # Filtrar só as em vigor (fim >= hoje)
        hoje_lic = datetime.now().date()
        if not df_lic_all.empty:
            col_fim_l = next((c for c in df_lic_all.columns if 'fim' in c.lower()), None)
            if col_fim_l:
                def _lic_em_vigor(fim_str):
                    try:
                        if '/' in str(fim_str):
                            return datetime.strptime(str(fim_str).strip(), '%d/%m/%Y').date() >= hoje_lic
                        else:
                            return datetime.strptime(f"{fim_str.strip()}-{hoje_lic.year}", '%d-%m-%Y').date() >= hoje_lic
                    except:
                        return True
                df_lic_show = df_lic_all[df_lic_all[col_fim_l].apply(_lic_em_vigor)]
            else:
                df_lic_show = df_lic_all
        else:
            df_lic_show = df_lic_all

        if not df_lic_show.empty:
            st.dataframe(df_lic_show, use_container_width=True, hide_index=True)
        else:
            st.info("Sem licenças em vigor.")

        st.markdown("---")
        st.markdown("#### ➕ Adicionar registo")

        col_l1, col_l2 = st.columns(2)
        with col_l1:
            mil_opts_l = {f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})".strip(): str(r.get('id',''))
                          for _, r in df_util.iterrows() if str(r.get('id','')).strip()}
            mil_sel_l = st.selectbox("Militar:", list(mil_opts_l.keys()), key="lic_mil")
            tipo_l = st.selectbox("Tipo:", ["Baixa", "Licença", "Outras Licenças", "Diligência", "Folga Complementar"], key="lic_tipo")
        with col_l2:
            ini_l = st.date_input("Data início:", format="DD/MM/YYYY", key="lic_ini")
            fim_l = st.date_input("Data fim:", format="DD/MM/YYYY", key="lic_fim")

        if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_lic"):
            try:
                sh_l = get_sheet()
                ws_l = sh_l.worksheet("Licenças")
                mid_l = mil_opts_l[mil_sel_l]
                ws_l.append_row([mid_l, tipo_l, ini_l.strftime('%d/%m/%Y'), fim_l.strftime('%d/%m/%Y')])
                load_licencas.clear()
                st.success("✅ Registo adicionado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

        # Remover registo
        if not df_lic_show.empty:
            st.markdown("---")
            st.markdown("#### 🗑️ Remover registo")
            col_id_l = 'id' if 'id' in df_lic_show.columns else df_lic_show.columns[0]
            col_tp_l = 'tipo' if 'tipo' in df_lic_show.columns else df_lic_show.columns[1]
            col_in_l = next((c for c in df_lic_show.columns if 'ini' in c.lower()), None)
            opts_rem_l = {f"{r[col_id_l]} -- {r[col_tp_l]} {r.get(col_in_l,'')}" : i
                          for i, (_, r) in enumerate(df_lic_show.iterrows())}
            rem_sel_l = st.selectbox("Registo:", list(opts_rem_l.keys()), key="lic_rem")
            if st.button("🗑️ Remover", key="btn_rem_lic", use_container_width=True):
                try:
                    sh_l = get_sheet()
                    ws_l = sh_l.worksheet("Licenças")
                    ws_l.delete_rows(opts_rem_l[rem_sel_l] + 2)  # +2 header+base0
                    load_licencas.clear()
                    st.success("✅ Removido!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # --- 📢 PUBLICAR ESCALA (ADMIN) ---
    elif menu == "📢 Publicar Escala":
        st.title("📢 Publicar Escala")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()
        dias_pub = load_dias_publicados()
        d_pub = st.date_input("Data:", format="DD/MM/YYYY", key="d_pub")
        aba_pub = d_pub.strftime("%d-%m")
        ja_publicado = aba_pub in dias_pub
        if ja_publicado:
            st.info(f"✅ Escala de **{d_pub.strftime('%d/%m/%Y')}** já está publicada.")
            if st.button("🔒 Despublicar", key="btn_despub", use_container_width=True):
                try:
                    sh_p = get_sheet()
                    ws_p = sh_p.worksheet("escala_publicada")
                    todos = ws_p.col_values(1)
                    if aba_pub in todos:
                        ws_p.delete_rows(todos.index(aba_pub) + 1)
                    load_dias_publicados.clear()
                    st.success("✅ Despublicado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        else:
            if st.button("📢 PUBLICAR ESCALA", key="btn_pub", use_container_width=True, type="primary"):
                try:
                    sh_p = get_sheet()
                    ws_p = sh_p.worksheet("escala_publicada")
                    ws_p.append_row([aba_pub])
                    load_dias_publicados.clear()
                    st.success(f"✅ Escala de **{d_pub.strftime('%d/%m/%Y')}** publicada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # --- 👤 GERIR UTILIZADORES (ADMIN) ---
    elif menu == "👤 Gerir Utilizadores":
        st.title("👤 Gerir Utilizadores")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()

        df_u_admin = load_utilizadores()
        if df_u_admin.empty:
            st.info("Sem utilizadores.")
        else:
            militares_opts_u = {
                f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})": r
                for _, r in df_u_admin.iterrows()
            }
            sel_u = st.selectbox("Selecionar militar:", list(militares_opts_u.keys()))
            row_u = militares_opts_u[sel_u]
            email_u = str(row_u.get('email', '')).strip()
            pin_atual = str(row_u.get('pin', '')).strip()
            tem_pin = bool(pin_atual and pin_atual != 'nan')
            estado_pin = "✅ PIN definido" if tem_pin else "❌ Sem PIN"
            st.info(f"**Email:** {email_u}  |  **PIN:** {estado_pin}")

            st.markdown("---")
            st.markdown("#### 🔑 Definir / Alterar PIN")
            with st.form("form_admin_pin"):
                novo_pin = st.text_input("Novo PIN (4 dígitos)", type="password", max_chars=4)
                conf_pin = st.text_input("Confirmar PIN", type="password", max_chars=4)
                if st.form_submit_button("💾 GUARDAR PIN", use_container_width=True):
                    if not novo_pin or not conf_pin:
                        st.warning("Preenche os dois campos.")
                    elif len(novo_pin) != 4 or not novo_pin.isdigit():
                        st.warning("O PIN deve ter exatamente 4 dígitos numéricos.")
                    elif novo_pin != conf_pin:
                        st.error("❌ Os PINs não coincidem.")
                    else:
                        # Verificar duplicado
                        pin_dup = False
                        for _, r_check in df_u_admin.iterrows():
                            if str(r_check.get('email', '')).strip().lower() == email_u.lower():
                                continue
                            if verificar_pin(novo_pin, str(r_check.get('pin', ''))):
                                pin_dup = True
                                break
                        if pin_dup:
                            st.error("❌ Este PIN já está a ser usado por outro militar.")
                        else:
                            try:
                                sh_u = get_sheet()
                                ws_u = sh_u.worksheet("utilizadores")
                                headers_u = [h.strip().lower() for h in ws_u.row_values(1)]
                                col_pin_u = headers_u.index('pin') + 1
                                col_email_u = headers_u.index('email') + 1
                                emails_col = ws_u.col_values(col_email_u)
                                linha_u = None
                                for i, ev in enumerate(emails_col):
                                    if ev.strip().lower() == email_u.lower():
                                        linha_u = i + 1
                                        break
                                if linha_u:
                                    h_u, salt_u = hash_pin(novo_pin)
                                    ws_u.update_cell(linha_u, col_pin_u, f"{h_u}:{salt_u}")
                                    load_utilizadores.clear()
                                    st.success(f"✅ PIN de **{row_u.get('nome','')}** atualizado!")
                                else:
                                    st.error("❌ Utilizador não encontrado na Sheet.")
                            except Exception as e:
                                st.error(f"Erro: {e}")

            if tem_pin:
                st.markdown("---")
                if st.button("🗑️ Remover PIN", use_container_width=True):
                    try:
                        sh_u = get_sheet()
                        ws_u = sh_u.worksheet("utilizadores")
                        headers_u = [h.strip().lower() for h in ws_u.row_values(1)]
                        col_pin_u = headers_u.index('pin') + 1
                        col_email_u = headers_u.index('email') + 1
                        emails_col = ws_u.col_values(col_email_u)
                        for i, ev in enumerate(emails_col):
                            if ev.strip().lower() == email_u.lower():
                                ws_u.update_cell(i + 1, col_pin_u, "")
                                load_utilizadores.clear()
                                st.success("✅ PIN removido.")
                                st.rerun()
                                break
                    except Exception as e:
                        st.error(f"Erro: {e}")
