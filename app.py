import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema de Escalas GNR", page_icon="🚓", layout="wide")

def load_sheet(aba_nome):
    try:
        # Puxa o URL dos secrets
        url = st.secrets["gsheet_url"]
        base_url = url.split('/edit')[0]
        # Formata o URL para exportar como CSV a aba específica
        csv_url = f"{base_url}/gviz/tq?tqx=out:csv&sheet={aba_nome}"
        df = pd.read_csv(csv_url)
        
        # Limpeza de colunas e dados
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Garantir que colunas essenciais são strings para comparação
        if 'id' in df.columns:
            df['id'] = df['id'].astype(str).str.strip()
        if 'serviço' in df.columns:
            df['serviço'] = df['serviço'].astype(str).str.strip()
        if 'horário' in df.columns:
            df['horário'] = df['horário'].fillna("---").astype(str).str.strip()
            
        return df
    except Exception as e:
        # Se der erro, mostramos apenas se estivermos a tentar debugar
        # st.error(f"Erro ao ler aba {aba_nome}: {e}")
        return None

def login():
    st.markdown("<h1 style='text-align: center;'>🔑 Acesso à Escala</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        email_i = st.text_input("Email").strip().lower()
        pass_i = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            df_u = load_sheet("utilizadores")
            if df_u is not None:
                # Verificamos se as colunas existem antes de filtrar
                if 'email' in df_u.columns and 'password' in df_u.columns:
                    user = df_u[(df_u['email'].str.lower() == email_i) & (df_u['password'].astype(str) == str(pass_i))]
                    if not user.empty:
                        st.session_state["logged_in"] = True
                        st.session_state["user_id"] = str(user.iloc[0]['id']).strip()
                        st.session_state["user_name"] = user.iloc[0]['nome']
                        st.rerun()
                    else:
                        st.error("Credenciais incorretas.")
                else:
                    st.error("A aba 'utilizadores' não tem as colunas email/password corretamente preenchidas.")
            else:
                st.error("Não foi possível aceder à Google Sheet. Verifique o link nos Secrets.")

def main_app():
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.info(f"ID: {st.session_state['user_id']}")
    
    # Botão de Sair no topo da sidebar para ser fácil
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logged_in"] = False
        st.rerun()
        
    menu = st.sidebar.radio("Navegação", ["📅 Escala Diária", "🔄 Solicitar Troca"])

    if menu == "📅 Escala Diária":
        st.title("📅 Escala de Serviço Diária")
        data_sel = st.date_input("Consultar dia:", format="DD/MM/YYYY")
        nome_aba = data_sel.strftime("%d-%m") # Formato 06-03
        
        df_dia = load_sheet(nome_aba)

        if df_dia is not None:
            # Filtra o serviço do próprio utilizador logado
            meu_df = df_dia[df_dia['id'] == st.session_state['user_id']]
            if not meu_df.empty:
                st.success(f"📌 **O TEU SERVIÇO:** {meu_df.iloc[0]['serviço']} | {meu_df.iloc[0]['horário']}")

            st.divider()
            
            def mostrar_bloco(titulo, lista_servicos, ordenar_hora=False, busca_exata=False):
                if busca_exata:
                    temp_df = df_dia[df_dia['serviço'].str.lower().isin([s.lower() for s in lista_servicos])].copy()
                else:
                    padrao = '|'.join(lista_servicos).lower()
                    temp_df = df_dia[df_dia['serviço'].str.lower().str.contains(padrao, na=False)].copy()
                
                if not temp_df.empty:
                    st.subheader(f"🔹 {titulo}")
                    # Agrupa militares pelo mesmo serviço e horário
                    agrupado = temp_df.groupby(['serviço', 'horário'])['id'].apply(lambda x: ', '.join(x)).reset_index()
                    agrupado = agrupado[['id', 'serviço', 'horário']]
                    if ordenar_hora:
                        agrupado = agrupado.sort_values(by='horário')
                    st.dataframe(agrupado, use_container_width=True, hide_index=True)

            # --- BLOCOS ORGANIZADOS ---
            mostrar_bloco("Atendimento", ["Atendimento"], ordenar_hora=True, busca_exata=True)
            mostrar_bloco("Apoio ao Atendimento", ["Apoio Atendimento", "Apoio ao Atendimento"], ordenar_hora=True, busca_exata=True)
            mostrar_bloco("Patrulha Ocorrências", ["Patrulha Ocorrências", "PO"], ordenar_hora=True, busca_exata=True)
            mostrar_bloco("Patrulha", ["Patrulha"], ordenar_hora=True, busca_exata=True)
            mostrar_bloco("Ronda", ["Ronda"], ordenar_hora=True)
            mostrar_bloco("Serviços Remunerados", ["Remunerado"], ordenar_hora=True)
            mostrar_bloco("Administrativo e Apoio", ["Secretaria", "Pronto", "Inquérito"])
            mostrar_bloco("Tribunal", ["Tribunal"])
            mostrar_bloco("Folgas", ["Folga"])
            mostrar_bloco("Férias e Licenças", ["Férias", "Licença"])
            mostrar_bloco("Saúde", ["Doente"])
            mostrar_bloco("Diligência", ["Diligência"])
        else:
            st.info(f"ℹ️ Escala de {nome_aba} não disponível ou aba não encontrada.")

    elif menu == "🔄 Solicitar Troca":
        # (O teu código de trocas original aqui...)
        st.title("🔄 Troca de Serviço")
        # ... (continua igual ao teu)
        st.info("Funcionalidade de geração de mensagem ativa.")

# Inicialização do estado
if "logged_in" not in st.session_state: 
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]: 
    login()
else: 
    main_app()
    
