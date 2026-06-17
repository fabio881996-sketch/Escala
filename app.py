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
import time

def norm(t):
    """Normaliza texto para comparação -- remove acentos e coloca em minúsculas."""
    return unicodedata.normalize('NFKD', str(t).lower()).encode('ascii', 'ignore').decode('ascii')

def norm_servico(s: str) -> str:
    """Normaliza nome de serviço para apresentação -- substitui termos antigos."""
    s = str(s).strip()
    for antigo, novo in [('Baixa', 'Convalescença'), ('Doente', 'Convalescença'),
                          ('baixa', 'convalescença'), ('doente', 'convalescença')]:
        s = s.replace(antigo, novo)
    return s

def _nc(s):
    """Normaliza nome de coluna -- remove acentos, strip, lower."""
    return unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii').strip().lower()

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
    """Migra o PIN de texto simples para hash."""
    try:
        h, salt = hash_pin(pin)
        pin_hash = f"{h}:{salt}"
        pg = get_pg_loader()
        if pg:
            df_u = pg.carregar_usuarios()
            if not df_u.empty and 'email' in df_u.columns:
                matches = df_u[df_u['email'].astype(str).str.lower().str.strip() == email.strip().lower()]
                if not matches.empty:
                    mid = str(matches.iloc[0]['id']).strip()
                    pg.actualizar_pin(mid, pin_hash)
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
IMPEDIMENTOS = ["férias", "licença", "convalescença", "diligência", "tribunal", "pronto", "secretaria", "inquérito", "outras licenças", "fcaa"]
IMPEDIMENTOS_PATTERN = '|'.join(IMPEDIMENTOS).lower()

# ============================================================
# 4. FUNÇÕES DE DADOS
# ============================================================
# ── PostgreSQL DataLoader ──────────────────────────────────
import os as _os

def _get_database_url():
    """Lê DATABASE_URL de variável de ambiente ou Streamlit secrets."""
    url = _os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            url = str(st.secrets["DATABASE_URL"])
        except Exception:
            pass
    return url

@st.cache_resource
def get_pg_loader():
    """DataLoader PostgreSQL — usado quando DATABASE_URL está definido."""
    try:
        _db_url = str(st.secrets["DATABASE_URL"])
    except Exception:
        _db_url = _os.environ.get("DATABASE_URL", "")
    if not _db_url:
        return None
    try:
        import sys as _sys
        _sys.path.insert(0, '/mount/src/escala')
        _os.environ["DATABASE_URL"] = _db_url
        from services.data_loader_pg import DataLoader as _DL_PG
        return _DL_PG()
    except Exception as _e:
        import traceback
        print(f"[PG ERROR] {_e}\n{traceback.format_exc()}")
        return None




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
    if 'serviço' in df.columns:
        df['serviço'] = df['serviço'].apply(norm_servico)
    if 'id' in df.columns:
        df['id'] = df['id'].str.split(r'[,;]')
        df = df.explode('id')
        df['id'] = df['id'].str.strip()
        df = df[df['id'] != ''].reset_index(drop=True)
    return df

def _df_from_values(vals) -> pd.DataFrame:
    """Converte get_all_values() para DataFrame normalizado -- mais rápido que get_all_records()."""
    if not vals or len(vals) < 2:
        return pd.DataFrame()
    hdrs = [str(h).strip().lower() for h in vals[0]]
    rows = []
    for row in vals[1:]:
        # Preencher colunas em falta com string vazia
        row_ext = list(row) + [''] * (len(hdrs) - len(row))
        rows.append({hdrs[i]: str(row_ext[i]).strip() for i in range(len(hdrs))})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.fillna("")
    if 'serviço' in df.columns:
        df['serviço'] = df['serviço'].apply(norm_servico)
    if 'id' in df.columns:
        df['id'] = df['id'].str.split(r'[,;]')
        df = df.explode('id')
        df['id'] = df['id'].str.strip()
        df = df[df['id'] != ''].reset_index(drop=True)
    return df

@st.cache_data(ttl=60)
def load_utilizadores() -> pd.DataFrame:
    """Carrega utilizadores do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_usuarios()
        except Exception as e:
            st.error(f"Erro PG utilizadores: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=30)
def load_trocas() -> pd.DataFrame:
    """Carrega trocas do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_trocas()
        except Exception as e:
            st.error(f"Erro PG trocas: {e}")
    return pd.DataFrame()


def invalidar_trocas():
    """Limpa cache de trocas."""
    load_trocas.clear()


@st.cache_data(ttl=60)
def load_lista_abas() -> list:
    """Devolve lista de abas do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_lista_abas()
        except Exception as e:
            st.error(f"Erro PG lista abas: {e}")
    return []


@st.cache_data(ttl=60)
def load_ordem_remunerados() -> pd.DataFrame:
    """Carrega ordem remunerados do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_ordem_remunerados()
        except Exception:
            pass
    return pd.DataFrame()


@st.cache_data(ttl=60)
def load_data(aba_nome: str) -> pd.DataFrame:
    """Carrega escala do dia do PostgreSQL."""
    import re as _re_ld
    if _re_ld.match(r'^\d{2}-\d{2}$', aba_nome.strip()):
        pg = get_pg_loader()
        if pg:
            try:
                return pg.carregar_escala(aba_nome)
            except Exception as e:
                st.error(f"Erro PG escala {aba_nome}: {e}")
    return pd.DataFrame()

def invalidar_trocas():
    """Limpa cache de trocas."""
    load_trocas.clear()

@st.cache_data(ttl=300)
def load_ferias(ano: int) -> pd.DataFrame:
    """Carrega férias do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_ferias(ano)
        except Exception as e:
            st.error(f"Erro PG ferias: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_licencas(ano: int) -> pd.DataFrame:
    """Carrega dispensas do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_licencas()
        except Exception as e:
            st.error(f"Erro PG licencas: {e}")
    return pd.DataFrame()

def militar_tem_dispensa_slot(mid: str, data, df_licencas: pd.DataFrame, servico: str, horario: str) -> bool:
    """Verifica se um militar tem dispensa de serviço/horário activa numa data.
    servico e horario são comparados com DISPENSA_SLOTS após normalização."""
    if df_licencas.empty: return False
    cols = df_licencas.columns.tolist()
    col_id  = 'id'   if 'id'   in cols else cols[0]
    col_tp  = 'tipo' if 'tipo' in cols else (cols[1] if len(cols)>1 else None)
    col_ini = next((c for c in cols if 'ini' in c.lower()), None)
    col_fim = next((c for c in cols if 'fim' in c.lower()), None)
    if not col_ini or not col_fim or not col_tp: return False

    data_date = data if hasattr(data, 'strftime') else datetime.strptime(str(data), '%d-%m').replace(year=datetime.now().year)
    if hasattr(data_date, 'date'): data_date = data_date.date()

    serv_n = norm(servico)
    hor_n  = str(horario).strip()

    linhas = df_licencas[df_licencas[col_id].astype(str).str.strip() == str(mid).strip()]
    for _, row in linhas.iterrows():
        tipo = str(row.get(col_tp, '')).strip()
        # Suportar múltiplos códigos separados por vírgula ex: "A1,PO2"
        codigos = [c.strip().upper() for c in tipo.replace(';', ',').split(',')]
        for codigo in codigos:
            if codigo not in DISPENSA_SLOTS: continue
            sv_slot, hr_slot = DISPENSA_SLOTS[codigo]
            if norm(sv_slot) != serv_n or hr_slot != hor_n: continue
            # Verificar datas
            ini_s = str(row.get(col_ini, '')).strip()
            fim_s = str(row.get(col_fim, '')).strip()
            if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan': continue
            try:
                if '/' in ini_s:
                    ini_d = datetime.strptime(ini_s, '%d/%m/%Y').date()
                    fim_d = datetime.strptime(fim_s, '%d/%m/%Y').date()
                else:
                    ano = data_date.year
                    ini_d = datetime.strptime(f"{ini_s}-{ano}", '%d-%m-%Y').date()
                    fim_d = datetime.strptime(f"{fim_s}-{ano}", '%d-%m-%Y').date()
                if ini_d <= data_date <= fim_d:
                    return True
            except:
                continue
    return False

def militar_de_licenca(mid: str, data, df_licencas: pd.DataFrame) -> str:
    """Devolve tipo de licença/baixa/diligência ou '' se não está. Formato: 'Tipo|observações'"""
    if df_licencas.empty: return ''
    cols = df_licencas.columns.tolist()
    col_id  = 'id'    if 'id'    in cols else cols[0]
    col_tp  = 'tipo'  if 'tipo'  in cols else (cols[1] if len(cols)>1 else None)
    col_ini = next((c for c in cols if 'ini' in c.lower()), None)
    col_fim = next((c for c in cols if 'fim' in c.lower()), None)
    col_obs = next((c for c in cols if 'obs' in c.lower()), None)
    if not col_ini or not col_fim: return ''

    data_date = data if hasattr(data, 'strftime') else datetime.strptime(str(data), '%d-%m').replace(year=datetime.now().year)
    if hasattr(data_date, 'date'): data_date = data_date.date()

    linhas = df_licencas[df_licencas[col_id].astype(str).str.strip() == str(mid).strip()]
    for _, row in linhas.iterrows():
        ini_s = str(row.get(col_ini, '')).strip()
        fim_s = str(row.get(col_fim, '')).strip()
        if not ini_s or not fim_s or ini_s == 'nan' or fim_s == 'nan': continue
        tipo = str(row.get(col_tp, 'Licença')).strip() if col_tp else 'Licença'
        # Ignorar entradas de dispensa de slot (A1, PO2, etc.)
        codigos = [c.strip().upper() for c in tipo.replace(';', ',').split(',')]
        if all(c in DISPENSA_SLOTS for c in codigos if c): continue
        try:
            if '/' in ini_s:
                ini_d = datetime.strptime(ini_s, '%d/%m/%Y').date()
                fim_d = datetime.strptime(fim_s, '%d/%m/%Y').date()
            else:
                ano = data_date.year
                ini_d = datetime.strptime(f"{ini_s}-{ano}", '%d-%m-%Y').date()
                fim_d = datetime.strptime(f"{fim_s}-{ano}", '%d-%m-%Y').date()
            if ini_d <= data_date <= fim_d:
                tipo = str(row.get(col_tp, 'Licença')).strip() if col_tp else 'Licença'
                obs  = str(row.get(col_obs, '') or '').strip() if col_obs else ''
                obs  = '' if obs == 'nan' else obs
                return f"{tipo}|{obs}" if obs else tipo
        except:
            continue
    return ''

@st.cache_data(ttl=3600)
def load_folgas(ano: int) -> pd.DataFrame:
    """Carrega folgas -- derivadas da escala no PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_folgas(ano)
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def load_grupos_folga() -> dict:
    """Carrega grupos de folga do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_grupos_folga()
        except Exception:
            pass
    return {}

@st.cache_data(ttl=120)
def load_dias_publicados() -> set:
    """Carrega dias publicados do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_dias_publicados()
        except Exception as e:
            st.error(f"Erro PG dias pub: {e}")
    return set()

@st.cache_data(ttl=300)
def load_servicos() -> dict:
    """Carrega serviços por militar do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_servicos()
        except Exception:
            pass
    return {}

@st.cache_data(ttl=300)
def load_listas() -> dict:
    """Carrega listas do PostgreSQL."""
    pg = get_pg_loader()
    if pg:
        try:
            return pg.carregar_listas()
        except Exception:
            pass
    return {}

@st.cache_data(ttl=86400)
def carregar_feriados(ano: int) -> list:
    """Carrega feriados -- lista fixos portugueses."""
    from datetime import date as _date
    return [
        _date(ano,1,1), _date(ano,4,25), _date(ano,5,1),
        _date(ano,6,10), _date(ano,8,15), _date(ano,10,5),
        _date(ano,11,1), _date(ano,12,1), _date(ano,12,8), _date(ano,12,25),
    ]

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


load_feriados = carregar_feriados


@st.cache_data(ttl=86400)
def contar_servicos_historico(alvo_id_c: str, sheet_id_c: str) -> pd.DataFrame:
    """Conta serviços históricos de um militar -- cache 24h."""
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
                vals = aba.get_all_values()
                df_aba = _df_from_values(vals)
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
                        'tipo': norm(serv)
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
    """Actualiza status de troca no PostgreSQL."""
    try:
        pg = get_pg_loader()
        if pg:
            # index_linha é o índice do DataFrame (0-based), id no PG pode ser diferente
            df_tr = load_trocas()
            if not df_tr.empty and 'id' in df_tr.columns:
                try:
                    troca_id = int(df_tr.iloc[index_linha]['id'])
                    pg.actualizar_status_troca(troca_id, novo_status)
                    pg.limpar_cache()
                    load_trocas.clear()
                    return True
                except Exception:
                    pass
        return False
    except Exception:
        return False
def salvar_troca_gsheet(linha: list) -> bool:
    """Adiciona uma nova linha de troca na Google Sheet."""
    try:
        _pg_tr2 = get_pg_loader()
        if _pg_tr2:
            try:
                _pg_tr2.guardar_troca({
                    "data": linha[0] if len(linha) > 0 else "",
                    "id_origem": linha[1] if len(linha) > 1 else "",
                    "servico_origem": linha[2] if len(linha) > 2 else "",
                    "id_destino": linha[3] if len(linha) > 3 else "",
                    "servico_destino": linha[4] if len(linha) > 4 else "",
                    "status": linha[5] if len(linha) > 5 else "Pendente_Militar",
                    "observacoes": linha[6] if len(linha) > 6 else "",
                    "data_pedido": linha[8] if len(linha) > 8 else "",
                })
                _pg_tr2.limpar_cache()
                load_trocas.clear()
            except Exception as _e_tr:
                st.error(f"Erro ao guardar troca: {_e_tr}")
                return False
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
    Atualiza o ordem_escala do dia seguinte no PostgreSQL.
    """
    try:
        pg = get_pg_loader()
        if not pg:
            return

        # Ler ordem base do próprio dia ou do anterior
        aba_ord_ant = (d_gerar - timedelta(days=1)).strftime('%d-%m')
        ordem = pg.carregar_ordem_escala(aba_dia)
        if not ordem:
            ordem = pg.carregar_ordem_escala(aba_ord_ant)
        if not ordem:
            return

        # Ler escala do dia para saber quem ficou escalado nos slots auto
        df_dia = load_data(aba_dia)
        ids_escalados = {}
        SLOTS_AUTO = [
            'Atendimento 00-08', 'Atendimento 08-16', 'Atendimento 16-24',
            'Patrulha Ocorrências 00-08', 'Patrulha Ocorrências 08-16', 'Patrulha Ocorrências 16-24',
            'Apoio Atendimento 08-16', 'Apoio Atendimento 16-24',
        ]
        if not df_dia.empty and 'serviço' in df_dia.columns:
            for _, row_d in df_dia.iterrows():
                sv = str(row_d.get('serviço', '')).strip()
                hor = str(row_d.get('horário', '')).strip()
                slot_key = f"{sv} {hor}".strip() if hor else sv
                for s in SLOTS_AUTO:
                    sv_s = s.rsplit(' ', 1)[0]
                    hor_s = s.rsplit(' ', 1)[1]
                    if sv.lower() == sv_s.lower() and hor == hor_s:
                        for mid in [m.strip() for m in str(row_d.get('id', '')).split(';') if m.strip()]:
                            if s not in ids_escalados:
                                ids_escalados[s] = []
                            if mid not in ids_escalados[s]:
                                ids_escalados[s].append(mid)

        # Mover escalados para o fim em cada slot
        nova_ordem = {}
        for slot, ids in ordem.items():
            escalados_slot = ids_escalados.get(slot, [])
            nao_escalados = [i for i in ids if i not in escalados_slot]
            nova_ordem[slot] = nao_escalados + escalados_slot

        # Guardar como ordem do dia seguinte
        nome_prox = (d_gerar + timedelta(days=1)).strftime('%d-%m')
        pg.guardar_ordem_escala(nome_prox, nova_ordem)

    except Exception as e:
        st.error(f"Erro ao actualizar ordem_escala: {e}")

def _atualizar_ordem_escala_em_cadeia(sh, aba_dia: str, d_gerar, max_dias=9):
    """Actualiza em cadeia os ordem_escala dos dias seguintes."""
    abas = load_lista_abas()
    _atualizar_ordem_escala_dia(sh, aba_dia, d_gerar)
    d_atual = d_gerar + timedelta(days=1)
    for _ in range(max_dias - 1):
        aba_atual = d_atual.strftime('%d-%m')
        if aba_atual not in abas:
            break
        _atualizar_ordem_escala_dia(sh, aba_atual, d_atual)
        d_atual += timedelta(days=1)


def _gerar_ordem_escala_dia_seguinte(sh, aba_dia: str, d_gerar):
    """Gera apenas o ordem_escala do dia seguinte."""
    _atualizar_ordem_escala_dia(sh, aba_dia, d_gerar)



def _rl_header(c_obj, titulo):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    c_obj.setFillColor(HexColor('#1a2b4a'))
    c_obj.rect(0, 267*mm, 210*mm, 30*mm, fill=1, stroke=0)
    c_obj.setFillColor(HexColor('#ffffff'))
    c_obj.setFont("Helvetica-Bold", 16)
    c_obj.drawCentredString(105*mm, 278*mm, titulo)

def guardar_pdf_drive(pdf_bytes: bytes, filename: str, folder_name: str = "Trocas GNR") -> str | None:
    """Guarda PDF no Google Drive. Devolve o link ou None se falhar."""
    try:
        import io, json, os
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload

        creds_raw = os.environ.get("GOOGLE_CREDENTIALS", "")
        if not creds_raw:
            return None
        info = json.loads(creds_raw)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds)

        # Procurar ou criar pasta
        q = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=q, fields="files(id)").execute()
        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            folder_meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
            folder = service.files().create(body=folder_meta, fields="id").execute()
            folder_id = folder["id"]

        # Upload do PDF
        file_meta = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
        f = service.files().create(body=file_meta, media_body=media, fields="id,webViewLink").execute()
        return f.get("webViewLink", "")
    except Exception:
        return None


def gerar_pdf_troca(dados: dict) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import base64 as _b64, tempfile as _tmp, os as _os, re as _re

    try:
        pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Italic', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'))
        fn, fn_bold, fn_it = 'DejaVu', 'DejaVu-Bold', 'DejaVu-Italic'
    except Exception:
        fn, fn_bold, fn_it = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'

    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    _cab_b64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/4QAiRXhpZgAATU0AKgAAAAgAAQESAAMAAAABAAEAAAAAAAD/2wBDAAIBAQIBAQICAgICAgICAwUDAwMDAwYEBAMFBwYHBwcGBwcICQsJCAgKCAcHCg0KCgsMDAwMBwkODw0MDgsMDAz/2wBDAQICAgMDAwYDAwYMCAcIDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAARCADrAY4DASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9/KKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKM0UAFFGaKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiijOaACiiigAooooAKKKKACiiigAooooAK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AAdfaj+0Va+CNP8ABXja0ubLwqfEy6rqd9p114bt7W6ma1/0y7RVuJxHdsXSSScEyMJGLa//AARy+Hfjj4dRfF4fFKw8Z2nxK8Rap4d1zXJ9Va+l0/UJZfCejRXEtrLITZs4v4dRikW1OY/JijYLElsoAPtiiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigArz3wJ+yz8OPhd8RNQ8XeHvBPhzRvEuqeeLjUbSySOc/aJRNcbSB8nnSqskmzHmOoZtzAGvQqKACiiigDH8beCNI+I3hi60XXtNs9X0m92+faXUYkim2uHXcp4OGVSPcCtiiigAryj4h/sQ/CT4qeLr3Xtf+HnhfUNY1Tb/aN0bNY5NUCqFAutmPtACgKBLuGBjpxXq9FAHl8v7GPwmm8Z6J4gHw58Hx6t4cjtYtMni0uKMWa2pJtdiKAn7gkmI4zET8m2vUKKKAMe78D6Pf+N9P8ST6daS69pNldabZX7Rg3FtbXMlvJcQo3UJI9pbMw7mBP7orYoooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//Z"
    try:
        _cab_bytes = _b64.b64decode(_cab_b64)
        with _tmp.NamedTemporaryFile(suffix='.jpg', delete=False) as _tf:
            _tf.write(_cab_bytes)
            _cab_path = _tf.name
        cab_w = 95*mm
        cab_h = cab_w * (235/398)
        cv.drawImage(_cab_path, 20*mm, h - 8*mm - cab_h, width=cab_w, height=cab_h, preserveAspectRatio=True)
        _os.unlink(_cab_path)
        titulo_x = 20*mm + cab_w + 10*mm
        titulo_y = h - 8*mm - cab_h/2
        cv.setFillColor(HexColor('#000000'))
        cv.setFont(fn_bold, 15)
        cv.drawString(titulo_x, titulo_y, "TROCA DE SERVIÇO")
        y = h - 8*mm - cab_h - 10*mm
    except Exception:
        cv.setFillColor(HexColor('#000000'))
        cv.setFont(fn_bold, 14)
        cv.drawCentredString(w/2, h - 20*mm, "TROCA DE SERVIÇO")
        y = h - 35*mm

    serv_orig = s(dados['serv_orig'])
    serv_dest = s(dados['serv_dest'])

    style = ParagraphStyle('body', fontName=fn, fontSize=11, leading=18)
    texto = (
        f"O militar <b>{s(dados['nome_origem'])}</b> (ID {s(dados['id_origem'])}), solicitou a "
        f"autorização para a troca do serviço <b>'{serv_orig}'</b> pelo serviço "
        f"<b>'{serv_dest}'</b> do militar <b>{s(dados['nome_destino'])}</b> "
        f"(ID {s(dados['id_destino'])}), para o dia <b>{s(dados['data'])}</b>."
    )
    p = Paragraph(texto, style)
    pw, ph = p.wrap(170*mm, h)
    p.drawOn(cv, 20*mm, y - ph)
    y -= ph + 10*mm

    # ── Confirmações ──────────────────────────────────────────
    cv.setFont(fn_bold, 10)
    cv.setFillColor(HexColor('#1a2b4a'))
    # ── Aviso serviços consecutivos ─────────────────────────────
    import re as _re2
    def _hor2(serv, grp):
        m = _re2.search(r'\((\d{2})-(\d{2})\)', str(serv))
        return int(m.group(grp)) if m else None
    _avisos = []
    if _hor2(serv_orig, 2) in (0, 24) and _hor2(serv_dest, 1) == 0:
        _avisos.append(f"Nota: <b>{s(dados['nome_origem'])}</b> ficará com serviços consecutivos: <b>{serv_orig}</b> seguido de <b>{serv_dest}</b>.")
    if _hor2(serv_dest, 2) in (0, 24) and _hor2(serv_orig, 1) == 0:
        _avisos.append(f"Nota: <b>{s(dados['nome_destino'])}</b> ficará com serviços consecutivos: <b>{serv_dest}</b> seguido de <b>{serv_orig}</b>.")
    if _avisos:
        style_av = ParagraphStyle('av', fontName=fn_bold, fontSize=10, leading=14, textColor=HexColor('#b45309'))
        for av in _avisos:
            cv.setFillColor(HexColor('#FFFBEB'))
            cv.setStrokeColor(HexColor('#f59e0b'))
            cv.setLineWidth(0.8)
            p_av = Paragraph(av, style_av)
            pw_av, ph_av = p_av.wrap(162*mm, h)
            cv.rect(20*mm, y - ph_av - 4*mm, 170*mm, ph_av + 8*mm, fill=1, stroke=1)
            p_av.drawOn(cv, 24*mm, y - ph_av - 1*mm)
            y -= ph_av + 14*mm


    cv.drawString(20*mm, y, "REGISTO DE CONFIRMAÇÕES")
    y -= 6*mm
    cv.setStrokeColor(HexColor('#1a2b4a'))
    cv.setLineWidth(0.8)
    cv.line(20*mm, y, w-20*mm, y)
    y -= 8*mm

    def _bloco(y, numero, titulo, nome, data, cor):
        bh = 22*mm
        cv.setFillColor(HexColor(cor))
        cv.rect(20*mm, y - bh, 170*mm, bh, fill=1, stroke=0)
        cv.setFillColor(HexColor('#1a2b4a'))
        cv.rect(20*mm, y - bh, 3*mm, bh, fill=1, stroke=0)
        cv.setFont(fn_bold, 14); cv.setFillColor(HexColor('#1a2b4a'))
        cv.drawString(26*mm, y - 14*mm, numero)
        cv.setFont(fn_bold, 9); cv.setFillColor(HexColor('#64748b'))
        cv.drawString(35*mm, y - 8*mm, titulo.upper())
        cv.setFont(fn_bold, 11); cv.setFillColor(HexColor('#1e293b'))
        cv.drawString(35*mm, y - 15*mm, nome)
        cv.setFont(fn_it, 9); cv.setFillColor(HexColor('#64748b'))
        cv.drawRightString(w - 22*mm, y - 15*mm, data if data else "—")
        return y - bh - 4*mm

    y = _bloco(y, "①", "Solicitante",
        f"{s(dados['nome_origem'])} (ID {s(dados['id_origem'])})",
        s(dados.get('data_pedido', '')), '#F8FAFC')
    y = _bloco(y, "②", "Aceite pelo militar de destino",
        f"{s(dados['nome_destino'])} (ID {s(dados['id_destino'])})",
        s(dados.get('data_aceitacao', '')), '#F0FDF4')
    y = _bloco(y, "③", "Autorizado superiormente",
        s(dados['validador']), s(dados['data_val']), '#EFF6FF')

    cv.setStrokeColor(HexColor('#cccccc'))
    cv.setLineWidth(0.5)
    cv.line(20*mm, 22*mm, w-20*mm, 22*mm)
    cv.setFont(fn_it, 8)
    cv.setFillColor(HexColor('#646464'))
    cv.drawRightString(w-20*mm, 15*mm, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    cv.save()
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

    df_aus,  df_rest = filtrar(r"ferias|licen|doente|folga|baixa|convalesc", df_raw_com)
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
        # Título sem linha inferior -- funde com conteúdo para bloco unificado
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        # Desenhar apenas topo + laterais (sem linha inferior)
        c.line(x, y, x+w, y)            # topo
        c.line(x, y, x, y-5.5*mm)       # esquerda
        c.line(x+w, y, x+w, y-5.5*mm)   # direita
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x+2*mm, y-4*mm, f"  {label.upper()}")
        # Linha subtil a separar título do conteúdo
        c.setStrokeColor(HexColor("#999999"))
        c.setLineWidth(0.4)
        c.line(x, y-5.5*mm, x+w, y-5.5*mm)
        return y - 6.5*mm

    def close_section(y_top, y_bottom, x=LM, w=TW):
        """Fecha o bloco da secção com borda exterior completa (título + conteúdo)."""
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.line(x, y_bottom, x+w, y_bottom)   # linha de fecho em baixo
        c.line(x, y_top, x, y_bottom)          # esquerda
        c.line(x+w, y_top, x+w, y_bottom)      # direita

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
    y_aus_top = y_col
    sec_title(y_col, "Ausências, Folgas e Licenças", x=LM, w=CW_ESQ)
    y_adm_top = y_col
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

    # Fechar blocos Ausências e ADM
    y_aus_bottom = min(y_esq, y_dir)
    close_section(y_aus_top, y_aus_bottom, x=LM, w=CW_ESQ)
    if grupos_adm:
        close_section(y_adm_top, y_aus_bottom, x=LM+CW_ESQ+GAP, w=CW_DIR)

    # Avançar y para o máximo das duas colunas
    y = y_aus_bottom - 2*mm

    # ---- ATENDIMENTO e APOIO lado a lado ----
    if not df_at.empty or not df_ap.empty:
        y_at = y
        y_at_top = y_at
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
            for hor, grp in df_at.assign(_hor_sort=df_at["horário"].str.extract(r"^(\d+)")[0].astype(float)).sort_values("_hor_sort").groupby("horário", sort=False):
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
            for hor, grp in df_ap.assign(_hor_sort=df_ap["horário"].str.extract(r"^(\d+)")[0].astype(float)).sort_values("_hor_sort").groupby("horário", sort=False):
                ids = ", ".join(grp["id_fmt"].tolist())
                y_dir2 = tbl_row(y_dir2, [hor, ids], wids_at_r, fill, x=x_dir2)
                fill = not fill

        y_at_bottom = min(y_esq2, y_dir2)
        if not df_at.empty:
            close_section(y_at_top, y_at_bottom, x=LM, w=CW2)
        if not df_ap.empty:
            close_section(y_at_top, y_at_bottom, x=LM+CW2+GAP, w=CW2)
        y = y_at_bottom - 2*mm

    # ---- PATRULHA OCORRÊNCIAS ----
    if not df_ocorr.empty:
        y_sec_top = y
        y = sec_title(y, "Patrulha Ocorrências")
        cols_oc = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"]
        _w = TW - 16*mm - 32*mm - 40*mm
        wids_oc = [16*mm, 32*mm, 40*mm, _w/3, _w/3, _w/3]
        y = tbl_header(y, cols_oc, wids_oc)
        fill = False
        for hor, grp in df_ocorr.assign(_hor_sort=df_ocorr["horário"].str.extract(r"^(\d+)")[0].astype(float)).sort_values("_hor_sort").groupby("horário", sort=False):
            ids  = ", ".join(grp["id_fmt"].tolist())
            def _v(col): return str(grp[col].iloc[0]).strip() if col in grp.columns else ""
            def _clean(v): return "" if v in ("nan", "None", "NaN") else v
            serv = grp["serviço"].iloc[0]
            ind  = _clean(_v("indicativo rádio"))
            rad  = _clean(_v("rádio"))
            vtr  = _clean(_v("viatura"))
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr], wids_oc, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        close_section(y_sec_top, y)
        y -= 2*mm

    # ---- PATRULHAS E POLICIAMENTO ----
    if not df_outras_pat.empty:
        y_sec_top = y
        y = sec_title(y, "Patrulhas e Policiamento")
        cols_pp = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura", "Giro"]
        _wp = TW - 16*mm - 32*mm - 34*mm - 14*mm
        wids_pp = [16*mm, 32*mm, 34*mm, _wp/3, _wp/3, _wp/3, 14*mm]
        y = tbl_header(y, cols_pp, wids_pp)
        fill = False
        for hor, grp in df_outras_pat.assign(_hor_sort=df_outras_pat["horário"].str.extract(r"^(\d+)")[0].astype(float)).sort_values("_hor_sort").groupby("horário", sort=False):
            ids  = ", ".join(grp["id_fmt"].tolist())
            serv = grp["serviço"].iloc[0]
            def _v(col): return str(grp[col].iloc[0]).strip() if col in grp.columns else ""
            def _clean(v): return "" if v in ("nan", "None", "NaN") else v
            ind  = _clean(_v("indicativo rádio"))
            rad  = _clean(_v("rádio"))
            vtr  = _clean(_v("viatura"))
            giro = _clean(_v("giro"))
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr, giro], wids_pp, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        close_section(y_sec_top, y)
        y -= 2*mm

    # ---- OUTROS SERVIÇOS ----
    if not df_outros.empty:
        y_sec_top = y
        y = sec_title(y, "Outros Serviços")
        cols_ot = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"]
        _wo = TW - 16*mm - 32*mm - 40*mm
        wids_ot = [16*mm, 32*mm, 40*mm, _wo/3, _wo/3, _wo/3]
        y = tbl_header(y, cols_ot, wids_ot)
        fill = False
        for (hor, serv), grp in df_outros.assign(_hor_sort=df_outros["horário"].str.extract(r"^(\d+)")[0].astype(float)).sort_values(["_hor_sort","serviço"]).groupby(["horário", "serviço"], sort=False):
            ids = ", ".join(grp["id_fmt"].tolist())
            def _clean(v): return "" if str(v).strip() in ("nan", "None", "NaN") else str(v).strip()
            ind = _clean(grp["indicativo rádio"].iloc[0]) if "indicativo rádio" in grp.columns else ""
            rad = _clean(grp["rádio"].iloc[0]) if "rádio" in grp.columns else ""
            vtr = _clean(grp["viatura"].iloc[0]) if "viatura" in grp.columns else ""
            y = tbl_row(y, [hor, ids, serv, ind, rad, vtr], wids_ot, fill)
            fill = not fill
            if y < 20*mm: y = new_page()
        close_section(y_sec_top, y)
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
        y_sec_top = y
        y = sec_title(y, "Serviços Remunerados / Gratificados")
        # Agrupar linhas por (horário+obs) para fundir célula -- preservar ordem original
        linhas_rem = []
        vistos = {}  # (hor, obs) -> já processado
        col_vtr = next((c for c in df_rem.columns if norm(c) == 'viatura'), None)
        for _, row in df_rem.iterrows():
            hor = str(row.get('horário', '')).strip()
            obs = str(row.get("observações", "")) if "observações" in df_rem.columns else ""
            if obs == 'nan': obs = ""
            chave = (hor, obs)
            if chave in vistos:
                continue
            vistos[chave] = True
            grp = df_rem[(df_rem['horário'] == hor)]
            if "observações" in df_rem.columns:
                grp = grp[grp['observações'].astype(str).str.strip().replace('nan','') == obs]
            ids = ", ".join(grp["id_fmt"].tolist())
            # Viatura -- concatenar viaturas distintas se houver mais que uma
            vtr = ""
            if col_vtr:
                vtr_vals = grp[col_vtr].dropna().astype(str).str.strip()
                vtr_vals = vtr_vals[vtr_vals.str.len() > 0].unique().tolist()
                vtr = " / ".join(vtr_vals) if vtr_vals else ""
            linhas_rem.append({'hor': hor, 'ids': ids, 'obs': obs, 'vtr': vtr})

        # Largura fixa para viatura -- viaturas múltiplas aparecem em linhas separadas
        _tem_dupla_vtr = any(' / ' in r['vtr'] for r in linhas_rem)
        _vtr_w = 20*mm if 'viatura' in df_rem.columns else 0
        _hor_w = 22*mm  # suficiente para 08:30-12:30
        wids_rm = [_hor_w, 35*mm, _vtr_w, TW-_hor_w-35*mm-_vtr_w]
        _obs_w = wids_rm[3]
        cols_rm = ["Horário", "Militares"] + (["Viatura"] if _vtr_w else []) + ["Observação"]
        y = tbl_header(y, cols_rm, wids_rm)
        fill = False

        x_obs_start = LM + wids_rm[0] + wids_rm[1] + _vtr_w + 2*mm
        x_obs_end   = LM + TW - 2*mm
        max_pts_rm  = x_obs_end - x_obs_start
        x_obs_col   = LM + wids_rm[0] + wids_rm[1] + _vtr_w

        # Calcular alturas e grupos de obs
        alturas = []
        for r in linhas_rem:
            obs_lines = wrap_text(r['obs'], max_pts_rm) if r['obs'] else [""]
            ids_lines = wrap_text(r['ids'], wids_rm[1] - 2*mm)
            vtr_lines = r['vtr'].split(' / ') if ' / ' in r['vtr'] else [r['vtr']]
            alturas.append(max(5*mm, max(len(obs_lines), len(ids_lines), len(vtr_lines)) * 5*mm))

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
            # Viatura -- uma por linha se dupla
            if _vtr_w:
                vtr_txt = r.get('vtr', '')
                vtr_lines = vtr_txt.split(' / ') if ' / ' in vtr_txt else [vtr_txt]
                c.setFont("Helvetica", 8.5)
                total_vtr_h = len(vtr_lines) * 5*mm
                y_vtr = y - (row_h_real - total_vtr_h) / 2 - 3.5*mm
                for li, vl in enumerate(vtr_lines):
                    c.drawCentredString(LM+wids_rm[0]+wids_rm[1]+_vtr_w/2, y_vtr - (li*5*mm), vl)
                c.setFont("Helvetica", 8.5)
            c.setStrokeColor(CINZA_LN)
            x_fim_esq = LM + wids_rm[0] + wids_rm[1] + _vtr_w
            # Linhas horizontais só até ao limite da área esquerda (não invadem a obs)
            c.line(LM, y, x_fim_esq, y)              # topo
            c.line(LM, y-row_h, x_fim_esq, y-row_h)  # fundo
            c.line(LM, y, LM, y-row_h)               # esquerda
            c.line(LM+wids_rm[0], y, LM+wids_rm[0], y-row_h)  # sep horário|militares
            if _vtr_w:
                c.line(LM+wids_rm[0]+wids_rm[1], y, LM+wids_rm[0]+wids_rm[1], y-row_h)  # sep militares|viatura
            y -= row_h

        # Agora desenhar as células de observação fundidas por cima
        for idx, (obs_txt, span_count, span_h) in obs_spans.items():
            if idx not in y_grupo:
                continue
            y_ini = y_grupo[idx]
            obs_lines_span = wrap_text(obs_txt, max_pts_rm) if obs_txt else [""]
            # Fundo branco da célula obs (apaga linhas horizontais que atravessaram)
            c.setFillColor(white)
            c.rect(x_obs_col, y_ini-span_h, _obs_w, span_h, fill=1, stroke=0)
            # Centrar texto verticalmente na célula fundida
            total_txt_h = len(obs_lines_span) * 5*mm
            y_texto = y_ini - (span_h - total_txt_h) / 2 - 3.5*mm
            c.setFillColor(black)
            c.setFont("Helvetica", 8.5)
            for li, obs_l in enumerate(obs_lines_span):
                c.drawString(x_obs_start, y_texto - (li * 5*mm), obs_l)
            # Linha vertical de separação + topo e fundo do grupo (sem horizontais internas)
            c.setStrokeColor(CINZA_LN)
            c.line(x_obs_col, y_ini, x_obs_col, y_ini-span_h)          # vertical esquerda
            c.line(x_obs_col, y_ini, LM+TW, y_ini)                      # topo
            c.line(x_obs_col, y_ini-span_h, LM+TW, y_ini-span_h)        # fundo
        close_section(y_sec_top, y)
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
        y_sec_top = y
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
        close_section(y_sec_top, y)
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
    """Remove linhas onde id ou serviço está vazio -- serviços sem militar escalado."""
    if df.empty:
        return df
    mask = df['id'].astype(str).str.strip().str.len() > 0 if 'id' in df.columns else pd.Series([True]*len(df))
    if 'serviço' in df.columns:
        mask = mask & (df['serviço'].astype(str).str.strip().str.len() > 0)
    return df[mask].copy()

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
    # Ordenar cronologicamente pelo início do horário
    df_sec = df_sec.copy()
    # Limpar 'nan' nas colunas extras antes de agrupar
    for col in ['indicativo rádio', 'rádio', 'viatura', 'giro', 'observações']:
        if col in df_sec.columns:
            df_sec[col] = df_sec[col].astype(str).replace({'nan': '', 'None': ''}).str.strip()
    df_sec['_hor_sort'] = pd.to_numeric(df_sec['horário'].str.extract(r'^(\d+)')[0], errors='coerce').fillna(99)
    df_sec = df_sec.sort_values(['_hor_sort', 'serviço'])
    st.markdown(_sec_header(titulo), unsafe_allow_html=True)
    if mostrar_extras:
        cols_ag = ['serviço', 'horário']
        for col in ['indicativo rádio', 'rádio', 'viatura', 'giro', 'observações']:
            if col in df_sec.columns and col not in excluir_cols:
                cols_ag.append(col)
        agg_dict: dict = {'id_disp': lambda x: ', '.join(x)}
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
        st.markdown("""
        <style>
        .stApp { background:#FFFFFF !important; }
        header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stStatusWidget"], #MainMenu { display:none !important; }
        .block-container { padding:2rem 1rem !important; max-width:480px !important; margin:0 auto !important; }
        </style>
        """, unsafe_allow_html=True)

        bloqueado = bool(st.session_state["pin_bloqueado_ate"] and datetime.now() < st.session_state["pin_bloqueado_ate"])
        is_desktop = st.session_state.get("_is_desktop", True)

        if is_desktop:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;padding:32px 0 24px 0;">
                <div style="font-size:2.8rem;margin-bottom:6px;">🚓</div>
                <div style="font-size:1.4rem;font-weight:800;color:#1A2B4A;margin-bottom:2px">Portal de Escalas</div>
                <div style="font-size:0.72rem;font-weight:600;color:#2563EB;text-transform:uppercase;margin-bottom:2px">Guarda Nacional Republicana</div>
                <div style="font-size:0.68rem;color:#64748B;margin-bottom:16px">Posto Territorial de Famalicão</div>
            </div>
            """, unsafe_allow_html=True)
            if st.session_state["pin_erro"]:
                st.error("PIN incorreto. Tenta novamente.")
            if bloqueado:
                resto = int((st.session_state["pin_bloqueado_ate"] - datetime.now()).total_seconds())
                st.error(f"🔒 Bloqueado. Aguarda {resto}s.")
            pin_input = st.text_input("PIN", type="password", max_chars=4,
                                      placeholder="Introduz o PIN", label_visibility="collapsed",
                                      key="pin_desktop_input")
            if st.button("ENTRAR", use_container_width=True, disabled=bloqueado):
                if len(str(pin_input)) == 4:
                    df_u = load_utilizadores()
                    user = None
                    for _, row_u in df_u.iterrows():
                        if verificar_pin(str(pin_input), str(row_u.get('pin', ''))):
                            user = row_u
                            break
                    if user is not None:
                        pin_guardado = str(user.get('pin', '')).strip()
                        if ':' not in pin_guardado or len(pin_guardado) <= 10:
                            migrar_pin_para_hash(str(user.get('email', '')), str(pin_input))
                        fazer_login(user, user['email'])
                        st.rerun(scope="app")
                    else:
                        st.session_state["pin_tentativas"] += 1
                        if st.session_state["pin_tentativas"] >= 3:
                            st.session_state["pin_bloqueado_ate"] = datetime.now() + timedelta(seconds=30)
                            st.session_state["pin_tentativas"] = 0
                        st.session_state["pin_erro"] = True
                        st.session_state["pin_buf"] = ""
                        st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📱 Usar keypad", use_container_width=True):
                st.session_state["_is_desktop"] = False
                st.rerun()
        else:
            st.markdown("""
            <style>
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
            if st.button("⌨️ Usar teclado", use_container_width=True):
                st.session_state["_is_desktop"] = True
                st.rerun()

    # ── MODO EMAIL/PASSWORD ── (removido -- login só por PIN)
    # ── MODO REGISTAR PIN ── (removido -- PINs criados pelos admins)



# ============================================================
# 8. APP PRINCIPAL (pós-login)
# ============================================================
else:
    # Arranque — essencial para sidebar e calendário do utilizador
    ano_atual    = datetime.now().year
    df_trocas    = load_trocas()         # badge pendentes
    df_util      = load_utilizadores()   # nome + is_admin
    feriados     = load_feriados(ano_atual)   # sidebar calendário
    df_ferias    = load_ferias(ano_atual)     # sidebar calendário
    df_folgas    = load_folgas(ano_atual)     # sidebar calendário
    grupos_folga = load_grupos_folga()        # sidebar calendário
    # df_licencas carregado lazy por menu

    u_id      = str(st.session_state['user_id'])
    u_nome    = st.session_state['user_nome']
    is_admin  = st.session_state.get("is_admin", False)

    # Bloquear acesso a não-admins
    if not is_admin:
        st.error("⛔ Acesso restrito a administradores.")
        st.info("📱 Aceda via Portal da Escala.")
        if st.button("🚪 Sair"):
            st.session_state.clear()
            st.rerun()
        st.stop()

    # Carregar dias publicados
    _dias_pub_global = load_dias_publicados()

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

        st.markdown("<p style='font-size:0.75rem;letter-spacing:0.08em;color:#94A3B8;margin:0 0 4px 0;'>MENU</p>", unsafe_allow_html=True)

        menu_opt = [
            "🔍 Escala Geral",
            "🏥 Dispensas",
            "📊 Estatísticas",
                                    "🚨 Alertas",
            "⚙️ Gerar Escala",
            "📢 Publicar Escala",
            "👤 Gerir Utilizadores",
        ]

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
                encontrou_algum = False

                # Carregar folgas para mostrar mesmo sem escala publicada
                df_folgas_me = load_folgas(ano_atual)
                grupos_me    = load_grupos_folga()
                feriados_me  = load_feriados(ano_atual)

                dias_sem_dados = 0
                for delta in range(30):
                    if dias_sem_dados >= 5:
                        break
                    dt = hj + timedelta(days=delta)
                    aba_dt = dt.strftime('%d-%m')
                    d_s = dt.strftime('%d/%m/%Y')
                    i = delta
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
                                st.markdown(f'<div class="card-servico card-rem"><p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#059669;">💶 Remunerado</span></p><h3>💰 {rr["serviço"]}</h3><p>🕒 {rr["horário"]}</p>{colegas_r_html}{matar_html_t}{obs_r_html}</div>', unsafe_allow_html=True)
                    else:
                        df_d = load_data(dt.strftime("%d-%m"))
                        if not df_d.empty:
                            # Suportar IDs agrupados (507;1185) e excluir remunerados como serviço principal
                            m = df_d[df_d['id'].astype(str).apply(lambda x: u_id in [i.strip() for i in re.split(r'[;,]+', x)])]
                            m = m[~m['serviço'].apply(norm).str.contains('remu|grat', na=False)]
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

                                # Verificar se tem remunerado no mesmo dia
                                df_rem_dia = df_d  # já carregado acima
                                cards_rem = []  # lista de (horario_inicio_min, html)
                                if not df_rem_dia.empty and 'serviço' in df_rem_dia.columns:
                                    # Remunerados escalados diretamente -- verificar se u_id está em qualquer linha (incluindo agrupadas)
                                    rem_mil = df_rem_dia[df_rem_dia['id'].astype(str).apply(
                                        lambda x: u_id in re.split(r'[;,]+', x)
                                    )]
                                    rem_mil = rem_mil[rem_mil['serviço'].apply(norm).str.contains('remu|grat', na=False)]
                                    # Remover duplicados por serviço+horário+viatura+obs (manter primeiro)
                                    dedup_cols = ['serviço','horário']
                                    for _dc in ['viatura','observações']:
                                        if _dc in rem_mil.columns:
                                            dedup_cols.append(_dc)
                                    rem_mil = rem_mil.drop_duplicates(subset=dedup_cols, keep='first').reset_index(drop=True)
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
                                        # Colegas no mesmo remunerado — filtrar por serviço+horário+viatura+obs
                                        serv_rr = str(rr['serviço']).strip().lower()
                                        hor_rr  = str(rr['horário']).strip()
                                        obs_rr  = str(rr.get('observações','')).strip().lower()
                                        vtr_rr  = str(rr.get('viatura','')).strip().lower()
                                        mask_colegas = (
                                            (df_rem_dia['serviço'].astype(str).str.strip().str.lower() == serv_rr) &
                                            (df_rem_dia['horário'].astype(str).str.strip() == hor_rr) &
                                            (df_rem_dia['id'].astype(str).str.strip() != u_id) &
                                            (df_rem_dia['id'].astype(str).str.strip() != '') &
                                            (df_rem_dia['id'].astype(str).str.strip() != 'nan')
                                        )
                                        # Se há viatura definida, filtrar também por viatura
                                        if vtr_rr:
                                            mask_colegas = mask_colegas & (df_rem_dia['viatura'].astype(str).str.strip().str.lower() == vtr_rr)
                                        # Se há obs definida, filtrar também por obs
                                        if obs_rr:
                                            mask_colegas = mask_colegas & (df_rem_dia['observações'].astype(str).str.strip().str.lower() == obs_rr)
                                        colegas_rem = df_rem_dia[mask_colegas]
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
                                        _html_rem = (
                                            f'<div class="card-servico card-rem">'
                                            f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#059669;">💶 Remunerado</span></p>'
                                            f'<h3>💰 {rr["serviço"]}</h3>'
                                            f'<p>🕒 {rr["horário"]}</p>'
                                            f'{colegas_rem_html}'
                                            f'{matar_html}'
                                            f'{obs_r_html}'
                                            f'</div>'
                                        )
                                        _ini_rem, _ = _parse_horario(str(rr['horário']))
                                        cards_rem.append((_ini_rem if _ini_rem is not None else 9999, _html_rem))
                                # Ordenar e renderizar remunerados — antes ou depois do serviço principal
                                _hor_principal, _ = _parse_horario(str(row['horário']))
                                _hor_principal = _hor_principal if _hor_principal is not None else 9999
                                for _ini_r, _html_r in sorted(cards_rem):
                                    if _ini_r < _hor_principal:
                                        st.markdown(_html_r, unsafe_allow_html=True)
                                # Mostrar serviço principal
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
                                for _ini_r, _html_r in sorted(cards_rem):
                                    if _ini_r >= _hor_principal:
                                        st.markdown(_html_r, unsafe_allow_html=True)
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
                            # Escala não publicada -- verificar folgas no mapa
                            tipo_folga_me = militar_de_folga(u_id, dt.date(), df_folgas_me, grupos_me, feriados_me)
                            if tipo_folga_me:
                                icone_folga = '😴' if 'semanal' in tipo_folga_me.lower() else '😴'
                                st.markdown(
                                    f'<div class="card-servico card-folga">'
                                    f'<p><b>{lbl}</b></p>'
                                    f'<h3>{icone_folga} {tipo_folga_me}</h3>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                encontrou_algum = True
                                dias_sem_dados = 0
                            else:
                                dias_sem_dados += 1

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
                            # Dias corridos: incluir fins de semana/feriados após o último dia
                            fim_ext = fim_d
                            while True:
                                prox = fim_ext + timedelta(days=1)
                                if prox.weekday() >= 5 or prox in fer_tab:
                                    fim_ext = prox
                                else:
                                    break
                            dc = (fim_ext - ini_d).days + 1
                            periodos_ft.append((ini_d, fim_d, du, dc))
                        total_du_ft = sum(p[2] for p in periodos_ft)

                        # Exportar férias para calendário -- em cima
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
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
        df_folgas = load_folgas(ano_atual)
        df_licencas = load_licencas(ano_atual)
        grupos_folga = load_grupos_folga()
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
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
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
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
        df_folgas = load_folgas(ano_atual)
        df_licencas = load_licencas(ano_atual)
        grupos_folga = load_grupos_folga()
        st.title("🔍 Escala Geral")

        if is_admin:
            tab_eg, tab_hist_serv = st.tabs(["📅 Escala do Dia", "🔎 Historial por Serviço"])
        else:
            tab_eg = st.container()
            tab_hist_serv = None

        with tab_eg:
            d_sel  = st.date_input("Seleciona a data:", format="DD/MM/YYYY")
            aba_sel = d_sel.strftime("%d-%m")

        # Só ver dias publicados (admins incluídos)
        if aba_sel not in _dias_pub_global:
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
                            ids_na_escala.add(mid_f)

                # Adicionar militares de folga que não estão na escala diária
                if not df_folgas.empty and not df_util.empty:
                    ids_na_escala = set(df_at['id'].astype(str).str.strip().tolist())
                    grupos_folga_g = load_grupos_folga()
                    for _, row_u in df_util.iterrows():
                        mid_u = str(row_u.get('id', '')).strip()
                        if not mid_u or mid_u in ids_na_escala:
                            continue
                        tipo_folga_g = militar_de_folga(mid_u, d_sel, df_folgas, grupos_folga_g, feriados)
                        if tipo_folga_g:
                            nova_linha = {c: '' for c in df_at.columns}
                            nova_linha['id'] = mid_u
                            nova_linha['id_disp'] = mid_u
                            nova_linha['serviço'] = tipo_folga_g
                            nova_linha['horário'] = ''
                            df_at = pd.concat([df_at, pd.DataFrame([nova_linha])], ignore_index=True)
                            ids_na_escala.add(mid_u)

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
                df_aus, df_res = filtrar_secao(["férias", "licença", "convalescença"], df_at)

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
                    # Limpar nan nas colunas antes de agrupar
                    df_remu = df_remu.copy()
                    for col in ['viatura', 'observações', 'giro']:
                        if col in df_remu.columns:
                            df_remu[col] = df_remu[col].astype(str).replace({'nan': '', 'None': ''}).str.strip()
                    # Agrupar por horário + viatura + obs (campos distintivos)
                    cols_rem = ['horário']
                    for c in ['viatura', 'observações']:
                        if c in df_remu.columns:
                            cols_rem.append(c)
                    rows_rem = []
                    for chave_rem, grp_rem in df_remu.sort_values('horário').groupby(cols_rem, sort=False):
                        if not isinstance(chave_rem, tuple):
                            chave_rem = (chave_rem,)
                        hor = chave_rem[0]
                        vtr = chave_rem[1] if len(chave_rem) > 1 else ''
                        obs = chave_rem[2] if len(chave_rem) > 2 else ''
                        if str(vtr) == 'nan': vtr = ''
                        if str(obs) == 'nan': obs = ''
                        ids = ', '.join(grp_rem['id_disp'].tolist())
                        rows_rem.append({'horário': hor, 'militares': ids, 'vtr': str(vtr), 'obs': str(obs)})

                    # Calcular rowspans por obs -- apenas blocos CONSECUTIVOS
                    obs_spans = {}
                    i = 0
                    while i < len(rows_rem):
                        obs_atual = rows_rem[i]['obs']
                        j = i + 1
                        if obs_atual:  # só fundir se obs não vazia
                            while j < len(rows_rem) and rows_rem[j]['obs'] == obs_atual:
                                j += 1
                        obs_spans[i] = (obs_atual, j - i)
                        i = j
                    obs_first = obs_spans  # {idx_inicio: (obs, count)}

                    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;border-bottom:2px solid {AZUL};"
                    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-bottom:1px solid #dde6f7;"
                    td_a = td_s + f"background:{AZUL_CLARO};"
                    td_hor = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-bottom:1px solid #dde6f7;white-space:nowrap;"
                    td_hor_a = td_hor + f"background:{AZUL_CLARO};"
                    # Célula obs sem border-bottom para não criar divisões dentro do rowspan
                    td_obs = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-left:2px solid {AZUL_MED};"

                    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;margin-bottom:2px'>"
                    html += "<table style='width:100%;border-collapse:collapse;'><thead><tr>"
                    html += f"<th style='{th_s}'>Horário</th><th style='{th_s}'>Militares</th><th style='{th_s}'>Viatura</th><th style='{th_s}'>Observação</th>"
                    html += "</tr></thead><tbody>"
                    for i, r in enumerate(rows_rem):
                        td = td_a if i % 2 == 0 else td_s
                        td_h = td_hor_a if i % 2 == 0 else td_hor
                        html += "<tr>"
                        html += f"<td style='{td_h}'>{r['horário']}</td>"
                        html += f"<td style='{td}'>{r['militares']}</td>"
                        html += f"<td style='{td}'>{r.get('vtr', '')}</td>"
                        if i in obs_first:
                            obs_txt, span = obs_first[i]
                            html += f"<td style='{td_obs}' rowspan='{span}'>{obs_txt}</td>"
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
                    _df_serv_h = pd.DataFrame()  # Serviços carregados do PG
                    serv_vals_h = []
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
                            pass  # histórico no PG
                            # Ordenar abas do mais recente para o mais antigo
                            abas_h = sorted(
                                [t for t in load_lista_abas() if re.match(r'^\d{2}-\d{2}$', t)],
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
    elif menu == "🔄 Giros":
        st.title("🔄 Giros")
        df_giros = load_utilizadores()
        if df_giros.empty or "giro" not in df_giros.columns:
            st.info("Sem dados de giros.")
        else:
            df_giros = df_giros[df_giros["giro"].astype(str).str.strip().isin(["I","II","III","IV"])]
            pesq_g = st.text_input("🔍 Pesquisar:", placeholder="nome, giro...")
            df_g = df_giros.copy()
            if pesq_g:
                p_g = pesq_g.lower()
                df_g = df_g[df_g.apply(lambda r: p_g in str(r.get("nome","")).lower() or p_g in str(r.get("giro","")).lower(), axis=1)]
            if df_g.empty:
                st.info("Sem resultados.")
            else:
                for giro in sorted(df_g["giro"].unique()):
                    st.markdown(f"**Giro {giro}**")
                    df_g_g = df_g[df_g["giro"] == giro][["id","posto","nome"]]
                    st.dataframe(df_g_g, use_container_width=True, hide_index=True)


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
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
        df_folgas = load_folgas(ano_atual)
        df_licencas = load_licencas(ano_atual)
        grupos_folga = load_grupos_folga()
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

            while dias_sem < 2 and j < 10:
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
                            if ini_h is None: continue
                            for _, ra in rows_a.iterrows():
                                _, fim_a = _parse_horario(ra['horário'])
                                if fim_a is None: continue
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
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
        df_folgas = load_folgas(ano_atual)
        df_licencas = load_licencas(ano_atual)
        grupos_folga = load_grupos_folga()
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
                _pg_conf = get_pg_loader()
                from collections import defaultdict
                for idx_res, res in enumerate(resultados_c):
                    aba_r = res['aba']
                    escalados_r = res['escalados']
                    ordem_r = res['ordem_atualizada']
                    data_r = res['data']

                    # Guardar escala no PostgreSQL
                    df_escala_r = res.get('df_escala')
                    if df_escala_r is not None and not df_escala_r.empty:
                        _pg_conf.guardar_escala(aba_r, df_escala_r)

                    # Actualizar ordem_escala do dia seguinte
                    nome_prox = (data_r + timedelta(days=1)).strftime('%d-%m')
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
                    ordem_base = {h: list(v) for h, v in ordem_r.items()}
                    ids_auto_r = set(m for m, _, _ in escalados_r)
                    for col_key_p, lista_p in ordem_base.items():
                        for mid_p in list(ids_auto_r):
                            if mid_p in lista_p:
                                lista_p.remove(mid_p)
                                lista_p.append(mid_p)
                    _pg_conf.guardar_ordem_escala(nome_prox, ordem_base)

                load_data.clear()
                del st.session_state['escala_gerada_multi']
                st.session_state['escala_ok'] = True
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao escrever: {e}")

        # ── Selecionar data(s) ──
        tab_auto, tab_editar, tab_rem = st.tabs(["⚙️ Escala Automática", "✏️ Editar Escala", "💶 Remunerados"])

        with tab_auto:
            d_gerar = st.date_input("Data a escalar:", format="DD/MM/YYYY", key="d_gerar_input")
            aba_dia = d_gerar.strftime("%d-%m")

            # ── Carregar serviços por militar ──
            militares_servicos = load_servicos()
            serv_headers = list(set(s for servs in militares_servicos.values() for s in servs))
            todos_servicos = [''] + sorted(set(serv_headers))

            # ── Botão para carregar/resetar tabela ──
            if st.button("📋 Carregar tabela do dia", key="btn_carregar_tabela", use_container_width=True):
                # Ler escala do dia do PostgreSQL — IDs múltiplos já estão separados
                mapa_existente = {}
                try:
                    df_tab = load_data(aba_dia)
                    if not df_tab.empty:
                        vals_tab_rows = []
                        # Simular formato vals_tab para reutilizar código abaixo
                        for _, row_t2 in df_tab.iterrows():
                            vals_tab_rows.append(row_t2.to_dict())
                        # Construir mapa_existente directamente do DataFrame
                        for row_t2 in vals_tab_rows:
                            id_raw = str(row_t2.get('id', '')).strip()
                            if not id_raw: continue
                            sv_t = str(row_t2.get('serviço', '')).strip()
                            if not sv_t: continue
                            dados_t = {
                                'serviço': sv_t,
                                'horário': str(row_t2.get('horário', '')).strip(),
                                'indicativo': str(row_t2.get('indicativo rádio', '')).strip(),
                                'rádio': str(row_t2.get('rádio', '')).strip(),
                                'giro': str(row_t2.get('giro', '')).strip(),
                                'viatura': str(row_t2.get('viatura', '')).strip(),
                                'observações': str(row_t2.get('observações', '')).strip(),
                            }
                            e_remun = bool(re.search(r'remun|gratif', norm(sv_t)))
                            ids_linha = [m.strip() for m in re.split(r'[;,\n]+', id_raw) if m.strip()]
                            if len(ids_linha) > 1 and e_remun:
                                chave = id_raw.strip()
                                if chave not in mapa_existente:
                                    mapa_existente[chave] = []
                                mapa_existente[chave].append(dados_t)
                            else:
                                for mid in ids_linha:
                                    if mid:
                                        if mid not in mapa_existente:
                                            mapa_existente[mid] = []
                                        mapa_existente[mid].append(dados_t)

                except Exception as e_tab:
                    st.error(f"Erro ao carregar tabela: {e_tab}")

                linhas = []
                # Primeiro adicionar linhas com múltiplos IDs e serviço REMUNERADO (não expandir)
                linhas_rem_multi_adicionadas = set()
                for chave, lista_dados in mapa_existente.items():
                    if ';' in chave or ',' in chave:
                        for d_multi in lista_dados:
                            if re.search(r'remun|gratif', norm(d_multi.get('serviço',''))):
                                chave_unica = f"{chave}|{d_multi.get('serviço','')}|{d_multi.get('horário','')}"
                                if chave_unica not in linhas_rem_multi_adicionadas:
                                    linhas_rem_multi_adicionadas.add(chave_unica)
                                    linhas.append({
                                        'id': chave, 'nome': chave,
                                        'serviço': d_multi['serviço'], 'horário': d_multi['horário'],
                                        'indicativo': d_multi['indicativo'], 'rádio': d_multi['rádio'],
                                        'giro': d_multi['giro'], 'viatura': d_multi.get('viatura',''),
                                        'observações': d_multi['observações'],
                                    })

                for _, row_u in df_util.iterrows():
                    mid = str(row_u.get('id', '')).strip()
                    if not mid or mid == 'nan':
                        continue
                    nome  = str(row_u.get('nome', '')).strip()
                    posto = str(row_u.get('posto', '')).strip()
                    # Filtrar militares de férias e dispensas (não mostrar na tabela)
                    if militar_de_ferias(mid, d_gerar, df_ferias, feriados):
                        continue
                    if militar_de_licenca(mid, d_gerar, df_licencas):
                        continue
                    # Dados existentes, folgas, serviço por defeito ou vazio
                    if mid in mapa_existente:
                        lista_dados = mapa_existente[mid]
                        # Separar remunerados dos serviços normais
                        servs_normais = [d for d in lista_dados if not re.search(r'remu|grat', norm(d.get('serviço','')))]
                        servs_rem     = [d for d in lista_dados if re.search(r'remu|grat', norm(d.get('serviço','')))]
                        # Usar o serviço normal como principal
                        if servs_normais:
                            dados = servs_normais[0]
                        else:
                            # Só tem remunerado — linha principal fica vazia (para escalamento)
                            dados = {'serviço': '', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        # Se sem serviço, verificar folgas e por defeito
                        if not str(dados.get('serviço','')).strip() or str(dados.get('serviço','')).strip() == 'nan':
                            tipo_folga = militar_de_folga(mid, d_gerar, df_folgas, grupos_folga, feriados)
                            if tipo_folga:
                                dados = {**dados, 'serviço': tipo_folga}
                            elif not df_folgas.empty and 'serviço' in df_folgas.columns:
                                col_id_f = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
                                linha_f = df_folgas[df_folgas[col_id_f].astype(str).str.strip() == mid]
                                if not linha_f.empty:
                                    sv_f = str(linha_f.iloc[0].get('serviço', '')).strip()
                                    if sv_f and sv_f != 'nan':
                                        dados = {**dados, 'serviço': sv_f}
                        # Adicionar linha principal (serviço normal ou vazio)
                        linhas.append({
                            'id': mid, 'nome': f"{posto} {nome}".strip(),
                            'serviço': dados['serviço'], 'horário': dados['horário'],
                            'indicativo': dados['indicativo'], 'rádio': dados['rádio'],
                            'giro': dados['giro'], 'viatura': dados.get('viatura',''), 'observações': dados['observações'],
                        })
                        # Não adicionar remunerados individuais — ficam na linha multi-ID
                        continue  # já adicionou as linhas
                    else:
                        tipo_folga = militar_de_folga(mid, d_gerar, df_folgas, grupos_folga, feriados)
                        if tipo_folga:
                            dados = {'serviço': tipo_folga, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        else:
                            # Serviço por defeito da coluna 'serviço' em folgas_2026 (ex: Pronto, Inquéritos)
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
                        'viatura':     dados.get('viatura',''),
                        'observações': dados['observações'],
                    })

                st.session_state['tabela_escala'] = linhas
                st.session_state['tabela_dia'] = aba_dia
                st.rerun()

            # ── Mostrar tabela editável ──
            if 'tabela_escala' in st.session_state and st.session_state.get('tabela_dia') == aba_dia:
                linhas = st.session_state['tabela_escala']

                col_cnt1, col_cnt2 = st.columns(2)
                with col_cnt1:
                    st.markdown(f"**{len(linhas)} militares — {d_gerar.strftime('%d/%m/%Y')}**")
                with col_cnt2:
                    n_disponiveis = sum(1 for l in linhas if not str(l.get('serviço','')).strip() or str(l.get('serviço','')).strip() == 'nan')
                    st.markdown(f"**{n_disponiveis} disponíveis**")
                if 'debug_confirmar' in st.session_state:
                    st.warning(f"🔍 {st.session_state.pop('debug_confirmar')}")
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

                # Opções de serviço -- abreviaturas + todos os serviços das listas
                _extras_listas = [s for s in (_listas_auto.get('Serviço', []) or [])
                                  if s and s not in ('','Atendimento','Patrulha Ocorrências','Apoio Atendimento')]
                _sv_opts_abrev = ['', 'A1','A2','A3','PO1','PO2','PO3','AA2','AA3'] + _extras_listas


                # Aplicar abreviaturas no df_edit para display
                # Mapeamento normalizado para converter serviço+horário → abreviatura
                _abrev_norm = {f"{norm(k.rsplit(' ',1)[0])} {k.rsplit(' ',1)[1]}": v for k, v in _abrev.items()}
                def _to_abrev(serv, hor):
                    chave_norm = f"{norm(serv)} {hor}".strip()
                    return _abrev_norm.get(chave_norm, serv)

                # Se há edições pendentes do data_editor (chave no session_state), aplicar ao tabela_escala
                _editor_key = "editor_escala"
                if _editor_key in st.session_state and pesq.strip():
                    _editor_state = st.session_state.get(_editor_key, {})
                    if _editor_state and 'edited_rows' in _editor_state:
                        _tabela_atual = st.session_state.get('tabela_escala', linhas)
                        _df_temp = pd.DataFrame(_tabela_atual)
                        for _idx_str, _changes in _editor_state['edited_rows'].items():
                            # idx no df_edit_show filtrado
                            pass  # será tratado pela fusão abaixo

                df_edit_abrev = df_edit.copy()
                df_edit_abrev['serviço'] = df_edit.apply(lambda r: _to_abrev(str(r['serviço']).strip(), str(r['horário']).strip()), axis=1)
                # Não limpar horário -- fica visível para edição

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
                    height=min(50 + len(df_edit_show) * 35, 2000),
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

                # Guardar edições no session_state para persistir durante pesquisa
                if pesq.strip():
                    # Só atualizar as linhas que foram editadas (visíveis na pesquisa)
                    tabela_atual = st.session_state.get('tabela_escala', linhas)
                    tabela_df = pd.DataFrame(tabela_atual)
                    for _, row_ed in df_editado_show.iterrows():
                        mid_ed = str(row_ed['id']).strip()
                        idx_t = tabela_df[tabela_df['id'].astype(str).str.strip() == mid_ed].index
                        if len(idx_t) > 0:
                            i_t = idx_t[0]
                            # Aplicar conversão de abreviatura
                            sv_t = str(row_ed.get('serviço','')).strip()
                            hor_t = str(row_ed.get('horário','')).strip()
                            if sv_t in _abrev_hor:
                                serv_r, hor_r = _abrev_hor[sv_t]
                                tabela_df.at[i_t, 'serviço'] = serv_r
                                if not hor_t or hor_t == 'nan':
                                    tabela_df.at[i_t, 'horário'] = hor_r
                                else:
                                    tabela_df.at[i_t, 'horário'] = hor_t
                            else:
                                tabela_df.at[i_t, 'serviço'] = sv_t
                                tabela_df.at[i_t, 'horário'] = hor_t
                            for col_t in ['indicativo','rádio','giro','viatura','observações']:
                                if col_t in row_ed.index:
                                    tabela_df.at[i_t, col_t] = row_ed[col_t]
                    st.session_state['tabela_escala'] = tabela_df.to_dict('records')

                col_g1, col_g2, col_g3 = st.columns(3)

                # ── Botão Limpar ──
                with col_g3:
                    if st.button("🗑️ Limpar escala", use_container_width=True, key="btn_limpar_escala"):
                        linhas_atuais = st.session_state.get('tabela_escala', [])
                        _serv_manter = {'férias', 'folga semanal', 'folga complementar'}
                        _serv_remover = {'remu', 'grat'}  # remover remunerados
                        # Remover duplicados por mid (remunerados duplicam o militar)
                        mids_vistos = set()
                        linhas_limpas = []
                        for row_l in linhas_atuais:
                            sv_l = str(row_l.get('serviço', '')).strip().lower()
                            mid_l = str(row_l.get('id', '')).strip()
                            # Remover linhas de remunerado
                            if any(x in sv_l for x in _serv_remover):
                                continue
                            # Evitar duplicados do mesmo militar
                            if mid_l in mids_vistos:
                                continue
                            mids_vistos.add(mid_l)
                            if sv_l in _serv_manter:
                                linhas_limpas.append(row_l)
                            else:
                                tipo_folga_l = militar_de_folga(mid_l, d_gerar, df_folgas, grupos_folga, feriados)
                                if tipo_folga_l:
                                    linhas_limpas.append({**row_l, 'serviço': tipo_folga_l, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''})
                                else:
                                    serv_def_l = ''
                                    if not df_folgas.empty and 'serviço' in df_folgas.columns:
                                        col_id_fl = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
                                        linha_fl = df_folgas[df_folgas[col_id_fl].astype(str).str.strip() == mid_l]
                                        if not linha_fl.empty:
                                            sv_fl = str(linha_fl.iloc[0].get('serviço', '')).strip()
                                            if sv_fl and sv_fl != 'nan': serv_def_l = sv_fl
                                    linhas_limpas.append({**row_l, 'serviço': serv_def_l, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''})
                        st.session_state['tabela_escala'] = linhas_limpas
                        st.session_state.pop('ordem_gerada', None)
                        st.rerun()

                # ── Botão Gerar Escala Automática ──
                with col_g1:
                    if st.button("⚙️ Gerar escala automática", use_container_width=True, key="btn_gerar_auto"):
                        with st.spinner("A gerar..."):
                            try:
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
                                    serv_norm = norm(serv)
                                    # Remunerados não impedem de ser escalado noutro serviço
                                    if serv and serv != 'nan' and not any(x in serv_norm for x in ['remu','grat']):
                                        ids_indisponiveis.add(mid)

                                # Carregar ordem_escala do PostgreSQL
                                _pg_g = get_pg_loader()
                                ordem_g = _pg_g.carregar_ordem_escala(aba_dia)
                                if not ordem_g:
                                    aba_ordem_ant = (d_gerar - timedelta(days=1)).strftime('%d-%m')
                                    ordem_g = _pg_g.carregar_ordem_escala(aba_ordem_ant)
                                if not ordem_g:
                                    st.error(f"Não encontrei ordem_escala para {aba_dia} no PostgreSQL. Precisa de migrar os dados da ordem_escala do Sheets.")
                                    st.stop()

                                df_ant_g2 = load_data((d_gerar - timedelta(days=1)).strftime("%d-%m"))

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


                                ids_escalados_g = set()
                                novas_linhas = {str(row_e['id']): dict(row_e) for _, row_e in df_editado.iterrows()}

                                # ── Regra da Secretaria ──────────────────────────────────
                                # Identificar militares da secretaria
                                ids_secretaria = set()
                                if not df_folgas.empty and 'serviço' in df_folgas.columns:
                                    col_id_f = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
                                    for _, row_f in df_folgas.iterrows():
                                        if norm(str(row_f.get('serviço', ''))) == 'secretaria':
                                            ids_secretaria.add(str(row_f.get(col_id_f, '')).strip())

                                # Contar secretaria disponíveis nesse dia
                                # (não ausentes, não já indisponíveis por dispensa/férias)
                                sec_disponiveis = set()
                                for mid_s in ids_secretaria:
                                    if mid_s in ids_indisponiveis: continue
                                    if militar_tem_dispensa_slot(mid_s, d_gerar, df_licencas, 'Secretaria', ''): continue
                                    if militar_de_ferias(mid_s, d_gerar, df_ferias, feriados): continue
                                    sec_disponiveis.add(mid_s)

                                # Tem de ficar sempre 1 na secretaria
                                # O primeiro a ser escalado é o topo da ordem_escala (A1, A2, A3)
                                # Por isso reserva-se o último disponível na ordem
                                # Militares da secretaria disponíveis (sem férias, tribunal, folga, dispensas)
                                # Regra: sempre tem de ficar ≥1 na secretaria
                                # Ao escalar para atendimento, verificar que ainda sobra 1
                                sec_escalados_atend = set()  # conta quantos da sec já foram escalados

                                for servico, horario, num in SLOTS_AJUSTADOS:
                                    col_key = f"{servico} {horario}"
                                    if col_key not in ordem_g:
                                        if servico == "Atendimento" and horario == "00-08":
                                            st.warning(f"⚠️ A1: coluna '{col_key}' não existe. Colunas: {list(ordem_g.keys())}")
                                        continue
                                    colocados = []
                                    for mid in ordem_g[col_key]:
                                        if len(colocados) >= num: break
                                        motivo = None
                                        if mid in ids_indisponiveis: motivo = 'indisponivel'
                                        elif mid in ids_escalados_g: motivo = 'ja_escalado'
                                        elif mid in sec_disponiveis and _e_atendimento(servico) and (len(sec_disponiveis) - len(sec_escalados_atend) <= 1): motivo = 'reservado_secretaria'
                                        elif militar_tem_dispensa_slot(mid, d_gerar, df_licencas, servico, horario): motivo = 'dispensa_slot'
                                        elif servico not in militares_servicos.get(mid, []): motivo = f'sem_servico:{militares_servicos.get(mid,[])}'
                                        elif horario == '00-08' and (servico == 'Atendimento' or servico == 'Patrulha Ocorrências') and militar_de_ferias(mid, d_gerar - timedelta(days=1), df_ferias, feriados): motivo = 'vem_de_ferias'
                                        else:
                                            ini_novo, _ = _parse_horario(horario)
                                            ok = True
                                            # Verificar descanso em relação ao dia anterior
                                            # Remunerados não contam para o descanso
                                            if not df_ant_g2.empty:
                                                rows_ant = df_ant_g2[df_ant_g2['id'].astype(str).str.strip() == mid]
                                                # Excluir remunerados
                                                rows_ant = rows_ant[~rows_ant['serviço'].apply(norm).str.contains('remu|grat', na=False)]
                                                for _, r_ant in rows_ant.iterrows():
                                                    _, fim_ant = _parse_horario(str(r_ant.get('horário','')))
                                                    if fim_ant and ini_novo is not None:
                                                        if (1440 - fim_ant) + ini_novo < 480:
                                                            ok = False; break
                                            if not ok: motivo = 'descanso'
                                        if motivo:
                                            pass
                                        else:
                                            if mid not in novas_linhas:
                                                continue  # não está na tabela do dia -- saltar
                                            colocados.append(mid)
                                            ids_escalados_g.add(mid)

                                    for mid in colocados:
                                        novas_linhas[mid]['serviço'] = servico
                                        novas_linhas[mid]['horário'] = horario
                                        if mid in sec_disponiveis and _e_atendimento(servico):
                                            sec_escalados_atend.add(mid)
                                        if servico == 'Patrulha Ocorrências':
                                            novas_linhas[mid]['indicativo'] = '031.6A'
                                            novas_linhas[mid]['viatura']    = 'BT-05-NX'
                                            novas_linhas[mid]['giro']       = 'I'
                                            if horario == '00-08':
                                                novas_linhas[mid]['rádio'] = '4110201'
                                            elif horario == '08-16':
                                                novas_linhas[mid]['rádio'] = '4110203'
                                            elif horario == '16-24':
                                                novas_linhas[mid]['rádio'] = '4110204'
                                        # Rodar na ordem
                                        ordem_g[col_key].remove(mid)
                                        ordem_g[col_key].append(mid)

                                # Adicionar militares da secretaria não escalados com serviço "Secretaria"
                                for mid_sec in sec_disponiveis:
                                    if mid_sec not in ids_escalados_g:
                                        if mid_sec in novas_linhas:
                                            novas_linhas[mid_sec]['serviço'] = 'Secretaria'
                                            novas_linhas[mid_sec]['horário'] = ''

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
                                _pg_esc = get_pg_loader()
                                _guardou_pg = False
                                if _pg_esc:
                                    try:
                                        _pg_esc.guardar_escala(aba_dia, df_editado)
                                        load_data.clear()
                                        st.success(f"✅ Escala de {aba_dia} guardada!")
                                        _guardou_pg = True
                                    except Exception as _e_pg_esc:
                                        st.warning(f"PostgreSQL falhou: {_e_pg_esc}")
                                # Escala guardada no PostgreSQL acima

                                # Gravar "Disponível" para militares do efetivo sem serviço escalado
                                # Gravar "Férias" ou tipo de licença para quem está ausente
                                ids_escalados = set()
                                for (sv_e, hr_e, obs_e), dados_g in grupos_sv.items():
                                    for mid_e in dados_g['ids']:
                                        ids_escalados.add(str(mid_e).strip())
                                linhas_disp = []
                                for _, row_u_c in df_util.iterrows():
                                    mid_u_c = str(row_u_c.get('id', '')).strip()
                                    if not mid_u_c or mid_u_c == 'nan':
                                        continue
                                    if mid_u_c in ids_escalados:
                                        continue
                                    # Determinar serviço a registar
                                    if militar_de_ferias(mid_u_c, d_gerar, df_ferias, feriados):
                                        sv_reg = 'Férias'
                                    else:
                                        lic_raw = militar_de_licenca(mid_u_c, d_gerar, df_licencas)
                                        if lic_raw:
                                            sv_reg = lic_raw.split('|')[0] if '|' in lic_raw else lic_raw
                                        else:
                                            sv_reg = 'Disponível'
                                    linha_disp = [''] * len(hdrs_c_raw)
                                    idx_id_c = next((i for i,h in enumerate(hdrs_c) if 'id' in h), None)
                                    idx_sv_c = next((i for i,h in enumerate(hdrs_c) if 'servi' in h), None)
                                    if idx_id_c is not None: linha_disp[idx_id_c] = mid_u_c
                                    if idx_sv_c is not None: linha_disp[idx_sv_c] = sv_reg
                                    linhas_disp.append(linha_disp)
                                # linhas_disp já guardadas no PostgreSQL acima

                                # Gerar ordem_escala do dia seguinte
                                _gerar_ordem_escala_dia_seguinte(sh_c, aba_dia, d_gerar)

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
                         'Convalescença', 'Diligência', 'Inquéritos', 'Secretaria',
                         'Pronto', 'Tribunal', 'Disponível',
                         'Patrulha Auto', 'Patrulha Apeada', 'EG', 'Tiro']
            _hdrs_e = list(set(s for servs in _mil_servicos.values() for s in servs))
            todos_servicos_e = [''] + sorted(set(_hdrs_e + _extras_e))
            opts_hor_e = [''] + sorted(set(str(s) for s in _listas.get('Horário', ['00-08', '08-16', '16-24']) if str(s).strip()))
            opts_rad_e = [''] + sorted(set(str(s) for s in _listas.get('Rádio', []) if str(s).strip()))
            opts_ind_e = [''] + sorted(set(str(s) for s in _listas.get('Indicativo', []) if str(s).strip()))
            opts_vtr_e = [''] + sorted(set(str(s) for s in _listas.get('Viatura', []) if str(s).strip()))
            opts_gir_e = [''] + sorted(set(str(s) for s in _listas.get('Giro', []) if str(s).strip()))
            opts_sv_e  = _listas.get('Serviço', todos_servicos_e) or todos_servicos_e
            opts_sv_e  = [''] + sorted(set(str(s) for s in opts_sv_e if str(s).strip()))
            if len(opts_hor_e) <= 1:
                opts_hor_e = ['', '00-08', '08-16', '16-24']

            def _adicionar_lista(campo, valor):
                """Listas não usadas no PostgreSQL."""
                pass


            col_e1, col_e2, col_e3 = st.columns([2, 2, 1])
            with col_e1:
                d_e1 = st.date_input("Dia 1:", format="DD/MM/YYYY", key="d_edit1")
            with col_e2:
                d_e2 = st.date_input("Dia 2:", format="DD/MM/YYYY", key="d_edit2", value=None)
            with col_e3:
                _ord_carregar = st.selectbox("Ordenar por:", ['ID', 'Nome', 'Serviço', 'Horário'], key='ord_carregar')

            dias_editar = [d for d in [d_e1, d_e2] if d is not None]

            if st.button("📋 Carregar dias", key="btn_carregar_editar", use_container_width=True):
                st.session_state['ord_editar'] = _ord_carregar
                # No PostgreSQL não precisamos de criar abas — as escalas são criadas ao guardar
                # Pré-calcular férias uma vez para todos os dias/militares
                ferias_cache_e = {}
                if 'id' not in df_util.columns:
                    st.error("Erro ao carregar utilizadores. Tenta novamente.")
                    st.stop()
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
                        _df_e_raw = load_data(aba_e)
                        vals_e_raw = [list(_df_e_raw.columns)] + _df_e_raw.values.tolist() if not _df_e_raw.empty else []
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
                                        if mid not in mapa_e:
                                            mapa_e[mid] = []
                                        mapa_e[mid].append(dados_r)
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
                    linhas_e_raw = []
                    for _, row_u in df_util.iterrows():
                        mid = str(row_u.get('id', '')).strip()
                        if not mid or mid == 'nan': continue
                        nome  = str(row_u.get('nome', '')).strip()
                        partes_nome = nome.split()
                        apelido = partes_nome[-1] if partes_nome else nome
                        if mid in mapa_e:
                            lista_e = mapa_e[mid]
                            # Preferir serviço normal (não remunerado)
                            servs_normais_e = [d for d in lista_e if not norm(d.get('serviço','')).startswith('remu') and not norm(d.get('serviço','')).startswith('grat')]
                            dados = servs_normais_e[0] if servs_normais_e else lista_e[0]
                        elif mid in em_ferias_e:
                            dados = {'serviço': 'Férias', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        else:
                            _lic_raw_e = militar_de_licenca(mid, d_e, df_licencas)
                            if _lic_raw_e:
                                _lic_tipo_e = _lic_raw_e.split('|')[0] if '|' in _lic_raw_e else _lic_raw_e
                                _lic_obs_e  = _lic_raw_e.split('|')[1] if '|' in _lic_raw_e else ''
                                dados = {'serviço': _lic_tipo_e, 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': _lic_obs_e}
                            else:
                                dados = {'serviço': 'Disponível', 'horário': '', 'indicativo': '', 'rádio': '', 'giro': '', 'viatura': '', 'observações': ''}
                        linhas_e_raw.append({'id': mid, 'apelido': apelido,
                                             'serviço': dados.get('serviço',''), 'horário': dados.get('horário',''),
                                             'indicativo': dados.get('indicativo',''), 'rádio': dados.get('rádio',''),
                                             'giro': dados.get('giro',''), 'viatura': dados.get('viatura',''),
                                             'observações': dados.get('observações','')})

                    # Agrupar por serviço+horário (só quando ambos preenchidos)
                    grupos_e = {}
                    linhas_e = []
                    for r in linhas_e_raw:
                        sv = r['serviço']
                        hr = r['horário']
                        if sv and hr:
                            chave = (sv, hr, r['indicativo'], r['rádio'], r['giro'], r['viatura'], r['observações'])
                            if chave in grupos_e:
                                idx = grupos_e[chave]
                                linhas_e[idx]['id']   += ';' + r['id']
                                linhas_e[idx]['nome'] += ', ' + r['apelido']
                            else:
                                grupos_e[chave] = len(linhas_e)
                                linhas_e.append({'id': r['id'], 'nome': r['apelido'],
                                                 'serviço': sv, 'horário': hr,
                                                 'indicativo': r['indicativo'], 'rádio': r['rádio'],
                                                 'giro': r['giro'], 'viatura': r['viatura'],
                                                 'observações': r['observações']})
                        else:
                            linhas_e.append({'id': r['id'], 'nome': r['apelido'],
                                             'serviço': sv, 'horário': hr,
                                             'indicativo': r['indicativo'], 'rádio': r['rádio'],
                                             'giro': r['giro'], 'viatura': r['viatura'],
                                             'observações': r['observações']})
                    dados_editar[aba_e] = {'linhas': linhas_e, 'data': d_e}

                    # Adicionar remunerados manuais agrupados por serviço+horário+campos distintivos
                    grupos_rem_e = {}
                    for mid_rem, lista_rem in mapa_e.items():
                        for d_rem in lista_rem:
                            if not re.search(r'remu|grat', norm(d_rem.get('serviço',''))):
                                continue
                            sv_r = d_rem['serviço']
                            hr_r = d_rem['horário']
                            ind_r = d_rem.get('indicativo','')
                            rad_r = d_rem.get('rádio','')
                            gir_r = d_rem.get('giro','')
                            vtr_r = d_rem.get('viatura','')
                            obs_r = d_rem.get('observações','')
                            chave_r = (sv_r, hr_r, ind_r, rad_r, gir_r, vtr_r, obs_r)
                            apelido_rem = ''
                            row_u_rem = df_util[df_util['id'].astype(str).str.strip() == mid_rem]
                            if not row_u_rem.empty:
                                nome_rem = str(row_u_rem.iloc[0].get('nome','')).strip()
                                partes_rem = nome_rem.split()
                                apelido_rem = partes_rem[-1] if partes_rem else nome_rem
                            if chave_r not in grupos_rem_e:
                                grupos_rem_e[chave_r] = {
                                    'ids': [mid_rem], 'nomes': [apelido_rem],
                                    'indicativo': ind_r, 'rádio': rad_r,
                                    'giro': gir_r, 'viatura': vtr_r, 'observações': obs_r,
                                }
                            else:
                                if mid_rem not in grupos_rem_e[chave_r]['ids']:
                                    grupos_rem_e[chave_r]['ids'].append(mid_rem)
                                    grupos_rem_e[chave_r]['nomes'].append(apelido_rem)
                    for (sv_r, hr_r, ind_r, rad_r, gir_r, vtr_r, obs_r), g_r in grupos_rem_e.items():
                        linhas_e.append({
                            'id': ';'.join(g_r['ids']), 'nome': ', '.join(g_r['nomes']),
                            'serviço': sv_r, 'horário': hr_r,
                            'indicativo': g_r['indicativo'], 'rádio': g_r['rádio'],
                            'giro': g_r['giro'], 'viatura': g_r['viatura'],
                            'observações': g_r['observações'],
                        })
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
                    # Tentar PostgreSQL primeiro
                    _pg_g = get_pg_loader()
                    if _pg_g:
                        for aba_g, df_g in editados_dict.items():
                            try:
                                # Agrupar militares por serviço+horário
                                grupos = {}
                                for _, r in df_g.iterrows():
                                    mid = str(r.get('id','')).strip()
                                    if not mid or mid == 'nan': continue
                                    sv = str(r.get('serviço','') or '').strip()
                                    if not sv: continue
                                    hr = str(r.get('horário','') or '').strip()
                                    chave = (sv, hr, str(r.get('indicativo','')), str(r.get('rádio','')), str(r.get('giro','')), str(r.get('viatura','')), str(r.get('observações','')))
                                    if chave not in grupos:
                                        grupos[chave] = {'ids':[], 'ind':str(r.get('indicativo','')), 'rad':str(r.get('rádio','')), 'giro':str(r.get('giro','')), 'vtr':str(r.get('viatura','')), 'obs':str(r.get('observações',''))}
                                    grupos[chave]['ids'].append(mid)
                                # Construir DataFrame para guardar
                                import pandas as _pd_g
                                linhas_pg = []
                                for (sv, hr, ind, rad, giro, vtr, obs), d in grupos.items():
                                    linhas_pg.append({'id': ';'.join(d['ids']), 'serviço': sv, 'horário': hr, 'indicativo rádio': d['ind'], 'rádio': d['rad'], 'giro': d['giro'], 'viatura': d['vtr'], 'observações': d['obs']})
                                df_pg = _pd_g.DataFrame(linhas_pg)
                                _pg_g.guardar_escala(aba_g, df_pg)
                            except Exception as _e_pg:
                                st.error(f"Erro PostgreSQL: {_e_pg}")
                        load_data.clear()
                        return

                    # Guardado no PostgreSQL acima
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
                        key="editor_unificado", num_rows="dynamic",
                        height=min(50 + len(df_uni) * 35, 2000),
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
                                df1 = pd.DataFrame(rows_1)
                                df2 = pd.DataFrame(rows_2)
                                _guardar_sheets({aba_1: df1, aba_2: df2})
                                load_data.clear()
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
                    st.caption("💡 O campo ID aceita vários militares separados por `;` (ex: `507;1185`). Podes adicionar ou remover linhas.")
                    df_s = pd.DataFrame(info_e['linhas'])
                    _ord_col_s = {'ID': 'id', 'Nome': 'nome', 'Serviço': 'serviço', 'Horário': 'horário'}.get(st.session_state.get('ord_editar', 'ID'), 'id')
                    if _ord_col_s in df_s.columns:
                        if _ord_col_s == 'id':
                            df_s = df_s.sort_values('id', key=lambda x: pd.to_numeric(x, errors='coerce').fillna(999999)).reset_index(drop=True)
                        else:
                            df_s = df_s.sort_values(_ord_col_s, key=lambda x: x.astype(str).str.lower()).reset_index(drop=True)
                    df_editado_s = st.data_editor(
                        df_s,
                        column_config={
                            'id':          st.column_config.TextColumn('ID(s)', width='small'),
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
                        key=f"editor_{aba_e}", num_rows="dynamic",
                        height=min(50 + len(df_s) * 35, 2000),
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
                                load_data.clear()

                                # Cancelar trocas aprovadas para IDs alterados
                                try:
                                    orig_dict_e = st.session_state.get('editar_escala_original', {})
                                    orig_aba_e = orig_dict_e.get(aba_e, {})
                                    ids_alterados = set()
                                    if orig_aba_e and not df_editado_s.empty:
                                        for _, row_e in df_editado_s.iterrows():
                                            mid_e = str(row_e.get('id','')).strip()
                                            if not mid_e or mid_e not in orig_aba_e: continue
                                            orig_r = orig_aba_e[mid_e]
                                            serv_orig_e = str(orig_r.get('serviço','')).strip()
                                            serv_novo_e = str(row_e.get('serviço','')).strip()
                                            hor_orig_e  = str(orig_r.get('horário','')).strip()
                                            hor_novo_e  = str(row_e.get('horário','')).strip()
                                            if serv_orig_e != serv_novo_e or hor_orig_e != hor_novo_e:
                                                ids_alterados.add(mid_e)

                                    if ids_alterados:
                                        data_aba_e = f"{aba_e[3:5]}/{aba_e[:2]}/{datetime.now().year}"
                                        _pg_tr_e = get_pg_loader()
                                        df_tr_e = load_trocas()
                                        canceladas_e = []
                                        if _pg_tr_e and not df_tr_e.empty and 'id' in df_tr_e.columns:
                                            matches_tr_e = df_tr_e[
                                                (df_tr_e['data'].astype(str) == data_aba_e) &
                                                (df_tr_e['status'].astype(str) == 'Aprovada') &
                                                (df_tr_e['id_origem'].astype(str).isin(ids_alterados) |
                                                 df_tr_e['id_destino'].astype(str).isin(ids_alterados))
                                            ]
                                            for _, tr_e in matches_tr_e.iterrows():
                                                _pg_tr_e.actualizar_status_troca(int(tr_e['id']), 'Cancelada')
                                                canceladas_e.append((str(tr_e['id_origem']), str(tr_e['id_destino'])))
                                            if canceladas_e:
                                                load_trocas.clear()
                                        # Notificar militares afectados
                                        if canceladas_e:
                                            try:
                                                import requests as _req_e
                                                todos_ids = set()
                                                for o, d in canceladas_e:
                                                    todos_ids.add(o); todos_ids.add(d)
                                                _req_e.post(
                                                    "https://portal-escalas-gnr-production.up.railway.app/api/notificacoes/notificar-interno",
                                                    json={
                                                        "secret": "gnr-famalicao-2026",
                                                        "u_ids": list(todos_ids),
                                                        "titulo": "🔄 Troca cancelada",
                                                        "corpo": f"A tua troca de {data_aba_e} foi cancelada devido a alteração da escala.",
                                                        "url": "/trocas",
                                                        "tag": "troca-cancelada",
                                                    }, timeout=5
                                                )
                                                st.info(f"ℹ️ {len(canceladas_e)} troca(s) cancelada(s) automaticamente e militares notificados.")
                                            except Exception:
                                                pass
                                        load_trocas.clear()
                                except Exception:
                                    pass

                                del st.session_state['editar_escala']
                                st.session_state.pop('editar_escala_original', None)
                                st.success("✅ Guardado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")



        with tab_rem:
            st.markdown("#### 💶 Remunerados")

            # Carregar ordem_remunerados (cacheado)
            df_ord_rem = load_ordem_remunerados()
            if df_ord_rem.empty:
                st.error("Aba 'ordem_remunerados' não encontrada ou vazia.")
                st.stop()
            else:
                # ── Configuração base ──────────────────────────────
                d_rem = st.date_input("Data:", format="DD/MM/YYYY", key="d_rem")

                # ── Lista de remunerados a nomear ──────────────────
                if 'rem_slots' not in st.session_state:
                    st.session_state['rem_slots'] = [{'hor': '', 'n': 2, 'obs': '', 'tab': 'A'}]

                st.markdown("**Remunerados a nomear em simultâneo:**")
                slots = st.session_state['rem_slots']
                for i, slot in enumerate(slots):
                    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns([2, 1, 1, 3, 0.5])
                    with col_s1:
                        slots[i]['hor'] = st.text_input(f"Horário {i+1}:", value=slot['hor'],
                            placeholder="ex: 08-12", key=f"hor_rem_{i}")
                    with col_s2:
                        slots[i]['n'] = st.number_input(f"Nº mil. {i+1}:", min_value=1, max_value=10,
                            value=slot['n'], key=f"n_rem_{i}")
                    with col_s3:
                        slots[i]['tab'] = st.selectbox(f"Tab. {i+1}:", ["A", "B"],
                            index=0 if slot.get('tab','A') == 'A' else 1, key=f"tab_rem_{i}")
                    with col_s4:
                        slots[i]['obs'] = st.text_input(f"Obs. {i+1}:", value=slot['obs'],
                            placeholder="ex: Reg. Trânsito", key=f"obs_rem_{i}")
                    with col_s5:
                        if i > 0:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🗑️", key=f"del_rem_{i}"):
                                st.session_state['rem_slots'].pop(i)
                                st.rerun()

                col_add, col_calc = st.columns(2)
                with col_add:
                    if st.button("➕ Adicionar remunerado", use_container_width=True, key="btn_add_rem"):
                        st.session_state['rem_slots'].append({'hor': '', 'n': 2, 'obs': '', 'tab': 'A'})
                        st.rerun()

                with col_calc:
                    calcular = st.button("🔍 Calcular Nomeação", use_container_width=True, key="btn_calc_rem")

                if calcular:
                    # Validar slots
                    slots_validos = [s for s in slots if s['hor'] and '-' in s['hor']]
                    if not slots_validos:
                        st.error("Introduz pelo menos um horário válido.")
                        st.stop()

                    aba_rem = d_rem.strftime("%d-%m")
                    df_dia_rem = load_data(aba_rem)
                    data_str_rem = d_rem.strftime("%d/%m/%Y")

                    is_fds = d_rem.weekday() >= 5

                    def _cols_para_tab(tab):
                        if tab == "B":
                            return "total_ano_b", "ultimo_b"
                        elif is_fds:
                            return "total_ano_a_fds", "ultimo_a_fds"
                        else:
                            return "total_ano_a_semana", "ultimo_a_semana"

                    # Parsear horários de todos os slots
                    slots_parsed = []
                    for slot in slots_validos:
                        hi, hf = _parse_horario(slot['hor'])
                        horas = round((hf - hi) / 60, 1) if hf and hi and hf > hi else round((1440 - hi + hf) / 60, 1) if hi is not None and hf is not None else 0
                        col_total, col_ultimo = _cols_para_tab(slot.get('tab', 'A'))
                        slots_parsed.append({**slot, 'hi': hi, 'hf': hf, 'horas': horas,
                                             'col_total': col_total, 'col_ultimo': col_ultimo})

                    # Para garantir que todas as colunas existem
                    col_total = "total_ano_a_semana"
                    col_ultimo = "ultimo_a_semana"

                    for col in ['disponivel', 'voluntario', 'folga', 'prescinde_descanso', col_total, col_ultimo]:
                        if col not in df_ord_rem.columns:
                            df_ord_rem[col] = ''
                    for bcol in ['disponivel', 'voluntario', 'folga', 'prescinde_descanso']:
                        df_ord_rem[bcol] = df_ord_rem[bcol].apply(
                            lambda v: v if isinstance(v, bool) else str(v).strip().lower() in ['true','1','sim','yes'])
                        df_ord_rem[bcol] = df_ord_rem[bcol].astype(str).str.strip().str.lower().isin(['true','1','sim','yes'])
                    df_ord_rem[col_total] = pd.to_numeric(df_ord_rem[col_total], errors='coerce').fillna(0)
                    df_ord_rem[col_ultimo] = pd.to_datetime(df_ord_rem[col_ultimo], dayfirst=True, errors='coerce')

                    def _sobreposicao(h1_ini, h1_fim, h2_ini, h2_fim):
                        if None in (h1_ini, h1_fim, h2_ini, h2_fim): return False
                        e1 = h1_fim if h1_fim > h1_ini else h1_fim + 1440
                        e2 = h2_fim if h2_fim > h2_ini else h2_fim + 1440
                        return h1_ini < e2 and h2_ini < e1

                    def _verif_descanso(hi_serv, hf_serv, hi_novo, hf_novo):
                        if None in (hi_serv, hf_serv, hi_novo, hf_novo): return True
                        fim_serv = hf_serv if hf_serv > hi_serv else hf_serv + 1440
                        fim_novo = hf_novo if hf_novo > hi_novo else hf_novo + 1440
                        # Descanso entre fim do serviço e início do remunerado
                        descanso_depois_serv = (hi_novo + 1440 - fim_serv) % 1440
                        # Descanso entre fim do remunerado e início do serviço
                        descanso_depois_rem = (hi_serv + 1440 - fim_novo) % 1440
                        # Basta garantir 8h num dos lados
                        return descanso_depois_serv >= 480 or descanso_depois_rem >= 480

                    _IMP_ABS = r'ferias|licen|convalesc|fcaa|cter|dilig|pronto'
                    _IMP_HOR = r'tribunal|inquer|secretaria'
                    servicos_dia = {}
                    militares_com_servico = set()
                    militares_de_folga = set()
                    if not df_dia_rem.empty:
                        for _, row_sd in df_dia_rem.iterrows():
                            mid_sd = str(row_sd['id']).strip()
                            if not mid_sd: continue
                            serv_norm = norm(str(row_sd.get('serviço', '')))
                            if 'folga semanal' in serv_norm or 'folga complementar' in serv_norm:
                                militares_de_folga.add(mid_sd)
                            elif re.search(_IMP_ABS, serv_norm):
                                pass
                            elif re.search(_IMP_HOR, serv_norm):
                                # Tribunal usa horário da sheet; secretaria/inquérito fixo 09-17
                                hor_sd = str(row_sd.get('horário', '')).strip()
                                if not hor_sd or '-' not in hor_sd:
                                    hor_sd = '09-17'  # secretaria/inquérito sem horário definido
                                hi_sd, hf_sd = _parse_horario(hor_sd)
                                servicos_dia.setdefault(mid_sd, []).append((hi_sd, hf_sd, str(row_sd.get('serviço',''))))
                                militares_com_servico.add(mid_sd)
                            elif not re.search(r'remu|grat', serv_norm):
                                hor_sd = str(row_sd.get('horário', '')).strip()
                                hi_sd, hf_sd = _parse_horario(hor_sd)
                                servicos_dia.setdefault(mid_sd, []).append((hi_sd, hf_sd, str(row_sd.get('serviço',''))))
                                militares_com_servico.add(mid_sd)

                    ausentes_dia = set()
                    if not df_dia_rem.empty:
                        aus_mask = df_dia_rem['serviço'].apply(norm).str.contains(_IMP_ABS, na=False)
                        for mid_a in df_dia_rem[aus_mask]['id'].astype(str).str.strip().tolist():
                            if mid_a: ausentes_dia.add(mid_a)
                    for _, row_u in df_ord_rem.iterrows():
                        mid_u = str(row_u.get('id', '')).strip()
                        if mid_u and militar_de_ferias(mid_u, d_rem, df_ferias, feriados):
                            ausentes_dia.add(mid_u)

                    df_disp = df_ord_rem[df_ord_rem['disponivel'] == True].copy()
                    df_disp_sorted = df_disp.sort_values([col_ultimo, col_total], ascending=[True, True], na_position='first')

                    def _pode_nomear_slot(row_r, mid_r, slot, ja_nomeados_ids, motivo_skip):
                        """Verifica se militar pode ser nomeado para este slot,
                        considerando serviços escalados E outros slots já atribuídos."""
                        if mid_r in ausentes_dia:
                            motivo_skip.append(f"{get_nome_curto(df_util, mid_r)} — ausente")
                            return False
                        # Todos os horários a verificar: serviço escalado + slots já atribuídos
                        todos_servicos = list(servicos_dia.get(mid_r, []))
                        for outro_slot_idx, outro_mid in ja_nomeados_ids:
                            if outro_mid == mid_r:
                                sp = slots_parsed[outro_slot_idx]
                                todos_servicos.append((sp['hi'], sp['hf'], f"Remunerado {sp['hor']}"))
                        for hi_s, hf_s, serv_s in todos_servicos:
                            if _sobreposicao(slot['hi'], slot['hf'], hi_s, hf_s):
                                motivo_skip.append(f"{get_nome_curto(df_util, mid_r)} — sobreposição com {serv_s}")
                                return False
                        if not bool(row_r['prescinde_descanso']):
                            for hi_s, hf_s, serv_s in todos_servicos:
                                if not _verif_descanso(hi_s, hf_s, slot['hi'], slot['hf']):
                                    motivo_skip.append(f"{get_nome_curto(df_util, mid_r)} — menos de 8h descanso com {serv_s}")
                                    return False
                        return True

                    # ── Alocação conjunta ────────────────────────────────────
                    # Estratégia: preferir militares diferentes entre slots,
                    # mas se não houver suficientes, permitir repetir desde que
                    # não haja sobreposição de horários
                    resultados_slots = []
                    # ja_nomeados_ids: lista de (slot_idx, mid) — para verificar cross-slot
                    # na 1ª passagem exclui quem já foi nomeado noutro slot
                    ja_nomeados_ids = []

                    for slot_idx, slot in enumerate(slots_parsed):
                        nomeados = []
                        avisos   = []
                        skipped  = []
                        _ct, _cu = slot['col_total'], slot['col_ultimo']
                        for col in [_ct, _cu]:
                            if col not in df_ord_rem.columns:
                                df_ord_rem[col] = ''
                        df_ord_rem[_ct] = pd.to_numeric(df_ord_rem[_ct], errors='coerce').fillna(0)
                        df_ord_rem[_cu] = pd.to_datetime(df_ord_rem[_cu], dayfirst=True, errors='coerce')
                        df_disp = df_ord_rem[df_ord_rem['disponivel'] == True].copy()
                        df_disp_sorted = df_disp.sort_values([_cu, _ct], ascending=[True, True], na_position='first')

                        ja_neste_slot = lambda: [n['id'] for n in nomeados]

                        def _nomear_grupo(filtro_fn, grupo_label, aviso_extra=False):
                            for _, row_r in df_disp_sorted.iterrows():
                                if len(nomeados) >= slot['n']: break
                                mid_r = str(row_r.get('id', '')).strip()
                                if not mid_r or mid_r in ja_neste_slot(): continue
                                if not filtro_fn(row_r, mid_r): continue
                                if _pode_nomear_slot(row_r, mid_r, slot, ja_nomeados_ids, skipped):
                                    if aviso_extra:
                                        avisos.append(f"⚠️ **{get_nome_curto(df_util, mid_r)} ({mid_r})** nomeado fora da lista de voluntários")
                                    label = grupo_label(mid_r)
                                    nomeados.append({'id': mid_r, 'nome': get_nome_curto(df_util, mid_r),
                                                     'grupo': label, 'total': int(row_r[_ct])})
                                    ja_nomeados_ids.append((slot_idx, mid_r))

                        # G1: voluntários com serviço/disponíveis — novos
                        _nomear_grupo(
                            lambda r, m: bool(r['voluntario']) and m not in ausentes_dia and m not in militares_de_folga
                                and not any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: 'Voluntário c/ serviço' if m in militares_com_servico else 'Voluntário disponível'
                        )
                        # G2: voluntários de folga — novos
                        _nomear_grupo(
                            lambda r, m: bool(r['voluntario']) and m in militares_de_folga and bool(r['folga'])
                                and m not in ausentes_dia and not any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: 'Voluntário de folga'
                        )
                        # G3: não voluntários — novos
                        _nomear_grupo(
                            lambda r, m: not bool(r['voluntario']) and m not in ausentes_dia and m not in militares_de_folga
                                and not any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: 'Não voluntário',
                            aviso_extra=True
                        )
                        # G1b: repetir voluntários com serviço/disponíveis já noutro slot
                        _nomear_grupo(
                            lambda r, m: bool(r['voluntario']) and m not in ausentes_dia and m not in militares_de_folga
                                and any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: ('Voluntário c/ serviço' if m in militares_com_servico else 'Voluntário disponível') + ' (já nomeado noutro remunerado)'
                        )
                        # G2b: repetir voluntários de folga já noutro slot
                        _nomear_grupo(
                            lambda r, m: bool(r['voluntario']) and m in militares_de_folga and bool(r['folga'])
                                and m not in ausentes_dia and any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: 'Voluntário de folga (já nomeado noutro remunerado)'
                        )
                        # G3b: repetir não voluntários já noutro slot
                        _nomear_grupo(
                            lambda r, m: not bool(r['voluntario']) and m not in ausentes_dia and m not in militares_de_folga
                                and any(m == mid for _, mid in ja_nomeados_ids),
                            lambda m: 'Não voluntário (já nomeado noutro remunerado)',
                            aviso_extra=True
                        )

                        resultados_slots.append({'slot': slot, 'nomeados': nomeados, 'avisos': avisos, 'skipped': skipped})


                    # ── Mostrar resultados ───────────────────────────────────
                    tipo_col = ""  # tabela é por slot
                    todos_ok = all(len(r['nomeados']) >= r['slot']['n'] for r in resultados_slots)

                    for i, res in enumerate(resultados_slots):
                        slot = res['slot']
                        nomeados = res['nomeados']
                        if nomeados:
                            st.success(f"✅ Remunerado {i+1} · {slot['hor']} · {len(nomeados)} militar(es):")
                            for n in nomeados:
                                st.markdown(f"- **{n['nome']} ({n['id']})** — {n['grupo']} | {n['total']}h acumuladas")
                            for av in res['avisos']:
                                st.warning(av)
                        else:
                            st.error(f"❌ Remunerado {i+1} · {slot['hor']} — Não foi possível nomear militares suficientes.")
                        if res['skipped']:
                            with st.expander(f"ℹ️ Ignorados — Remunerado {i+1}"):
                                for s in res['skipped']:
                                    st.caption(s)

                    if any(len(r['nomeados']) > 0 for r in resultados_slots):
                        st.session_state['rem_nomeados'] = {
                            'resultados': resultados_slots,
                            'data': data_str_rem,
                            'aba': aba_rem,
                            'tabela': 'A',  # tabela é por slot
                            'col_total': col_total,
                            'col_ultimo': col_ultimo,
                        }
                # Confirmar nomeação
                if 'rem_nomeados' in st.session_state:
                    dados_rem = st.session_state['rem_nomeados']
                    resumo = " | ".join(
                        f"{r['slot']['hor']}: {', '.join(n['nome'] for n in r['nomeados'])}"
                        for r in dados_rem['resultados'] if r['nomeados']
                    )
                    st.info(f"📋 Pronto a confirmar: {resumo} — {dados_rem['data']}")
                    if st.button("✅ CONFIRMAR NOMEAÇÃO E ESCREVER NA ESCALA", use_container_width=True, type="primary", key="btn_conf_rem"):
                        try:
                            _pg_rem = get_pg_loader()
                            df_dia_actual = load_data(dados_rem['aba'])

                            for res in dados_rem['resultados']:
                                if not res['nomeados']: continue
                                slot = res['slot']
                                ids_nomeados = [n['id'] for n in res['nomeados']]
                                ids_str = ";".join(ids_nomeados)
                                tab_slot = slot.get('tab', 'A')
                                serv_novo = f"Svç Remunerado - Tabela {tab_slot}"
                                hor_novo  = slot['hor']

                                # Verificar duplicado
                                ja_existe = False
                                if not df_dia_actual.empty and 'serviço' in df_dia_actual.columns:
                                    ja_existe = not df_dia_actual[
                                        (df_dia_actual['serviço'].astype(str).str.strip() == serv_novo) &
                                        (df_dia_actual['horário'].astype(str).str.strip() == hor_novo)
                                    ].empty
                                if ja_existe:
                                    st.warning(f"⚠️ Remunerado {tab_slot} ({hor_novo}) já existe — não duplicado.")
                                    continue

                                # Adicionar linha ao PostgreSQL
                                _pg_rem.adicionar_linha_escala(dados_rem['aba'], {
                                    'id': ids_str, 'serviço': serv_novo, 'horário': hor_novo,
                                    'viatura': '', 'rádio': '', 'indicativo rádio': '',
                                    'giro': '', 'observações': slot.get('obs', ''),
                                })

                                # Actualizar ordem remunerados
                                hi_s, hf_s = _parse_horario(slot['hor'])
                                horas_add = round((hf_s - hi_s) / 60, 1) if hf_s and hi_s and hf_s > hi_s else round((1440 - hi_s + hf_s) / 60, 1) if hi_s and hf_s else 1
                                from datetime import datetime as _dt_rem
                                for mid_n in ids_nomeados:
                                    _pg_rem.actualizar_ordem_remunerado(mid_n, tab_slot, horas_add, _dt_rem.now())

                            load_data.clear()
                            st.session_state.pop('rem_nomeados', None)
                            st.success("✅ Nomeação confirmada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

            # --- GESTÃO DE REMUNERADOS NOMEADOS ---
        
                def _repor_data_ultimo(ws_ord_r, hdrs_r, ws_hist_r, mid_r, col_ult_r, col_data_cancelada):
                    """Após cancelar/substituir, repõe a data do último remunerado do histórico."""
                    hist_vals = ws_hist_r.get_all_values()
                    if len(hist_vals) <= 1:
                        data_repor = ''
                    else:
                        # Filtrar linhas deste militar e deste tipo
                        tipo_r = col_ult_r  # ex: ultimo_a_fds
                        linhas_mil = [
                            row for row in hist_vals[1:]
                            if len(row) >= 3 and str(row[0]).strip() == mid_r and str(row[2]).strip() == tipo_r
                            and str(row[1]).strip() != col_data_cancelada  # excluir a data que acabou de ser cancelada
                        ]
                        if not linhas_mil:
                            data_repor = ''
                        else:
                            # Ordenar por data descendente, pegar a mais recente
                            datas_r = []
                            for lr in linhas_mil:
                                try:
                                    datas_r.append((datetime.strptime(lr[1].strip(), '%d/%m/%Y'), lr[1].strip()))
                                except:
                                    pass
                            data_repor = max(datas_r, key=lambda x: x[0])[1] if datas_r else ''
        
                    # Atualizar col_ult_r no ordem_remunerados
                    col_ult_idx_r = hdrs_r.index(col_ult_r) if col_ult_r in hdrs_r else None
                    col_id_idx_r  = hdrs_r.index('id') if 'id' in hdrs_r else 0
                    if col_ult_idx_r is None:
                        return
                    ord_vals = ws_ord_r.get_all_values()
                    upds_r = []
                    for i_r, row_r2 in enumerate(ord_vals[1:], start=2):
                        mid_r2 = str(row_r2[col_id_idx_r]).strip() if col_id_idx_r < len(row_r2) else ''
                        if mid_r2 == mid_r:
                            cl_r = chr(ord('A') + col_ult_idx_r)
                            upds_r.append({'range': f'{cl_r}{i_r}', 'values': [[data_repor]]})
                            break
                    pass  # actualizado no PG
        
                st.divider()
                st.markdown("#### 📋 Remunerados Nomeados (hoje em diante)")
        
                col_gest1, col_gest2 = st.columns([3,1])
                with col_gest2:
                    if st.button("🔄 Carregar lista", key="btn_carregar_gest", use_container_width=True):
                        st.session_state['gest_carregado'] = True
        
                if not st.session_state.get('gest_carregado'):
                    st.info("Clica em **🔄 Carregar lista** para ver os remunerados nomeados.")
                else:
                    hoje = date.today()
                    abas_existentes_g = load_lista_abas()
                    remunerados_lista = []  # [{data, aba, linha_idx, ids, horario, tabela, obs}]
        
                    with st.spinner("A carregar remunerados..."):
                        for delta in range(15):
                            d_g = hoje + timedelta(days=delta)
                            aba_g = d_g.strftime("%d-%m")
                            if aba_g not in abas_existentes_g:
                                continue
                            try:
                                df_g = load_data(aba_g)
                                if df_g.empty:
                                    continue
                                # Simular formato vals_g para reutilizar código
                                for i, row_dict in enumerate(df_g.to_dict('records'), start=2):
                                    row_g = [str(row_dict.get(c, '')) for c in df_g.columns]
                                    hdrs_g = [_nc(h) for h in df_g.columns]
                                    idx_id   = hdrs_g.index('id')       if 'id'       in hdrs_g else 0
                                    idx_serv = hdrs_g.index('servico')  if 'servico'  in hdrs_g else (hdrs_g.index('servico') if 'servico' in hdrs_g else 1)
                                    idx_hor  = hdrs_g.index('horario')  if 'horario'  in hdrs_g else 2
                                    idx_obs  = hdrs_g.index('observacoes') if 'observacoes' in hdrs_g else 6
                                    if len(row_g) <= idx_serv:
                                        continue
                                    serv_g = norm(str(row_g[idx_serv]))
                                    if 'remunerado' in serv_g:
                                        tabela_g = 'A' if 'tabela a' in serv_g else ('B' if 'tabela b' in serv_g else '?')
                                        remunerados_lista.append({
                                            'data': d_g.strftime("%d/%m/%Y"),
                                            'data_obj': d_g,
                                            'aba': aba_g,
                                            'linha_idx': i,  # linha real no Sheets (1-based)
                                            'ids': str(row_g[idx_id]).strip() if idx_id < len(row_g) else '',
                                            'horario': str(row_g[idx_hor]).strip() if idx_hor < len(row_g) else '',
                                            'tabela': tabela_g,
                                            'obs': str(row_g[idx_obs]).strip() if idx_obs < len(row_g) else '',
                                        })
                            except:
                                continue
        
                    if not remunerados_lista:
                        st.info("Não há remunerados nomeados nos próximos 15 dias.")
                    else:
                        for rem_g in remunerados_lista:
                            nomes_g = []
                            for mid_g in rem_g['ids'].replace(';', ',').split(','):
                                mid_g = mid_g.strip()
                                if mid_g:
                                    nomes_g.append(f"{get_nome_curto(df_util, mid_g)} ({mid_g})")
                            label_g = f"📅 {rem_g['data']} | Tabela {rem_g['tabela']} | {rem_g['horario']} | {', '.join(nomes_g)}"
                            if rem_g['obs']:
                                label_g += f" | {rem_g['obs']}"
            
                            with st.expander(label_g):
                                st.markdown(f"**Militares:** {', '.join(nomes_g)}")
                                st.markdown(f"**Horário:** {rem_g['horario']} | **Tabela:** {rem_g['tabela']}")
                                if rem_g['obs']:
                                    st.markdown(f"**Obs:** {rem_g['obs']}")
            
                                col_ga, col_gb = st.columns(2)
                                chave_base = f"{rem_g['aba']}_{rem_g['linha_idx']}"
            
                                with col_ga:
                                    if st.button("🗑️ Cancelar remunerado", key=f"canc_{chave_base}", use_container_width=True):
                                        st.session_state[f'gest_acao_{chave_base}'] = 'cancelar'
            
                                with col_gb:
                                    if st.button("🔄 Substituir militar", key=f"subs_{chave_base}", use_container_width=True):
                                        st.session_state[f'gest_acao_{chave_base}'] = 'substituir'
            
                                acao_g = st.session_state.get(f'gest_acao_{chave_base}')
            
                                # ── CANCELAR ──
                                if acao_g == 'cancelar':
                                    st.warning("Tens a certeza que queres cancelar este remunerado? As horas serão subtraídas.")
                                    if st.button("✅ Confirmar cancelamento", key=f"conf_canc_{chave_base}", use_container_width=True, type="primary"):
                                        try:
                                            _pg_canc = get_pg_loader()
                                            # Remover linha da escala
                                            df_aba_c = load_data(rem_g['aba'])
                                            if not df_aba_c.empty:
                                                ids_rem_c = [x.strip() for x in rem_g['ids'].replace(';',',').split(',') if x.strip()]
                                                serv_c = rem_g.get('serv_orig', '')
                                                hor_c  = rem_g['horario']
                                                # Filtrar todas as linhas excepto a do remunerado a cancelar
                                                mask_canc = ~(
                                                    df_aba_c['serviço'].astype(str).str.contains('remun|gratif', case=False, na=False) &
                                                    (df_aba_c['horário'].astype(str).str.strip() == hor_c)
                                                )
                                                df_sem_rem = df_aba_c[mask_canc]
                                                _pg_canc.guardar_escala(rem_g['aba'], df_sem_rem)

                                            # Subtrair horas da ordem remunerados
                                            horas_c = 0
                                            if '-' in rem_g['horario']:
                                                try:
                                                    hi_c = int(rem_g['horario'].split('-')[0].strip())
                                                    hf_c = int(rem_g['horario'].split('-')[1].strip())
                                                    horas_c = hf_c - hi_c if hf_c > hi_c else (24 - hi_c + hf_c)
                                                except: pass
                                            is_fds_c = rem_g['data_obj'].weekday() >= 5
                                            tab_c = rem_g.get('tabela', 'A')
                                            from datetime import datetime as _dt_canc
                                            for mid_c in [x.strip() for x in rem_g['ids'].replace(';',',').split(',') if x.strip()]:
                                                _pg_canc.actualizar_ordem_remunerado(mid_c, tab_c, -horas_c, _dt_canc.now())

                                            load_data.clear()
                                            st.session_state.pop(f'gest_acao_{chave_base}', None)
                                            st.session_state['gest_carregado'] = False
                                            st.success("✅ Remunerado cancelado!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro: {e}")

                                # ── SUBSTITUIR ──
                                elif acao_g == 'substituir':
                                    ids_atuais = [x.strip() for x in rem_g['ids'].replace(';',',').split(',') if x.strip()]
                                    nomes_atuais = {mid: get_nome_curto(df_util, mid) for mid in ids_atuais}
                                    mid_sair = st.selectbox("Militar que sai:", ids_atuais,
                                        format_func=lambda x: f"{nomes_atuais.get(x,x)} ({x})", key=f"sair_{chave_base}")
                                    militares_disponiveis_s = [m for m in df_util['id'].astype(str).tolist() if m not in ids_atuais]
                                    mid_entra = st.selectbox("Militar que entra:", militares_disponiveis_s,
                                        format_func=lambda x: get_nome_curto(df_util, x), key=f"entra_{chave_base}")
                                    if st.button("✅ Confirmar substituição", key=f"conf_sub_{chave_base}", use_container_width=True, type="primary"):
                                        try:
                                            _pg_sub = get_pg_loader()
                                            df_aba_s = load_data(rem_g['aba'])
                                            if not df_aba_s.empty and 'serviço' in df_aba_s.columns:
                                                # Actualizar a linha do remunerado com novo ID
                                                ids_novos = [mid_entra if m == mid_sair else m for m in ids_atuais]
                                                ids_novos_str = ";".join(ids_novos)
                                                hor_s = rem_g['horario']
                                                mask_rem_s = df_aba_s['serviço'].astype(str).str.contains('remun|gratif', case=False, na=False) & (df_aba_s['horário'].astype(str).str.strip() == hor_s)
                                                df_aba_s.loc[mask_rem_s, 'id'] = ids_novos_str
                                                _pg_sub.guardar_escala(rem_g['aba'], df_aba_s)
                                            load_data.clear()
                                            st.session_state.pop(f'gest_acao_{chave_base}', None)
                                            st.session_state['gest_carregado'] = False
                                            st.success("✅ Substituição efectuada!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro: {e}")

        tab_disp_normal, tab_disp_slot = st.tabs(["📋 Dispensas Gerais", "🔒 Serviços/Horários"])

        # ── Tab Dispensas Gerais ──
        with tab_disp_normal:
            # Mostrar registos existentes
            df_lic_all = load_licencas(ano_atual)
            # Filtrar só as em vigor (fim >= hoje) e excluir registos de slot
            hoje_lic = datetime.now().date()
            if not df_lic_all.empty:
                col_fim_l = next((c for c in df_lic_all.columns if 'fim' in c.lower()), None)
                col_tp_l2 = 'tipo' if 'tipo' in df_lic_all.columns else None
                # Excluir registos de dispensa de slot
                if col_tp_l2:
                    def _is_slot(tipo_str):
                        codigos = [c.strip().upper() for c in str(tipo_str).replace(';',',').split(',')]
                        return all(c in DISPENSA_SLOTS for c in codigos if c)
                    df_lic_all = df_lic_all[~df_lic_all[col_tp_l2].apply(_is_slot)]
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
                tipo_l = st.selectbox("Tipo:", ["Convalescença", "Licença", "Outras Licenças", "Diligência", "Tribunal", "Instrução", "FCAA CTer", "Folga Complementar"], key="lic_tipo")
            with col_l2:
                ini_l = st.date_input("Data início:", format="DD/MM/YYYY", key="lic_ini")
                fim_l = st.date_input("Data fim:", format="DD/MM/YYYY", key="lic_fim")
            obs_l = st.text_input("Observações:", placeholder="ex: Tribunal de Braga", key="lic_obs")

            if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_lic"):
                try:
                    mid_l = mil_opts_l[mil_sel_l]
                    get_pg_loader().adicionar_licenca({"id": mid_l, "tipo": tipo_l, "inicio": ini_l.strftime('%d/%m/%Y'), "fim": fim_l.strftime('%d/%m/%Y'), "obs": obs_l.strip()})
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
                        _idx_rem = opts_rem_l[rem_sel_l]
                        _row_rem = df_lic_show.iloc[_idx_rem]
                        _id_rem = int(_row_rem.get("id", 0)) if "id" in _row_rem.index else 0
                        if _id_rem:
                            get_pg_loader().remover_licenca(_id_rem)
                            load_licencas.clear()
                            st.success("✅ Removido!")
                            st.rerun()
                        else:
                            st.error("Não foi possível identificar o registo")
                    except Exception as e:
                        st.error(f"Erro: {e}")

        # ── Tab Serviços/Horários ──
        with tab_disp_slot:
            st.markdown("#### 🔒 Dispensa de Serviço/Horário")
            st.caption("O militar é ignorado pelo gerar escala automático apenas para os slots seleccionados.")

            # Mostrar dispensas de slot activas
            df_lic_slot_all = load_licencas(ano_atual)
            if not df_lic_slot_all.empty and 'tipo' in df_lic_slot_all.columns:
                def _is_slot2(tipo_str):
                    codigos = [c.strip().upper() for c in str(tipo_str).replace(';',',').split(',')]
                    return any(c in DISPENSA_SLOTS for c in codigos if c)
                df_lic_slot_show = df_lic_slot_all[df_lic_slot_all['tipo'].apply(_is_slot2)]
                col_fim_sl = next((c for c in df_lic_slot_all.columns if 'fim' in c.lower()), None)
                if col_fim_sl:
                    df_lic_slot_show = df_lic_slot_show[df_lic_slot_show[col_fim_sl].apply(_lic_em_vigor)]
            else:
                df_lic_slot_show = pd.DataFrame()

            if not df_lic_slot_show.empty:
                # Mostrar com descrição dos slots
                def _desc_slots(tipo_str):
                    codigos = [c.strip().upper() for c in str(tipo_str).replace(';',',').split(',')]
                    descs = []
                    for c in codigos:
                        if c in DISPENSA_SLOTS:
                            sv, hr = DISPENSA_SLOTS[c]
                            descs.append(f"{c} ({sv} {hr})")
                    return ', '.join(descs)
                df_lic_slot_show = df_lic_slot_show.copy()
                df_lic_slot_show['slots'] = df_lic_slot_show['tipo'].apply(_desc_slots)
                st.dataframe(df_lic_slot_show, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dispensas de serviço/horário activas.")

            st.markdown("---")
            st.markdown("#### ➕ Adicionar dispensa de slot")

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                mil_opts_sl = {f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})".strip(): str(r.get('id',''))
                               for _, r in df_util.iterrows() if str(r.get('id','')).strip()}
                mil_sel_sl = st.selectbox("Militar:", list(mil_opts_sl.keys()), key="slot_mil")
                slots_opts = {
                    'A1 — Atendimento 00-08':           'A1',
                    'A2 — Atendimento 08-16':           'A2',
                    'A3 — Atendimento 16-24':           'A3',
                    'PO1 — Patrulha Ocorrências 00-08': 'PO1',
                    'PO2 — Patrulha Ocorrências 08-16': 'PO2',
                    'PO3 — Patrulha Ocorrências 16-24': 'PO3',
                    'AA2 — Apoio Atendimento 08-16':    'AA2',
                    'AA3 — Apoio Atendimento 16-24':    'AA3',
                }
                slots_sel = st.multiselect("Slots:", list(slots_opts.keys()), key="slot_sel")
            with col_s2:
                ini_sl = st.date_input("Data início:", format="DD/MM/YYYY", key="slot_ini")
                fim_sl = st.date_input("Data fim:", format="DD/MM/YYYY", key="slot_fim")

            if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_slot"):
                if not slots_sel:
                    st.warning("Selecciona pelo menos um slot.")
                else:
                    try:
                        mid_sl = mil_opts_sl[mil_sel_sl]
                        codigos_sl = ','.join(slots_opts[s] for s in slots_sel)
                        get_pg_loader().adicionar_licenca({"id": mid_sl, "tipo": codigos_sl, "inicio": ini_sl.strftime('%d/%m/%Y'), "fim": fim_sl.strftime('%d/%m/%Y'), "obs": ""})
                        load_licencas.clear()
                        st.success(f"✅ Dispensa de slot adicionada: {codigos_sl}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

            # Remover
            if not df_lic_slot_show.empty:
                st.markdown("---")
                st.markdown("#### 🗑️ Remover dispensa de slot")
                col_id_sl = 'id' if 'id' in df_lic_slot_show.columns else df_lic_slot_show.columns[0]
                col_in_sl = next((c for c in df_lic_slot_show.columns if 'ini' in c.lower()), None)
                opts_rem_sl = {f"{r[col_id_sl]} -- {r['tipo']} {r.get(col_in_sl,'')}" : i
                               for i, (_, r) in enumerate(df_lic_slot_show.iterrows())}
                rem_sel_sl = st.selectbox("Registo:", list(opts_rem_sl.keys()), key="slot_rem")
                if st.button("🗑️ Remover", key="btn_rem_slot", use_container_width=True):
                    try:
                        _idx_sl = opts_rem_sl[rem_sel_sl]
                        _row_sl = df_disp_slot.iloc[_idx_sl] if not df_disp_slot.empty else None
                        if _row_sl is not None and "id" in _row_sl.index:
                            get_pg_loader().remover_licenca(int(_row_sl.get("id", 0)))
                        load_licencas.clear()
                        st.success("✅ Removido!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # --- 📢 PUBLICAR ESCALA (ADMIN) ---
    elif menu == "📢 Publicar Escala":
        df_ferias = load_ferias(ano_atual)
        feriados = load_feriados(ano_atual)
        df_folgas = load_folgas(ano_atual)
        df_licencas = load_licencas(ano_atual)
        grupos_folga = load_grupos_folga()
        st.title("📢 Publicar Escala")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()
        dias_pub = load_dias_publicados()

        # Navegação dia a dia
        if 'pub_data_offset' not in st.session_state:
            st.session_state['pub_data_offset'] = 0

        d_pub = (datetime.now() + timedelta(days=st.session_state['pub_data_offset'])).date()
        aba_pub = d_pub.strftime("%d-%m")
        ja_publicado = aba_pub in dias_pub
        dia_semana = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"][d_pub.weekday()]

        # Barra de navegação
        col_ant, col_data, col_prox = st.columns([1, 3, 1])
        with col_ant:
            if st.button("◀", use_container_width=True, key="pub_ant"):
                st.session_state['pub_data_offset'] -= 1
                st.rerun()
        with col_data:
            st.markdown(
                f"<div style='text-align:center;padding:10px;background:white;border-radius:10px;"
                f"border:1.5px solid #E2E8F0;font-weight:700;font-size:1rem;color:#1A2B4A'>"
                f"{dia_semana}, {d_pub.strftime('%d/%m/%Y')}</div>",
                unsafe_allow_html=True
            )
        with col_prox:
            if st.button("▶", use_container_width=True, key="pub_prox"):
                st.session_state['pub_data_offset'] += 1
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Card de estado
        if ja_publicado:
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border:2px solid #059669;"
                f"border-radius:16px;padding:24px;text-align:center;margin-bottom:20px'>"
                f"<div style='font-size:2.5rem'>✅</div>"
                f"<div style='font-size:1.1rem;font-weight:800;color:#065F46;margin:8px 0'>Escala publicada</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            if st.button("🔒 Despublicar este dia", key="btn_despub", use_container_width=True):
                try:
                    get_pg_loader().despublicar_dia(aba_pub)
                    load_dias_publicados.clear()
                    load_data.clear()
                    st.success("✅ Despublicado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        else:
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#FFF7ED,#FED7AA);border:2px solid #F97316;"
                f"border-radius:16px;padding:24px;text-align:center;margin-bottom:20px'>"
                f"<div style='font-size:2.5rem'>📋</div>"
                f"<div style='font-size:1.1rem;font-weight:800;color:#9A3412;margin:8px 0'>Escala não publicada</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            if st.button("📢 PUBLICAR ESCALA", key="btn_pub", use_container_width=True, type="primary"):
                try:
                    get_pg_loader().publicar_dia(aba_pub)
                    load_dias_publicados.clear()
                    load_data.clear()
                    st.success(f"✅ Escala de **{d_pub.strftime('%d/%m/%Y')}** publicada!")
                    # Notificar via Railway (push notifications)
                    try:
                        import requests as _req
                        _req.post(
                            "https://portal-escalas-gnr-production.up.railway.app/api/notificacoes/publicar-escala",
                            json={"aba": aba_pub, "secret": "gnr-famalicao-2026"},
                            timeout=5
                        )
                    except Exception:
                        pass
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

        tab_pin, tab_add, tab_rem = st.tabs(["🔑 Gerir PIN", "➕ Adicionar Militar", "🗑️ Remover Militar"])

        # ── Tab Gerir PIN ──
        with tab_pin:
            if df_u_admin.empty:
                st.info("Sem utilizadores.")
            else:
                militares_opts_u = {
                    f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})": r
                    for _, r in df_u_admin.iterrows()
                }
                sel_u = st.selectbox("Selecionar militar:", list(militares_opts_u.keys()), key="sel_u_pin")
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
                                    h_u, salt_u = hash_pin(novo_pin)
                                    id_u = str(row_u.get('id', '')).strip()
                                    get_pg_loader().actualizar_pin(id_u, f"{h_u}:{salt_u}")
                                    load_utilizadores.clear()
                                    st.success(f"✅ PIN de **{row_u.get('nome','')}** atualizado!")
                                except Exception as e:
                                    st.error(f"Erro: {e}")

                if tem_pin:
                    st.markdown("---")
                    if st.button("🗑️ Remover PIN", use_container_width=True, key="btn_rem_pin"):
                        try:
                            id_u = str(row_u.get('id', '')).strip()
                            get_pg_loader().actualizar_pin(id_u, "")
                            load_utilizadores.clear()
                            st.success("✅ PIN removido.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

        # ── Tab Adicionar Militar ──
        with tab_add:
            st.markdown("#### ➕ Adicionar Novo Militar")
            st.caption("O militar é adicionado ao efetivo e colocado no topo de todos os slots do ordem_escala mais recente.")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                novo_id    = st.text_input("ID:", key="add_id")
                novo_nome  = st.text_input("Nome:", key="add_nome")
            with col_a2:
                novo_posto = st.text_input("Posto:", key="add_posto")
                novo_email = st.text_input("Email:", key="add_email")

            if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_mil"):
                if not novo_id.strip() or not novo_nome.strip():
                    st.warning("ID e Nome são obrigatórios.")
                elif novo_id.strip() in df_u_admin['id'].astype(str).str.strip().values:
                    st.error(f"❌ Já existe um militar com o ID {novo_id.strip()}.")
                else:
                    try:
                        # Adicionar no PostgreSQL
                        import psycopg2, os as _os_add
                        _db_url_add = str(st.secrets.get("DATABASE_URL", _os_add.environ.get("DATABASE_URL","")))
                        with psycopg2.connect(_db_url_add) as _conn_add:
                            with _conn_add.cursor() as _cur_add:
                                _cur_add.execute("""
                                    INSERT INTO utilizadores (id, nome, posto, email)
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT (id) DO UPDATE SET nome=EXCLUDED.nome, posto=EXCLUDED.posto, email=EXCLUDED.email
                                """, (novo_id.strip(), novo_nome.strip(), novo_posto.strip(), novo_email.strip()))
                            _conn_add.commit()

                        # Adicionar ao topo do ordem_escala mais recente
                        _pg_add = get_pg_loader()
                        aba_ord_mais_recente = sorted(load_lista_abas(), reverse=True)
                        if aba_ord_mais_recente:
                            aba_ord = aba_ord_mais_recente[0]
                            ordem_atual = _pg_add.carregar_ordem_escala(aba_ord)
                            if ordem_atual:
                                for slot in ordem_atual:
                                    if novo_id.strip() not in ordem_atual[slot]:
                                        ordem_atual[slot].insert(0, novo_id.strip())
                                _pg_add.guardar_ordem_escala(aba_ord, ordem_atual)

                        load_utilizadores.clear()
                        st.success(f"✅ Militar **{novo_nome.strip()}** (ID: {novo_id.strip()}) adicionado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao adicionar: {e}")

        # ── Tab Remover Militar ──
        with tab_rem:
            st.markdown("#### 🗑️ Remover Militar do Efetivo")
            st.caption("O militar é removido dos utilizadores e do ordem_escala mais recente.")
            if df_u_admin.empty:
                st.info("Sem utilizadores.")
            else:
                militares_opts_rem = {
                    f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})": r
                    for _, r in df_u_admin.iterrows()
                }
                sel_rem = st.selectbox("Selecionar militar a remover:", list(militares_opts_rem.keys()), key="sel_u_rem")
                row_rem = militares_opts_rem[sel_rem]
                mid_rem = str(row_rem.get('id', '')).strip()
                nome_rem = str(row_rem.get('nome', '')).strip()

                st.warning(f"⚠️ Tens a certeza que queres remover **{nome_rem}** (ID: {mid_rem}) do efetivo?")

                if st.button("🗑️ CONFIRMAR REMOÇÃO", use_container_width=True, type="primary", key="btn_conf_rem"):
                    try:
                        import psycopg2, os as _os_rem
                        _db_url_rem = str(st.secrets.get("DATABASE_URL", _os_rem.environ.get("DATABASE_URL","")))
                        with psycopg2.connect(_db_url_rem) as _conn_rem:
                            with _conn_rem.cursor() as _cur_rem:
                                _cur_rem.execute("DELETE FROM utilizadores WHERE id = %s", (mid_rem,))
                            _conn_rem.commit()

                        # Remover do ordem_escala
                        _pg_rem2 = get_pg_loader()
                        aba_ord_rem = sorted(load_lista_abas(), reverse=True)
                        if aba_ord_rem:
                            ordem_rem = _pg_rem2.carregar_ordem_escala(aba_ord_rem[0])
                            if ordem_rem:
                                for slot in ordem_rem:
                                    ordem_rem[slot] = [m for m in ordem_rem[slot] if m != mid_rem]
                                _pg_rem2.guardar_ordem_escala(aba_ord_rem[0], ordem_rem)

                        load_utilizadores.clear()
                        st.success(f"✅ Militar **{nome_rem}** removido!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao remover: {e}")
