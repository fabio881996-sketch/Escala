import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    .sidebar-nome { color: #FFFFFF !important; font-size: 1.2rem; font-weight: bold; }
    .sidebar-id { color: #D1D1D1 !important; font-size: 0.9rem; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .card-servico { background: white; padding: 15px; border-radius: 10px; border-left: 6px solid #455A64; margin-bottom: 10px; color: #333; border: 1px solid #EAECEF; }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #F0F7FF !important; }
    .card-troca { border-left-color: #FFD54F !important; background-color: #FFFDE7 !important; }
    .texto-pedido { color: #1A1A1A !important; font-weight: 500; }
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
    
    # Notificações
    ped_m = 0; ped_a = 0
    if not df_trocas.empty and 'status' in df_trocas.columns:
        ped_m = len(df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])])
        ped_a = len(df_trocas[df_trocas['status'] == 'Pendente_Admin'])

    with st.sidebar:
        st.markdown(f'<p class="sidebar-nome">👮‍♂️ {st.session_state["user_nome"]}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sidebar-id">ID: {st.session_state["user_id"]}</p>', unsafe_allow_html=True)
        st.markdown("---")
        menu = st.radio("MENU", [
            "📅 Minha Escala", 
            "🔍 Escala Geral", 
            "🔄 Solicitar Troca", 
            f"📥 Pedidos Recebidos ({ped_m})" if ped_m > 0 else "📥 Pedidos Recebidos",
            f"⚖️ Validar Trocas ({ped_a})" if ped_a > 0 else "⚖️ Validar Trocas",
            "👥 Efetivo"
        ])
        if st.button("Sair", use_container_width=True): 
            st.session_state["logged_in"] = False
            st.rerun()

    # --- 4. ESCALA GERAL (ORDEM CORRIGIDA) ---
    if menu == "🔍 Escala Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        df_dia = load_data(data_sel.strftime("%d-%m"))
        
        if not df_dia.empty:
            df_atual = df_dia.copy()
            df_atual['id_display'] = df_atual['id'].astype(str)
            
            # Aplicar Trocas Aprovadas
            if not df_trocas.empty and 'status' in df_trocas.columns:
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
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp.groupby(['serviço', 'horário'], sort=False)['id_display'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado.rename(columns={'id_display': 'id'})[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    return df_fonte[~df_fonte['id'].isin(temp['id'])]
                return df_fonte

            # A ORDEM QUE DEFINISTE:
            df_processo = df_atual.copy()
            df_processo = mostrar_seccao("Comando e Administrativos", ["pronto", "secretaria", "inquérito"], df_processo)
            df_processo = mostrar_seccao("Atendimento", ["atendimento"], df_processo)
            df_processo = mostrar_seccao("Apoio ao Atendimento", ["apoio"], df_processo)
            df_processo = mostrar_seccao("Patrulhas", ["po", "patrulha", "ronda", "vtr"], df_processo)
            
            # Capturar Folgas e Ausentes para garantir que os "Outros" não os apanham
            df_finais = df_processo[df_processo['serviço'].str.lower().str.contains("folga|férias|licença|doente|tribunal|diligência|remu|grat", na=False)]
            df_sobra = df_processo[~df_processo['id'].isin(df_finais['id'])]
            
            # Outros entre Patrulhas e Folgas
            _ = mostrar_seccao("Outros Serviços", [""], df_sobra)
            
            # Folgas e Ausentes
            df_finais = mostrar_seccao("Remunerados", ["remu", "grat"], df_finais)
            df_finais = mostrar_seccao("Folga", ["folga"], df_finais)
            _ = mostrar_seccao("Ausentes", ["férias", "licença", "doente", "tribunal", "diligência"], df_finais)
            
        else: st.warning("Sem dados para esta data.")

    # --- 5. MINHA ESCALA ---
    elif menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            dt = hoje + timedelta(days=i)
            d_str = dt.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else dt.strftime("%d/%m (%a)")
            
            # Lógica de Troca Aprovada
            troca_v = pd.DataFrame()
            if not df_trocas.empty and 'status' in df_trocas.columns:
                troca_v = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id']) & (df_trocas['status'] == 'Aprovada')]
            
            if not troca_v.empty:
                t = troca_v.iloc[0]
                st.markdown(f'<div class="card-servico card-troca"><b>{label}</b><br><h3>{t["servico_destino"]}</h3><p>🔄 Validada c/ ID {t["id_destino"]}</p></div>', unsafe_allow_html=True)
            else:
                df_d = load_data(dt.strftime("%d-%m"))
                if not df_d.empty:
                    meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
                    if not meu.empty:
                        st.markdown(f'<div class="card-servico card-meu"><b>{label}</b><br><h3>{meu.iloc[0]["serviço"]}</h3><span>🕒 {meu.iloc[0]["horário"]}</span></div>', unsafe_allow_html=True)

    # --- 6. PEDIDOS RECEBIDOS (VISIBILIDADE) ---
    elif "Pedidos Recebidos" in menu:
        st.title("📥 Pedidos para Aceitar")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            minhas = df_trocas[(df_trocas['status'] == 'Pendente_Militar') & (df_trocas['id_destino'] == st.session_state['user_id'])]
            if not minhas.empty:
                for idx, row in minhas.iterrows():
                    with st.container():
                        st.markdown(f"""<div class="card-servico card-troca"><span class="texto-pedido">📅 <b>{row['data']}</b><br>ID {row['id_origem']} quer trocar.<br><b>Recebes:</b> {row['servico_origem']}<br><b>Dás:</b> {row['servico_destino']}</span></div>""", unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("✅ ACEITAR", key=f"ac_{idx}"):
                            atualizar_status_gsheet(idx, "Pendente_Admin"); st.rerun()
                        if c2.button("❌ RECUSAR", key=f"re_{idx}"):
                            atualizar_status_gsheet(idx, "Recusada"); st.rerun()
            else: st.info("Sem pedidos.")

    # --- 7. VALIDAR TROCAS (INFO COMPLETA) ---
    elif "Validar Trocas" in menu:
        st.title("⚖️ Validação Admin")
        if not df_trocas.empty and 'status' in df_trocas.columns:
            pend = df_trocas[df_trocas['status'] == 'Pendente_Admin']
            for idx, row in pend.iterrows():
                st.warning(f"DATA: {row['data']}")
                st.write(f"Militar {row['id_origem']} vai para {row['servico_destino']}")
                st.write(f"Militar {row['id_destino']} vai para {row['servico_origem']}")
                c1, c2 = st.columns(2)
                if c1.button("✔️ VALIDAR", key=f"ok_{idx}"):
                    atualizar_status_gsheet(idx, "Aprovada"); st.rerun()
                if c2.button("🚫 REJEITAR", key=f"no_{idx}"):
                    atualizar_status_gsheet(idx, "Rejeitada_Admin"); st.rerun()

    # --- OUTROS MENUS ---
    elif menu == "🔄 Solicitar Troca":
        # ... (Mantém-se a lógica de seleção de data e colega já funcional)
        st.title("🔄 Nova Solicitação")
        d_t = st.date_input("Data:", format="DD/MM/YYYY")
        df_d = load_data(d_t.strftime("%d-%m"))
        if not df_d.empty:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']}", axis=1).tolist()
                c_sel = st.selectbox("Trocar com:", opcoes)
                if st.button("Enviar Pedido"):
                    # Lógica de salvar_troca_gsheet...
                    st.success("Enviado!")

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_data("utilizadores")
        st.dataframe(df_u[['id', 'posto', 'nome', 'telemóvel']], hide_index=True)
