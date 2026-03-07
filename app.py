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

# Custom CSS para melhorar o aspeto
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stSidebar { background-color: #1e2b3c !important; }
    .stSidebar .sidebar-content { color: white; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. Função de Carregamento (Método CSV Robusto)
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        
        # Limpeza e Normalização
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()
        
        if 'horário' in df.columns:
            df['horário'] = df['horário'].replace("nan", "---")
            
        return df
    except:
        return None

# 3. Lógica de Login
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1e2b3c;'>🚓 Portal GNR</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Introduza as suas credenciais para aceder às escalas.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            email_i = st.text_input("📧 Email").strip().lower()
            pass_i = st.text_input("🔑 Password", type="password")
            submit = st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True)
            
            if submit:
                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'] == str(pass_i))]
                    if not user.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = user.iloc[0]['id']
                        st.session_state["user_name"] = user.iloc[0]['nome']
                        st.session_state["user_posto"] = user.iloc[0]['posto']
                        st.rerun()
                    else:
                        st.error("❌ Credenciais incorretas.")
                else:
                    st.error("⚠️ Erro de ligação à base de dados.")

# 4. Aplicação Principal
def main_app():
    # Sidebar Personalizada
    st.sidebar.markdown(f"<h2 style='color: white; text-align: center;'>{st.session_state['user_posto']}</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<h3 style='color: white; text-align: center;'>{st.session_state['user_name']}</h3>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='color: #bdc3c7; text-align: center;'>ID: {st.session_state['user_id']}</p>", unsafe_allow_html=True)
    st.sidebar.divider()
    
    menu = st.sidebar.radio("📋 MENU PRINCIPAL", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Solicitar Troca"])
    
    if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

    # --- ABA: MINHA ESCALA ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Selecionar data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""
                <div style="background-color: #d4edda; padding: 20px; border-radius: 10px; border-left: 5px solid #28a745;">
                    <h2 style="margin:0; color: #155724;">✅ {meu_df.iloc[0]['serviço']}</h2>
                    <p style="margin:0; font-size: 18px;"><b>Horário:</b> {meu_df.iloc[0]['horário']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ Não constas na escala para este dia.")
        else:
            st.info(f"ℹ️ Escala de {nome_aba} ainda não disponível.")

    # --- ABA: CONSULTA GERAL ---
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
            mostrar_bloco("Administrativo / Tribunal", ["secretaria", "tribunal", "inquérito", "pronto"])
            mostrar_bloco("Indisponíveis (Folgas/Férias/Doente)", ["folga", "férias", "licença", "doente"])
        else:
            st.error("Escala não encontrada.")

    # --- ABA: SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        data_t = st.date_input("Data do serviço:", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                
                # Lista colegas disponíveis (que não estão de folga/férias/doentes)
                indisp = ["folga", "férias", "doente", "licença"]
                df_colegas = df_dia_t[(df_dia_t['id'] != st.session_state['user_id']) & 
                                      (~df_dia_t['serviço'].str.lower().str.contains('|'.join(indisp)))]
                
                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'] + " - " + df_colegas['serviço'] + " (" + df_colegas['horário'] + ")"
                    with st.form("form_troca"):
                        colega = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_input("Motivo:")
                        if st.form_submit_button("GERAR MENSAGEM"):
                            id_colega = colega.split(" - ")[0]
                            msg = f"*SOLICITAÇÃO DE TROCA ({nome_aba_t})*\n\n" \
                                  f"👉 *SAIR:* {st.session_state['user_posto']} {st.session_state['user_name']} ({meu_s} - {meu_h})\n" \
                                  f"👉 *ENTRAR:* ID {id_colega}\n" \
                                  f"📝 *MOTIVO:* {motivo}"
                            st.subheader("Copia a mensagem abaixo:")
                            st.code(msg, language="text")
            else:
                st.error("Não estás escalado para este dia.")

# Inicialização e Execução
if "logged_in" not in st.session_state: 
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
