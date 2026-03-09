import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. BLOCO DE ASPETO VISUAL (RECUPERADO) ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .sidebar-nome { color: #FFFFFF !important; font-size: 1.2rem; font-weight: bold; margin-bottom: 0px; }
    .sidebar-id { color: #D1D1D1 !important; font-size: 0.9rem; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    h1, h2, h3 { color: #2C3E50 !important; font-weight: 700 !important; }
    div[data-testid="stForm"] { background-color: #455A64 !important; border-radius: 15px !important; padding: 40px !important; color: white !important; }
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label { color: #FFFFFF !important; }
    div[data-testid="stForm"] input { background-color: #FFFFFF !important; color: #333333 !important; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .texto-admin { color: #2C3E50 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES ---
ADMINS = ["ferreira.fr@gnr.pt", "carmo.haf@gnr.pt", "veiga.hfp@gnr.pt"]
SERVICOS_EXCLUIDOS = ["inquérito", "secretaria", "pronto", "férias", "licença", "doente", "tribunal", "diligência"]

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

def salvar_troca_gsheet(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
        return True
    except: return False

def atualizar_status_gsheet(index_linha, novo_status):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        # Coluna 6 é o 'status'
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
                if not df_u.empty:
                    user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
                    if not user.empty:
                        st.session_state.update({
                            "logged_in": True, 
                            "user_id": str(user.iloc[0]['id']), 
                            "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                            "user_email": u,
                            "is_admin": u in ADMINS
                        })
                        st.rerun()
                    else: st.error("Dados incorretos.")
else:
    # --- 4. CARREGAMENTO E NOTIFICAÇÕES ---
    df_trocas = load_data("registos_trocas")
    
    pedidos_militar = 0
    pedidos_admin = 0
    
    if not df_trocas.empty and 'status' in df_trocas.columns:
        pedidos_militar = len(df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])])
        pedidos_admin = len(df_trocas[df_trocas['status'] == 'Pendente_Admin'])

    # --- 5. SIDEBAR ---
    with st.sidebar:
        st.markdown(f'<p class="sidebar-nome">👮‍♂️ {st.session_state["user_nome"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]} {"(ADMIN)" if st.session_state["is_admin"] else ""}</p>', unsafe_allow_html=True)
        st.markdown("---")
        
        menu_items = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca"]
        
        txt_pedidos = f"📥 Pedidos Recebidos {'('+str(pedidos_militar)+')' if pedidos_militar > 0 else ''}"
        menu_items.append(txt_pedidos)
        
        if st.session_state["is_admin"]:
            txt_adm = f"⚖️ Validar Trocas (ADMIN) {'('+str(pedidos_admin)+')' if pedidos_admin > 0 else ''}"
            menu_items.append(txt_adm)
        
        menu_items.append("👥 Efetivo")
        menu = st.radio("MENU", menu_items)
        
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 6. LÓGICA DE MENUS ---

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            
            # Só mostra trocas com status "Aprovada"
            troca_aprovada = pd.DataFrame()
            if not df_trocas.empty and 'status' in df_trocas.columns:
                troca_aprovada = df_trocas[(df_trocas['data'] == d_str) & 
                                         (df_trocas['id_origem'].astype(str) == st.session_state['user_id']) & 
                                         (df_trocas['status'] == 'Aprovada')]
            
            if not troca_aprovada.empty:
                t = troca_aprovada.iloc[0]
                st.markdown(f"""<div class="card-servico card-troca"><b>{label}</b><br><h3>{t["servico_destino"]}</h3>
                <p style="margin:0; font-size:0.8rem; color: #555;">🔙 Era: {t["servico_origem"]}</p>
                <p style="margin:5px 0 0 0; font-weight: bold; color: #2C3E50;">🔄 Troca c/ ID {t["id_destino"]} (APROVADA)</p></div>""", unsafe_allow_html=True)
            else:
                df_dia = load_data(dt.strftime("%d-%m"))
                if not df_dia.empty:
                    meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                    if not meu.empty:
                        st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Nova Troca")
        d_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        df_d = load_data(d_t.strftime("%d-%m"))
        
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_servico_texto = meu.iloc[0]['serviço'].lower()
                if any(ext in meu_servico_texto for ext in SERVICOS_EXCLUIDOS):
                    st.warning(f"⚠️ O serviço {meu.iloc[0]['serviço']} não permite trocas.")
                else:
                    meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                    st.info(f"O teu serviço original: {meu_s}")
                    
                    colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                    filtro = '|'.join(SERVICOS_EXCLUIDOS).lower()
                    colegas_v = colegas[~colegas['serviço'].str.lower().str.contains(filtro, na=False)]
                    
                    if not colegas_v.empty:
                        df_util = load_data("utilizadores")
                        opcoes = colegas_v.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                        with st.form("f_solic"):
                            c_sel = st.selectbox("Trocar com?", opcoes)
                            if st.form_submit_button("ENVIAR PEDIDO AO COLEGA"):
                                id_c = c_sel.split(" - ")[0]
                                serv_c = c_sel.split(" - ", 1)[1]
                                email_c = df_util[df_util['id'].astype(str) == id_c]['email'].values[0]
                                
                                # Salva como Pendente_Militar
                                if salvar_troca_gsheet([d_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c, "Pendente_Militar", email_c]):
                                    st.success("Pedido enviado! O colega tem de aceitar no portal."); st.balloons()
            else: st.warning("Não tens serviço neste dia.")

    elif "Pedidos Recebidos" in menu:
        st.title("📥 Pedidos para Aceitar")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            minhas_pend = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])]
            if not minhas_pend.empty:
                for idx, row in minhas_pend.iterrows():
                    with st.expander(f"Pedido de ID {row['id_origem']} para o dia {row['data']}", expanded=True):
                        st.write(f"**Tu dás:** {row['servico_destino']}")
                        st.write(f"**Tu recebes:** {row['servico_origem']}")
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Aceitar Troca", key=f"acc_{idx}"):
                            atualizar_status_gsheet(idx, "Pendente_Admin")
                            st.success("Aceite! Aguarda agora validação do Admin."); st.rerun()
                        if c2.button("❌ Recusar", key=f"rec_{idx}"):
                            atualizar_status_gsheet(idx, "Recusada")
                            st.rerun()
            else: st.info("Não tens pedidos pendentes.")

    elif "Validar Trocas" in menu:
        st.title("⚖️ Validação de Admins")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            pend_adm = df_trocas[df_trocas['status'] == 'Pendente_Admin']
            if not pend_adm.empty:
                for idx, row in pend_adm.iterrows():
                    st.write(f"📅 **{row['data']}** | ID {row['id_origem']} ↔️ ID {row['id_destino']}")
                    st.write(f"Serviços: {row['servico_origem']} por {row['servico_destino']}")
                    c1, c2 = st.columns(2)
                    if c1.button("✔️ VALIDAR", key=f"vld_{idx}"):
                        atualizar_status_gsheet(idx, "Aprovada")
                        st.success("Troca validada!"); st.rerun()
                    if c2.button("🚫 REJEITAR", key=f"rej_{idx}"):
                        atualizar_status_gsheet(idx, "Rejeitada_Admin")
                        st.rerun()
            else: st.info("Não há trocas pendentes de validação.")

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_data("utilizadores")
        if not df_u.empty: st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], hide_index=True)
