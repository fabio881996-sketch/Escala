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

# 2. CSS - BASE INALTERÁVEL (Subtítulos brancos, Botão Sair vermelho, etc)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; border-right: 1px solid #37474F; }
    .profile-card { background: #37474F; padding: 20px; border-radius: 12px; margin-bottom: 25px; text-align: center; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    div[data-testid="stForm"] * { color: white !important; }

    /* SUBTÍTULOS EM BRANCO */
    div[data-testid="stExpander"] summary p { color: white !important; font-weight: bold !important; font-size: 1.1rem !important; }
    div[data-testid="stExpander"] summary { background-color: #455A64 !important; border-radius: 8px !important; padding: 5px 10px !important; }
    div[data-testid="stExpander"] summary svg { fill: white !important; }
    .st-expander { border: none !important; background-color: transparent !important; margin-bottom: 15px !important; }

    /* TABELAS */
    .stDataFrame { background-color: #FFFFFF !important; border: 1px solid #EAECEF !important; border-radius: 8px !important; }
    [data-testid="stDataFrame"] table thead th { background-color: #F8FAFC !important; color: #1A1C1E !important; font-weight: bold !important; }
    
    h1, h2, h3, p { color: #1A1C1E !important; }
    
    section[data-testid="stSidebar"] .stButton>button {
        background-color: #e74c3c !important; color: white !important; border: none !important; font-weight: bold !important; border-radius: 8px !important;
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
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Troquei", "🔄 Solicitar Troca"])
        if st.button("🚪 Sair do Portal", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        st.subheader("Próximos Serviços")
        hoje = datetime.now()
        encontrou_algum = False
        for i in range(8):
            data_verificar = hoje + timedelta(days=i)
            nome_aba = data_verificar.strftime("%d-%m")
            df_dia = load_sheet(nome_aba)
            if df_dia is not None:
                meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
                if not meu_df.empty:
                    encontrou_algum = True
                    label_dia = "HOJE" if i == 0 else data_verificar.strftime("%d/%m (%a)")
                    st.markdown(f"""<div style="background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px;"><span style="color: #455A64; font-weight: bold; font-size: 0.9rem;">{label_dia}</span><h3 style="margin:0; color: #1A1C1E !important;">{meu_df.iloc[0]['serviço']}</h3><p style="color: #546E7A; margin:0;">🕒 {meu_df.iloc[0]['horário']}</p></div>""", unsafe_allow_html=True)
        if not encontrou_algum: st.info("Não foram encontrados serviços escalados.")
        st.divider()
        st.subheader("Consultar outra data")
        data_sel = st.date_input("Escolha o dia:", format="DD/MM/YYYY")
        nome_aba_sel = data_sel.strftime("%d-%m")
        df_sel = load_sheet(nome_aba_sel)
        if df_sel is not None:
            meu_df_sel = df_sel[df_sel['id'] == st.session_state['user_id']]
            if not meu_df_sel.empty: st.success(f"Nesse dia estarás de: **{meu_df_sel.iloc[0]['serviço']}** ({meu_df_sel.iloc[0]['horário']})")
            else: st.warning("Não constas na escala deste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
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
            filtrar_e_mostrar("Apoio ao Atendimento", ["apoio"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "renu", "grat", "extra"], excluir=False)
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente", "diligência", "falta"])
            filtrar_e_mostrar("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando", "permanência"])

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Lista de Efetivo")
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            colunas_finais = ["id", "nim", "posto", "nome", "email", "telemóvel"]
            colunas_existentes = [c for c in colunas_finais if c in df_u.columns]
            st.dataframe(df_u[colunas_existentes], use_container_width=True, hide_index=True)

    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca Efetuada")
        st.write("Utiliza este formulário para informar que já realizaste uma troca com um colega.")
        
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            with st.form("form_troquei"):
                data_troca = st.date_input("Data do serviço trocado:", format="DD/MM/YYYY")
                # Cria lista de nomes para o selectbox
                lista_militares = df_u.apply(lambda x: f"{x['posto']} {x['nome']} ({x['id']})", axis=1).tolist()
                militar_troca = st.selectbox("Com quem trocou o serviço?", lista_militares)
                motivo = st.text_area("Notas adicionais (opcional):")
                
                if st.form_submit_button("REGISTAR TROCA"):
                    st.success(f"Troca registada para o dia {data_troca.strftime('%d/%m/%Y')} com {militar_troca}.")
                    st.info("Nota: Este registo é provisório e será validado pelo Comando.")

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca de Serviço")
        st.info("Funcionalidade em desenvolvimento.")

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
