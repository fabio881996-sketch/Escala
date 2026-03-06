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
    st.error("Erro na configuração dos Secrets do Google Sheets.")
    st.stop()

# 3. FUNÇÃO PARA CARREGAR DADOS COM LIMPEZA
def load_data(aba_nome):
    try:
        df = conn.read(worksheet=aba_nome, ttl=0)
        if df is not None:
            # Normalizar nomes das colunas: remove espaços, acentos comuns e minúsculas
            df.columns = [str(c).strip().lower()
                          .replace('ç', 'c').replace('í', 'i').replace('ó', 'o') 
                          for c in df.columns]
            
            # Mapeamento flexível de colunas
            mapa = {}
            for col in df.columns:
                if 'id' in col: mapa[col] = 'id'
                elif 'serv' in col: mapa[col] = 'servico'
                elif 'hor' in col: mapa[col] = 'horario'
            
            df = df.rename(columns=mapa)
            return df
        return None
    except:
        return None

# 4. TELA DE LOGIN
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_data("utilizadores")
            if df_u is not None:
                # Procura user
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == str(u_pass))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
            else:
                st.error("Não foi possível carregar a aba 'utilizadores'.")

# 5. APLICAÇÃO PRINCIPAL
def main_app():
    # Sidebar
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID: {st.session_state['user_id']}")
    
    menu_opcoes = ["📅 Escala Diária", "🔄 Solicitar Troca", "📋 Meus Pedidos"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        menu_opcoes.append("🛡️ Painel Admin")
    
    menu = st.sidebar.radio("Navegação", menu_opcoes)

    # --- ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        
        df_dia = load_data(nome_aba)
        df_trocas = load_data("trocas")

        if df_dia is not None:
            # Limpeza de dados das células
            for col in ['id', 'servico', 'horario']:
                if col in df_dia.columns:
                    df_dia[col] = df_dia[col].fillna("---").astype(str).str.strip()

            # Lógica de Substituição de Trocas Aceites
            if df_trocas is not None and not df_trocas.empty:
                df_trocas.columns = [str(c).strip().lower() for c in df_trocas.columns]
                trocas_ok = df_trocas[(df_trocas['data'] == nome_aba) & (df_trocas['status'].str.lower() == "aceite")]
                for _, t in trocas_ok.iterrows():
                    idx = df_dia[df_dia['id'] == str(t['id_requerente'])].index
                    if not idx.empty:
                        df_dia.at[idx[0], 'id'] = f"🔄 {t['id_substituto']}"

            # Destaque do utilizador
            meu_id = st.session_state['user_id']
            meu_serv = df_dia[df_dia['id'].str.contains(meu_id, na=False)]
            if not meu_serv.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_serv.iloc[0]['servico']} | {meu_serv.iloc[0]['horario']}")

            st.divider()

            # Funcao Blocos
            def mostrar_bloco(titulo, termos, exata=False):
                if exata:
                    temp = df_dia[df_dia['servico'].str.lower().isin([s.lower() for s in termos])]
                else:
                    padrao = '|'.join(termos).lower()
                    temp = df_dia[df_dia['servico'].str.lower().str.contains(padrao, na=False)]
                
                if not temp.empty:
                    st.subheader(f"🔹 {titulo}")
                    agrupado = temp.groupby(['servico', 'horario'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(agrupado[['id', 'servico', 'horario']], use_container_width=True, hide_index=True)

            # Renderização
            mostrar_bloco("Atendimento", ["Atendimento"], exata=True)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio Atendimento", "Apoio ao Atendimento"], exata=True)
            mostrar_bloco("Patrulha Ocorrências / PO", ["Patrulha Ocorrências", "PO"])
            mostrar_bloco("Patrulha", ["Patrulha"], exata=True)
            mostrar_bloco("Ronda / Remunerados", ["Ronda", "Remunerado"])
            mostrar_bloco("Administrativo / Secretaria", ["Secretaria", "Pronto", "Inquérito"])
            mostrar_bloco("Folgas / Férias", ["Folga", "Férias", "Licença"])
        else:
            st.warning(f"Escala de {nome_aba} não encontrada na Google Sheet.")

    # --- SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Novo Pedido de Troca")
        with st.form("troca_form"):
            data_t = st.date_input("Data do serviço")
            id_sub = st.text_input("ID do Colega")
            motivo = st.text_area("Motivo")
            if st.form_submit_button("Submeter Pedido"):
                df_t = load_data("trocas")
                nova_t = pd.DataFrame([{
                    "data": data_t.strftime("%d-%m"),
                    "id_requerente": st.session_state['user_id'],
                    "id_substituto": id_sub,
                    "motivo": motivo,
                    "status": "Pendente"
                }])
                df_final = pd.concat([df_t, nova_t], ignore_index=True)
                conn.update(worksheet="trocas", data=df_final)
                st.success("Pedido enviado para o Administrador!")

    # --- PAINEL ADMIN ---
    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Painel de Validação")
        df_t = load_data("trocas")
        if df_t is not None and not df_t.empty:
            pendentes = df_t[df_t['status'].astype(str).str.lower() == "pendente"]
            if not pendentes.empty:
                for idx, r in pendentes.iterrows():
                    st.write(f"**{r['data']}**: ID {r['id_requerente']} 🔄 ID {r['id_substituto']}")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Aprovar", key=f"ok_{idx}"):
                        df_t.at[idx, 'status'] = "Aceite"
                        conn.update(worksheet="trocas", data=df_t)
                        st.rerun()
                    if c2.button("❌ Recusar", key=f"no_{idx}"):
                        df_t.at[idx, 'status'] = "Recusado"
                        conn.update(worksheet="trocas", data=df_t)
                        st.rerun()
            else: st.info("Sem pedidos pendentes.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# CONTROLO DE SESSÃO
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
