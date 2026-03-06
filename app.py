import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema GNR - Trocas", page_icon="🚓", layout="wide")

# CONFIGURAÇÃO DO ADMINISTRADOR
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        if 'id' in df.columns: df['id'] = df['id'].astype(str).str.strip()
        return df
    except:
        return None

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    
    # Define o menu com base no email
    opcoes_menu = ["📅 Escala Diária", "🔄 Minhas Trocas"]
    if st.session_state['user_email'] == EMAIL_ADMIN:
        opcoes_menu.append("🛡️ Painel Admin")
    
    menu = st.sidebar.radio("Navegação", opcoes_menu)

    # --- 📅 ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço")
        # ... (Aqui manténs todo o código dos blocos Atendimento, Patrulha, etc. que já tinhas)
        st.info("Visualização da Escala Geral")

    # --- 🔄 MINHAS TROCAS (Utilizador) ---
    elif menu == "🔄 Minhas Trocas":
        st.title("🔄 Gestão de Trocas")
        tab1, tab2 = st.tabs(["Solicitar Nova Troca", "Histórico/Status"])
        
        with tab1:
            data_t = st.date_input("Data do serviço", format="DD/MM/YYYY")
            df_dia = load_sheet(data_t.strftime("%d-%m"))
            if df_dia is not None:
                meu_id = st.session_state['user_id']
                meu_servico = df_dia[df_dia['id'] == meu_id]
                
                if not meu_servico.empty:
                    st.write(f"O teu serviço: **{meu_servico.iloc[0]['serviço']}**")
                    colegas = df_dia[df_dia['id'] != meu_id]
                    selecionado = st.selectbox("Escolher colega para troca:", colegas['id'].tolist())
                    motivo = st.text_area("Motivo da troca")
                    
                    if st.button("Enviar Pedido ao Comandante"):
                        # Aqui o sistema simula o envio. 
                        # Para gravar real, precisamos da conexão st.connection("gsheets")
                        st.success(f"Pedido enviado! Aguarda validação de {EMAIL_ADMIN}")
                        st.info("Status atual: ⏳ PENDENTE")
                else:
                    st.warning("Não estás escalado para este dia.")

        with tab2:
            st.subheader("Estado dos teus pedidos")
            df_t = load_sheet("trocas")
            if df_t is not None:
                minhas = df_t[(df_t['id_requerente'] == st.session_state['user_id']) | 
                              (df_t['id_substituto'] == st.session_state['user_id'])]
                st.dataframe(minhas, use_container_width=True, hide_index=True)

    # --- 🛡️ PAINEL ADMIN (Só para ferreira.fr@gnr.pt) ---
    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Validação de Pedidos de Troca")
        df_t = load_sheet("trocas")
        
        if df_t is not None and not df_t.empty:
            pendentes = df_t[df_t['status'].str.lower() == "pendente"]
            if not pendentes.empty:
                for idx, row in pendentes.iterrows():
                    with st.expander(f"Pedido: {row['id_requerente']} 🔄 {row['id_substituto']} ({row['data']})"):
                        st.write(f"**Motivo:** {row['motivo']}")
                        col1, col2 = st.columns(2)
                        if col1.button("✅ Aprovar", key=f"app_{idx}"):
                            st.success("Troca Aprovada! A escala será atualizada.")
                        if col2.button("❌ Recusar", key=f"rej_{idx}"):
                            st.error("Troca Recusada.")
            else:
                st.write("Não existem pedidos pendentes.")
        else:
            st.info("Sem registos na aba de trocas.")

# --- LOGIN MODIFICADO PARA GUARDAR EMAIL ---
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso GNR</h1>", unsafe_allow_html=True)
    with st.form("login"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                user = df_u[(df_u['email'].str.lower() == u_email) & (df_u['password'].astype(str) == str(u_pass))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email # Guarda o email para validar admin
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
