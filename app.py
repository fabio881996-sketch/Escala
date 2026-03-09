import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

# CSS para garantir que o visual não quebre
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def get_gspread_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro nas Credenciais: {e}")
        return None

def load_sheet(aba_nome):
    try:
        # Tentativa de leitura via CSV (mais rápido)
        url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df.replace("nan", "")
    except:
        # Se falhar o CSV (ex: permissões), tenta via API gspread
        try:
            client = get_gspread_client()
            if client:
                sh = client.open_by_url(st.secrets["gsheet_url"])
                worksheet = sh.worksheet(aba_nome)
                df = pd.DataFrame(worksheet.get_all_records()).astype(str)
                df.columns = [c.strip().lower() for c in df.columns]
                return df
        except:
            return None
    return None

def registrar_troca_excel(dados_lista):
    client = get_gspread_client()
    if client:
        try:
            sh = client.open_by_url(st.secrets["gsheet_url"])
            worksheet = sh.worksheet("registos_trocas")
            worksheet.append_row(dados_lista)
            return True
        except Exception as e:
            st.error(f"Erro ao escrever na aba: {e}")
    return False

# --- TELA DE LOGIN ---
def login_screen():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u_input = st.text_input("📧 Email").strip().lower()
            p_input = st.text_input("🔑 Password", type="password").strip()
            
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    user_match = df_u[(df_u['email'].astype(str).str.lower() == u_input) & (df_u['password'].astype(str) == p_input)]
                    if not user_match.empty:
                        res = user_match.iloc[0]
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = str(res['id'])
                        st.session_state["user_nome"] = f"{res['posto']} {res['nome']}"
                        st.rerun()
                    else:
                        st.error("Utilizador ou password incorretos.")
                else:
                    st.error("Erro: Não foi possível aceder à folha de utilizadores. Verifique a partilha com o robô.")

# --- APP APÓS LOGIN ---
def main_app():
    with st.sidebar:
        st.markdown(f"<div style='text-align:center;'><h3>👮‍♂️ {st.session_state['user_nome']}</h3><p>ID: {st.session_state['user_id']}</p></div>", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Troquei", "👥 Efetivo"])
        if st.button("🚪 Sair"):
            st.session_state["logged_in"] = False
            st.rerun()

    df_trocas = load_sheet("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dv = hoje + timedelta(days=i)
            d_str = dv.strftime('%d/%m/%Y')
            
            t_ativa = None
            if df_trocas is not None and not df_trocas.empty:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_sheet(dv.strftime("%d-%m"))
            label = "HOJE" if i == 0 else dv.strftime("%d/%m (%a)")

            if t_ativa is not None:
                st.markdown(f"<div class='card-servico' style='border-left-color: #FFD54F;'><b>{label}</b> (TROCA)<br><h3>{t_ativa['servico_destino']}</h3></div>", unsafe_allow_html=True)
            elif df_dia is not None:
                meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                if not meu.empty:
                    st.markdown(f"<div class='card-servico'><b>{label}</b><br><h3>{meu.iloc[0]['serviço']}</h3></div>", unsafe_allow_html=True)

    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca")
        data_t = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_sheet(data_t.strftime("%d-%m"))
        if df_d is not None:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço: {meu_s}")
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                with st.form("f"):
                    c_sel = st.selectbox("Com quem?", opcoes)
                    if st.form_submit_button("GRAVAR"):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        if registrar_troca_excel([data_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]):
                            st.success("Gravado!")
                            st.balloons()

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Dia:", format="DD/MM/YYYY")
        df_dia = load_sheet(data_sel.strftime("%d-%m"))
        if df_dia is not None:
            st.dataframe(df_dia[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)

# --- EXECUÇÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_screen()
else:
    main_app()
    
