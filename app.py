import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. Configuração de Página e Estilo (RECUPERADO)
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    div[data-testid="stForm"] * { color: white !important; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexões e Dados
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        # Limpeza de dados para evitar o erro do login
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except: return None

def registrar_troca_excel(dados_lista):
    try:
        client = get_gspread_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet("registos_trocas")
        worksheet.append_row(dados_lista)
        return True
    except Exception as e:
        st.error(f"Erro na API do Google: {e}")
        return False

# 3. Login Visual (RECUPERADO)
def login_screen():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("📧 Email").strip().lower()
            p = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    # Filtro seguro contra NaNs
                    user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                    if not user.empty:
                        st.session_state.update({
                            "logged_in": True, 
                            "user_id": user.iloc[0]['id'], 
                            "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"
                        })
                        st.rerun()
                    else: st.error("Dados incorretos.")

# 4. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div style="text-align:center; padding:20px; background:#37474F; border-radius:10px; margin-bottom:20px;">
            <div style="font-size:40px;">👮‍♂️</div>
            <h3 style="color:white; margin:0;">{st.session_state['user_nome']}</h3>
            <p style="color:#B0BEC5; font-size:0.8rem;">ID: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Troquei", "👥 Efetivo"])
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    df_trocas = load_sheet("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            
            t_ativa = None
            if df_trocas is not None and not df_trocas.empty:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'] == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_sheet(data_v.strftime("%d-%m"))
            label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")

            if t_ativa is not None:
                st.markdown(f"""<div class="card-servico" style="border-left-color: #FFD54F;">
                    <span style="color:#455A64; font-weight:bold;">{label}</span> <span class="troca-tag">TROCA REGISTADA</span>
                    <h3 style="margin:0;">{t_ativa['servico_destino']}</h3>
                    <p style="margin:0; font-style:italic; font-size:0.9rem;">🔄 Trocaste o teu {t_ativa['servico_origem']} com ID {t_ativa['id_destino']}</p>
                </div>""", unsafe_allow_html=True)
            elif df_dia is not None:
                meu = df_dia[df_dia['id'] == st.session_state['user_id']]
                if not meu.empty:
                    st.markdown(f"""<div class="card-servico">
                        <span style="color:#455A64; font-weight:bold;">{label}</span>
                        <h3 style="margin:0;">{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})</h3>
                    </div>""", unsafe_allow_html=True)

    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca Permanente")
        data_t = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_d = load_sheet(data_t.strftime("%d-%m"))
        
        if df_d is not None:
            meu = df_d[df_d['id'] == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço original: **{meu_s}**")
                
                colegas = df_d[df_d['id'] != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("f_troca"):
                    c_sel = st.selectbox("Com quem trocaste?", opcoes)
                    if st.form_submit_button("GRAVAR TROCA NO EXCEL", use_container_width=True):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        
                        nova_linha = [data_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]
                        
                        with st.spinner("A comunicar com a Google API..."):
                            if registrar_troca_excel(nova_linha):
                                st.success("Gravado com sucesso! A escala geral já está atualizada.")
                                st.balloons()
            else: st.warning("Não tens serviço escalado neste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        d_str = data_sel.strftime('%d/%m/%Y')
        df_dia = load_sheet(data_sel.strftime("%d-%m"))
        
        if df_dia is not None:
            if df_trocas is not None and not df_trocas.empty:
                trocas_dia = df_trocas[df_trocas['data'] == d_str]
                for _, t in trocas_dia.iterrows():
                    m_orig = df_dia['id'] == t['id_origem']
                    m_dest = df_dia['id'] == t['id_destino']
                    if any(m_orig) and any(m_dest):
                        # Swap para visualização
                        serv_original = df_dia.loc[m_orig, 'serviço'].values[0]
                        df_dia.loc[m_orig, 'serviço'] = f"{t['servico_destino']} (T)"
                        df_dia.loc[m_dest, 'serviço'] = f"{serv_original} (T)"
            st.dataframe(df_dia[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            st.dataframe(df_u[['id', 'nim', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)

# Execução
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    login_screen()
else:
    main_app()
    
