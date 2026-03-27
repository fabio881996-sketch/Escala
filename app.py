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
    """Normaliza texto para comparação — remove acentos e coloca em minúsculas."""
    return unicodedata.normalize('NFKD', str(t).lower()).encode('ascii', 'ignore').decode('ascii')

def hash_pin(pin: str, salt: str = None):
    """Gera hash+salt de um PIN. Retorna (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{pin}".encode()).hexdigest()
    return h, salt

def verificar_pin(pin_input: str, pin_guardado: str) -> bool:
    """Verifica PIN — suporta texto simples (migração) e hash:salt."""
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
    import time
    for tentativa in range(3):
        try:
            sh = get_sheet()
            if sh is None:
                return pd.DataFrame()
            return _df_from_records(sh.worksheet(aba_nome).get_all_records())
        except Exception:
            if tentativa < 2:
                get_sheet.clear()
                time.sleep(1)
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

def invalidar_trocas():
    """Limpa cache de trocas."""
    load_data.clear()

@st.cache_data(ttl=3600)
def load_ferias(ano: int) -> pd.DataFrame:
    """Carrega plano de férias de um ano — cache 1h."""
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

@st.cache_data(ttl=86400)
@st.cache_data(ttl=60)
def load_dias_publicados() -> set:
    """Carrega datas publicadas da aba 'escala_publicada' — formato DD-MM."""
    try:
        sh = get_sheet()
        if sh is None:
            return set()
        ws = sh.worksheet("escala_publicada")
        valores = ws.col_values(1)
        return set(str(v).strip() for v in valores if str(v).strip() and str(v).strip() != 'data')
    except Exception:
        return set()

def load_feriados(ano: int) -> list:
    """Carrega feriados de um ano da aba 'feriados' — cache 24h."""
    try:
        sh = get_sheet()
        if sh is None:
            return []
        ws = sh.worksheet("feriados")
        valores = ws.get_all_values()
        if not valores:
            return []
        # Debug temporário — guardar em session_state para mostrar
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
    """Conta serviços históricos de um militar — cache 24h."""
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
                continue  # exceção — adjacente é atendimento/apoio
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
            # Se qualquer um dos serviços for atendimento/apoio — isento
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


def gerar_pdf_escala_dia(data: str, df_raw: pd.DataFrame) -> bytes:
    """Gera PDF da escala diaria em A4 retrato usando reportlab - layout original."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white, black
    from datetime import datetime as _dt

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

    df_aus,  df_rest = filtrar(r"ferias|licen|doente|folga", df_raw_com)
    df_adm,  df_rest = filtrar(r"pronto|secretaria|inquer|comando|dilig", df_rest)
    df_ap,   df_rest = filtrar(r"apoio", df_rest)
    df_at,   df_rest = filtrar(r"atendimento", df_rest)
    df_pat,  df_rest = filtrar(r"po|patrulha|ronda|vtr|giro", df_rest)
    df_rem,  df_rest = filtrar(r"remu|grat", df_rest)
    df_outros = df_rest

    # Agrupar patrulha ocorrencias por horario
    df_ocorr = df_pat[df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()
    df_outras_pat = df_pat[~df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()

    AZUL_ESC  = HexColor("#14285f")
    AZUL_MED  = HexColor("#cdd7f2")
    FILL_ALT  = HexColor("#ebf1ff")
    CINZA_LN  = HexColor("#c0c0c0")
    CINZA_TXT = HexColor("#787878")

    W, H = A4
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    # ---- helpers ----
    LM = 10*mm   # margem esquerda
    RM = 10*mm   # margem direita
    TW = W - LM - RM  # largura total

    def new_page():
        c.showPage()
        return H - 10*mm

    def draw_header(y):
        box_w = 50*mm
        box_h = 20*mm
        header_w = TW - box_w - 2*mm

        # Cabeçalho azul — só à esquerda
        c.setFillColor(AZUL_ESC)
        c.rect(LM, y-box_h, header_w, box_h, fill=1, stroke=0)
        c.setFillColor(white)
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

        # Caixa de assinatura — canto superior direito, mesma altura
        box_x = LM + header_w + 2*mm
        box_y = y - box_h
        c.setStrokeColor(AZUL_ESC)
        c.setLineWidth(1)
        c.rect(box_x, box_y, box_w, box_h, fill=0, stroke=1)
        c.setFillColor(AZUL_ESC)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(box_x + box_w/2, box_y + box_h - 4*mm, "O COMANDANTE")
        c.setFillColor(CINZA_TXT)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(box_x + box_w/2, box_y + 3.5*mm, "Hugo Alexandre Ferreira do Carmo")
        c.drawCentredString(box_x + box_w/2, box_y + 1*mm, "Sargento-Ajudante")
        c.setLineWidth(0.5)

        return y - box_h - 2*mm

    def sec_title(y, label, x=LM, w=TW):
        c.setFillColor(AZUL_ESC)
        c.rect(x, y-5.5*mm, w, 5.5*mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x+2*mm, y-4*mm, f"  {label.upper()}")
        return y - 6.5*mm

    def tbl_header(y, cols, widths, x=LM):
        c.setFillColor(AZUL_MED)
        c.rect(x, y-5*mm, sum(widths), 5*mm, fill=1, stroke=0)
        c.setFillColor(HexColor("#0f235a"))
        c.setFont("Helvetica-Bold", 8.5)
        xi = x
        for col, w in zip(cols, widths):
            c.drawCentredString(xi + w/2, y-3.5*mm, col)
            xi += w
        c.setStrokeColor(CINZA_LN)
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
    y = H - 10*mm
    y = draw_header(y)
    y -= 2*mm

    # ---- AUSÊNCIAS e ADM lado a lado ----
    CW2 = TW/2 - 1*mm   # largura de cada coluna
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
    sec_title(y_col, "Ausências, Folgas e Licenças", x=LM, w=CW2)
    if grupos_adm:
        sec_title(y_col, "Outras Situações / ADM", x=LM+CW2+GAP, w=CW2)
    y_col -= 6.5*mm

    # Linhas esquerda
    y_esq = y_col
    max_pts_esq = CW2 - 37*mm  # já em pontos
    label_w_esq = 35*mm
    for serv, ids in grupos_aus.items():
        ids_txt = ", ".join(ids)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(AZUL_ESC)
        c.drawString(LM+2*mm, y_esq-3.5*mm, f"  {serv}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(black)
        # Wrap IDs em múltiplas linhas
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
        for li, ln in enumerate(linhas_ids):
            indent = LM+label_w_esq if li == 0 else LM+5*mm
            c.drawString(indent, y_esq-3.5*mm, ln)
            y_esq -= 5*mm

    # Linhas direita
    y_dir = y_col
    x_dir = LM + CW2 + GAP
    max_pts_dir = CW2 - 37*mm
    for serv, ids in grupos_adm.items():
        ids_txt = ", ".join(ids)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(AZUL_ESC)
        c.drawString(x_dir+2*mm, y_dir-3.5*mm, f"  {serv}:")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(black)
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
        for li, ln in enumerate(linhas_ids):
            indent = x_dir+label_w_esq if li == 0 else x_dir+5*mm
            c.drawString(indent, y_dir-3.5*mm, ln)
            y_dir -= 5*mm

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

        # Coluna esquerda — Atendimento
        y_esq2 = y_at
        if not df_at.empty:
            wids_at_l = [20*mm, CW2-20*mm]
            y_esq2 = tbl_header(y_at, cols_at, wids_at_l, x=LM)
            fill = False
            for hor, grp in df_at.groupby("horário", sort=False):
                ids = ", ".join(grp["id_fmt"].tolist())
                y_esq2 = tbl_row(y_esq2, [hor, ids], wids_at_l, fill, x=LM)
                fill = not fill

        # Coluna direita — Apoio
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
        wids_oc = [18*mm, 35*mm, 42*mm, 22*mm, 22*mm, 51*mm]
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
        wids_pp = [18*mm, 35*mm, 37*mm, 22*mm, 22*mm, 36*mm, 20*mm]
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
        wids_ot = [18*mm, 35*mm, 42*mm, 22*mm, 22*mm, 51*mm]
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
        wids_rm = [15*mm, 25*mm, TW-40*mm]
        cols_rm = ["Horário", "Militares", "Observação"]
        y = tbl_header(y, cols_rm, wids_rm)
        fill = False

        x_obs_start = LM + wids_rm[0] + wids_rm[1] + 2*mm
        x_obs_end   = LM + TW - 2*mm
        max_pts_rm  = x_obs_end - x_obs_start  # já em pontos, não multiplicar
        for hor, grp in df_rem.groupby("horário", sort=False):
            ids = ", ".join(grp["id_fmt"].tolist())
            obs = str(grp["observações"].iloc[0]) if "observações" in grp.columns else ""
            if obs == 'nan': obs = ""
            obs_lines = wrap_text(obs, max_pts_rm) if obs else [""]
            ids_lines = wrap_text(ids, (wids_rm[1] - 2*mm))
            row_h = max(5*mm, max(len(obs_lines), len(ids_lines)) * 5*mm)
            if y - row_h < 20*mm: y = new_page()
            if fill:
                c.setFillColor(FILL_ALT)
                c.rect(LM, y-row_h, TW, row_h, fill=1, stroke=0)
            c.setFillColor(black)
            c.setFont("Helvetica", 8.5)
            c.drawCentredString(LM+wids_rm[0]/2, y-3.5*mm, str(hor))
            for li, id_l in enumerate(ids_lines):
                c.drawCentredString(LM+wids_rm[0]+wids_rm[1]/2, y-(li*5*mm)-3.5*mm, id_l)
            for li, obs_l in enumerate(obs_lines):
                c.drawString(x_obs_start, y-(li*5*mm)-3.5*mm, obs_l)
            c.setStrokeColor(CINZA_LN)
            c.rect(LM, y-row_h, TW, row_h, fill=0, stroke=1)
            c.line(LM+wids_rm[0], y, LM+wids_rm[0], y-row_h)
            c.line(LM+wids_rm[0]+wids_rm[1], y, LM+wids_rm[0]+wids_rm[1], y-row_h)
            y -= row_h
            fill = not fill
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
                                        # Verificar PIN — suporta texto simples e hash
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

    # ── MODO EMAIL/PASSWORD ── (removido — login só por PIN)
    # ── MODO REGISTAR PIN ── (removido — PINs criados pelos admins)



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
            menu_opt += ["", "🏖️ Férias", "📊 Estatísticas", "⚖️ Validar Trocas", "📜 Trocas Validadas", "🚨 Alertas", "⚙️ Gerar Escala", "👤 Gerir Utilizadores"]

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
                dias_publicados_cal = load_dias_publicados() if not is_admin else None
                for d in range(1, n_dias + 1):
                    dt_cal = datetime(ano_sel, mes_sel, d)
                    aba = dt_cal.strftime("%d-%m")
                    # Não-admins: só mostrar dias publicados
                    if not is_admin and dias_publicados_cal is not None and aba not in dias_publicados_cal:
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
                dias_publicados = load_dias_publicados()

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
                sel_mil_f = st.selectbox("Selecionar militar:", ["— O meu próprio —"] + list(militares_opts_f.keys()))
                alvo_id_f = u_id if sel_mil_f == "— O meu próprio —" else militares_opts_f[sel_mil_f]
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
        d_sel  = st.date_input("Seleciona a data:", format="DD/MM/YYYY")
        aba_sel = d_sel.strftime("%d-%m")

        # Não-admins: só ver dias publicados
        if not is_admin and aba_sel not in load_dias_publicados():
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
                    if militar_de_ferias(mid_f, d_sel, df_ferias, feriados):
                        nova_linha = {c: '' for c in df_at.columns}
                        nova_linha['id'] = mid_f
                        nova_linha['id_disp'] = mid_f
                        nova_linha['serviço'] = 'Férias'
                        nova_linha['horário'] = ''
                        df_at = pd.concat([df_at, pd.DataFrame([nova_linha])], ignore_index=True)

            pdf_bytes = gerar_pdf_escala_dia(d_sel.strftime("%d/%m/%Y"), df_at)
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
    # --- 🔄 TROCAS ---
    elif menu == "🔄 Trocas":
        st.title("🔄 Trocas")
        tab_sol, tab_ped, tab_hist = st.tabs(["📨 Solicitar", "📥 Pedidos Recebidos", "📋 Histórico"])

        with tab_sol:
            st.title("🔄 Solicitar Troca de Serviço")

            tipo_troca = st.radio(
                "Tipo de pedido:",
                ["🔄 Troca Simples", "🔁 Troca a 3", "💶 Fazer Remunerado"],
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

                # IDs que já têm troca pendente nesse dia — excluir das listas
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

                # Função auxiliar — remunerado não cedido é impedimento
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
                        # Remunerados que NÃO foram cedidos — são impedimento
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
                            # Folgas — verificar só o descanso do militar de folga (destino)
                            for _, row_c in cols_folga.iterrows():
                                id_c   = str(row_c['id'])
                                serv_c = str(row_c['serviço'])
                                hor_c  = str(row_c['horário'])
                                erros_destino = verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg)
                                erros_dest_only = [e for e in erros_destino if e.startswith("O militar de destino")]
                                if not erros_dest_only:
                                    nome_c = get_nome_curto(df_util, id_c)
                                    opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")
                            # Restantes — com verificação de descanso
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
                            (df_d['id'].astype(str).str.strip() != 'nan') &
                            (~df_d['id'].astype(str).str.strip().isin(ids_com_troca))
                        ]
                        outros_t3 = outros_t3[~outros_t3['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False)]
                        outros_t3 = outros_t3[~outros_t3['id'].astype(str).apply(_tem_rem_nao_cedido)]
                        opcoes_t3 = {f"{r['id']} {get_nome_curto(df_util, str(r['id']))} — {r['serviço']} ({r['horário']})": r['id'] for _, r in outros_t3.iterrows() if str(r['id']).strip()}
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
                            - **{sel1}** `{serv1}` → fica com o serviço do 2º
                            - **{sel2}** `{serv2}` → fica com o teu serviço
                            """)
                            if st.button("📨 Enviar pedidos de troca a 3", use_container_width=True):
                                data_str = dt_s.strftime('%d/%m/%Y')
                                meu_serv_t3_completo = servico_override if servico_override else f"{meu_serv_t3} ({meu_hor_t3})"
                                # Tu → 1º (tu dás o teu serviço ao 1º, recebes o serv1)
                                linha1 = [data_str, u_id, meu_serv_t3_completo, id1, f"{serv1} ({hor1})", "Pendente_Militar", "", "", ""]
                                # 2º → 1º (2º dá o seu serviço ao 1º, 1º recebe serv2)
                                linha2 = [data_str, id2, f"{serv2} ({hor2})", id1, meu_serv_t3_completo, "Pendente_Militar", "", "", ""]
                                salvar_troca_gsheet(linha1)
                                salvar_troca_gsheet(linha2)
                                st.success("✅ Dois pedidos de troca enviados! Aguarda aceitação de ambos.")

                # ── Fazer Remunerado ──
                elif tipo_troca == "💶 Fazer Remunerado":
                    _imp_rem = r'ferias|licen|doente|dilig|tribunal|pronto|secretaria|inquer'
                    _motivo_imp = ''
                    if not meu.empty and re.search(_imp_rem, norm(meu.iloc[0]['serviço'])):
                        _motivo_imp = meu.iloc[0]['serviço']
                    elif militar_de_ferias(u_id, dt_s, df_ferias, feriados):
                        _motivo_imp = 'Férias'
                    if _motivo_imp:
                        st.warning(f"Não podes fazer remunerados — estás com **{_motivo_imp}**.")
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

        # --- 📥 PEDIDOS RECEBIDOS ---
        with tab_ped:
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
                            atualizar_status_gsheet(idx, "Pendente_Admin")
                            st.rerun()
                        if c2.button("❌ RECUSAR", key=f"re_{idx}", use_container_width=True):
                            atualizar_status_gsheet(idx, "Recusada")
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
                            titulo = f"{cor} {r['data']} — Fazer Remunerado: {outro_serv} ({status})"
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
                                        invalidar_trocas()
                                        st.success("Pedido cancelado.")
                                        st.rerun()

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
                df_a_serv = df_a[~df_a['serviço'].apply(norm).str.contains('remu|grat', na=False)]
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
                            (~df_a['serviço'].apply(norm).str.contains('remu|grat|folga|ferias|licen|doente', na=False))
                        ]
                        rows_ant = df_ant_a[
                            (df_ant_a['id'].astype(str) == mid) &
                            (~df_ant_a['serviço'].apply(norm).str.contains('remu|grat|folga|ferias|licen|doente', na=False))
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
                    if militar_de_ferias(mid, dt_a.date(), df_ferias, feriados):
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

        # --- ⚙️ GERAR ESCALA (ADMIN) ---
    elif menu == "⚙️ Gerar Escala":
        st.title("⚙️ Gerar Escala Automática")
        if not is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()


        # ── Processar confirmação pendente ──
        form_key = 'FormSubmitter:form_confirmar_escala-✅ CONFIRMAR E ESCREVER NA ESCALA'
        if st.session_state.get(form_key) and 'escala_gerada' in st.session_state:
            del st.session_state[form_key]
            dados = st.session_state['escala_gerada']
            escalados_c = dados['escalados']
            ordem_c = dados['ordem_atualizada']
            headers_c = dados['ordem_headers']
            aba_c = dados['aba_dia']
            try:
                sh_c = get_sheet()
                ws_dia_c = sh_c.worksheet(aba_c)
                linhas_c = ws_dia_c.get_all_values()
                hdrs = [h.strip().lower() for h in linhas_c[0]]
                ix_id   = hdrs.index('id')      if 'id'      in hdrs else 0
                ix_serv = hdrs.index('serviço') if 'serviço' in hdrs else 1
                ix_hor  = hdrs.index('horário') if 'horário' in hdrs else 2
                from collections import defaultdict
                agr = defaultdict(list)
                simp = []
                for mid, serv, hor in escalados_c:
                    if serv == "Patrulha Ocorrências":
                        agr[(serv, hor)].append(mid)
                    else:
                        simp.append((mid, serv, hor))
                emap = {}
                for (serv, hor), ids in agr.items():
                    emap[(norm(serv), hor.strip())] = ';'.join(ids)
                for mid, serv, hor in simp:
                    emap[(norm(serv), hor.strip())] = mid
                upd = []
                for i, row in enumerate(linhas_c[1:], start=2):
                    sc = norm(row[ix_serv].strip()) if ix_serv < len(row) else ''
                    hc = str(row[ix_hor]).strip() if ix_hor < len(row) else ''
                    ic = str(row[ix_id]).strip()  if ix_id  < len(row) else ''
                    ch = (sc, hc)
                    if ch in emap and not ic:
                        cl = chr(ord('A') + ix_id)
                        upd.append({'range': f'{cl}{i}', 'values': [[emap[ch]]]})
                        del emap[ch]
                if upd:
                    ws_dia_c.batch_update(upd)

                # Escrever disponíveis na linha "Disponíveis"
                if dados.get('todos_disponiveis'):
                    ids_disp = ';'.join(dados['todos_disponiveis'])
                    for i, row in enumerate(linhas_c[1:], start=2):
                        sc2 = norm(row[ix_serv].strip()) if ix_serv < len(row) else ''
                        ic2 = str(row[ix_id]).strip() if ix_id < len(row) else ''
                        if sc2 == 'disponiveis' and not ic2:
                            cl = chr(ord('A') + ix_id)
                            ws_dia_c.update(f'{cl}{i}', [[ids_disp]])
                            break
                nova_o = [headers_c]
                ml = max(len(v) for v in ordem_c.values())
                for i in range(ml):
                    nova_o.append([ordem_c[h][i] if i < len(ordem_c[h]) else '' for h in headers_c])

                # Contabilizar escalas manuais — mover para o fim da coluna respetiva
                _slots_map = {
                    (norm("Atendimento"),          "00-08"): "Atendimento 00-08",
                    (norm("Atendimento"),          "08-16"): "Atendimento 08-16",
                    (norm("Atendimento"),          "16-24"): "Atendimento 16-24",
                    (norm("Patrulha Ocorrências"), "00-08"): "Patrulha Ocorrências 00-08",
                    (norm("Patrulha Ocorrências"), "08-16"): "Patrulha Ocorrências 08-16",
                    (norm("Patrulha Ocorrências"), "16-24"): "Patrulha Ocorrências 16-24",
                    (norm("Apoio Atendimento"),    "08-16"): "Apoio Atendimento 08-16",
                    (norm("Apoio Atendimento"),    "16-24"): "Apoio Atendimento 16-24",
                }
                # IDs já escalados automaticamente
                ids_auto = set(m for m, _, _ in escalados_c)
                for row_m in linhas_c[1:]:
                    serv_m = norm(row_m[ix_serv].strip()) if ix_serv < len(row_m) else ''
                    hor_m  = str(row_m[ix_hor]).strip()   if ix_hor  < len(row_m) else ''
                    id_m   = str(row_m[ix_id]).strip()    if ix_id   < len(row_m) else ''
                    if not id_m or id_m == 'nan':
                        continue
                    col_key_m = _slots_map.get((serv_m, hor_m))
                    if not col_key_m or col_key_m not in ordem_c:
                        continue
                    for mid_m in re.split(r'[;,]', id_m):
                        mid_m = mid_m.strip()
                        if not mid_m or mid_m in ids_auto:
                            continue
                        # É escala manual — mover para o fim da coluna
                        if mid_m in ordem_c[col_key_m]:
                            ordem_c[col_key_m].remove(mid_m)
                            ordem_c[col_key_m].append(mid_m)

                # Recalcular nova_o com manuais incluídos
                nova_o = [headers_c]
                ml = max(len(v) for v in ordem_c.values())
                for i in range(ml):
                    nova_o.append([ordem_c[h][i] if i < len(ordem_c[h]) else '' for h in headers_c])

                # Criar ordem_escala do dia seguinte
                from datetime import datetime as _dt_c
                d_gerar_c = _dt_c.strptime(f"{aba_c}-{_dt_c.now().year}", "%d-%m-%Y")
                nome_novo = f"ordem_escala {(d_gerar_c + timedelta(days=1)).strftime('%d-%m')}"
                try:
                    sh_c.worksheet(nome_novo).clear()
                    sh_c.worksheet(nome_novo).update('A1', nova_o)
                except:
                    ws_ord_c2 = sh_c.add_worksheet(title=nome_novo, rows=100, cols=len(headers_c))
                    ws_ord_c2.update('A1', nova_o)

                load_data.clear()
                del st.session_state['escala_gerada']
                st.session_state['escala_ok'] = True
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao escrever: {e}")

        # ── Selecionar data(s) ──
        modo = st.radio("Modo:", ["📅 Dia único", "📆 Intervalo de dias"], horizontal=True)
        if modo == "📅 Dia único":
            d_gerar = st.date_input("Data a escalar:", format="DD/MM/YYYY")
            datas_gerar = [d_gerar]
        else:
            col_ini, col_fim = st.columns(2)
            with col_ini:
                d_ini = st.date_input("Data início:", format="DD/MM/YYYY")
            with col_fim:
                d_fim = st.date_input("Data fim:", format="DD/MM/YYYY")
            datas_gerar = []
            d_cur = d_ini
            while d_cur <= d_fim:
                datas_gerar.append(d_cur)
                d_cur += timedelta(days=1)
            st.caption(f"{len(datas_gerar)} dias selecionados")

        aba_dia = datas_gerar[0].strftime("%d-%m") if datas_gerar else ""

        if st.button("⚙️ GERAR ESCALA", use_container_width=True, type="primary"):
            with st.spinner("A gerar escala..."):
                try:
                    sh = get_sheet()

                    # ── Carregar serviços (uma vez) ──
                    ws_serv = sh.worksheet("serviços")
                    serv_vals = ws_serv.get_all_values()
                    serv_headers = [str(h).strip() for h in serv_vals[0]]
                    df_serv = pd.DataFrame(serv_vals[1:], columns=serv_headers)
                    militares_servicos = {}
                    for col in serv_headers:
                        ids_col = [str(v).strip() for v in df_serv[col] if str(v).strip()]
                        for mid in ids_col:
                            if mid not in militares_servicos:
                                militares_servicos[mid] = []
                            militares_servicos[mid].append(col)

                    df_ferias_g = load_ferias(datas_gerar[0].year)
                    feriados_g  = load_feriados(datas_gerar[0].year)

                    # Ordem inicial — do primeiro dia
                    aba_primeiro = datas_gerar[0].strftime("%d-%m")
                    aba_ordem_dia = f"ordem_escala {aba_primeiro}"
                    aba_ordem_ant = f"ordem_escala {(datas_gerar[0] - timedelta(days=1)).strftime('%d-%m')}"
                    try:
                        ws_ordem = sh.worksheet(aba_ordem_dia)
                    except:
                        try:
                            ws_ordem = sh.worksheet(aba_ordem_ant)
                        except:
                            st.error("Não foi encontrado nenhum snapshot de ordem_escala.")
                            st.stop()
                    ordem_vals = ws_ordem.get_all_values()
                    ordem_headers = [str(h).strip() for h in ordem_vals[0]]
                    ordem_atual = {h: [] for h in ordem_headers}
                    for row in ordem_vals[1:]:
                        for i, h in enumerate(ordem_headers):
                            val = str(row[i]).strip() if i < len(row) else ''
                            if val:
                                ordem_atual[h].append(val)

                    resultados_dias = []  # lista de dicts por dia

                    for d_gerar in datas_gerar:
                        aba_dia_loop = d_gerar.strftime("%d-%m")

                        # Aba do dia
                        try:
                            ws_dia_loop = sh.worksheet(aba_dia_loop)
                            dia_vals_loop = ws_dia_loop.get_all_values()
                            dia_headers_loop = [str(h).strip().lower() for h in dia_vals_loop[0]]
                            df_dia_loop = pd.DataFrame(dia_vals_loop[1:], columns=dia_headers_loop)
                            df_dia_loop = df_dia_loop[df_dia_loop.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
                        except:
                            # Aba não existe — saltar dia
                            continue

                        # Indisponíveis
                        ids_indisponiveis = set()
                        if not df_dia_loop.empty and 'id' in df_dia_loop.columns:
                            for _, row in df_dia_loop.iterrows():
                                mid = str(row.get('id', '')).strip()
                                if mid and mid != 'nan':
                                    for m in re.split(r'[;,]', mid):
                                        m = m.strip()
                                        if m: ids_indisponiveis.add(m)
                        todos_ids = list(militares_servicos.keys())
                        for mid in todos_ids:
                            if militar_de_ferias(mid, d_gerar, df_ferias_g, feriados_g):
                                ids_indisponiveis.add(mid)

                        # Slots preenchidos
                        slots_preenchidos = {}
                        if not df_dia_loop.empty and 'id' in df_dia_loop.columns and 'serviço' in df_dia_loop.columns:
                            for _, row in df_dia_loop.iterrows():
                                mid_r = str(row.get('id', '')).strip()
                                serv_r = norm(str(row.get('serviço', '')).strip())
                                hor_r  = str(row.get('horário', '')).strip()
                                if mid_r and mid_r != 'nan' and serv_r and hor_r:
                                    chave_r = (serv_r, hor_r)
                                    slots_preenchidos[chave_r] = slots_preenchidos.get(chave_r, 0) + len([x for x in re.split(r'[;,]', mid_r) if x.strip()])

                        SLOTS = [
                            ("Atendimento",          "00-08", 1),
                            ("Atendimento",          "08-16", 1),
                            ("Atendimento",          "16-24", 1),
                            ("Patrulha Ocorrências",  "00-08", 2),
                            ("Patrulha Ocorrências",  "08-16", 2),
                            ("Patrulha Ocorrências",  "16-24", 2),
                            ("Apoio Atendimento",     "08-16", 1),
                            ("Apoio Atendimento",     "16-24", 1),
                        ]
                        SLOTS_AJUSTADOS = []
                        for servico_s, horario_s, num_s in SLOTS:
                            chave_s = (norm(servico_s), horario_s)
                            ja = slots_preenchidos.get(chave_s, 0)
                            vagas = max(0, num_s - ja)
                            if vagas > 0:
                                SLOTS_AJUSTADOS.append((servico_s, horario_s, vagas))

                        escalados = []
                        ids_escalados = set()
                        ordem_atualizada = {h: list(v) for h, v in ordem_atual.items()}
                        df_ant_g = load_data((d_gerar - timedelta(days=1)).strftime("%d-%m"))
                        _servicos_escalaveis = ['atendimento', 'patrulha ocorrencias', 'apoio atendimento', 'patrulha ocorrências']

                        for servico, horario, num in SLOTS_AJUSTADOS:
                            col_key = f"{servico} {horario}"
                            if col_key not in ordem_atualizada:
                                continue
                            lista = ordem_atualizada[col_key]
                            colocados = []
                            for mid in lista:
                                if len(colocados) >= num: break
                                if mid in ids_indisponiveis or mid in ids_escalados: continue
                                if servico not in militares_servicos.get(mid, []): continue
                                ini_novo_g, _ = _parse_horario(horario)
                                if ini_novo_g is not None and ini_novo_g < 480:
                                    d_ant = d_gerar - timedelta(days=1)
                                    if militar_de_ferias(mid, d_ant, df_ferias_g, feriados_g): continue
                                    cols_f = df_ferias_g.columns.tolist()
                                    id_col_f = 'id' if 'id' in cols_f else cols_f[0]
                                    mil_f2 = df_ferias_g[df_ferias_g[id_col_f].astype(str).str.strip() == str(mid).strip()]
                                    fim_hoje = False
                                    for _, row_f2 in mil_f2.iterrows():
                                        for fc in [c for c in cols_f if 'fim' in c.lower()]:
                                            fs = str(row_f2.get(fc, '')).strip()
                                            if not fs or fs == 'nan': continue
                                            fd = _parse_data_ferias(fs, d_gerar.year)
                                            if not fd: continue
                                            fr = _fim_ferias_real(fd, feriados_g)
                                            if fr == d_gerar: fim_hoje = True; break
                                        if fim_hoje: break
                                    if fim_hoje: continue
                                if not df_ant_g.empty:
                                    rows_ant = df_ant_g[df_ant_g['id'].astype(str).str.strip() == mid]
                                    ini_novo_g2, _ = _parse_horario(horario)
                                    descanso_ok = True
                                    for _, r_ant in rows_ant.iterrows():
                                        hor_ant = str(r_ant.get('horário', '')).strip()
                                        if not hor_ant: continue
                                        _, fim_ant_g = _parse_horario(hor_ant)
                                        if fim_ant_g is None or ini_novo_g2 is None: continue
                                        if (1440 - fim_ant_g) + ini_novo_g2 < 480:
                                            descanso_ok = False; break
                                    if not descanso_ok: continue
                                colocados.append(mid)
                                ids_escalados.add(mid)
                                escalados.append((mid, servico, horario))
                            for mid in colocados:
                                ordem_atualizada[col_key].remove(mid)
                                ordem_atualizada[col_key].append(mid)

                        todos_disponiveis = [mid for mid in todos_ids
                                            if mid not in ids_indisponiveis and mid not in ids_escalados]

                        resultados_dias.append({
                            'data': d_gerar,
                            'aba': aba_dia_loop,
                            'escalados': escalados,
                            'disponiveis': todos_disponiveis,
                            'ordem_atualizada': ordem_atualizada,
                        })

                        # Atualizar ordem para o próximo dia
                        ordem_atual = ordem_atualizada

                    st.session_state['escala_gerada_multi'] = {
                        'resultados': resultados_dias,
                        'ordem_headers': ordem_headers,
                    }


                except Exception as e:
                    st.error(f"Erro ao gerar escala: {e}")

            # ── Mostrar resultado multi-dia (fora do bloco gerar) ──
            if 'escala_gerada_multi' in st.session_state:
                dados_multi = st.session_state['escala_gerada_multi']
                resultados = dados_multi['resultados']
                ordem_headers = dados_multi['ordem_headers']

                total_escalados = sum(len(r['escalados']) for r in resultados)
                st.success(f"✅ {len(resultados)} dia(s) gerados — {total_escalados} militares escalados no total!")
                st.markdown("---")

                for res in resultados:
                    data_str = res['data'].strftime('%d/%m/%Y')
                    escalados_r = res['escalados']
                    disponiveis_r = res['disponiveis']
                    with st.expander(f"📅 {data_str} — {len(escalados_r)} escalados", expanded=len(resultados)==1):
                        if escalados_r:
                            df_res = pd.DataFrame(escalados_r, columns=['ID', 'Serviço', 'Horário'])
                            df_res['Nome'] = df_res['ID'].apply(lambda x: get_nome_curto(df_util, x))
                            st.dataframe(df_res[['ID', 'Nome', 'Serviço', 'Horário']], use_container_width=True, hide_index=True)
                        if disponiveis_r:
                            st.markdown("**👥 Militares de sobra:**")
                            sobra = [{'ID': mid, 'Nome': get_nome_curto(df_util, mid)} for mid in disponiveis_r]
                            st.dataframe(pd.DataFrame(sobra), use_container_width=True, hide_index=True)

                st.markdown("---")
                if st.button("✅ CONFIRMAR E ESCREVER NA ESCALA", use_container_width=True, type="primary", key="btn_confirmar_escala"):
                    st.session_state['confirmar_escala'] = True

                if st.session_state.get('confirmar_escala', False):
                    st.session_state['confirmar_escala'] = False
                    try:
                        sh2 = get_sheet()
                        from collections import defaultdict
                        for res in resultados:
                            aba_r = res['aba']
                            escalados_r = res['escalados']
                            ordem_r = res['ordem_atualizada']
                            data_r = res['data']

                            ws_dia_r = sh2.worksheet(aba_r)
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

                            # Escrever disponíveis
                            if res['disponiveis']:
                                ids_disp_r = ';'.join(res['disponiveis'])
                                for i, row in enumerate(todas_linhas_r[1:], start=2):
                                    sc2 = norm(row[ix_serv_r].strip()) if ix_serv_r < len(row) else ''
                                    ic2 = str(row[ix_id_r]).strip() if ix_id_r < len(row) else ''
                                    if sc2 == 'disponiveis' and not ic2:
                                        cl2 = chr(ord('A') + ix_id_r)
                                        ws_dia_r.update(f'{cl2}{i}', [[ids_disp_r]])
                                        break

                            # Criar ordem_escala do dia seguinte
                            from datetime import datetime as _dt_r
                            nome_prox = f"ordem_escala {(data_r + timedelta(days=1)).strftime('%d-%m')}"
                            nova_o_r = [ordem_headers]
                            ml_r = max(len(v) for v in ordem_r.values())
                            for i in range(ml_r):
                                nova_o_r.append([ordem_r[h][i] if i < len(ordem_r[h]) else '' for h in ordem_headers])
                            try:
                                sh2.worksheet(nome_prox).clear()
                                sh2.worksheet(nome_prox).update('A1', nova_o_r)
                            except:
                                ws_prox = sh2.add_worksheet(title=nome_prox, rows=100, cols=len(ordem_headers))
                                ws_prox.update('A1', nova_o_r)

                        load_data.clear()
                        del st.session_state['escala_gerada_multi']
                        st.session_state['escala_ok'] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao escrever: {e}")

        if st.session_state.pop('escala_ok', False):
            st.success("✅ Escala escrita e ordem atualizada!")

        # ── Publicar escala ──
        st.markdown("---")
        st.markdown("#### 📢 Publicar Escala")
        dias_pub = load_dias_publicados()
        d_pub = st.date_input("Data a publicar:", format="DD/MM/YYYY", key="d_pub")
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
                        idx_p = todos.index(aba_pub) + 1
                        ws_p.delete_rows(idx_p)
                    load_dias_publicados.clear()
                    st.success("✅ Escala despublicada!")
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
