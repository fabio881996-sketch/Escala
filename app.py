import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Setup
st.set_page_config(page_title="GNR Escalas", layout="wide")
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# 2. Conexão
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(aba):
    try:
        return conn.read(worksheet=aba, ttl=0)
    except:
        return None

# 3. Login
def login():
    st.title("🔑 Login GNR")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df = load_data("utilizadores")
            if df is not None:
                df.columns = [str(c).strip().lower() for c in df.columns]
                user = df[(df['email'].astype(str).str.strip().str.lower() == u_email) & (df['password'].astype(str).str.strip() == str(u_pass))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.rerun()
                else:
                    st.error("Dados incorretos")

# 4. App Principal
def main_app():
    st.sidebar.write(f"Utilizador: {st.session_state['user_name']}")
    
    menu = st.sidebar.radio("Menu", ["📅 Escala", "🔄 Trocas", "🛡️ Admin"])
    
    if menu == "📅 Escala":
        st.title("📅 Escala Diária")
        data_sel = st.date_input("Data")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_data(nome_aba)
        
        if df_dia is not None:
            df_dia.columns = [str(c).strip().lower() for c in df_dia.columns]
            st.success(f"Escala de {nome_aba} carregada")
            st.dataframe(df_dia, use_container_width=True, hide_index=True)
        else:
            st.warning("Escala não encontrada")

    elif menu == "🔄 Trocas":
        st.title("🔄 Pedir Troca")
        with st.form("t_form"):
            dt = st.date_input("Data da troca").strftime("%d-%m")
            sub = st.text_input("ID Substituto")
            if st.form_submit_button("Enviar"):
                df_t = load_data("trocas")
                nova = pd.DataFrame([{"data": dt, "id_requerente": st.session_state['user_id'], "id_substituto": sub, "status": "Pendente"}])
                df_f = pd.concat([df_t, nova], ignore_index=True)
                conn.update(worksheet="trocas", data=df_f)
                st.success("Enviado")

    elif menu == "🛡️ Admin":
        if st.session_state['user_email'] == EMAIL_ADMIN:
            st.title("🛡️ Painel Admin")
            df_t = load_data("trocas")
            if df_t is not None:
                st.dataframe(df_t)
        else:
            st.error("Acesso negado")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# 5. Execução
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
    
