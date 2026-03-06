import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Sistema GNR - Escalas", page_icon="🚓", layout="wide")

# CONFIGURAÇÃO DO ADMIN
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# Inicializar Conexão Segura
conn = st.connection("gsheets", type=GSheetsConnection)

def mostrar_bloco(df, titulo, lista_servicos, ordenar_hora=False, busca_exata=False):
    if busca_exata:
        temp_df = df[df['serviço'].str.lower().isin([s.lower() for s in lista_servicos])].copy()
    else:
        padrao = '|'.join(lista_servicos).lower()
        temp_df = df[df['serviço'].str.lower().str.contains(padrao, na=False)].copy()
    
    if not temp_df.empty:
        st.subheader(f"🔹 {titulo}")
        agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
        agrupado = agrupado[['id', 'serviço', 'horário']]
        if ordenar_hora:
            agrupado = agrupado.sort_values(by='horário')
        st.dataframe(agrupado, use_container_width=True, hide_index=True)

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso à Escala</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                df_u = conn.read(worksheet="utilizadores")
                df_u.columns = [c.strip().lower() for c in df_u.columns]
                user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = email_i
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")
            except Exception as e:
                st.error(f"Erro de conexão: Verifique os Secrets e a aba 'utilizadores'.")

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    
    opcoes = ["📅 Escala Diária", "🔄 Solicitar Troca", "📋 Meus Pedidos"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        opcoes.append("🛡️ Painel Admin")
    menu = st.sidebar.radio("Navegação", opcoes)

    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        
        try:
            df_dia = conn.read(worksheet=nome_aba)
            df_dia.columns = [c.strip().lower() for c in df_dia.columns]
            df_dia['horário'] = df_dia['horário'].fillna("---")
            
            meu_df = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
            if not meu_df.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()
            mostrar_bloco(df_dia, "Atendimento", ["Atendimento"], True, True)
            mostrar_bloco(df_dia, "Apoio ao Atendimento", ["Apoio Atendimento", "Apoio ao Atendimento"], True, True)
            mostrar_bloco(df_dia, "Patrulha Ocorrências", ["PO", "Patrulha Ocorrências"], True, True)
            mostrar_bloco(df_dia, "Folgas", ["Folga"])
            mostrar_bloco(df_dia, "Férias e Licenças", ["Férias", "Licença"])
        except:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Validação de Trocas")
        try:
            df_t = conn.read(worksheet="trocas")
            st.dataframe(df_t, use_container_width=True)
        except:
            st.error("Crie a aba 'trocas' na sua Google Sheet.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# Lógica de Sessão
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
