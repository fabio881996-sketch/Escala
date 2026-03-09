import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuração de Página
st.set_page_config(
    page_title="GNR - Portal de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS - BASE INALTERÁVEL
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; border-right: 1px solid #37474F; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; margin-bottom: 25px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    div[data-testid="stForm"] * { color: white !important; }
    div[data-testid="stExpander"] summary p { color: white !important; font-weight: bold !important; font-size: 1.1rem !important; }
    div[data-testid="stExpander"] summary { background-color: #455A64 !important; border-radius: 8px !important; }
    .stDataFrame { background-color: #FFFFFF !important; border: 1px solid #EAECEF !important; border-radius: 8px !important; }
    h1, h2, h3, p { color: #1A1C1E !important; }
    section[data-testid="stSidebar"] .stButton>button {
        background-color: #e74c3c !important; color: white !important; border: none !important; font-weight: bold !important; border-radius: 8px !important;
    }
    .troca-tag {
        background-color: #FFD54F; color: #000000 !important; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; margin-left: 10px;
    }
    .info-troca-detalhe { font-size: 0.85rem; color: #546E7A !important; margin-top: 5px; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# 3. Funções de Carregamento
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str) 
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except: return None

# 4. Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white !important;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'] == str(pass_i))]
                    if not user.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user.iloc[0]['id']
                        st.session_state["user_nome_completo"] = f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}".strip()
                        st.rerun()

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div class="profile-card"><div style="font-size: 35px; margin-bottom: 5px;">👮‍♂️</div><h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #B0BEC5; font-size: 0.8rem;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Troquei", "📜 Trocas Registadas"])
        if st.button("🚪 Sair do Portal", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # Carregar base de trocas permanente
    df_trocas_permanente = load_sheet("registos_trocas")

    # --- ABA MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            data_str = data_v.strftime('%d/%m/%Y')
            nome_aba = data_v.strftime("%d-%m")
            
            # Procurar troca na aba permanente
            troca_ativa = None
            if df_trocas_permanente is not None and not df_trocas_permanente.empty:
                t_filter = df_trocas_permanente[(df_trocas_permanente['data'] == data_str) & (df_trocas_permanente['id_origem'] == st.session_state['user_id'])]
                if not t_filter.empty:
                    troca_ativa = t_filter.iloc[0]

            df_dia = load_sheet(nome_aba)
            servico_exibir = None
            detalhe_html = ""
            status_html = ""

            if troca_ativa is not None:
                servico_exibir = troca_ativa['servico_destino']
                detalhe_html = f"""<div class="info-troca-detalhe">🔄 Trocaste o teu <b>{troca_ativa['servico_origem']}</b> com o <b>ID {troca_ativa['id_destino']}</b></div>"""
                status_html = '<span class="troca-tag">TROCA REGISTADA</span>'
            elif df_dia is not None:
                meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
                if not meu_df.empty:
                    servico_exibir = f"{meu_df.iloc[0]['serviço']} ({meu_df.iloc[0]['horário']})"

            if servico_exibir:
                label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")
                st.markdown(f"""<div style="background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px;"><span style="color: #455A64; font-weight: bold; font-size: 0.9rem;">{label}</span>{status_html}<h3 style="margin:0; color: #1A1C1E !important;">{servico_exibir}</h3>{detalhe_html}</div>""", unsafe_allow_html=True)

    # --- ABA CONSULTA GERAL (COM REFLEXO DAS TROCAS) ---
    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        data_str_sel = data_sel.strftime('%d/%m/%Y')
        df_dia = load_sheet(data_sel.strftime("%d-%m"))
        
        if df_dia is not None:
            # Aplicar trocas da aba permanente à visualização geral
            if df_trocas_permanente is not None and not df_trocas_permanente.empty:
                trocas_dia = df_trocas_permanente[df_trocas_permanente['data'] == data_str_sel]
                for _, t in trocas_dia.iterrows():
                    # Marcar visualmente no DataFrame quem trocou
                    mask_origem = df_dia['id'] == t['id_origem']
                    mask_destino = df_dia['id'] == t['id_destino']
                    
                    if any(mask_origem) and any(mask_destino):
                        # Swap de serviços para exibição
                        serv_original_origem = df_dia.loc[mask_origem, 'serviço'].values[0]
                        df_dia.loc[mask_origem, 'serviço'] = f"{t['servico_destino']} (T)"
                        df_dia.loc[mask_destino, 'serviço'] = f"{serv_original_origem} (T)"

            df_restante = df_dia.copy()
            def filtrar_e_mostrar(titulo, keywords):
                nonlocal df_restante
                padrao = '|'.join(keywords).lower()
                temp_df = df_restante[df_restante['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento", "apoio"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Outros", [""])

    # --- ABA TROQUEI (AVISO DE ESCRITA) ---
    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca Efetuada")
        st.warning("⚠️ Para a troca ser permanente, deves registar os dados na aba 'registos_trocas' da tua Google Sheet.")
        data_troca = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        df_dia = load_sheet(data_troca.strftime("%d-%m"))
        if df_dia is not None:
            meu_serv = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_serv.empty:
                st.info(f"O teu serviço: **{meu_serv.iloc[0]['serviço']}** ({meu_serv.iloc[0]['horário']})")

    elif menu == "📜 Trocas Registadas":
        st.title("📜 Histórico Permanente (Aba registos_trocas)")
        if df_trocas_permanente is not None:
            st.dataframe(df_trocas_permanente, use_container_width=True, hide_index=True)
        else: st.error("Aba 'registos_trocas' não encontrada.")

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Lista de Efetivo")
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            st.dataframe(df_u[["id", "nim", "posto", "nome", "email", "telemóvel"]], use_container_width=True, hide_index=True)

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
