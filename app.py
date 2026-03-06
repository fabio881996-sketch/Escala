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
        # Limpeza de colunas e dados
        df.columns = [c.strip().lower() for c in df.columns]
        df['id'] = df['id'].astype(str).str.strip()
        df['serviço'] = df['serviço'].astype(str).str.strip()
        df['horário'] = df['horário'].fillna("---").astype(str).str.strip()
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
                    st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
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
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()
            
            def mostrar_bloco(titulo, lista_servicos, ordenar_hora=False, busca_exata=False):
                if busca_exata:
                    # Procura o termo exato (ex: evita que 'Atendimento' apanhe 'Apoio ao Atendimento')
                    temp_df = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])].copy()
                else:
                    # Procura se a palavra está contida (útil para Folgas/Férias)
                    padrao = '|'.join(lista_servicos).lower()
                    temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                
                if not temp_df.empty:
                    st.subheader(f"🔹 {titulo}")
                    agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    agrupado = agrupado[['id', 'serviço', 'horário']]
                    if ordenar_hora:
                        agrupado = agrupado.sort_values(by='horário')
                    st.dataframe(agrupado, use_container_width=True, hide_index=True)

            # --- ORGANIZAÇÃO DOS BLOCOS ---
            
            # Atendimento (Busca exata para não misturar com o Apoio)
            mostrar_bloco("Atendimento", ["Atendimento"], ordenar_hora=True, busca_exata=True)
            
            # Apoio ao Atendimento (Bloco exclusivo)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio ao Atendimento"], ordenar_hora=True, busca_exata=True)
            
            # Operacional
            mostrar_bloco("Patrulha Ocorrências", ["Patrulha Ocorrências", "PO"], ordenar_hora=True)
            mostrar_bloco("Patrulha", ["Patrulha"], ordenar_hora=True, busca_exata=True)
            mostrar_bloco("Ronda", ["Ronda"], ordenar_hora=True)
            mostrar_bloco("Serviços Remunerados", ["Remunerado"], ordenar_hora=True)
            
            # Administrativo e Ausências
            mostrar_bloco("Administrativo e Apoio", ["Secretaria", "Pronto", "Inquérito", "Diligência", "Tribunal"])
            mostrar_bloco("Folgas", ["Folga"])
            mostrar_bloco("Férias e Licenças", ["Férias", "Licença"])
            mostrar_bloco("Saúde", ["Doente"])
            
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível.")

    elif menu == "🔄 Solicitar Troca":
        # ... (Código de trocas permanece o mesmo para garantir consistência)
        st.title("🔄 Troca de Serviço")
        data_t = st.date_input("Data do serviço", format="DD/MM/YYYY")
        nome_aba_t = data_t.strftime("%d-%m")
        df_dia_t = load_sheet(nome_aba_t)

        if df_dia_t is not None:
            indisponivel = ["folga", "férias", "licença", "doente", "diligência", "tribunal", "inquérito", "secretaria", "pronto"]
            meu_df = df_dia_t[df_dia_t['id'] == st.session_state['user_id']]
            
            if not meu_df.empty:
                meu_servico_str = meu_df.iloc[0]['serviço'].lower()
                is_indisponivel = any(x in meu_servico_str for x in indisponivel)
                
                if not is_indisponivel:
                    meu_s, meu_h = meu_df.iloc[0]['serviço'], meu_df.iloc[0]['horário']
                    df_colegas = df_dia_t[
                        (df_dia_t['id'] != st.session_state['user_id']) & 
                        (~df_dia_t['serviço'].str.lower().str.contains('|'.join(indisponivel), na=False))
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
                    st.error(f"Estás de '{meu_df.iloc[0]['serviço']}'. Troca não permitida.")
            else:
                st.error("Não constas na escala deste dia.")

    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if not st.session_state["logged_in"]: login()
else: main_app()
    
