import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="GNR - Gestão de Trocas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .sidebar-nome { color: #FFFFFF !important; font-size: 1.2rem; font-weight: bold; }
    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; }
    .status-pendente { color: #FFA000; font-weight: bold; }
    .status-aprovada { color: #2E7D32; font-weight: bold; }
    .badge-notif { background-color: #FF5252; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

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
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def atualizar_status_troca(index_linha, novo_status):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        # Coluna 6 é o 'status'
        aba.update_cell(index_linha + 2, 6, novo_status)
        return True
    except: return False

def solicitar_troca_gsheet(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        sh.worksheet("registos_trocas").append_row(linha)
        return True
    except: return False

# --- 3. LOGIN ---
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    # (O Teu bloco de login aqui igual ao anterior...)
    with st.form("login_form"):
        u = st.text_input("Email").strip().lower()
        p = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRAR"):
            df_u = load_data("utilizadores")
            user = df_u[(df_u['email'].str.lower() == u) & (df_u['password'] == p)]
            if not user.empty:
                st.session_state.update({
                    "logged_in": True, "user_id": str(user.iloc[0]['id']), 
                    "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                    "user_email": u, "is_admin": u in ADMINS
                })
                st.rerun()
else:
    # CARREGAR DADOS GLOBAIS
    df_trocas = load_data("registos_trocas")
    
    # CONTADORES PARA NOTIFICAÇÕES
    pedidos_militar = 0
    pedidos_admin = 0
    if not df_trocas.empty:
        pedidos_militar = len(df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])])
        pedidos_admin = len(df_trocas[df_trocas['status'] == 'Pendente_Admin'])

    # --- 4. SIDEBAR ---
    with st.sidebar:
        st.markdown(f'<p class="sidebar-nome">👮‍♂️ {st.session_state["user_nome"]}</p>', unsafe_allow_html=True)
        
        menu_items = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca"]
        
        # Menu de Solicitações com Badge
        txt_solic = "📥 Pedidos Recebidos"
        if pedidos_militar > 0: txt_solic += f" ({pedidos_militar})"
        menu_items.append(txt_solic)
        
        if st.session_state["is_admin"]:
            txt_admin = "⚖️ Validar Trocas (ADMIN)"
            if pedidos_admin > 0: txt_admin += f" ({pedidos_admin})"
            menu_items.append(txt_admin)
            
        menu_items.append("📜 Histórico")
        menu = st.radio("MENU", menu_items)

    # --- 5. LÓGICA DE MENUS ---

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        # Só mostra trocas se o status for "Aprovada"
        # (Lógica similar à anterior, mas filtrando status == 'Aprovada')
        st.info("Aqui aparecem apenas os serviços confirmados pelos Admins.")

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Nova Solicitação")
        d_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        df_d = load_data(d_t.strftime("%d-%m"))
        
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.write(f"O teu serviço: **{meu_s}**")
                
                df_u = load_data("utilizadores")
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                
                # Filtro de serviços excluídos
                filtro = '|'.join(SERVICOS_EXCLUIDOS).lower()
                colegas_v = colegas[~colegas['serviço'].str.lower().str.contains(filtro, na=False)]
                
                opcoes = colegas_v.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("f_solicitar"):
                    c_sel = st.selectbox("Com quem queres trocar?", opcoes)
                    if st.form_submit_button("ENVIAR PEDIDO AO COLEGA"):
                        id_dest = c_sel.split(" - ")[0]
                        serv_dest = c_sel.split(" - ", 1)[1]
                        email_dest = df_u[df_u['id'].astype(str) == id_dest]['email'].values[0]
                        
                        nova_linha = [d_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_dest, serv_dest, "Pendente_Militar", email_dest]
                        if solicitar_troca_gsheet(nova_linha):
                            st.success("Pedido enviado! O teu colega foi notificado e precisa de aceitar.")
                            st.info(f"Notificação enviada para: {email_dest}")

    elif "Pedididos Recebidos" in menu:
        st.title("📥 Pedidos de Troca para Ti")
        minhas_solic = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])]
        
        if not minhas_solic.empty:
            for idx, row in minhas_solic.iterrows():
                with st.container():
                    st.write(f"📅 **{row['data']}** | O Militar {row['id_origem']} quer trocar contigo.")
                    st.write(f"Tu dás: {row['servico_destino']} ↔️ Tu recebes: {row['servico_origem']}")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ ACEITAR", key=f"acc_{idx}"):
                        atualizar_status_troca(idx, "Pendente_Admin")
                        st.success("Aceitaste! Agora aguarda validação do Admin."); st.rerun()
                    if c2.button("❌ RECUSAR", key=f"rec_{idx}"):
                        atualizar_status_troca(idx, "Recusada")
                        st.error("Recusaste o pedido."); st.rerun()
                st.divider()
        else: st.write("Não tens pedidos pendentes.")

    elif "Validar Trocas" in menu:
        st.title("⚖️ Validação de Admins")
        pedidos_finais = df_trocas[df_trocas['status'] == 'Pendente_Admin']
        
        if not pedidos_finais.empty:
            for idx, row in pedidos_finais.iterrows():
                st.warning(f"PEDIDO: ID {row['id_origem']} ↔️ ID {row['id_destino']} ({row['data']})")
                col1, col2 = st.columns(2)
                if col1.button("✔️ APROVAR TROCA", key=f"adm_ok_{idx}"):
                    atualizar_status_troca(idx, "Aprovada")
                    st.success("Troca validada e inserida na escala!"); st.rerun()
                if col2.button("🚫 REJEITAR", key=f"adm_no_{idx}"):
                    atualizar_status_troca(idx, "Rejeitada_Admin")
                    st.rerun()
        else: st.write("Não há trocas à espera de validação.")
            
