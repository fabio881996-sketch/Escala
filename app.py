import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO (BOTÃO SAIR VISÍVEL) ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    h1, h2, h3 { color: #1E3A8A !important; font-weight: 800 !important; }
    
    /* Botão Sair - Branco com texto preto para visibilidade */
    .stButton > button {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        font-weight: bold !important;
    }

    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    
    /* Títulos dos Expanders */
    .st-emotion-cache-p64bsy p { color: #1E3A8A !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]

# --- 2. FUNÇÕES DE DADOS ---
def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def load_data(aba_nome):
    try:
        client = get_client()
        if client:
            sh = client.open_by_url(st.secrets["gsheet_url"])
            df = pd.DataFrame(sh.worksheet(aba_nome).get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df.fillna("")
        return pd.DataFrame()
    except: return pd.DataFrame()

def atualizar_status_gsheet(index_linha, novo_status):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status)
        return True
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
                user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                if not user.empty:
                    st.session_state.update({
                        "logged_in": True, "user_id": str(user.iloc[0]['id']), 
                        "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                        "user_email": u, "is_admin": u in ADMINS
                    })
                    st.rerun()
                else: st.error("Dados incorretos.")
else:
    df_trocas = load_data("registos_trocas")
    
    # Restrição de Menu para Admins
    menu_options = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca", "📥 Pedidos Recebidos"]
    if st.session_state.get("is_admin", False):
        menu_options.append("⚖️ Validar Trocas")
    menu_options.append("👥 Efetivo")

    with st.sidebar:
        st.write(f"👮‍♂️ **{st.session_state['user_nome']}**")
        menu = st.radio("MENU", menu_options)
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 4. MINHA ESCALA (SEM "FAZ:", COM DETALHE DA TROCA) ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        user_atual = str(st.session_state['user_id'])
        
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            
            troca_v = pd.DataFrame()
            if not df_trocas.empty:
                troca_v = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['status'] == 'Aprovada') & 
                                   ((df_trocas['id_origem'].astype(str) == user_atual) | 
                                    (df_trocas['id_destino'].astype(str) == user_atual))]
            
            if not troca_v.empty:
                t = troca_v.iloc[0]
                if str(t['id_origem']) == user_atual:
                    servico_exibir = t['servico_destino']
                    era = t['servico_origem']
                    com = t['id_destino']
                else:
                    servico_exibir = t['servico_origem']
                    era = t['servico_destino']
                    com = t['id_origem']
                
                st.markdown(f"""
                <div class="card-servico card-troca">
                    <b>{label}</b><br>
                    <h3>{servico_exibir}</h3>
                    <p style="margin:0; color:#666;">🔙 Troca de: {era}</p>
                    <p style="margin:0; font-weight: bold;">🔄 Trocado com ID: {com}</p>
                </div>""", unsafe_allow_html=True)
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    meu = df_d[df_d['id'].astype(str) == user_atual]
                    if not meu.empty:
                        st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    # --- 5. ESCALA GERAL (RECUPERADA E COMPLETA) ---
    elif menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if not df_dia.empty:
            df_atual = df_dia.copy()
            df_atual['id_display'] = df_atual['id'].astype(str)
            
            # Aplicar trocas visíveis na escala geral
            if not df_trocas.empty:
                trocas_v = df_trocas[(df_trocas['data'] == data_sel.strftime('%d/%m/%Y')) & (df_trocas['status'] == 'Aprovada')]
                for _, t in trocas_v.iterrows():
                    m_orig = df_atual['id'].astype(str) == str(t['id_origem'])
                    if any(m_orig): 
                        df_atual.loc[m_orig, 'serviço'] = t['servico_destino']
                        df_atual.loc[m_orig, 'id_display'] = f"{t['id_origem']} (🔄)"
                    m_dest = df_atual['id'].astype(str) == str(t['id_destino'])
                    if any(m_dest): 
                        df_atual.loc[m_dest, 'serviço'] = t['servico_origem']
                        df_atual.loc[m_dest, 'id_display'] = f"{t['id_destino']} (🔄)"

            def mostrar_seccao(titulo, keywords, df_fonte):
                padrao = '|'.join(keywords).lower()
                temp = df_fonte[df_fonte['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp.empty:
                    with st.expander(f"🔹 {titulo.upper()}", expanded=True):
                        agrupado = temp.groupby(['serviço', 'horário'], sort=False)['id_display'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado.rename(columns={'id_display': 'id'})[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    return df_fonte[~df_fonte['id'].isin(temp['id'])]
                return df_fonte

            df_p = df_atual.copy()
            df_p = mostrar_seccao("Comando e Administrativos", ["pronto", "secretaria", "inquérito"], df_p)
            df_p = mostrar_seccao("Atendimento", ["atendimento"], df_p)
            df_p = mostrar_seccao("Apoio ao Atendimento", ["apoio"], df_p)
            df_p = mostrar_seccao("Patrulhas", ["po", "patrulha", "ronda", "vtr"], df_p)
            
            # Tribunal nos Outros
            df_finais = df_p[df_p['serviço'].str.lower().str.contains("folga|férias|licença|doente|diligência|remu|grat", na=False)]
            df_sobra = df_p[~df_p['id'].isin(df_finais['id'])]
            
            _ = mostrar_seccao("Outros Serviços", [""], df_sobra)
            df_finais = mostrar_seccao("Remunerados", ["remu", "grat"], df_finais)
            df_finais = mostrar_seccao("Folga", ["folga"], df_finais)
            _ = mostrar_seccao("Ausentes", ["férias", "licença", "doente", "diligência"], df_finais)
        else:
            st.warning("Sem dados.")

    # (Menus de Pedidos Recebidos, Validar Trocas, Solicitar Troca e Efetivo seguem abaixo...)
    
