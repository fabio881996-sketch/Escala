import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E VISUAL ORIGINAL ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    div[data-testid="stForm"] * { color: white !important; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); color: #455A64; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE DADOS ---
def get_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_data(aba_nome):
    try:
        # Tenta leitura rápida via CSV
        base_url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df.fillna("")
    except:
        try:
            client = get_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            worksheet = sh.worksheet(aba_nome)
            df = pd.DataFrame(worksheet.get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except: return pd.DataFrame() # Retorna vazio se a aba não existir

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

# --- LÓGICA DE ACESSO ---
if "logged_in" not in st.session_state: 
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # LOGIN VISUAL CENTRADO
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("📧 Email").strip().lower()
            p = st.text_input("🔑 Password", type="password").strip()
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                if not df_u.empty:
                    user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                    if not user.empty:
                        st.session_state.update({
                            "logged_in": True, 
                            "user_id": str(user.iloc[0]['id']), 
                            "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"
                        })
                        st.rerun()
                    else: st.error("Dados incorretos.")
                else: st.error("Erro ao carregar utilizadores.")
else:
    # --- APP PRINCIPAL ---
    with st.sidebar:
        st.markdown(f"""<div style="text-align:center; padding:10px;">
            <h3 style="margin:0;">👮‍♂️ {st.session_state['user_nome']}</h3>
            <p style="font-size:0.8rem; opacity:0.8;">ID: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Registar Troca", "👥 Efetivo"])
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    df_trocas = load_data("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            aba_dia = data_v.strftime("%d-%m")
            
            # PROTEÇÃO CONTRA COLUNA 'DATA' INEXISTENTE
            t_ativa = None
            if not df_trocas.empty and 'data' in df_trocas.columns:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_data(aba_dia)
            label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")

            if t_ativa is not None:
                st.markdown(f"""<div class="card-servico" style="border-left-color: #FFD54F;">
                    <b>{label}</b> <span class="troca-tag">TROCA</span><br>
                    <h3 style="margin:0;">{t_ativa['servico_destino']}</h3>
                    <p style="margin:0; font-size:0.8rem;">Em vez de: {t_ativa['servico_origem']}</p>
                </div>""", unsafe_allow_html=True)
            elif not df_dia.empty:
                meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                if not meu.empty:
                    st.markdown(f"""<div class="card-servico">
                        <b>{label}</b><br>
                        <h3 style="margin:0;">{meu.iloc[0]['serviço']}</h3>
                        <p style="margin:0;">{meu.iloc[0]['horário']}</p>
                    </div>""", unsafe_allow_html=True)

    elif menu == "🔄 Registar Troca":
        st.title("🔄 Registar Troca Permanente")
        data_sel = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if not df_dia.empty:
            meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"Serviço original: **{meu_s}**")
                
                colegas = df_dia[df_dia['id'].astype(str) != st.session_state['user_id']]
                lista = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                
                with st.form("form_troca"):
                    c_sel = st.selectbox("Com quem trocaste?", lista)
                    if st.form_submit_button("GRAVAR NO EXCEL", use_container_width=True):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        dados = [data_sel.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]
                        
                        if salvar_troca(dados):
                            st.success("Gravado! A escala já está atualizada.")
                            st.balloons()
            else: st.warning("Não tens serviço neste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        d_str = data_sel.strftime('%d/%m/%Y')
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if not df_dia.empty:
            # Aplicar trocas visuais na lista geral
            if not df_trocas.empty and 'data' in df_trocas.columns:
                trocas_dia = df_trocas[df_trocas['data'] == d_str]
                for _, t in trocas_dia.iterrows():
                    m_orig = df_dia['id'].astype(str) == str(t['id_origem'])
                    m_dest = df_dia['id'].astype(str) == str(t['id_destino'])
                    if any(m_orig) and any(m_dest):
                        # Marcar como trocado visualmente
                        df_dia.loc[m_orig, 'serviço'] = f"{t['servico_destino']} 🔄"
                        df_dia.loc[m_dest, 'serviço'] = f"{t['servico_origem']} 🔄"

            # Desenhar os Blocos (Cards) em vez de tabela
            for _, row in df_dia.iterrows():
                is_me = row['id'].astype(str) == st.session_state['user_id']
                border_color = "#1E88E5" if is_me else "#455A64"
                bg_color = "#E3F2FD" if is_me else "#FFFFFF"
                
                st.markdown(f"""
                    <div class="card-servico" style="border-left-color: {border_color}; background-color: {bg_color};">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-weight: bold; color: #263238;">ID: {row['id']}</span>
                            <span style="color: #546E7A; font-size: 0.9rem;">{row['horário']}</span>
                        </div>
                        <h3 style="margin: 5px 0; color: #263238;">{row['serviço']}</h3>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Não há escala carregada para este dia.")

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_data("utilizadores")
        if not df_u.empty:
            st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)
            
