import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO
st.set_page_config(page_title="GNR - Sistema de Escalas", layout="wide")

# 2. CONEXÃO
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(aba_nome):
    try:
        # ttl=0 para garantir dados frescos
        df = conn.read(worksheet=aba_nome, ttl=0)
        if df is not None:
            # Normalizar cabeçalhos (remover espaços e acentos)
            df.columns = [str(c).strip().lower()
                          .replace('ç', 'c').replace('í', 'i').replace('ó', 'o') 
                          .replace('é', 'e').replace('ã', 'a').replace('ê', 'e')
                          for c in df.columns]
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
                else: st.error("Email ou Password incorretos.")
            else: st.error("Erro: Aba 'utilizadores' não encontrada.")

# 4. APP PRINCIPAL
def main_app():
    st.sidebar.write(f"👤 {st.session_state['user_name']}")
    menu = st.sidebar.radio("Menu", ["📅 Escala", "🔄 Trocas", "🛡️ Admin"])

    if menu == "📅 Escala":
        st.title("📅 Escala Diária")
        data_sel = st.date_input("Selecione o dia", value=datetime.now())
        
        # LISTA DE POSSÍVEIS NOMES PARA A ABA
        # O código vai tentar todos estes até um funcionar
        tentativas = [
            data_sel.strftime("%d-%m"),       # 06-03
            data_sel.strftime("%-d-%-m"),     # 6-3
            data_sel.strftime("%d/%m"),       # 06/03
            f"{data_sel.day}-{data_sel.month}",# 6-3 (manual)
            "0" + data_sel.strftime("%d-%m") if data_sel.day < 10 else data_sel.strftime("%d-%m")
        ]
        
        df_dia = None
        aba_encontrada = ""
        
        for nome in tentativas:
            df_dia = load_data(nome)
            if df_dia is not None:
                aba_encontrada = nome
                break

        if df_dia is not None:
            st.success(f"✅ Escala carregada (Aba: {aba_encontrada})")
            
            # Mapear colunas para ID, Serviço e Horário
            mapa = {}
            for col in df_dia.columns:
                if 'id' in col: mapa[col] = 'ID'
                elif 'serv' in col: mapa[col] = 'Serviço'
                elif 'hor' in col: mapa[col] = 'Horário'
            
            df_final = df_dia.rename(columns=mapa)
            
            # Destacar o serviço do próprio utilizador
            meu_id = st.session_state['user_id']
            meu_serv = df_final[df_final['ID'].astype(str).str.contains(meu_id, na=False)]
            
            if not meu_serv.empty:
                st.info(f"🚩 **O TEU SERVIÇO:** {meu_serv.iloc[0]['Serviço']} | {meu_serv.iloc[0]['Horário']}")

            st.divider()
            
            # Mostrar por blocos organizados
            def bloco(titulo, palavras):
                padrao = '|'.join(palavras).lower()
                temp = df_final[df_final['Serviço'].str.lower().str.contains(padrao, na=False)]
                if not temp.empty:
                    st.subheader(f"🔹 {titulo}")
                    st.dataframe(temp[['ID', 'Serviço', 'Horário']], use_container_width=True, hide_index=True)

            bloco("Atendimento e Apoio", ["atendimento"])
            bloco("Patrulhas e Ocorrências", ["patrulha", "po", "ocorrência"])
            bloco("Outros Serviços", ["ronda", "secretaria", "remunerado"])
            bloco("Ausências", ["folga", "férias", "licença", "doente"])
            
        else:
            st.error(f"❌ Não foi possível encontrar a aba para o dia {data_sel.strftime('%d-%m')}")
            st.info("💡 Dica: No Google Sheets, clique na aba com o botão direito, selecione 'Mudar nome' e coloque um apóstrofo antes: **'06-03**. Isso força o Google a tratar como texto.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

# 5. CONTROLO
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
