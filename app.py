import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="GNR - Sistema de Gestão", layout="wide")

# 2. CONEXÃO
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(aba_nome):
    try:
        # ttl=0 garante que não usamos lixo da memória (cache)
        df = conn.read(worksheet=aba_nome, ttl=0)
        if df is not None:
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        return None
    except:
        return None

# 3. LOGIN
def login():
    st.markdown("<h1 style='text-align: center;'>🚓 Login GNR</h1>", unsafe_allow_html=True)
    with st.form("login"):
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
                    st.rerun()
                else: st.error("Credenciais incorretas.")
            else: st.error("Erro: Não consigo ler a aba 'utilizadores'. Verifique a partilha da folha.")

# 4. APP PRINCIPAL
def main_app():
    st.sidebar.write(f"👤 {st.session_state['user_name']}")
    menu = st.sidebar.radio("Navegação", ["📅 Escala Diária", "🔄 Trocas", "🛡️ Admin"])

    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço")
        data_sel = st.date_input("Escolha o dia", value=datetime.now())
        
        # O código vai tentar encontrar a aba, não importa como se chame
        dia = data_sel.strftime("%d")
        mes = data_sel.strftime("%m")
        
        # Tenta formatos: "06-03", "6-3", "06/03", "6/3"
        possibilidades = [f"{dia}-{mes}", f"{int(dia)}-{int(mes)}", f"{dia}/{mes}", f"{int(dia)}/{int(mes)}"]
        
        df_dia = None
        aba_final = ""
        
        for p in possibilidades:
            df_dia = load_data(p)
            if df_dia is not None:
                aba_final = p
                break

        if df_dia is not None:
            st.success(f"✅ Escala carregada com sucesso (Aba: {aba_final})")
            
            # Limpeza técnica de colunas
            mapa = {}
            for col in df_dia.columns:
                if 'id' in col: mapa[col] = 'ID'
                elif 'serv' in col: mapa[col] = 'Serviço'
                elif 'hor' in col: mapa[col] = 'Horário'
            df_final = df_dia.rename(columns=mapa)

            # Mostrar o serviço do utilizador logado
            meu_id = st.session_state['user_id']
            meu_serv = df_final[df_final['ID'].astype(str).str.contains(meu_id, na=False)]
            if not meu_serv.empty:
                st.info(f"🚩 **O TEU SERVIÇO:** {meu_serv.iloc[0]['Serviço']} | {meu_serv.iloc[0]['Horário']}")

            st.divider()
            
            # Organização por Blocos
            def bloco(titulo, palavras):
                padrao = '|'.join(palavras).lower()
                temp = df_final[df_final['Serviço'].str.lower().str.contains(padrao, na=False)]
                if not temp.empty:
                    st.subheader(f"🔹 {titulo}")
                    st.dataframe(temp[['ID', 'Serviço', 'Horário']], use_container_width=True, hide_index=True)

            bloco("Atendimento", ["atendimento"])
            bloco("Patrulhas e PO", ["patrulha", "po"])
            bloco("Outros", ["ronda", "secretaria", "pronto", "remunerado"])
            bloco("Ausências", ["folga", "férias", "licença", "doente"])
            
        else:
            st.error(f"❌ Não encontrei a aba para o dia {dia}-{mes}")
            st.warning("⚠️ Verificação Crítica: A primeira linha da aba '06-03' na Google Sheet TEM de ser os cabeçalhos (ID, Serviço, Horário).")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# CONTROLO
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
