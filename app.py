import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# 1. Configuração de Página e Estilo
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] { background-color: #455A64; border-radius: 15px; padding: 30px; color: white; }
    div[data-testid="stForm"] * { color: white !important; }
    .troca-tag { background-color: #FFD54F; color: black; padding: 2px 10px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    .card-servico { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EAECEF; border-left: 5px solid #455A64; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções de Ligação
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def load_sheet(aba_nome):
    try:
        # Usamos uma técnica de leitura mais robusta
        url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        # Limpeza profunda: remove espaços e converte tudo para string limpa
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df.replace("nan", "")
    except Exception as e:
        return None

def registrar_troca_excel(dados_lista):
    try:
        client = get_gspread_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet("registos_trocas")
        worksheet.append_row(dados_lista)
        return True
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return False

# 3. Tela de Login (Ajustada para máxima compatibilidade)
def login_screen():
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u_input = st.text_input("📧 Email").strip().lower()
            p_input = st.text_input("🔑 Password", type="password").strip()
            
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                if not u_input or not p_input:
                    st.warning("Preencha todos os campos.")
                    return

                df_u = load_sheet("utilizadores")
                if df_u is not None:
                    # Filtro ultra-robusto
                    user_match = df_u[
                        (df_u['email'].astype(str).str.lower() == u_input) & 
                        (df_u['password'].astype(str) == p_input)
                    ]
                    
                    if not user_match.empty:
                        res = user_match.iloc[0]
                        st.session_state.update({
                            "logged_in": True, 
                            "user_id": str(res['id']), 
                            "user_nome": f"{res['posto']} {res['nome']}"
                        })
                        st.rerun()
                    else:
                        st.error("Utilizador ou password incorretos.")
                else:
                    st.error("Não foi possível carregar a lista de utilizadores.")

# 4. App Principal
def main_app():
    with st.sidebar:
        st.markdown(f"""<div style="text-align:center; padding:20px; background:#37474F; border-radius:10px; margin-bottom:20px;">
            <div style="font-size:40px;">👮‍♂️</div>
            <h3 style="color:white; margin:0;">{st.session_state['user_nome']}</h3>
            <p style="color:#B0BEC5; font-size:0.8rem;">ID: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Troquei", "👥 Efetivo"])
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    df_trocas = load_sheet("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            nome_aba = data_v.strftime("%d-%m")
            
            # Verificar troca
            t_ativa = None
            if df_trocas is not None and not df_trocas.empty:
                # Garantir que a comparação de IDs é feita como string
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            df_dia = load_sheet(nome_aba)
            label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")

            if t_ativa is not None:
                st.markdown(f"""<div class="card-servico" style="border-left-color: #FFD54F;">
                    <span style="color:#455A64; font-weight:bold;">{label}</span> <span class="troca-tag">TROCA REGISTADA</span>
                    <h3 style="margin:0;">{t_ativa['servico_destino']}</h3>
                    <p style="margin:0; font-style:italic; font-size:0.9rem;">🔄 Trocaste o teu {t_ativa['servico_origem']} com ID {t_ativa['id_destino']}</p>
                </div>""", unsafe_allow_html=True)
            elif df_dia is not None:
                meu = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                if not meu.empty:
                    st.markdown(f"""<div class="card-servico">
                        <span style="color:#455A64; font-weight:bold;">{label}</span>
                        <h3 style="margin:0;">{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})</h3>
                    </div>""", unsafe_allow_html=True)

    elif menu == "🔄 Troquei":
        st.title("🔄 Registar Troca Permanente")
        data_t = st.date_input("Data da troca:", format="DD/MM/YYYY")
        df_d = load_sheet(data_t.strftime("%d-%m"))
        
        if df_d is not None:
            meu = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu.empty:
                meu_s = f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"O teu serviço original: **{meu_s}**")
                
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("f_troca"):
                    c_sel = st.selectbox("Com quem trocaste?", opcoes)
                    if st.form_submit_button("GRAVAR TROCA NO EXCEL", use_container_width=True):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        
                        nova_linha = [data_t.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_s, id_c, serv_c]
                        
                        with st.spinner("A gravar..."):
                            if registrar_troca_excel(nova_linha):
                                st.success("Gravado! A escala geral e a tua escala foram atualizadas.")
                                st.balloons()
            else: st.warning("Não tens serviço neste dia.")

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala Geral")
        data_sel = st.date_input("Ver dia:", format="DD/MM/YYYY")
        d_str = data_sel.strftime('%d/%m/%Y')
        df_dia = load_sheet(data_sel.strftime("%d-%m"))
        
        if df_dia is not None:
            if df_trocas is not None and not df_trocas.empty:
                trocas_dia = df_trocas[df_trocas['data'] == d_str]
                for _, t in trocas_dia.iterrows():
                    m_orig = df_dia['id'].astype(str) == str(t['id_origem'])
                    m_dest = df_dia['id'].astype(str) == str(t['id_destino'])
                    if any(m_orig) and any(m_dest):
                        serv_original = df_dia.loc[m_orig, 'serviço'].values[0]
                        df_dia.loc[m_orig, 'serviço'] = f"{t['servico_destino']} (T)"
                        df_dia.loc[m_dest, 'serviço'] = f"{serv_original} (T)"
            st.dataframe(df_dia[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo")
        df_u = load_sheet("utilizadores")
        if df_u is not None:
            st.dataframe(df_u[['id', 'nim', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)

# Main
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    login_screen()
else:
    main_app()
    
    
