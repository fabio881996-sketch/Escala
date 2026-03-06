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
        
        data_t = st.date_input("Data do serviço a trocar", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            # 1. Identificar o MEU serviço automaticamente
            meu_df = df_dia_t[df_dia_t['id'].astype(str) == st.session_state['user_id']]
            
            if meu_df.empty:
                st.warning("Não tens serviço atribuído neste dia, portanto não podes solicitar troca.")
            else:
                meu_s = meu_df.iloc[0]['serviço']
                meu_h = meu_df.iloc[0]['horário']
                
                st.info(f"*O teu serviço atual:* {meu_s} ({meu_h})")

                # 2. Filtrar colegas disponíveis (Excluir folgas/férias/etc)
                excluir = ["folga", "férias", "ferias", "pronto", "inquéritos", "inqueritos", "secretaria"]
                df_colegas = df_dia_t[
                    (df_dia_t['id'].astype(str) != st.session_state['user_id']) & 
                    (~df_dia_t['serviço'].str.lower().isin(excluir))
                ].copy()

                if not df_colegas.empty:
                    # Criar uma coluna legível para o menu de seleção
                    df_colegas['info_selecao'] = df_colegas['id'].astype(str) + " - " + df_colegas['serviço'] + " (" + df_colegas['horário'] + ")"
                    
                    with st.form("form_troca_detalhado"):
                        selecao = st.selectbox("Trocar com (ID - Serviço - Horário):", df_colegas['info_selecao'].tolist())
                        
                        # Extrair dados do colega selecionado
                        colega_id = selecao.split(" - ")[0]
                        colega_info = df_colegas[df_colegas['id'].astype(str) == colega_id].iloc[0]
                        
                        motivo = st.text_area("Motivo da Troca")
                        
                        if st.form_submit_button("Gerar Pedido de Troca"):
                            msg = (
                                f"🚨 SOLICITAÇÃO DE TROCA DE SERVIÇO\n"
                                f"📅 DATA: {nome_aba_t}\n\n"
                                f"👤 REQUERENTE (ID {st.session_state['user_id']}):\n"
                                f"Saída: {meu_s} ({meu_h})\n\n"
                                f"👤 SUBSTITUTO (ID {colega_id}):\n"
                                f"Entrada: {colega_info['serviço']} ({colega_info['horário']})\n\n"
                                f"📝 MOTIVO: {motivo}"
                            )
                            st.warning("Copia o pedido abaixo:")
                            st.code(msg)
                else:
                    st.warning("Não existem colegas no terreno disponíveis para troca nesta data.")
        else:
            st.error(f"A escala para {nome_aba_t} ainda não foi publicada.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
