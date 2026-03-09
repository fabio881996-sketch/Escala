import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. Configuração de Página e Estilo
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #455A64; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; }
    .info-troca { font-size: 0.85rem; color: #546E7A; font-style: italic; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Conexão com Google Sheets (Escrita)
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# 3. Carregamento de Dados (Leitura Rápida)
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except: return None

# 4. Função de Escrita
def registrar_troca_excel(dados_lista):
    try:
        client = get_gspread_client()
        # Abre a folha pelo URL que está nos secrets
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet("registos_trocas")
        worksheet.append_row(dados_lista)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar: {e}")
        return False

# --- APP PRINCIPAL ---
def main_app():
    with st.sidebar:
        st.write(f"👮‍♂️ **{st.session_state['user_nome']}**")
        menu = st.radio("Menu", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Troquei", "👥 Efetivo"])
        if st.button("Sair"): st.session_state["logged_in"] = False; st.rerun()

    # Carregar trocas registadas
    df_trocas = load_sheet("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            
            # Verificar troca
            t_ativa = None
            if df_trocas is not None and not df_trocas.empty:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'] == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_sheet(data_v.strftime("%d-%m"))
            if t_ativa is not None:
                st.info(f"📅 {d_str} - TROCA: {t_ativa['servico_destino']}")
                st.write(f"Trocaste o teu {t_ativa['servico_origem']} com ID {t_ativa['id_destino']}")
            elif df_dia is not None:
                meu = df_dia[df_dia['id'] == st.session_state['user_id']]
                if not meu.empty:
                    st.success(f"📅 {d_str} - {meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})")

    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca no Sistema")
        data_t = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_d = load_sheet(data_t.strftime("%d-%m"))
        
        if df_d is not None:
            meu = df_d[df_d['id'] == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço: {meu_s}")
                
                colegas = df_d[df_d['id'] != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("f_troca"):
                    c_sel = st.selectbox("Com quem trocaste?", opcoes)
                    if st.form_submit_button("GRAVAR TROCA DEFINITIVA"):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        
                        nova_linha = [data_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]
                        
                        if registrar_troca_excel(nova_linha):
                            st.success("Troca gravada no Excel com sucesso!")
                            st.balloons()
            else: st.warning("Não tens serviço escalado neste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        d_str = data_sel.strftime('%d/%m/%Y')
        df_dia = load_sheet(data_sel.strftime("%d-%m"))
        
        if df_dia is not None:
            # Aplicar trocas visuais
            if df_trocas is not None and not df_trocas.empty:
                trocas_dia = df_trocas[df_trocas['data'] == d_str]
                for _, t in trocas_dia.iterrows():
                    m_orig = df_dia['id'] == t['id_origem']
                    m_dest = df_dia['id'] == t['id_destino']
                    if any(m_orig) and any(m_dest):
                        df_dia.loc[m_orig, 'serviço'] = f"{t['servico_destino']} (T)"
                        df_dia.loc[m_dest, 'serviço'] = f"{t['servico_origem']} (T)"
            st.dataframe(df_dia[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

# Login e Inicialização (mantém o que tinhas)
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    # Coloca aqui a tua função de login anterior
    u = st.text_input("Email").lower()
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        df_u = load_sheet("utilizadores")
        user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
        if not user.empty:
            st.session_state.update({"logged_in": True, "user_id": user.iloc[0]['id'], "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"})
            st.rerun()
else: main_app()
    
