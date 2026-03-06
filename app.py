import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema GNR - Escalas", layout="wide")

# Inicializar conexão
conn = st.connection("gsheets", type=GSheetsConnection)

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- TELA DE LOGIN ---
if not st.session_state["logado"]:
    st.title("🔑 Login GNR")
    with st.form("login"):
        email = st.text_input("Email").strip().lower()
        senha = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                df_u = conn.read(ttl=0) # Lê a primeira aba (utilizadores)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                user = df_u[(df_u['email'].astype(str).str.lower() == email) & 
                            (df_u['password'].astype(str) == senha)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais incorretas.")
            except Exception as e:
                st.error("Erro ao carregar utilizadores.")
                st.code(e)

# --- TELA PRINCIPAL (PÓS-LOGIN) ---
else:
    st.sidebar.success(f"Utilizador: {st.session_state['nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    tab1, tab2 = st.tabs(["📅 Ver Escala", "🔄 Pedir Troca"])

    # ABA 1: VISUALIZAR ESCALA
    with tab1:
        st.subheader("Consulta de Escala")
        data_sel = st.date_input("Selecione o dia", value=pd.to_datetime("2026-03-06"))
        nome_aba = data_sel.strftime("%d-%m")

        if st.button(f"Carregar Dia {nome_aba}"):
            try:
                df_escala = conn.read(worksheet=nome_aba, ttl=0)
                st.dataframe(df_escala, use_container_width=True, hide_index=True)
            except:
                st.warning(f"Aba '{nome_aba}' não encontrada.")

    # ABA 2: FORMULÁRIO DE TROCA
    with tab2:
        st.subheader("Solicitar Troca de Serviço")
        st.info("Preencha os dados abaixo para submeter o pedido de troca para validação.")
        
        with st.form("form_troca", clear_on_submit=True):
            data_troca = st.date_input("Dia do Serviço a trocar")
            militar_destino = st.text_input("Com quem deseja trocar? (Nome do militar)")
            motivo = st.text_area("Motivo da troca")
            
            if st.form_submit_button("Submeter Pedido"):
                # Criar o novo registo
                novo_pedido = pd.DataFrame([{
                    "data_pedido": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "quem_pede": st.session_state["nome"],
                    "com_quem": militar_destino,
                    "dia_servico": data_troca.strftime("%d/%m/%Y"),
                    "motivo": motivo,
                    "estado": "Pendente"
                }])

                try:
                    # Ler dados existentes
                    existentes = conn.read(worksheet="pedidos_troca", ttl=0)
                    # Juntar o novo pedido aos antigos
                    updated_df = pd.concat([existentes, novo_pedido], ignore_index=True)
                    # Gravar de volta na Google Sheet
                    conn.update(worksheet="pedidos_troca", data=updated_df)
                    
                    st.success("✅ Pedido de troca submetido com sucesso!")
                    st.balloons()
                except Exception as e:
                    st.error("Erro ao gravar o pedido. Verifique se a aba 'pedidos_troca' existe.")
                    st.code(e)
                    
