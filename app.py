import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Sistema GNR - Escalas", page_icon="🚓", layout="wide")

# LOGIN DO ADMIN
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# 2. CONEXÃO COM GOOGLE SHEETS
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na configuração dos Secrets.")
    st.stop()

# 3. FUNÇÃO PARA CARREGAR DADOS (COM ELIMINAÇÃO DE CACHE)
def load_data(aba_nome, forcar=False):
    try:
        # Se forçar=True, o ttl=0 garante que ele vai buscar os dados frescos à Google
        tempo_cache = 0 if forcar else 600 
        df = conn.read(worksheet=aba_nome, ttl=tempo_cache)
        
        if df is not None:
            # Normalizar cabeçalhos para evitar erros de acentos/espaços
            df.columns = [str(c).strip().lower()
                          .replace('ç', 'c').replace('í', 'i').replace('ó', 'o') 
                          .replace('é', 'e').replace('ã', 'a')
                          for c in df.columns]
            
            # Mapeamento flexível
            mapa = {}
            for col in df.columns:
                if 'id' in col: mapa[col] = 'id'
                elif 'serv' in col: mapa[col] = 'servico'
                elif 'hor' in col: mapa[col] = 'horario'
            
            return df.rename(columns=mapa)
        return None
    except Exception:
        return None

# 4. TELA DE LOGIN
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_data("utilizadores")
            if df_u is not None:
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == str(u_pass))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.rerun()
                else: st.error("Credenciais inválidas.")
            else: st.error("Erro ao ler aba 'utilizadores'. Verifique a Sheet.")

# 5. APLICAÇÃO PRINCIPAL
def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    
    # BOTÃO PARA LIMPAR CACHE (Se a escala não aparecer, clicar aqui)
    if st.sidebar.button("🔄 Forçar Atualização"):
        st.cache_data.clear()
        st.rerun()

    menu_opcoes = ["📅 Escala Diária", "🔄 Solicitar Troca", "📋 Meus Pedidos"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        menu_opcoes.append("🛡️ Painel Admin")
    
    menu = st.sidebar.radio("Navegação", menu_opcoes)

    # --- ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Escolha o dia:", value=datetime.now(), format="DD/MM/YYYY")
        
        # Tenta os dois formatos comuns: "06-03" e "6-3"
        aba_alvo = data_sel.strftime("%d-%m")
        aba_alternativa = f"{data_sel.day}-{data_sel.month}"
        
        df_dia = load_data(aba_alvo)
        if df_dia is None:
            df_dia = load_data(aba_alternativa)

        if df_dia is not None:
            # Limpar espaços dentro das células
            for col in ['id', 'servico', 'horario']:
                if col in df_dia.columns:
                    df_dia[col] = df_dia[col].fillna("---").astype(str).str.strip()

            # Mostrar o teu serviço
            meu_id = st.session_state['user_id']
            meu_serv = df_dia[df_dia['id'].str.contains(meu_id, na=False)]
            if not meu_serv.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_serv.iloc[0]['servico']} | {meu_serv.iloc[0]['horario']}")

            st.divider()

            # Lógica de Blocos
            def mostrar_bloco(titulo, termos):
                padrao = '|'.join(termos).lower()
                temp = df_dia[df_dia['servico'].str.lower().str.contains(padrao, na=False)]
                if not temp.empty:
                    st.subheader(f"🔹 {titulo}")
                    agrupado = temp.groupby(['servico', 'horario'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(agrupado[['id', 'servico', 'horario']], use_container_width=True, hide_index=True)

            mostrar_bloco("Atendimento / Apoio", ["atendimento"])
            mostrar_bloco("Patrulhas / PO", ["patrulha", "po"])
            mostrar_bloco("Administrativo / Outros", ["secretaria", "pronto", "ronda", "remunerado"])
            mostrar_bloco("Folgas e Ausências", ["folga", "ferias", "licenca", "doente"])
        else:
            st.warning(f"⚠️ Aba '{aba_alvo}' não encontrada.")
            st.info("Verifique se o nome da aba na Google Sheet é exatamente **06-03**.")

    # --- RESTO DO CÓDIGO (TROCAS E ADMIN) ---
    elif menu == "🔄 Solicitar Troca":
        st.info("Funcionalidade de troca ativa. Grave os dados na aba 'trocas'.")
        # (O código de gravação de trocas que já tínhamos)

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
