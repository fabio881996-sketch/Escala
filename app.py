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

# Inicialização do histórico (Ainda em sessão, até criarmos a aba no Excel)
if "historico_trocas" not in st.session_state:
    st.session_state["historico_trocas"] = []

# 2. CSS - BASE INALTERÁVEL
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; border-right: 1px solid #37474F; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; margin-bottom: 25px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* SUBTÍTULOS EM BRANCO */
    div[data-testid="stExpander"] summary p { color: white !important; font-weight: bold !important; font-size: 1.1rem !important; }
    div[data-testid="stExpander"] summary { background-color: #455A64 !important; border-radius: 8px !important; padding: 5px 10px !important; }
    
    /* TABELAS */
    .stDataFrame { background-color: #FFFFFF !important; border: 1px solid #EAECEF !important; }
    
    section[data-testid="stSidebar"] .stButton>button {
        background-color: #e74c3c !important; color: white !important; font-weight: bold !important; border-radius: 8px !important;
    }
    
    .troca-tag {
        background-color: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-left: 10px;
    }
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

# 4. Login (Inalterado)
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
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Troquei", "📜 As Minhas Trocas"])
        if st.button("🚪 Sair do Portal", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # --- ABA MINHA ESCALA COM LÓGICA DE TROCA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        
        for i in range(8):
            data_verificar = hoje + timedelta(days=i)
            data_str = data_verificar.strftime('%d/%m/%Y')
            nome_aba = data_verificar.strftime("%d-%m")
            
            # Verificar se há troca registada para este utilizador nesta data
            troca_ativa = next((t for t in st.session_state["historico_trocas"] if t["Data"] == data_str), None)
            
            df_dia = load_sheet(nome_aba)
            if df_dia is not None or troca_ativa:
                label_dia = "HOJE" if i == 0 else data_verificar.strftime("%d/%m (%a)")
                
                # Se houver troca, o serviço "novo" é o que o colega tinha
                if troca_ativa:
                    servico_exibir = troca_ativa["Colega/Serviço"].split(" - ")[1]
                    status_txt = '<span class="troca-tag">TROCA REGISTADA</span>'
                else:
                    meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
                    if not meu_df.empty:
                        servico_exibir = f"{meu_df.iloc[0]['serviço']} ({meu_df.iloc[0]['horário']})"
                        status_txt = ""
                    else: continue

                st.markdown(f"""
                <div style="background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px;">
                    <span style="color: #455A64; font-weight: bold; font-size: 0.9rem;">{label_dia}</span> {status_txt}
                    <h3 style="margin:0; color: #1A1C1E !important;">{servico_exibir}</h3>
                </div>
                """, unsafe_allow_html=True)

    # --- ABA CONSULTA GERAL (MANTIDA BASE) ---
    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        data_str_sel = data_sel.strftime('%d/%m/%Y')
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        
        if df_dia is not None:
            # Aplicar trocas temporárias ao DataFrame antes de exibir
            for t in st.session_state["historico_trocas"]:
                if t["Data"] == data_str_sel:
                    # Lógica simples de swap no DF para visualização
                    id_eu = st.session_state["user_id"]
                    id_colega = t["Colega/Serviço"].split(" - ")[0]
                    
                    idx_eu = df_dia.index[df_dia['id'] == id_eu].tolist()
                    idx_colega = df_dia.index[df_dia['id'] == id_colega].tolist()
                    
                    if idx_eu and idx_colega:
                        # Troca os serviços no DataFrame de visualização
                        serv_eu = df_dia.at[idx_eu[0], 'serviço']
                        df_dia.at[idx_eu[0], 'serviço'] = f"{df_dia.at[idx_colega[0], 'serviço']} (T)"
                        df_dia.at[idx_colega[0], 'serviço'] = f"{serv_eu} (T)"

            df_restante = df_dia.copy()
            def filtrar_e_mostrar(titulo, keywords, excluir=True):
                nonlocal df_restante
                padrao = '|'.join(keywords).lower()
                df_busca = df_dia if not excluir else df_restante
                temp_df = df_busca[df_busca['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)
                    if excluir: df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Folga", ["folga"])
            # ... resto dos filtros permanecem iguais ...

    # --- ABA TROQUEI (Inalterada, apenas adiciona ao historico_trocas) ---
    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca Efetuada")
        data_troca = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        nome_aba = data_troca.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        
        if df_dia is not None:
            meu_serv = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_serv.empty:
                st.info(f"O teu serviço original: **{meu_serv.iloc[0]['serviço']}**")
                excluir = ["férias", "doente", "licença", "tribunal", "secretaria"]
                df_colegas = df_dia[(df_dia['id'] != st.session_state['user_id']) & (~df_dia['serviço'].str.lower().str.contains('|'.join(excluir)))]
                opcoes = df_colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("f_troca"):
                    colega = st.selectbox("Com quem trocou?", opcoes)
                    if st.form_submit_button("REGISTAR"):
                        st.session_state["historico_trocas"].append({
                            "Data": data_troca.strftime('%d/%m/%Y'),
                            "Colega/Serviço": colega
                        })
                        st.success("Troca refletida no sistema!")
        else: st.error("Escala não encontrada para este dia.")

    elif menu == "📜 As Minhas Trocas":
        st.title("📜 Trocas Ativas")
        st.write(st.session_state["historico_trocas"])

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
