import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração de Estilo e Página
st.set_page_config(
    page_title="GNR - Sistema de Gestão de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS para um aspeto profissional
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #1e2b3c !important; }
    [data-testid="stSidebar"] .stMarkdown h2, [data-testid="stSidebar"] .stMarkdown h3 { color: white !important; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1e2b3c; color: white; }
    .status-card { background-color: #d4edda; padding: 20px; border-radius: 10px; border-left: 5px solid #28a745; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Função de Carregamento CSV (O "Tanque de Guerra")
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        
        # Limpeza e Normalização
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        
        return df
    except:
        return None

# 3. Lógica de Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1e2b3c;'>🚓 Portal GNR</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Identifique-se para consultar a escala.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            if st.form_submit_button("ENTRAR"):
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    # Verifica se as colunas existem
                    cols = df_u.columns
                    if 'email' in cols and 'password' in cols:
                        user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'] == str(pass_i))]
                        if not user.empty:
                            st.session_state["logged_in"] = True
                            st.session_state["user_id"] = user.iloc[0]['id']
                            st.session_state["user_nome_completo"] = f"{user.iloc[0]['posto']} {user.iloc[0]['nome']}".strip()
                            st.rerun()
                        else:
                            st.error("❌ Credenciais incorretas.")
                    else:
                        st.error("⚠️ Erro: Colunas 'email' ou 'password' não encontradas na aba utilizadores.")
                else:
                    st.error("⚠️ Erro de ligação à Google Sheet.")

# 4. Aplicação Principal
def main_app():
    # Sidebar com Nome precedido pelo Posto
    st.sidebar.markdown(f"<h2 style='text-align: center;'>{st.session_state['user_nome_completo']}</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='color: #bdc3c7; text-align: center;'>ID: {st.session_state['user_id']}</p>", unsafe_allow_html=True)
    st.sidebar.divider()
    
    menu = st.sidebar.radio("📋 MENU", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Solicitar Troca"])
    
    if st.sidebar.button("🚪 Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()

    # --- MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""
                <div class="status-card">
                    <h2 style="margin:0; color: #155724;">✅ {meu_df.iloc[0]['serviço']}</h2>
                    <p style="margin:0; font-size: 18px;"><b>Horário:</b> {meu_df.iloc[0]['horário']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não constas na escala para este dia.")
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    # --- CONSULTA GERAL ---
    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Completa")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY", key="geral")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            def mostrar_bloco(titulo, lista_keywords):
                padrao = '|'.join(lista_keywords).lower()
                temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                if not temp_df.empty:
                    with st.expander(f"🔹 {titulo}", expanded=True):
                        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                        st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            mostrar_bloco("Atendimento e Patrulhas", ["atendimento", "patrulha", "po", "ronda"])
            mostrar_bloco("Administrativo / Apoio", ["secretaria", "tribunal", "inquérito", "pronto"])
            mostrar_bloco("Ausências", ["folga", "férias", "licença", "doente"])
        else:
            st.error("Aba não encontrada.")

    # --- SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        data_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                indisp = ["folga", "férias", "doente", "licença"]
                df_colegas = df_dia_t[(df_dia_t['id'] != st.session_state['user_id']) & 
                                      (~df_dia_t['serviço'].str.lower().str.contains('|'.join(indisp)))]
                
                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'] + " - " + df_colegas['serviço']
                    with st.form("form_troca"):
                        colega = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_input("Motivo:")
                        if st.form_submit_button("GERAR MENSAGEM"):
                            id_c = colega.split(" - ")[0]
                            msg = f"*SOLICITAÇÃO DE TROCA ({nome_aba_t})*\n\n" \
                                  f"👉 *SAIR:* {st.session_state['user_nome_completo']} ({meu_s})\n" \
                                  f"👉 *ENTRAR:* ID {id_c}\n" \
                                  f"📝 *MOTIVO:* {motivo}"
                            st.code(msg, language="text")
            else:
                st.error("Não estás escalado para este dia.")

# Inicialização do Estado
if "logged_in" not in st.session_state: 
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
