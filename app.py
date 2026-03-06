import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema GNR - Escalas", page_icon="🚓", layout="wide")

# CONFIGURAÇÃO
EMAIL_ADMIN = "ferreira.fr@gnr.pt"
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(aba):
    try:
        return conn.read(worksheet=aba, ttl=0)
    except:
        return None

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    
    menu_opcoes = ["📅 Escala Diária", "🔄 Solicitar Troca", "📋 Meus Pedidos"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        menu_opcoes.append("🛡️ Painel Admin")
    
    menu = st.sidebar.radio("Navegação", menu_opcoes)

    # --- 📅 ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        
        df_dia = load_data(nome_aba)
        df_trocas = load_data("trocas")

        if df_dia is not None:
            # Limpeza de dados da escala
            df_dia.columns = [c.strip().lower() for c in df_dia.columns]
            df_dia['id'] = df_dia['id'].astype(str).str.strip()
            df_dia['serviço'] = df_dia['serviço'].fillna("").astype(str).str.strip()
            df_dia['horário'] = df_dia['horário'].fillna("---").astype(str).str.strip()

            # Lógica de substituição por trocas Aceites
            if df_trocas is not None and not df_trocas.empty:
                df_trocas.columns = [c.strip().lower() for c in df_trocas.columns]
                # Filtrar trocas aceites para este dia
                trocas_dia = df_trocas[(df_trocas['data'] == nome_aba) & (df_trocas['status'].str.lower() == "aceite")]
                
                for _, troca in trocas_dia.iterrows():
                    idx = df_dia[df_dia['id'] == str(troca['id_requerente'])].index
                    if not idx.empty:
                        # Substitui o ID original pelo ID do substituto na visualização
                        df_dia.at[idx[0], 'id'] = f"{troca['id_substituto']} (Troca)"

            # Mostrar o serviço do utilizador logado
            meu_id = st.session_state['user_id']
            meu_df = df_dia[df_dia['id'].str.contains(meu_id)]
            if not meu_df.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()

            # Função para desenhar os blocos
            def mostrar_bloco(titulo, lista_servicos, busca_exata=False):
                if busca_exata:
                    temp_df = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])].copy()
                else:
                    padrao = '|'.join(lista_servicos).lower()
                    temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                
                if not temp_df.empty:
                    st.subheader(f"🔹 {titulo}")
                    agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            # --- RENDERIZAÇÃO DOS BLOCOS ---
            mostrar_bloco("Atendimento", ["Atendimento"], busca_exata=True)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio Atendimento", "Apoio ao Atendimento"], busca_exata=True)
            mostrar_bloco("Patrulha Ocorrências", ["Patrulha Ocorrências", "PO"])
            mostrar_bloco("Patrulha", ["Patrulha"], busca_exata=True)
            mostrar_bloco("Ronda", ["Ronda"])
            mostrar_bloco("Serviços Remunerados", ["Remunerado"])
            mostrar_bloco("Administrativo e Apoio", ["Secretaria", "Pronto", "Inquérito"])
            mostrar_bloco("Tribunal", ["Tribunal"])
            mostrar_bloco("Diligência", ["Diligência"])
            mostrar_bloco("Folgas", ["Folga"])
            mostrar_bloco("Férias e Licenças", ["Férias", "Licença"])
            mostrar_bloco("Saúde", ["Doente"])
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    # --- 🔄 SOLICITAR TROCA (ESCRITA) ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Solicitar Troca de Serviço")
        # (Lógica de formulário que guarda na aba 'trocas' enviada anteriormente)
        st.info("Aqui o utilizador preenche os dados e clica em submeter.")

    # --- 🛡️ PAINEL ADMIN ---
    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Validação de Trocas")
        # (Lógica de aprovação/recusa que altera o status na aba 'trocas')

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# --- LÓGICA DE LOGIN (Mantém a que já funciona) ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df = load_data("utilizadores")
            if df is not None:
                df.columns = [c.strip().lower() for c in df.columns]
                user = df[(df['email'].str.lower() == u_email) & (df['password'].astype(str) == str(u_pass))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.rerun()
                else: st.error("Incorreto.")

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
