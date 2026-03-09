import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E ESTILO VISUAL ORIGINAL ---
st.set_page_config(page_title="GNR - Portal de Escalas", page_icon="🚓", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA !important; }
    [data-testid="stSidebar"] { background-color: #455A64 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    /* Estilo do Formulário de Login */
    div[data-testid="stForm"] { 
        background-color: #455A64; 
        border-radius: 15px; 
        padding: 30px; 
        box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
    }
    div[data-testid="stForm"] * { color: white !important; }
    
    /* Estilo dos Blocos (Cards) */
    .card-servico { 
        background: #FFFFFF; 
        padding: 18px; 
        border-radius: 10px; 
        border: 1px solid #EAECEF; 
        border-left: 6px solid #455A64; 
        margin-bottom: 12px; 
        box-shadow: 2px 2px 8px rgba(0,0,0,0.05);
        color: #263238;
    }
    .card-meu { border-left-color: #1E88E5 !important; background-color: #E3F2FD !important; }
    .card-troca { border-left-color: #FFD54F !important; }
    .troca-tag { 
        background-color: #FFD54F; 
        color: black; 
        padding: 3px 12px; 
        border-radius: 20px; 
        font-weight: bold; 
        font-size: 0.75rem; 
        float: right;
    }
    .horario-text { color: #546E7A; font-size: 0.9rem; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNÇÕES DE LIGAÇÃO AO GOOGLE SHEETS ---
def get_client():
    try:
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de Credenciais: {e}")
        return None

def load_data(aba_nome):
    # Tenta via CSV (Leitura rápida)
    try:
        base_url = st.secrets["gsheet_url"].split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url, dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        return df.replace("nan", "")
    except:
        # Fallback via API se o CSV falhar ou aba for privada
        try:
            client = get_client()
            sh = client.open_by_url(st.secrets["gsheet_url"])
            worksheet = sh.worksheet(aba_nome)
            df = pd.DataFrame(worksheet.get_all_records()).astype(str)
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except: return pd.DataFrame()

def salvar_troca(linha):
    try:
        client = get_client()
        sh = client.open_by_url(st.secrets["gsheet_url"])
        worksheet = sh.worksheet("registos_trocas")
        worksheet.append_row(linha)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar no Excel: {e}")
        return False

# --- 3. LÓGICA DE LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h1 style='text-align: center; color: white;'>🚓 Portal de Escalas</h1>", unsafe_allow_html=True)
            u_in = st.text_input("📧 Email").strip().lower()
            p_in = st.text_input("🔑 Password", type="password").strip()
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                df_u = load_data("utilizadores")
                if not df_u.empty:
                    user_match = df_u[(df_u['email'].str.lower() == u_in) & (df_u['password'] == p_in)]
                    if not user_match.empty:
                        res = user_match.iloc[0]
                        st.session_state.update({
                            "logged_in": True,
                            "user_id": str(res['id']),
                            "user_nome": f"{res['posto']} {res['nome']}"
                        })
                        st.rerun()
                    else: st.error("Email ou Password incorretos.")
                else: st.error("Não foi possível validar utilizadores.")

# --- 4. APP APÓS LOGIN ---
else:
    with st.sidebar:
        st.markdown(f"""<div style="text-align:center; padding:15px; background:#37474F; border-radius:10px; margin-bottom:20px;">
            <div style="font-size:45px;">👮‍♂️</div>
            <h3 style="color:white; margin:0;">{st.session_state['user_nome']}</h3>
            <p style="color:#B0BEC5; font-size:0.85rem; margin:0;">ID Militar: {st.session_state['user_id']}</p>
        </div>""", unsafe_allow_html=True)
        
        menu = st.radio("NAVEGAÇÃO", ["📅 Minha Escala", "🔍 Consulta Geral", "🔄 Registar Troca", "👥 Efetivo"])
        st.markdown("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state["logged_in"] = False
            st.rerun()

    # Carregar trocas globais
    df_trocas = load_data("registos_trocas")

    if menu == "📅 Minha Escala":
        st.title("📅 O Teu Serviço")
        hoje = datetime.now()
        
        for i in range(8):
            data_v = hoje + timedelta(days=i)
            d_str = data_v.strftime('%d/%m/%Y')
            label = "HOJE" if i == 0 else data_v.strftime("%d/%m (%a)")
            
            # Verificar se há troca registada para mim neste dia
            t_ativa = None
            if not df_trocas.empty and 'data' in df_trocas.columns:
                f = df_trocas[(df_trocas['data'] == d_str) & (df_trocas['id_origem'].astype(str) == st.session_state['user_id'])]
                if not f.empty: t_ativa = f.iloc[0]

            if t_ativa is not None:
                st.markdown(f"""<div class="card-servico card-troca">
                    <span class="troca-tag">TROCA EFETUADA</span>
                    <span style="font-weight:bold;">{label}</span>
                    <h3 style="margin:8px 0;">{t_ativa['servico_destino']}</h3>
                    <p style="margin:0; font-style:italic; font-size:0.85rem;">Substitui o teu serviço original: {t_ativa['servico_origem']}</p>
                </div>""", unsafe_allow_html=True)
            else:
                df_dia = load_data(data_v.strftime("%d-%m"))
                if not df_dia.empty:
                    meu_s = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
                    if not meu_s.empty:
                        st.markdown(f"""<div class="card-servico card-meu">
                            <span style="font-weight:bold;">{label}</span>
                            <h3 style="margin:8px 0;">{meu_s.iloc[0]['serviço']}</h3>
                            <span class="horario-text">🕒 {meu_s.iloc[0]['horário']}</span>
                        </div>""", unsafe_allow_html=True)

    elif menu == "🔍 Consulta Geral":
        st.title("🔍 Escala de Serviço Geral")
        data_g = st.date_input("Selecionar Dia:", value=datetime.now(), format="DD/MM/YYYY")
        d_str_g = data_g.strftime('%d/%m/%Y')
        df_g = load_data(data_g.strftime("%d-%m"))
        
        if not df_g.empty:
            # Processar trocas visuais na lista geral
            for _, row in df_g.iterrows():
                servico_final = row['serviço']
                horario_final = row['horário']
                is_troca = False
                
                if not df_trocas.empty and 'data' in df_trocas.columns:
                    # Se eu sou a origem da troca
                    t_orig = df_trocas[(df_trocas['data'] == d_str_g) & (df_trocas['id_origem'].astype(str) == str(row['id']))]
                    if not t_orig.empty:
                        servico_final = f"{t_orig.iloc[0]['servico_destino']} 🔄"
                        is_troca = True
                
                is_me = str(row['id']) == st.session_state['user_id']
                css_class = "card-meu" if is_me else ""
                
                st.markdown(f"""<div class="card-servico {css_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight:bold; color:#455A64;">ID: {row['id']}</span>
                        <span class="horario-text">{horario_final}</span>
                    </div>
                    <h3 style="margin:5px 0;">{servico_final}</h3>
                </div>""", unsafe_allow_html=True)
        else:
            st.warning("Nenhum serviço escalado para este dia.")

    elif menu == "🔄 Registar Troca":
        st.title("🔄 Registar Troca no Sistema")
        st.write("Usa este formulário para oficializar uma troca direta com um colega.")
        
        d_troca = st.date_input("Data do serviço a trocar:", format="DD/MM/YYYY")
        df_d = load_data(d_troca.strftime("%d-%m"))
        
        if not df_d.empty:
            meu_serv = df_d[df_d['id'].astype(str) == st.session_state['user_id']]
            if not meu_serv.empty:
                meu_original = f"{meu_serv.iloc[0]['serviço']} ({meu_serv.iloc[0]['horário']})"
                st.success(f"O teu serviço: **{meu_original}**")
                
                colegas = df_d[df_d['id'].astype(str) != st.session_state['user_id']]
                opcoes = colegas.apply(lambda x: f"{x['id']} - {x['serviço']} ({x['horário']})", axis=1).tolist()
                
                with st.form("form_troca_final"):
                    c_sel = st.selectbox("Com quem trocaste?", opcoes)
                    if st.form_submit_button("GRAVAR TROCA NO EXCEL", use_container_width=True):
                        id_c = c_sel.split(" - ")[0]
                        serv_c = c_sel.split(" - ", 1)[1]
                        
                        linha = [d_troca.strftime('%d/%m/%Y'), st.session_state['user_id'], meu_original, id_c, serv_c]
                        
                        if salvar_troca(linha):
                            st.success("Troca registada com sucesso! Os cards foram atualizados.")
                            st.balloons()
            else: st.warning("Não tens serviço escalado para este dia.")
        else: st.error("Não existe escala criada para este dia no Excel.")

    elif menu == "👥 Efetivo":
        st.title("👥 Efetivo do Posto")
        df_ef = load_data("utilizadores")
        if not df_ef.empty:
            st.dataframe(df_ef[['id', 'posto', 'nome', 'telemóvel']], use_container_width=True, hide_index=True)         
