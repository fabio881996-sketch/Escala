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
    st.error("Erro na configuração dos Secrets. Verifique o TOML.")
    st.stop()

# --- ESTADO DA SESSÃO ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
if "user_nome" not in st.session_state:
    st.session_state["user_nome"] = ""

# --- FUNÇÃO DE LOGIN ---
def login():
    st.title("🔑 Acesso ao Sistema GNR")
    
    # Sidebar para ferramentas de emergência
    if st.sidebar.button("Limpar Cache/Erros"):
        st.cache_data.clear()
        st.rerun()

    with st.form("login_form"):
        u_email = st.text_input("Email do Militar").strip().lower()
        u_pass = st.text_input("Palavra-passe", type="password")
        
        if st.form_submit_button("Entrar"):
            try:
                # Lemos a PRIMEIRA aba (sem especificar nome para evitar Erro 400)
                df_u = conn.read(ttl=0) 
                
                # Normalizar colunas
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                
                # Verificar credenciais
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == u_pass)]
                
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["user_nome"] = user.iloc[0]['nome']
                    st.success(f"Bem-vindo, {st.session_state['user_nome']}!")
                    st.rerun()
                else:
                    st.error("Email ou Palavra-passe incorretos.")
            except Exception as e:
                st.error("🚨 Erro ao aceder à base de dados de utilizadores.")
                st.info("Garanta que a aba de utilizadores é a PRIMEIRA da esquerda na sua Google Sheet.")
                st.expander("Erro Técnico").code(e)

# --- ÁREA LOGADA ---
def main_app():
    st.sidebar.title(f"🚓 Olá, {st.session_state['user_nome']}")
    
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["logado"] = False
        st.rerun()

    # Organização por Separadores
    tab1, tab2 = st.tabs(["📅 Consulta de Escala", "🔄 Pedido de Troca"])

    # --- SEPARADOR 1: ESCALAS ---
    with tab1:
        st.subheader("Visualizar Escala de Serviço")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            data_sel = st.date_input("Selecione o dia:", value=datetime.now())
            # Formato do nome da aba sugerido: escala_06_03
            nome_aba = data_sel.strftime("escala_%d_%m")
        
        if st.button(f"Carregar Escala ({nome_aba})"):
            try:
                # Tenta ler a aba específica do dia
                df_escala = conn.read(worksheet=nome_aba, ttl=0)
                if df_escala is not None:
                    st.success(f"Escala de {data_sel.strftime('%d/%m/%Y')} carregada.")
                    st.dataframe(df_escala, use_container_width=True, hide_index=True)
            except:
                st.warning(f"Não encontrei a aba '{nome_aba}' na sua Google Sheet.")
                st.info("Dica: Certifique-se de que a aba tem exatamente este nome e não tem células mescladas.")

    # --- SEPARADOR 2: TROCAS ---
    with tab2:
        st.subheader("Solicitar Troca de Turno")
        st.write("Utilize o formulário abaixo para registar um pedido oficial de troca.")
        
        with st.form("form_troca", clear_on_submit=True):
            data_servico = st.date_input("Dia do seu serviço original")
            militar_com_quem = st.text_input("Militar com quem pretende trocar")
            motivo = st.text_area("Motivo da solicitação")
            
            if st.form_submit_button("Submeter Pedido"):
                try:
                    # 1. Preparar os dados do novo pedido
                    novo_registo = pd.DataFrame([{
                        "data_pedido": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "quem_pede": st.session_state["user_nome"],
                        "com_quem": militar_com_quem,
                        "dia_servico": data_servico.strftime("%d/%m/%Y"),
                        "motivo": motivo,
                        "estado": "PENDENTE"
                    }])

                    # 2. Ler pedidos existentes para não apagar nada
                    # Requer que a aba 'pedidos_troca' já exista na Sheet
                    df_antigo = conn.read(worksheet="pedidos_troca", ttl=0)
                    
                    # 3. Concatenar (juntar)
                    df_final = pd.concat([df_antigo, novo_registo], ignore_index=True)
                    
                    # 4. Atualizar a Google Sheet
                    conn.update(worksheet="pedidos_troca", data=df_final)
                    
                    st.success("✅ Pedido enviado com sucesso! Aguarde validação superior.")
                    st.balloons()
                except Exception as e:
                    st.error("Erro ao gravar pedido na aba 'pedidos_troca'.")
                    st.code(e)

# --- EXECUÇÃO ---
if not st.session_state["logado"]:
    login()
else:
    main_app()
    
