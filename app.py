[20:51, 06/03/2026] Fábio Ferreira: import streamlit as st
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
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso à Escala</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.f…
[20:55, 06/03/2026] Fábio Ferreira: import streamlit as st
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
        # Garantir que o ID é sempre string para a concatenação
        df['id'] = df['id'].astype(str)
        return df
    except:
        return None

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso à Escala</h1>", unsafe_allow_html=True)
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
            # Destaque individual (procura o ID antes de agrupar)
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.success(f"📌 *O TEU SERVIÇO:* {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()
            
            # --- FUNÇÃO DE EXIBIÇÃO POR BLOCO COM AGRUPAMENTO ---
            def mostrar_bloco(titulo, lista_servicos, ordenar_hora=False):
                # Filtra os serviços
                temp_df = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])].copy()
                
                if not temp_df.empty:
                    st.subheader(f"🔹 {titulo}")
                    
                    # AGRUPAMENTO: Junta IDs com o mesmo serviço e horário
                    # Exemplo: ID 101, 102 | Patrulha | 08:00-16:00
                    agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    
                    # Reorganizar colunas para ID aparecer primeiro
                    agrupado = agrupado[['id', 'serviço', 'horário']]
                    
                    if ordenar_hora:
                        agrupado = agrupado.sort_values(by='horário')
                    
                    st.dataframe(agrupado, use_container_width=True, hide_index=True)

            # --- ORGANIZAÇÃO DA ESCALA ---
            mostrar_bloco("Atendimento", ["Atendimento"], ordenar_hora=True)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio ao Atendimento"], ordenar_hora=True)
            mostrar_bloco("Patrulha Ocorrências", ["Patrulha Ocorrências", "PO"], ordenar_hora=True)
            mostrar_bloco("Patrulha", ["Patrulha"], ordenar_hora=True)
            mostrar_bloco("Ronda", ["Ronda"], ordenar_hora=True)
            mostrar_bloco("Serviços Remunerados", ["Remunerado"], ordenar_hora=True)
            mostrar_bloco("Administrativo e Apoio", ["Secretaria", "Pronto", "Inquéritos", "Diligência", "Tribunal"])
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
            indisponivel = ["folga semanal", "folga complementar", "férias", "outras licenças", "doentes", "diligência", "tribunal", "inquéritos", "secretaria", "pronto"]
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            
            if not meu_df.empty and meu_df.iloc[0]['serviço'].lower() not in indisponivel:
                meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                
                df_colegas = df_dia_t[
                    (df_dia_t['id'] != st.session_state['user_id']) & 
                    (~df_dia_t['serviço'].str.lower().isin(indisponivel))
                ].copy()

                if not df_colegas.empty:
                    df_colegas['display'] = df_colegas['id'] + " - " + df_colegas['serviço'] + " (" + df_colegas['horário'] + ")"
                    with st.form("form_troca"):
                        selecao = st.selectbox("Trocar com:", df_colegas['display'].tolist())
                        motivo = st.text_area("Motivo da troca:")
                        if st.form_submit_button("Gerar Mensagem"):
                            id_c = selecao.split(" - ")[0]
                            c_info = df_colegas[df_colegas['id'] == id_c].iloc[0]
                            msg = f"SOLICITAÇÃO DE TROCA ({nome_aba_t}):\nSair: ID {st.session_state['user_id']} ({meu_s})\nEntrar: ID {id_c} ({c_info['serviço']})\nMotivo: {motivo}"
                            st.code(msg)
                else:
                    st.warning("Sem colegas operacionais disponíveis.")
            else:
                st.error("Troca não permitida nesta condição.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
    
