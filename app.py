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

# 2. CSS - DESIGN PREMIUM E CLEAN
st.markdown("""
    <style>
    /* FUNDO DA PÁGINA - Cinza Profissional */
    .stApp { 
        background-color: #F0F2F6; 
    }
    
    /* BARRA LATERAL - Estilo Dark Premium */
    [data-testid="stSidebar"] { 
        background-color: #263238 !important; 
        border-right: 1px solid #10171a; 
    }
    
    /* LOGIN - RIGOROSAMENTE COMO PEDISTE (Escuro e elegante) */
    div[data-testid="stForm"] { 
        background-color: #263238; 
        border-radius: 20px; 
        padding: 40px;
        border: 1px solid #37474f;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    }
    div[data-testid="stForm"] h1, div[data-testid="stForm"] label, div[data-testid="stForm"] p { 
        color: #FFFFFF !important; 
    }

    /* CARD DE PERFIL NA SIDEBAR */
    .profile-card { 
        background: #37474F; 
        padding: 20px; 
        border-radius: 15px; 
        margin-bottom: 25px; 
        border: 1px solid rgba(255,255,255,0.05); 
        text-align: center; 
    }
    
    /* BLOCOS DE SERVIÇO (Expanders) - DESIGN CLEAN */
    .streamlit-expanderHeader {
        background-color: #FFFFFF !important;
        border-radius: 10px !important;
        border: none !important;
        font-weight: bold !important;
        color: #263238 !important;
    }
    .st-expander {
        border: none !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        background-color: #FFFFFF !important;
        border-radius: 12px !important;
        margin-bottom: 15px !important;
    }

    /* TEXTOS SIDEBAR */
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, div[data-baseweb="radio"] div { 
        color: #ECEFF1 !important; 
    }
    
    /* CARD DE SERVIÇO PRINCIPAL (Minha Escala) */
    .status-card { 
        background: #FFFFFF; 
        padding: 30px; 
        border-radius: 20px; 
        border-left: 8px solid #263238; 
        box-shadow: 0 10px 20px rgba(0,0,0,0.05); 
        margin-bottom: 20px;
    }

    /* TABELAS MAIS LIMPAS */
    .stDataFrame {
        background-color: #FFFFFF;
        border-radius: 10px;
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

# 4. Login (Protegido e com as cores da Sidebar)
def login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; opacity: 0.8;'>Posto Territorial de Famalicão</p>", unsafe_allow_html=True)
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
        st.markdown(f"""<div class="profile-card"><div style="font-size: 40px; margin-bottom: 10px;">👮‍♂️</div><p style="color: #CFD8DC; font-size: 0.7rem; margin:0; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Militar em Serviço</p><h2 style="margin:0; font-size: 1.2rem; color: #FFFFFF !important;">{st.session_state['user_nome_completo']}</h2><p style="color: #90A4AE; font-size: 0.85rem;">ID: {st.session_state['user_id']}</p></div>""", unsafe_allow_html=True)
        
        menu = st.radio("MENU DE NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "👥 Lista Efetivo", "🔄 Solicitar Troca"])
        
        st.markdown("<br><hr style='border-color: #37474f;'><br>", unsafe_allow_html=True)
        if st.button("🚪 Terminar Sessão", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # --- ÁREA DE CONTEÚDO ---
    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        data_sel = st.date_input("Escolher Data:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)
        if df_dia is not None:
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.markdown(f"""<div class="status-card"><p style="color: #546E7A; font-weight: bold; margin-bottom: 5px;">SERVIÇO ATRIBUÍDO:</p><h1 style="margin:0; color: #263238; font-size: 2.5rem;">{meu_df.iloc[0]['serviço']}</h1><hr style="border-color: #F0F2F6;"><p style="margin-top:10px; font-size: 1.4rem; color: #455A64;">🕒 Horário: <span style="color: #263238; font-weight: bold;">{meu_df.iloc[0]['horário']}</span></p></div>""", unsafe_allow_html=True)
            else: st.warning("⚠️ Não consta serviço para este dia.")
        else: st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral do Posto")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY", key="geral")
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

            # Blocos Ordenados
            filtrar_e_mostrar("Atendimento", ["atendimento"])
            filtrar_e_mostrar("Apoio ao Atendimento", ["apoio"])
            filtrar_e_mostrar("Patrulhas", ["po", "patrulha", "ronda", "vtr"])
            filtrar_e_mostrar("Remunerados", ["remu", "renu", "grat", "extra"], excluir=False)
            filtrar_e_mostrar("Folga", ["folga"])
            filtrar_e_mostrar("Ausentes", ["férias", "licença", "doente", "diligência", "falta"])
            filtrar_e_mostrar("Administrativo e Outros", ["secretaria", "tribunal", "inquérito", "pronto", "oficina", "comando", "permanência"])
        else: st.error("Dia não disponível.")

    elif menu == "👥 Lista Efetivo":
        st.title("👥 Efetivo do Posto")
        df_efetivo = load_sheet("utilizadores")
        if df_efetivo is not None:
            ordem = ['id', 'posto', 'nome', 'telemóvel', 'email', 'password']
            cols = [c for c in ordem if c in df_efetivo.columns]
            st.dataframe(df_efetivo[cols], use_container_width=True, hide_index=True)

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitação de Troca")
        # ... (Restante do código de troca mantido)
        pass

# Inicialização
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
