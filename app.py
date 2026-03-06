import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Sistema de Escalas GNR", layout="wide", page_icon="🚓")

# --- CONEXÃO COM GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na configuração dos Secrets.")
    st.stop()

# --- ESTADO DA SESSÃO ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "user_nome" not in st.session_state:
    st.session_state["user_nome"] = ""

# --- ÁREA DE LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Acesso ao Sistema GNR")
    
    with st.form("login_form"):
        u_email = st.text_input("Email do Militar").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # Lemos a PRIMEIRA aba (utilizadores)
                df_u = conn.read(ttl=0) 
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == u_pass)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["user_nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Email ou Palavra-passe incorretos.")
            except Exception as e:
                st.error("Erro ao aceder à base de dados.")
                st.code(e)

# --- ÁREA PRINCIPAL (LOGADA) ---
else:
    st.sidebar.title(f"🚓 Olá, {st.session_state['user_nome']}")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logado"] = False
        st.rerun()

    tab1, tab2 = st.tabs(["📅 Consulta de Escala", "🔄 Pedido de Troca"])

    with tab1:
        st.subheader("Visualizar Escala de Serviço")
        
        # Seleção de Data
        data_sel = st.date_input("Selecione o dia:", value=datetime.now())
        nome_aba = data_sel.strftime("escala_%d_%m")
        
        st.info(f"A procurar na aba: **{nome_aba}**")

        # Botão para carregar dados
        if st.button(f"Carregar Escala"):
            # Limpamos o cache apenas para esta operação para forçar leitura nova
            st.cache_data.clear() 
            
            try:
                # Tenta ler a aba específica
                df_escala = conn.read(worksheet=nome_aba, ttl=0)
                
                if df_escala is not None and not df_escala.empty:
                    st.success(f"Escala de {data_sel.strftime('%d/%m/%Y')} carregada!")
                    st.dataframe(df_escala, use_container_width=True, hide_index=True)
                else:
                    st.warning("A aba existe, mas parece estar vazia.")
            except Exception as e:
                st.error(f"Não foi possível carregar a aba '{nome_aba}'.")
                st.markdown("""
                **Verificações rápidas na Google Sheet:**
                1. O nome da aba é exatamente `escala_06_03`? (Sem espaços extras)
                2. Existem **células mescladas** (unidas)? Se sim, desfaça-as.
                3. A folha tem filtros ativos? Desative-os.
                """)
                with st.expander("Detalhes do Erro"):
                    st.code(e)

    with tab2:
        st.subheader("Solicitar Troca de Turno")
        with st.form("form_troca", clear_on_submit=True):
            data_servico = st.date_input("Dia do seu serviço original")
            militar_com_quem = st.text_input("Militar com quem pretende trocar")
            motivo = st.text_area("Motivo da solicitação")
            
            if st.form_submit_button("Submeter Pedido"):
                try:
                    novo_registo = pd.DataFrame([{
                        "data_pedido": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "quem_pede": st.session_state["user_nome"],
                        "com_quem": militar_com_quem,
                        "dia_servico": data_servico.strftime("%d/%m/%Y"),
                        "motivo": motivo,
                        "estado": "PENDENTE"
                    }])

                    # Lê a aba de pedidos
                    df_antigo = conn.read(worksheet="pedidos_troca", ttl=0)
                    df_final = pd.concat([df_antigo, novo_registo], ignore_index=True)
                    
                    # Atualiza a Sheet
                    conn.update(worksheet="pedidos_troca", data=df_final)
                    st.success("✅ Pedido enviado com sucesso!")
                    st.balloons()
                except Exception as e:
                    st.error("Erro ao gravar pedido na aba 'pedidos_troca'.")
                    st.code(e)
                    
