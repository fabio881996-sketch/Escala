import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sistema de Escalas GNR", page_icon="🚓", layout="centered")

# --- FUNÇÃO PARA CARREGAR QUALQUER ABA ---
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        # Formato para ler aba específica
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except:
        return None

# --- LOGIN ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Acesso Privado - Posto Territorial Famalicão</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Dados de acesso incorretos.")

# --- APP PRINCIPAL ---
def main_app():
    # Sidebar com info do utilizador
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID Mecanográfico: {st.session_state['user_id']}")
    
    st.title("📅 Consulta de Escala Diária")
    st.write("Selecione o dia no calendário para ver quem está de serviço.")

    # 1. Seleção da Data
    data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
    nome_aba = data_sel.strftime("%d-%m") # Formato da aba na Google Sheet (ex: 06-03)

    st.divider()

    # 2. Carregar Dados
    df_users = load_sheet("utilizadores")
    df_dia = load_sheet(nome_aba)

    if df_dia is not None and df_users is not None:
        # Cruza o ID da aba do dia com o Nome da aba utilizadores
        # Garante que ambos os IDs são tratados como strings para não dar erro
        df_dia['id'] = df_dia['id'].astype(str)
        df_users['id'] = df_users['id'].astype(str)
        
        resultado = pd.merge(df_dia, df_users[['id', 'nome']], on='id', how='left')

        # 3. Destaque para o utilizador logado
        meu_servico = resultado[resultado['id'] == st.session_state['user_id']]
        
        if not meu_servico.empty:
            st.success(f"*O teu serviço para dia {nome_aba}:*")
            col1, col2 = st.columns(2)
            col1.metric("Turno", meu_servico.iloc[0]['turno'])
            col2.metric("Local", meu_servico.iloc[0]['local'])
        else:
            st.warning("Não tens serviço atribuído nesta data.")

        # 4. Tabela Geral do Dia
        st.subheader(f"Equipa completa em {nome_aba}")
        # Ordenar por turno para ficar organizado
        resultado = resultado.sort_values(by='turno')
        st.dataframe(resultado[['nome', 'turno', 'local']], use_container_width=True, hide_index=True)

    else:
        st.error(f"⚠️ A escala para o dia {nome_aba} ainda não foi carregada no sistema.")
        st.info("Podes tentar outro dia ou contactar o administrador.")

    # Botão Sair
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()

# Lógica de Fluxo
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
