import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. BLOCO DE ASPETO VISUAL ---
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
    .texto-pedido { color: #1A1A1A !important; font-weight: 500; }
    .texto-admin-negrito { color: #2C3E50 !important; font-weight: bold; }
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

def atualizar_status_gsheet(index_linha, novo_status):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        aba = sh.worksheet("registos_trocas")
        aba.update_cell(index_linha + 2, 6, novo_status)
        return True
    except: return False

def salvar_troca_gsheet(linha):
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
                            "logged_in": True, "user_id": str(user.iloc[0]['id']), 
                            "user_nome": f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}",
                            "user_email": u, "is_admin": u in ADMINS
                        })
                        st.rerun()
                    else: st.error("Dados incorretos.")
else:
    df_trocas = load_data("registos_trocas")
    
    # Notificações na Sidebar
    ped_militar = 0
    ped_admin = 0
    if not df_trocas.empty and 'status' in df_trocas.columns:
        ped_militar = len(df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])])
        ped_admin = len(df_trocas[df_trocas['status'] == 'Pendente_Admin'])

    with st.sidebar:
        st.markdown(f'<p class="sidebar-nome">👮‍♂️ {st.session_state["user_nome"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]}</p>', unsafe_allow_html=True)
        st.markdown("---")
        menu_items = ["📅 Minha Escala", "🔍 Escala Geral", "🔄 Solicitar Troca"]
        menu_items.append(f"📥 Pedidos Recebidos ({ped_militar})" if ped_militar > 0 else "📥 Pedidos Recebidos")
        if st.session_state["is_admin"]:
            menu_items.append(f"⚖️ Validar Trocas ({ped_admin})" if ped_admin > 0 else "⚖️ Validar Trocas")
        menu_items.append("👥 Efetivo")
        menu = st.radio("MENU", menu_items)
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 4. ESCALA GERAL (LOGICA DE ORDENAÇÃO) ---
    if menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        d_str_sel = data_sel.strftime('%d/%m/%Y')
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if not df_dia.empty:
            df_atual = df_dia.copy()
            df_atual['id_display'] = df_atual['id'].astype(str)
            
            if not df_trocas.empty and 'status' in df_trocas.columns:
                trocas_v = df_trocas[(df_trocas['data'] == d_str_sel) & (df_trocas['status'] == 'Aprovada')]
                for _, t in trocas_v.iterrows():
                    m_orig = df_atual['id'].astype(str) == str(t['id_origem'])
                    if any(m_orig):
                        df_atual.loc[m_orig, 'serviço'] = t['servico_destino']
                        df_atual.loc[m_orig, 'id_display'] = f"{t['id_origem']} (🔄 c/ {t['id_destino']})"
                    m_dest = df_atual['id'].astype(str) == str(t['id_destino'])
                    if any(m_dest):
                        df_atual.loc[m_dest, 'serviço'] = t['servico_origem']
                        df_atual.loc[m_dest, 'id_display'] = f"{t['id_destino']} (🔄 c/ {t['id_origem']})"

            def mostrar_grupo(titulo, keywords, df_base, prioritarios=None):
                padrao = '|'.join(keywords).lower()
                temp_df = df_base[df_base['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        # Ordenação especial para Atendimento
                        if prioritarios:
                            temp_df['prioridade'] = temp_df['serviço'].str.lower().apply(lambda x: 0 if any(p in x for p in prioritarios) else 1)
                            temp_df = temp_df.sort_values(by=['prioridade', 'serviço'])
                        
                        agrupado = temp_df.groupby(['serviço', 'horário'], sort=False)['id_display'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado.rename(columns={'id_display': 'id'})[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    return df_base[~df_base['id'].isin(temp_df['id'])]
                return df_base

            # ORDEM DAS SECÇÕES
            df_atual = mostrar_grupo("Comando e Administrativos", ["pronto", "secretaria", "inquérito"])
            df_atual = mostrar_grupo("Atendimento", ["atendimento", "apoio"], prioritarios=["atendimento"])
            df_atual = mostrar_grupo("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            df_atual = mostrar_grupo("Remunerados", ["remu", "grat"])
            df_atual = mostrar_grupo("Folga", ["folga"])
            df_atual = mostrar_grupo("Ausentes", ["férias", "licença", "doente", "tribunal", "diligência"])
            mostrar_grupo("Outros", [""], df_atual)
        else: st.warning("Sem dados.")

    # --- 5. SOLICITAÇÕES (TEXTO CORRIGIDO) ---
    elif "Pedidos Recebidos" in menu:
        st.title("📥 Pedidos Pendentes")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            minhas = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])]
            if not minhas.empty:
                for idx, row in minhas.iterrows():
                    with st.container():
                        st.markdown(f"""<div class="card-servico card-troca">
                            <span class="texto-pedido">📅 <b>Data: {row['data']}</b></span><br>
                            <span class="texto-pedido">O Militar ID {row['id_origem']} quer trocar contigo.</span><br><br>
                            <span class="texto-pedido"><b>Vais receber:</b> {row['servico_origem']}</span><br>
                            <span class="texto-pedido"><b>Vais dar:</b> {row['servico_destino']}</span>
                        </div>""", unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("✅ ACEITAR", key=f"ac_{idx}"):
                            atualizar_status_gsheet(idx, "Pendente_Admin")
                            st.rerun()
                        if c2.button("❌ RECUSAR", key=f"re_{idx}"):
                            atualizar_status_gsheet(idx, "Recusada")
                            st.rerun()
            else: st.info("Sem pedidos.")

    # --- 6. VALIDAÇÃO ADMIN (INFO COMPLETA) ---
    elif "Validar Trocas" in menu:
        st.title("⚖️ Validação de Admins")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            pend_adm = df_trocas[df_trocas['status'] == 'Pendente_Admin']
            if not pend_adm.empty:
                for idx, row in pend_adm.iterrows():
                    with st.container():
                        st.markdown(f"""<div style="background: #FFF9C4; padding: 15px; border-radius: 10px; border: 1px solid #FBC02D;">
                            <span class="texto-admin-negrito">📅 DATA DA TROCA: {row['data']}</span><hr>
                            <b>Militar Solicitante (ID {row['id_origem']}):</b><br>
                            Sai de: {row['servico_origem']}<br>
                            Entra em: {row['servico_destino']}<br><br>
                            <b>Militar Destino (ID {row['id_destino']}):</b><br>
                            Sai de: {row['servico_destino']}<br>
                            Entra em: {row['servico_origem']}
                        </div>""", unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("✔️ APROVAR E ATUALIZAR ESCALA", key=f"ok_{idx}"):
                            atualizar_status_gsheet(idx, "Aprovada")
                            st.success("Troca aprovada com sucesso!")
                            st.rerun()
                        if c2.button("🚫 REJEITAR PEDIDO", key=f"no_{idx}"):
                            atualizar_status_gsheet(idx, "Rejeitada_Admin")
                            st.rerun()
            else: st.info("Nada para validar.")

    # ... Restantes menus (Minha Escala, Solicitar Troca, Efetivo) mantêm-se iguais
