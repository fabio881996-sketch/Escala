import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Sistema GNR - Gestão", page_icon="🚓", layout="wide")

# 2. CONEXÃO
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets.")
    st.stop()

# 3. FUNÇÃO DE LEITURA ROBUSTA
def load_data(aba_nome):
    try:
        # ttl=0 força a leitura de dados novos sem cache
        df = conn.read(worksheet=aba_nome, ttl=0)
        if df is not None:
            # Limpa nomes de colunas (tira espaços, acentos e põe minúsculas)
            df.columns = [str(c).strip().lower()
                          .replace('ç', 'c').replace('í', 'i').replace('ó', 'o') 
                          .replace('é', 'e').replace('ã', 'a').replace('ê', 'e')
                          for c in df.columns]
            return df
        return None
    except:
        return None

# 4. LOGIN
def login():
    st.markdown("<h1 style='text-align: center;'>🚓 Acesso GNR</h1>", unsafe_allow_html=True)
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
                else: st.error("Email ou Password incorretos.")
            else: st.error("Não detetei a aba 'utilizadores'. Verifique a Sheet.")

# 5. APP PRINCIPAL
def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    
    menu = st.sidebar.radio("Navegação", ["📅 Escala Diária", "🔄 Solicitar Troca", "🛡️ Painel Admin"])

    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço")
        data_sel = st.date_input("Data:", value=datetime.now())
        nome_aba = data_sel.strftime("%d-%m") # Tenta "06-03"

        df_dia = load_data(nome_aba)

        if df_dia is not None:
            st.success(f"✅ Escala encontrada para {nome_aba}")
            
            # Mapeamento flexível das colunas para garantir visualização
            mapa = {}
            for col in df_dia.columns:
                if 'id' in col: mapa[col] = 'ID'
                elif 'serv' in col: mapa[col] = 'Serviço'
                elif 'hor' in col: mapa[col] = 'Horário'
            
            df_exibir = df_dia.rename(columns=mapa)
            
            # Mostrar o serviço do utilizador logado
            meu_id = st.session_state['user_id']
            # Procura o ID em qualquer coluna que contenha 'ID'
            meu_serv = df_exibir[df_exibir['ID'].astype(str).str.contains(meu_id, na=False)]
            
            if not meu_serv.empty:
                st.info(f"🚩 **O TEU SERVIÇO:** {meu_serv.iloc[0]['Serviço']} | {meu_serv.iloc[0]['Horário']}")
            
            st.divider()
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)
            
        else:
            st.error(f"❌ Não encontrei a aba '{nome_aba}'")
            
            # --- BLOCO DE DIAGNÓSTICO ---
            with st.expander("🔍 Clique aqui para Diagnóstico Técnico"):
                st.write("A App está a tentar ler o ficheiro, mas a aba não responde.")
                st.write("1. Verifique se a folha está PARTILHADA com o email da Service Account como EDITOR.")
                st.write("2. Verifique se não existem linhas vazias ACIMA dos cabeçalhos ID, Serviço, Horário.")
                
                if st.button("Tentar ler aba 'utilizadores' para testar conexão"):
                    teste = load_data("utilizadores")
                    if teste is not None:
                        st.write("Conexão OK! Consigo ler a aba 'utilizadores'.")
                        st.write("Abas disponíveis na folha (Cabeçalhos lidos):", teste.columns.tolist())
                    else:
                        st.write("Erro: Não consigo ler nem a aba 'utilizadores'. Verifique as permissões.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# CONTROLO
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
