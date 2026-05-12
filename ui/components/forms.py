"""
ui/components/forms.py
======================
Formulários reutilizáveis para o Portal GNR.

Funções:
    - ``render_troca_form()`` — formulário de pedido de troca de serviço.
    - ``render_remunerado_form()`` — formulário de cedência / pedido de remunerado.
    - ``render_escala_editor()`` — editor inline da escala diária.
    - ``render_validacao_form()`` — formulário de validação de pedido (aceitar/rejeitar).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# ======================================================================
# Formulário de troca de serviço
# ======================================================================

def render_troca_form(
    data_troca: date,
    meu_servico: str,
    opcoes_militares: List[str],
    *,
    key_prefix: str = "troca",
    on_submit: Callable[[Dict[str, Any]], None] | None = None,
) -> Optional[Dict[str, Any]]:
    """Renderiza formulário de pedido de troca de serviço.

    Args:
        data_troca: Data da troca.
        meu_servico: Serviço actual do militar (ex: "Patrulha (08-16)").
        opcoes_militares: Lista de opções no formato "ID Nome - Serviço (Horário)".
        key_prefix: Prefixo para keys Streamlit.
        on_submit: Callback opcional chamado com os dados ao submeter.

    Returns:
        Dicionário com os dados do pedido, ou None se não submetido.

    Exemplo::

        resultado = render_troca_form(
            date(2026, 5, 15),
            "Patrulha Ocorrências (08-16)",
            ["101 Cabo Silva - Atendimento (08-16)", "202 Cabo Santos - Folga ()"],
        )
        if resultado:
            salvar_troca(resultado)
    """
    if not opcoes_militares:
        st.warning("Não há militares disponíveis para troca neste dia.")
        return None

    # Header do formulário
    st.markdown(
        f"<div style='"
        f"background:linear-gradient(135deg, #1A2B4A 0%, #243B5C 100%);"
        f"color:white;padding:12px 16px;border-radius:10px 10px 0 0;"
        f"font-weight:700;font-size:0.95rem;"
        f"'>🔄 Pedido de Troca de Serviço</div>",
        unsafe_allow_html=True,
    )

    # Info do serviço actual
    st.markdown(
        f"<div style='"
        f"background:#EFF6FF;border:1px solid #DBEAFE;border-radius:0;"
        f"padding:10px 14px;font-size:0.85rem;color:#1E3A8A;"
        f"border-left:none;border-right:none;"
        f"'>📋 O teu serviço: <b>{meu_servico}</b> — {data_troca.strftime('%d/%m/%Y')}</div>",
        unsafe_allow_html=True,
    )

    # Selectbox de militar alvo
    alvo = st.selectbox(
        "👤 Trocar com:",
        opcoes_militares,
        key=f"{key_prefix}_sel_alvo",
    )

    # Verificar se inclui remunerado
    incluir_rem = False
    if alvo and "💶[" in alvo:
        rem_hor = alvo.split("💶[")[1].rstrip("]")
        incluir_rem = st.checkbox(
            f"⚠️ Este militar tem remunerado ({rem_hor}). Incluir transferência?",
            key=f"{key_prefix}_chk_incluir_rem",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Botão de envio
    resultado = None
    if st.button("📨 ENVIAR PEDIDO", use_container_width=True, key=f"{key_prefix}_btn_enviar"):
        if alvo:
            id_destino = alvo.split(" ")[0]
            # Limpar indicação de remunerado
            serv_destino_raw = alvo.split(" - ", 1)[1] if " - " in alvo else alvo
            serv_destino = serv_destino_raw.split(" 💶[")[0] if " 💶[" in serv_destino_raw else serv_destino_raw

            resultado = {
                "data": data_troca.strftime("%d/%m/%Y"),
                "id_destino": id_destino,
                "servico_destino": serv_destino,
                "servico_origem": meu_servico,
                "incluir_remunerado": incluir_rem,
                "observacoes": "INCLUIR_REMUNERADO" if incluir_rem else "",
            }

            if on_submit:
                on_submit(resultado)

    return resultado


# ======================================================================
# Formulário de cedência de remunerado
# ======================================================================

def render_remunerado_form(
    data: date,
    remunerado_info: str,
    opcoes_militares: List[str],
    *,
    tipo: str = "dar",
    key_prefix: str = "rem",
    on_submit: Callable[[Dict[str, Any]], None] | None = None,
) -> Optional[Dict[str, Any]]:
    """Renderiza formulário de cedência ou pedido de remunerado.

    Args:
        data: Data do remunerado.
        remunerado_info: Info do remunerado (ex: "Remunerado GNR (18-22)").
        opcoes_militares: Lista de militares disponíveis.
        tipo: "dar" para ceder, "fazer" para pedir.
        key_prefix: Prefixo para keys Streamlit.
        on_submit: Callback ao submeter.

    Returns:
        Dicionário com dados, ou None.
    """
    if not opcoes_militares:
        st.warning("Não há militares disponíveis.")
        return None

    titulo = "💶 Ceder Remunerado" if tipo == "dar" else "💶 Fazer Remunerado"
    st.info(f"📋 {remunerado_info}")

    instrucao = (
        "Seleciona o militar a quem queres ceder o remunerado."
        if tipo == "dar"
        else "Seleciona o remunerado que queres fazer."
    )
    st.info(instrucao)

    with st.form(f"{key_prefix}_form"):
        sel = st.selectbox("👤 Militar:", opcoes_militares, key=f"{key_prefix}_sel")
        btn_label = "💶 CEDER REMUNERADO" if tipo == "dar" else "💶 PEDIR REMUNERADO"

        resultado = None
        if st.form_submit_button(btn_label, use_container_width=True):
            if sel:
                id_sel = sel.split(" ")[0]
                resultado = {
                    "data": data.strftime("%d/%m/%Y"),
                    "id_militar": id_sel,
                    "remunerado": remunerado_info,
                    "tipo": tipo,
                }
                if on_submit:
                    on_submit(resultado)

    return resultado


# ======================================================================
# Editor inline de escala
# ======================================================================

def render_escala_editor(
    df_escala: pd.DataFrame,
    *,
    colunas_editaveis: List[str] | None = None,
    key: str = "escala_editor",
    altura: int = 400,
) -> pd.DataFrame:
    """Renderiza editor inline da escala usando st.data_editor.

    Args:
        df_escala: DataFrame da escala.
        colunas_editaveis: Lista de colunas que podem ser editadas.
            Se None, usa ["serviço", "horário", "observações"].
        key: Key Streamlit.
        altura: Altura do editor em pixéis.

    Returns:
        DataFrame editado.

    Exemplo::

        df_editado = render_escala_editor(df_escala)
        if not df_editado.equals(df_escala):
            guardar_alteracoes(df_editado)
    """
    if colunas_editaveis is None:
        colunas_editaveis = ["serviço", "horário", "observações"]

    if df_escala.empty:
        st.info("Sem dados de escala para editar.")
        return df_escala

    # Configurar colunas
    column_config = {}
    disabled_cols = []
    for col in df_escala.columns:
        if col not in colunas_editaveis:
            disabled_cols.append(col)

    df_editado = st.data_editor(
        df_escala,
        key=key,
        height=altura,
        use_container_width=True,
        disabled=disabled_cols,
        num_rows="dynamic",
    )

    return df_editado


# ======================================================================
# Formulário de validação de pedido
# ======================================================================

def render_validacao_form(
    pedido_info: Dict[str, str],
    *,
    key_prefix: str = "validacao",
    on_aprovar: Callable[[], None] | None = None,
    on_rejeitar: Callable[[], None] | None = None,
) -> Optional[str]:
    """Renderiza formulário de validação (aprovar/rejeitar) de um pedido.

    Args:
        pedido_info: Dicionário com informações do pedido:
            - ``tipo`` (str): tipo de pedido
            - ``militar_origem`` (str): quem pediu
            - ``militar_destino`` (str): com quem
            - ``servico`` (str): serviço envolvido
            - ``data`` (str): data
            - ``status`` (str): estado actual
        key_prefix: Prefixo para keys Streamlit.
        on_aprovar: Callback se aprovado.
        on_rejeitar: Callback se rejeitado.

    Returns:
        "aprovado", "rejeitado", ou None.
    """
    # Detalhes do pedido
    st.markdown(
        f"<div style='"
        f"background:#EFF6FF;border:1px solid #DBEAFE;"
        f"border-radius:8px;padding:12px 16px;"
        f"font-size:0.85rem;color:#1E3A8A;"
        f"margin-bottom:12px;"
        f"'>"
        f"<div><b>📅 Data:</b> {pedido_info.get('data', 'N/A')}</div>"
        f"<div><b>👤 Origem:</b> {pedido_info.get('militar_origem', 'N/A')}</div>"
        f"<div><b>👤 Destino:</b> {pedido_info.get('militar_destino', 'N/A')}</div>"
        f"<div><b>📋 Serviço:</b> {pedido_info.get('servico', 'N/A')}</div>"
        f"<div><b>🏷️ Estado:</b> {pedido_info.get('status', 'N/A')}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Botões
    col1, col2 = st.columns(2)

    resultado = None
    with col1:
        if st.button(
            "✅ Aprovar",
            key=f"{key_prefix}_btn_aprovar",
            use_container_width=True,
        ):
            resultado = "aprovado"
            if on_aprovar:
                on_aprovar()

    with col2:
        if st.button(
            "❌ Rejeitar",
            key=f"{key_prefix}_btn_rejeitar",
            use_container_width=True,
        ):
            resultado = "rejeitado"
            if on_rejeitar:
                on_rejeitar()

    return resultado
