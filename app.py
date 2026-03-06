import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema de Escalas GNR", page_icon="🚓", layout="centered")

def load_sheet(aba_nome):
    try:
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except:
        return None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Acesso à Escala</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                if not user.empty:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = str(user.iloc[0]['id'])
                    st.session_state["user_name"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID: {st.session_state['user_id']}")
    
    menu = st.sidebar.radio("Navegação", ["📅 Escala Diária", "🔄 Solicitar Troca"])

    # --- OPÇÃO 1: ESCALA DIÁRIA ---
    if menu == "📅 Escala Diária":
        st.title("📅 Escala Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            meu_servico = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
            if not meu_servico.empty:
                st.success(f"📌 *O TEU SERVIÇO:* {meu_servico.iloc[0]['serviço']} | {meu_servico.iloc[0]['horário']}")
            
            st.subheader(f"👥 Equipa em Serviço - {nome_aba}")
            st.dataframe(df_dia[['id', 'serviço', 'horário']].sort_values(by='horário'), use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    # --- OPÇÃO 2: SOLICITAR TROCA ---
    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Troca de Serviço")
        st.write("Selecione a data para ver os colegas disponíveis para troca.")

        data_t = st.date_input("Data do serviço a trocar", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            # LISTA DE PALAVRAS A EXCLUIR (ADMINISTRATIVOS E FOLGAS)
            excluir = ["folga", "férias", "ferias", "pronto", "inquéritos", "inqueritos", "secretaria"]
            
            # Filtro: 
            # 1. Não pode ser o próprio utilizador
            # 2. O serviço não pode conter as palavras da lista 'excluir'
            df_filtrado = df_dia_t[
                (df_dia_t['id'].astype(str) != st.session_state['user_id']) & 
                (~df_dia_t['serviço'].str.lower().isin(excluir))
            ]
            
            ids_disponiveis = df_filtrado['id'].unique()

            if len(ids_disponiveis) > 0:
                with st.form("form_troca_filtrado"):
                    id_colega = st.selectbox("Trocar com o ID (apenas elementos no terreno):", ids_disponiveis)
                    servico_meu = st.text_input("Teu serviço atual (Ex: Patrulha)")
                    obs = st.text_area("Notas/Motivo")
                    
                    if st.form_submit_button("Gerar Pedido"):
                        msg = (f"SOLICITAÇÃO DE TROCA:\nData: {nome_aba_t}\nRequerente: ID {st.session_state['user_id']}\nSubstituto: ID {id_colega}\nServiço: {servico_meu}\nMotivo: {obs}")
                        st.warning("Copia e envia ao Admin/Comando:")
                        st.code(msg)
            else:
                st.warning("Não existem colegas disponíveis para troca neste dia (todos em folga, férias ou serviço interno).")
        else:
            st.error(f"Escala de {nome_aba_t} ainda não criada.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
