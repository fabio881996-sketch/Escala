import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO VISUAL ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* Login */
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    
    /* Cards */
    .card-servico { 
        background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; 
        border-left: 6px solid #455A64; margin-bottom: 10px; color: #333;
    }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.7rem; float: right; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data(aba_nome):
    try:
        base_url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except:
        try:
            client = get_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

def salvar_troca(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
        return True
    except: return False

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login"):
            st.markdown("<h2 style='text-align:center;'>🚓 Portal de Escalas</h2>", unsafe_allow_html=True)
            u = st.text_input("Email").strip().lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                if not user.empty:
                    st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"})
                    st.rerun()
                else: st.error("Dados incorretos.")
else:
    # --- 4. APP PRINCIPAL ---
    with st.sidebar:
        st.markdown(f"### 👮‍♂️ {st.session_state['user_nome']}\n**ID:** {st.session_state['user_id']}")
        menu = st.radio("MENU", ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Registar Troca", "📜 Trocas Registadas", "👥 Efetivo"])
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    df_trocas = load_data("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            
            # Ver se eu troquei este dia
            troca = pd.DataFrame()
            if not df_trocas.empty and 'data' in df_trocas.columns:
                troca = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]

            if not troca.empty:
                t = troca.iloc[0]
                st.markdown(f"""<div class="card-servico card-troca">
                    <span class="troca-tag">TROCA COM ID {t['id_destino']}</span>
                    <b>{label}</b><br><h3 style="margin:5px 0;">{t['servico_destino']}</h3>
                    <p style="margin:0; font-size:0.8rem; color: #666;">Original: {t['servico_origem']}</p>
                </div>""", unsafe_allow_html=True)
            else:
                df_dia = load_data(dt.strftime("%d-%m"))
                if not df_dia.empty:
                    meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                    if not meu.empty:
                        st.markdown(f"""<div class="card-servico card-meu">
                            <b>{label}</b><br><h3 style="margin:5px 0;">{meu.iloc[0]['serviço']}</h3>
                            <span>🕒 {meu.iloc[0]['horário']}</span>
                        </div>""", unsafe_allow_html=True)

    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_g = st.date_input("Dia:", format="DD/MM/YYYY")
        df_g = load_data(data_g.strftime("%d-%m"))
        if not df_g.empty:
            for _, r in df_g.iterrows():
                is_me = str(r['id']) == st.session_state['user_id']
                st.markdown(f"""<div class="card-servico {'card-meu' if is_me else ''}">
                    <small>ID: {r['id']}</small> | <b>{r['horário']}</b>
                    <h4 style="margin:5px 0;">{r['serviço']}</h4>
                </div>""", unsafe_allow_html=True)

    elif menu == "🔄 Registar Troca":
        st.title("🔄 Registar Troca Permanente")
        d_t = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_d = load_data(d_t.strftime("%d-%m"))
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço: {meu_s}")
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                with st.form("f_t"):
                    c_sel = st.selectbox("Com quem trocaste?", opcoes)
                    if st.form_submit_button("GRAVAR TROCA"):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        if salvar_troca([d_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]):
                            st.success("Gravado!"); st.balloons()
            else: st.warning("Sem serviço neste dia.")

    elif menu == "📜 Trocas Registadas":
        st.title("📜 Histórico de Trocas")
        if not df_trocas.empty:
            st.dataframe(df_trocas, use_container_width=True, hide_index=True)
        else: st.info("Nenhuma troca registada até ao momento.")

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_data("utilizadores")
        if not df_u.empty: st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], hide_index=True)
            
