import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sistema de Escalas GNR", page_icon="🚓", layout="centered")

# --- FUNÇÃO PARA CARREGAR QUALQUER ABA ---
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        # Formato para ler aba específica via CSV
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        # Limpar nomes de colunas (remover espaços e pôr em minúsculas)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except:
        return None

# --- LOGIN ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Acesso à Escala</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                # Verificação de login na aba 'utilizadores'
                user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")

# --- APP PRINCIPAL ---
def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID: {st.session_state['user_id']}")
    
    st.title("📅 Escala de Serviço Diária")
    st.write("Selecione um dia para ver a escala de todos os elementos.")

    # 1. Seleção da Data
    data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
    nome_aba = data_sel.strftime("%d-%m") # Nome da aba na Sheet (ex: 06-03)

    st.divider()

    # 2. Carregar Dados das duas abas necessárias
    df_users = load_sheet("utilizadores")
    df_dia = load_sheet(nome_aba)

    if df_dia is not None and df_users is not None:
        # Garantir que o ID é string em ambos os lados para o cruzamento (merge)
        df_dia['id'] = df_dia['id'].astype(str)
        df_users['id'] = df_users['id'].astype(str)
        
        # Cruzar a aba do dia com a aba de utilizadores para obter os Nomes reais
        # Colunas esperadas na aba do dia: id, serviço, horário
        resultado = pd.merge(df_dia, df_users[['id', 'nome']], on='id', how='left')

        # 3. Mostrar primeiro o serviço do próprio utilizador (Destaque)
        meu_servico = resultado[resultado['id'] == st.session_state['user_id']]
        
        if not meu_servico.empty:
            with st.expander("📌 O MEU SERVIÇO", expanded=True):
                c1, c2 = st.columns(2)
                c1.write(f"*Serviço:* {meu_servico.iloc[0]['serviço']}")
                c2.write(f"*Horário:* {meu_servico.iloc[0]['horário']}")
        else:
            st.warning("Não tens serviço atribuído nesta data específica.")

        # 4. Mostrar a Escala de Todos (O que pediste)
        st.subheader(f"👥 Escala Geral - {nome_aba}")
        
        # Selecionar e ordenar colunas para exibição
        # Colunas finais: Nome, Serviço, Horário
        if 'nome' in resultado.columns:
            exibicao = resultado[['nome', 'serviço', 'horário']].sort_values(by='horário')
            
            # Melhorar a tabela visualmente
            st.dataframe(
                exibicao, 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.error("Erro ao cruzar dados dos funcionários.")

    else:
        st.info(f"ℹ️ A escala para o dia *{nome_aba}* ainda não foi criada na Google Sheet.")

    # Botão Sair
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()

# Fluxo da App
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
