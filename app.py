import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. BLOCO DE ASPETO VISUAL (CONCLUÍDO) ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    
    /* Nome na lateral mais claro (Branco Brilhante) */
    .sidebar-nome { color: #FFFFFF !important; font-size: 1.2rem; font-weight: bold; margin-bottom: 0px; }
    .sidebar-id { color: #D1D1D1 !important; font-size: 0.9rem; }
    
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    h1, h2, h3 { color: #2C3E50 !important; font-weight: 700 !important; }
    
    div[data-testid="stForm"] {
        background-color: #455A64 !important; 
        border-radius: 15px !important;
        padding: 40px !important;
        color: white !important;
    }
    
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label { color: #FFFFFF !important; }
    div[data-testid="stForm"] input { background-color: #FFFFFF !important; color: #333333 !important; }

    .streamlit-expanderHeader { 
        background-color: #FFFFFF !important; 
        color: #2C3E50 !important; 
        font-weight: bold !important;
        border: 1px solid #DDE1E6 !important;
        border-radius: 8px !important;
    }

    .card-servico { 
        background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; 
        border-left: 6px solid #455A64; margin-bottom: 10px; color: #333;
    }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

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
            if client:
                sh = client.open_by_url(st.secrets["gsheet_url"])
                df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
                df.columns = [c.strip().lower() for c in df.columns]
                return df
            return pd.DataFrame()
        except: return pd.DataFrame()

def salvar_troca(linha):
    try:
        client = get_client()
        if client:
            sh = client.open_by_url(st.secrets["gsheet_url"])
            sh.worksheet("registos_trocas").append_row(linha)
            return True
        return False
    except: return False

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align:center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u = st.text_input("Email").strip().lower()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                df_u = load_data("utilizadores")
                if not df_u.empty:
                    user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                    if not user.empty:
                        st.session_state.update({"logged_in": True, "user_id": str(user.iloc[0]['id']), "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}"})
                        st.rerun()
                    else: st.error("Dados incorretos.")
else:
    # --- 4. INTERFACE ---
    with st.sidebar:
        st.markdown(f'<p class="sidebar-nome">👮‍♂️ {st.session_state["user_nome"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]}</p>', unsafe_allow_html=True)
        st.markdown("---")
        menu = st.radio("MENU", ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Registar Troca", "📜 Trocas Registadas", "👥 Efetivo"])
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    df_trocas = load_data("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            troca = pd.DataFrame()
            if not df_trocas.empty and 'data' in df_trocas.columns:
                troca = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]
            if not troca.empty:
                t = troca.iloc[0]
                st.markdown(f'<div class="card-servico card-troca"><b>{label}</b><br><h3>{t["servico_destino"]}</h3><p>Troca c/ ID {t["id_destino"]}</p></div>', unsafe_allow_html=True)
            else:
                df_dia = load_data(dt.strftime("%d-%m"))
                if not df_dia.empty:
                    meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                    if not meu.empty:
                        st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        d_str_sel = data_sel.strftime('%d/%m/%Y')
        df_dia = load_data(data_sel.strftime("%d-%m"))
        if not df_dia.empty:
            df_atual = df_dia.copy()
            df_atual['id_display'] = df_atual['id'].astype(str)
            if not df_trocas.empty:
                trocas_do_dia = df_trocas[df_trocas['data'] == d_str_sel]
                for _, t in trocas_do_dia.iterrows():
                    m_orig = df_atual['id'].astype(str) == str(t['id_origem'])
                    if any(m_orig):
                        df_atual.loc[m_orig, 'serviço'] = t['servico_destino']
                        df_atual.loc[m_orig, 'id_display'] = f"{t['id_origem']} (🔄 c/ {t['id_destino']})"
                    m_dest = df_atual['id'].astype(str) == str(t['id_destino'])
                    if any(m_dest):
                        df_atual.loc[m_dest, 'serviço'] = t['servico_origem']
                        df_atual.loc[m_dest, 'id_display'] = f"{t['id_destino']} (🔄 c/ {t['id_origem']})"

            def mostrar_grupo(titulo, keywords, df_base, excluir=True):
                padrao = '|'.join(keywords).lower()
                temp_df = df_base[df_base['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id_display'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado.rename(columns={'id_display': 'id'})[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    if excluir: return df_base[~df_base['id'].isin(temp_df['id'])]
                return df_base

            df_atual = mostrar_grupo("Atendimento", ["atendimento"], df_atual)
            df_atual = mostrar_grupo("Patrulhas", ["po", "patrulha", "ronda", "vtr"], df_atual)
            _ = mostrar_grupo("Remunerados", ["remu", "grat"], df_atual, excluir=False)
            df_atual = mostrar_grupo("Folga", ["folga"], df_atual)
            df_atual = mostrar_grupo("Ausentes", ["férias", "licença", "doente"], df_atual)
            df_atual = mostrar_grupo("Outros", [""], df_atual)
        else: st.warning("Sem dados.")

    elif menu == "🔄 Registar Troca":
        st.title("🔄 Registar Troca")
        d_t = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_data(d_t.strftime("%d-%m"))
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"Teu serviço: {meu_s}")
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                with st.form("f_t"):
                    c_sel = st.selectbox("Trocar com?", opcoes)
                    if st.form_submit_button("GRAVAR"):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        if salvar_troca([d_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]):
                            st.success("Gravado!"); st.balloons()
            else: st.warning("Sem serviço.")

    elif menu == "📜 Trocas Registadas":
        st.title("📜 Histórico")
        st.dataframe(df_trocas, use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_data("utilizadores")
        if not df_u.empty: st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], hide_index=True)
