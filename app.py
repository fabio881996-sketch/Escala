import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Sistema GNR - Escalas", page_icon="🚓", layout="wide")

# 2. DEFINIÇÕES GERAIS
EMAIL_ADMIN = "ferreira.fr@gnr.pt"

# 3. CONEXÃO COM GOOGLE SHEETS
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na ligação GSheets. Verifica os Secrets.")
    st.stop()

def load_data(aba):
    try:
        df = conn.read(worksheet=aba, ttl=0)
        return df
    except:
        return None

# 4. FUNÇÃO DE LOGIN
def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_data("utilizadores")
            if df_u is not None:
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                user = df_u[
                    (df_u['email'].astype(str).str.strip().str.lower() == u_email) & 
                    (df_u['password'].astype(str).str.strip() == str(u_pass))
                ]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.session_state["user_email"] = u_email
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")
            else:
                st.error("Não foi possível carregar a tabela de utilizadores.")

# 5. APLICAÇÃO PRINCIPAL
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
            df_dia.columns = [str(c).strip().lower() for c in df_dia.columns]
            df_dia['id'] = df_dia['id'].astype(str).str.strip()
            df_dia['serviço'] = df_dia['serviço'].fillna("").astype(str).str.strip()
            df_dia['horário'] = df_dia['horário'].fillna("---").astype(str).str.strip()

            # Lógica de Trocas Aceites
            if df_trocas is not None and not df_trocas.empty:
                df_trocas.columns = [str(c).strip().lower() for c in df_trocas.columns]
                trocas_aceites = df_trocas[(df_trocas['data'] == nome_aba) & (df_trocas['status'].str.lower() == "aceite")]
                for _, t in trocas_aceites.iterrows():
                    idx = df_dia[df_dia['id'] == str(t['id_requerente'])].index
                    if not idx.empty:
                        df_dia.at[idx[0], 'id'] = f"{t['id_substituto']} (Troca)"

            # Mostrar meu serviço
            meu_df = df_dia[df_dia['id'].str.contains(st.session_state['user_id'])]
            if not meu_df.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()

            # Função de Blocos
            def mostrar_bloco(titulo, lista_servicos, exato=False):
                if exato:
                    temp = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])]
                else:
                    padrao = '|'.join(lista_servicos).lower()
                    temp = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)]
                
                if not temp.empty:
                    st.subheader(f"🔹 {titulo}")
                    agrupado = temp.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    st.dataframe(agrupado[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            mostrar_bloco("Atendimento", ["Atendimento"], exato=True)
            mostrar_bloco("Apoio Atendimento", ["Apoio Atendimento", "Apoio ao Atendimento"])
            mostrar_bloco("Patrulha Ocorrências", ["PO", "Patrulha Ocorrências"])
            mostrar_bloco("Operacional", ["Patrulha", "Ronda", "Remunerado"])
            mostrar_bloco("Administrativo", ["Secretaria", "Pronto", "Inquérito"])
            mostrar_bloco("Ausências", ["Folga", "Férias", "Licença", "Doente", "Tribunal", "Diligência"])
        else:
            st.warning(f"Escala de {nome_aba} não encontrada.")

    # --- 🔄 SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Novo Pedido de Troca")
        with st.form("troca_form"):
            data_t = st.date_input("Data do Serviço", format="DD/MM/YYYY")
            id_sub = st.text_input("ID do Substituto").strip()
            motivo = st.text_area("Motivo")
            if st.form_submit_button("Submeter Pedido"):
                df_t = load_data("trocas")
                novo_p = pd.DataFrame([{"data": data_t.strftime("%d-%m"), "id_requerente": st.session_state['user_id'], "id_substituto": id_sub, "motivo": motivo, "status": "Pendente"}])
                df_final = pd.concat([df_t, novo_p], ignore_index=True)
                conn.update(worksheet="trocas", data=df_final)
                st.success("Pedido enviado!")

    # --- 🛡️ PAINEL ADMIN ---
    elif menu == "🛡️ Painel Admin":
        st.title("🛡️ Gestão de Trocas")
        df_t = load_data("trocas")
        if df_t is not None and not df_t.empty:
            df_t.columns = [str(c).strip().lower() for c in df_t.columns]
            pendentes = df_t[df_t['status'].str.lower() == "pendente"]
            if not pendentes.empty:
                for idx, row in pendentes.iterrows():
                    with st.expander(f"Pedido de {row['id_requerente']} para {row['data']}"):
                        col1, col2 = st.columns(2)
                        if col1.button("✅ Aprovar", key=f"apr_{idx}"):
                            df_t.at[idx, 'status'] = "Aceite"
                            conn.update(worksheet="trocas", data=df_t)
                            st.rerun()
                        if col2.button("❌ Recusar", key=f"rec_{idx}"):
                            df_t.at[idx, 'status'] = "Recusado"
                            conn.update(worksheet="trocas", data=df_t)
                            st.rerun()
            else: st.info("Sem pedidos pendentes.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# 6. CONTROLO DE EXECUÇÃO
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app()
