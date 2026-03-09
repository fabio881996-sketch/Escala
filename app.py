import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. Configuração e Estilo
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções de Dados (API e Cache)
def get_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data(aba_nome):
    try:
        # Tentativa rápida via CSV (para leitura)
        base_url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except:
        # Fallback via API se o CSV falhar
        try:
            client = get_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            worksheet = sh.worksheet(aba_nome)
            df = pd.DataFrame(worksheet.get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except: return None

def salvar_troca(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet("registos_trocas")
        worksheet.append_row(linha)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar: {e}")
        return False

# 3. Lógica do Menu
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # Tela de Login Original
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("📧 Email").strip().lower()
            p = st.text_input("🔑 Password", type="password").strip()
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                if df_u is not None:
                    user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                    if not user.empty:
                        st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"})
                        st.rerun()
                    else: st.error("Incorreto.")
else:
    # APP PRINCIPAL
    with st.sidebar:
        st.markdown(f"### 👮‍♂️ {st.session_state['user_nome']}")
        menu = st.radio("MENU", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Registar Troca", "👥 Efetivo"])
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    # Carregar trocas registadas para uso em todas as abas
    df_trocas = load_data("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço (Próximos 7 dias)")
        hoje = datetime.now()
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            aba_dia = data_v.strftime("%d-%m")
            
            # Verificar se existe troca para este user neste dia
            t_ativa = None
            if df_trocas is not None and not df_trocas.empty:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'] == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_data(aba_dia)
            label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")

            if t_ativa is not None:
                st.markdown(f"""<div class="card-servico" style="border-left-color: #FFD54F;">
                    <b>{label}</b> <span class="troca-tag">TROCA</span><br>
                    <h3 style="margin:0;">{t_ativa['servico_destino']}</h3>
                    <p style="color:gray; font-size:0.8rem;">Em substituição de: {t_ativa['servico_origem']}</p>
                </div>""", unsafe_allow_html=True)
            elif df_dia is not None:
                meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                if not meu.empty:
                    st.markdown(f"""<div class="card-servico">
                        <b>{label}</b><br>
                        <h3 style="margin:0;">{meu.iloc[0]['serviço']}</h3>
                        <p style='margin:0;'>{meu.iloc[0]['horário']}</p>
                    </div>""", unsafe_allow_html=True)

    elif menu == "🔄 Registar Troca":
        st.title("🔄 Registar Troca no Excel")
        data_sel = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if df_dia is not None:
            meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço original: **{meu_s}**")
                
                colegas = df_dia[df_dia['id'].astype(str) != st.session_state['user_id']]
                lista = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                
                with st.form("troca_api"):
                    c_sel = st.selectbox("Com quem trocas?", lista)
                    if st.form_submit_button("CONFIRMAR E GRAVAR NO EXCEL"):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        dados = [data_sel.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]
                        
                        if salvar_troca(dados):
                            st.success("Gravado com sucesso no Google Sheets!")
                            st.balloons()
            else: st.warning("Não tens serviço neste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_g = st.date_input("Ver dia:", format="DD/MM/YYYY")
        df_g = load_data(data_g.strftime("%d-%m"))
        if df_g is not None:
            st.dataframe(df_g[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Lista de Efetivo")
        df_u = load_data("utilizadores")
        if df_u is not None:
            st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)
            
