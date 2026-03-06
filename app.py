import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="GNR - Gestão de Escalas", layout="wide", page_icon="🚓")

# --- CONEXÃO ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro nos Secrets.")
    st.stop()

if "logado" not in st.session_state:
    st.session_state["logado"] = False

# --- LOGIN ---
if not st.session_state["logado"]:
    st.title("🚓 Portal de Escalas GNR")
    with st.form("login_form"):
        u_email = st.text_input("Email").strip().lower()
        u_pass = st.text_input("Password", type="password")
        if st.form_submit_button("Entrar"):
            try:
                # Lemos a primeira aba (utilizadores)
                df_u = conn.read(ttl=0)
                df_u.columns = [str(c).strip().lower() for c in df_u.columns]
                user = df_u[(df_u['email'].astype(str).str.lower() == u_email) & 
                            (df_u['password'].astype(str) == u_pass)]
                if not user.empty:
                    st.session_state["logado"] = True
                    st.session_state["user_nome"] = user.iloc[0]['nome']
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
            except Exception as e:
                st.error("Erro de conexão. Verifique os Secrets.")

# --- ÁREA LOGADA ---
else:
    st.sidebar.title(f"Militar: {st.session_state['user_nome']}")
    if st.sidebar.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()

    tab1, tab2 = st.tabs(["📅 Escala Diária", "🔄 Troca de Serviço"])

    with tab1:
        st.subheader("Consultar Escala")
        data_sel = st.date_input("Data:", value=datetime.now())
        nome_aba_alvo = data_sel.strftime("escala_%d_%m")

        if st.button("🔄 Carregar/Atualizar Escala"):
            st.cache_data.clear()
            try:
                # MÉTODO NOVO: Em vez de pedir a aba ao Google, 
                # pedimos a folha e especificamos a aba aqui.
                df_escala = conn.read(worksheet=nome_aba_alvo, ttl=0)
                
                if df_escala is not None and not df_escala.empty:
                    st.success(f"Escala {nome_aba_alvo} carregada.")
                    st.dataframe(df_escala, use_container_width=True, hide_index=True)
                else:
                    st.warning("A aba existe mas não tem dados.")
            except Exception as e:
                st.error(f"Não foi possível ler a aba '{nome_aba_alvo}'")
                st.info("Tente o seguinte: Vá à Google Sheet e mude o nome da aba para algo simples como 'TESTE' e tente carregar.")
                with st.expander("Detalhes Técnicos do Erro"):
                    st.code(str(e))

    with tab2:
        st.subheader("Pedir Troca")
        with st.form("troca"):
            d_servico = st.date_input("Dia do Serviço")
            m_com_quem = st.text_input("Trocar com (Posto/Nome)")
            razon = st.text_area("Motivo")
            if st.form_submit_button("Submeter"):
                try:
                    # Tenta ler a aba de pedidos, se falhar cria estrutura
                    try:
                        df_p = conn.read(worksheet="pedidos_troca", ttl=0)
                    except:
                        df_p = pd.DataFrame(columns=["data_pedido", "militar", "troca_com", "dia", "motivo", "estado"])

                    novo = pd.DataFrame([{
                        "data_pedido": datetime.now().strftime("%d/%m/%Y"),
                        "militar": st.session_state["user_nome"],
                        "troca_com": m_com_quem,
                        "dia": d_servico.strftime("%d/%m/%Y"),
                        "motivo": razon,
                        "estado": "PENDENTE"
                    }])
                    
                    df_final = pd.concat([df_p, novo], ignore_index=True)
                    conn.update(worksheet="pedidos_troca", data=df_final)
                    st.success("Pedido enviado!")
                except Exception as e:
                    st.error("Erro ao gravar. Verifique se a aba 'pedidos_troca' existe.")
                    
