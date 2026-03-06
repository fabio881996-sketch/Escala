import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema de Escalas GNR", page_icon="🚓", layout="wide")

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

    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m")
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            # 1. O MEU SERVIÇO (Destaque)
            meu_df = df_dia[df_dia['id'].astype(str) == st.session_state['user_id']]
            if not meu_df.empty:
                st.success(f"📌 *O TEU SERVIÇO:* {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()
            
            # --- FUNÇÃO PARA MOSTRAR BLOCOS ---
            def mostrar_bloco(titulo, lista_servicos, ordenar_hora=False):
                # Filtra os serviços que pertencem a este bloco (case-insensitive)
                temp_df = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])]
                if not temp_df.empty:
                    st.subheader(f"🔹 {titulo}")
                    if ordenar_hora:
                        temp_df = temp_df.sort_values(by='horário')
                    st.dataframe(temp_df[['id', 'serviço', 'horário']], use_container_width=True, hide_index=True)

            # --- ORGANIZAÇÃO POR CATEGORIAS ---
            
            # BLOCO 1: Operacional / Atendimento (Ordenado por Horário)
            mostrar_bloco("Atendimento", ["Atendimento"], ordenar_hora=True)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio ao Atendimento"], ordenar_hora=True)
            mostrar_bloco("PO / Patrulha / Ronda", ["PO", "Patrulha", "Ronda"], ordenar_hora=True)
            mostrar_bloco("Remunerado", ["Remunerado"], ordenar_hora=True)
            
            # BLOCO 2: Administrativo e Outros
            mostrar_bloco("Administrativo e Apoio", ["Secretaria", "Pronto", "Inquéritos", "Diligência", "Tribunal"])
            
            # BLOCO 3: Ausências e Licenças
            mostrar_bloco("Folgas", ["Folga Semanal", "Folga Complementar"])
            mostrar_bloco("Férias e Licenças", ["Férias", "Outras Licenças"])
            mostrar_bloco("Saúde", ["Doentes"])

        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🔄 Solicitar Troca":
        st.title("🔄 Troca de Serviço")
        data_t = st.date_input("Data do serviço", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            # Filtro de quem NÃO pode trocar (indisponíveis)
            indisponivel = ["folga semanal", "folga complementar", "férias", "outras licenças", "doentes", "diligência", "tribunal", "inquéritos", "secretaria", "pronto"]
            
            meu_df = df_dia_t[df_dia_t['id'].astype(str) == st.session_state['user_id']]
            
            if not meu_df.empty and meu_df.iloc[0]['serviço'].lower() not in indisponivel:
                meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                
                # Colegas disponíveis (apenas Atendimento, Patrulha, PO, Remunerado)
                df_colegas = df_dia_t[
                    (df_dia_t['id'].astype(str) != st.session_state['user_id']) & 
                    (~df_dia_t['serviço'].str.lower().isin(indisponivel))
                ].copy()

                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'].astype(str) + " - " + df_colegas['serviço'] + " (" + df_colegas['horário'] + ")"
                    with st.form("form_troca"):
                        selecao = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_area("Motivo:")
                        if st.form_submit_button("Gerar Pedido"):
                            id_c = selecao.split(" - ")[0]
                            c_info = df_colegas[df_colegas['id'].astype(str) == id_c].iloc[0]
                            msg = f"PEDIDO DE TROCA ({nome_aba_t}):\nSair: ID {st.session_state['user_id']} ({meu_s})\nEntrar: ID {id_c} ({c_info['serviço']})\nMotivo: {motivo}"
                            st.code(msg)
                else:
                    st.warning("Sem colegas operacionais disponíveis para troca.")
            else:
                st.error("Não podes solicitar trocas nesta condição ou data.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
