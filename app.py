import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuração de Página
st.set_page_config(
    page_title="GNR - Portal de Escalas",
    page_icon="🚓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. CSS - DESIGN CLEAN, CONTRASTE ALTO
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Claro Platina (Muito suave) */
    .stApp { 
        background-color: #F8F9FA; 
    }
    
    /* BARRA LATERAL - Mantida Dark (Como pediste para não mexer) */
    [data-testid="stSidebar"] { 
        background-color: #263238 !important; 
    }
    
    /* LOGIN - RIGOROSAMENTE IGUAL (Escuro) */
    div[data-testid="stForm"] { 
        background-color: #263238; 
        border-radius: 15px; 
        padding: 30px;
        color: white;
    }
    div[data-testid="stForm"] p, div[data-testid="stForm"] label, div[data-testid="stForm"] h1 { 
        color: white !important; 
    }

    /* BLOCOS DE SERVIÇO (Expanders) - AGORA CLEAN E CLAROS */
    .st-expander {
        background-color: #FFFFFF !important;
        border: 1px solid #E9ECEF !important;
        border-radius: 8px !important;
        box-shadow: none !important;
        margin-bottom: 10px !important;
    }
    
    /* Título dos Blocos - Texto escuro para contraste máximo */
    .streamlit-expanderHeader {
        color: #212529 !important;
        font-weight: 600 !important;
        background-color: #FFFFFF !important;
    }

    /* CARD DE SERVIÇO PRINCIPAL (Minha Escala) */
    .status-card { 
        background: #FFFFFF; 
        padding: 25px; 
        border-radius: 12px; 
        border: 1px solid #E9ECEF;
        border-left: 5px solid #455A64;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Ajuste de Texto Geral na Página */
    h1, h2, h3, p {
        color: #212529 !important;
    }
    
    /* Tabelas */
    .stDataFrame {
        border: 1px solid #E9ECEF;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Função de Carregamento
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")
        return df
    except:
        return None

# 4. Login (Protegido)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Posto Territorial de Famalicão</p>", unsafe_allow_html=True)
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
                    else: st.error("❌ Credenciais incorretas.")
                else: st.error("⚠️ Erro de base de dados.")

# 5. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div style="background: #37474F; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px;">
            <div style="font-size: 35px;">👮‍♂️</div>
            <h2 style="margin:0; font-size: 1.1rem; color: white !important;">{st.session_state['user_nome_completo']}</h2>
            <p style="color: #B0BEC5; font-size: 0.8rem; margin:0;">ID: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Sair"):
            st.session_state["logged_in"] = False
            st.rerun()

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""<div class="status-card">
                    <h1 style="margin:0; font-size: 2rem;">{meu_df.iloc[0]['serviço']}</h1>
                    <p style="color: #6C757D; font-size: 1.2rem;">🕒 Horário: <b>{meu_df.iloc[0]['horário']}</b></p>
                </div>""", unsafe_allow_html=True)
            else: st.warning("⚠️ Sem serviço para este dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Escolher dia:", format="DD/MM/YYYY", key="geral")
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
                    if excluir:
                        df_restante = df_restante[~df_restante['id'].isin(temp_df['id'])]

            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Apoio ao Atendimento", ["apoio"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "renu", "grat", "extra"], excluir=False)
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente", "diligência", "falta"])
            filtrar_e_mostrar("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando", "permanência"])

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo")
        df_ef = load_sheet("utilizadores")
        if df_ef is not None:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel', 'email', 'password']], use_container_width=True, hide_index=True)

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Troca de Serviço")
        pass

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
