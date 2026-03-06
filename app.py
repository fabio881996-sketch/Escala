import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Gestão de Escalas GNR", page_icon="📅")

# --- FUNÇÃO PARA LER ABAS ESPECÍFICAS ---
def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        # Formato para ler uma aba específica pelo nome
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        # Limpeza de nomes de colunas
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro ao ler aba {aba_nome}: {e}")
        return None

# --- LOGIN ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Escala de Serviço Posto Territorial Famalicão</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_input = st.text_input("Email").strip().lower()
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_users = load_sheet("utilizadores") # Lê a aba de logins
            if df_users is not None:
                user_row = df_users[(df_users['email'].str.lower() == email_input) & (df_users['password'].astype(str) == str(pass_input))]
                if not user_row.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = email_input
                    st.session_state["user_name"] = user_row.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Password incorretos.")

# --- APP PRINCIPAL ---
def main_app():
    st.sidebar.title(f"👤 {st.session_state['user_name']}")
    escolha = st.sidebar.radio("Navegação", ["A Minha Escala", "Ver Escala Geral"])
    
    df_escala = load_sheet("escala") # Lê a aba de turnos
    if df_escala is None: return

    # Converter datas com segurança
    df_escala['data'] = pd.to_datetime(df_escala['data'], errors='coerce').dt.date

    if escolha == "A Minha Escala":
        st.title("📅 Meus Turnos")
        minha = df_escala[df_escala['email'].str.lower() == st.session_state['user_email']]
        if not minha.empty:
            st.dataframe(minha[['data', 'turno', 'local']].sort_values('data'), use_container_width=True, hide_index=True)
        else:
            st.info("Não tens turnos agendados.")

    elif escolha == "Ver Escala Geral":
        st.title("👥 Escala por Dia")
        dia = st.date_input("Escolha o dia", datetime.now().date())
        # Cruzar com a aba de utilizadores para mostrar o NOME em vez do email na escala geral
        df_users = load_sheet("utilizadores")
        
        escala_dia = df_escala[df_escala['data'] == dia]
        if not escala_dia.empty and df_users is not None:
            # Junta as duas tabelas para mostrar o nome real do funcionário
            resultado = pd.merge(escala_dia, df_users[['email', 'nome']], on='email', how='left')
            st.dataframe(resultado[['nome', 'turno', 'local']], use_container_width=True, hide_index=True)
        else:
            st.warning("Ninguém escalado para este dia.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
