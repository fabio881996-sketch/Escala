"""
ui/components/filters.py
========================
Barra de filtros e pesquisa reutilizável para o Portal GNR.

Funções:
    - ``render_filtros()`` — barra de filtros com data, militar, serviço, tipo.
    - ``filtrar_secao()`` — filtra DataFrame por padrão de tipo de serviço.
    - ``render_search_box()`` — caixa de pesquisa com botão.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# ======================================================================
# Filtro por tipo de serviço (lógica extraída do original)
# ======================================================================

def filtrar_secao(
    keys: List[str],
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Filtra linhas de um DataFrame pela coluna 'serviço' usando padrão regex.

    Args:
        keys: Lista de termos de pesquisa (ex: ["férias", "licença", "convalescença"]).
        df: DataFrame com coluna 'serviço'.

    Returns:
        Tupla ``(df_filtrado, df_restante)``.

    Exemplo::

        df_aus, df_rest = filtrar_secao(["férias", "licença"], df_escala)
    """
    pattern = "|".join(k for k in keys if k).lower()
    if not pattern:
        return pd.DataFrame(), df
    mask = df["serviço"].str.lower().str.contains(pattern, na=False)
    return df[mask].copy(), df[~mask].copy()


def limpar_sem_militar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas onde ID ou serviço está vazio.

    Args:
        df: DataFrame com colunas 'id' e opcionalmente 'serviço'.

    Returns:
        DataFrame filtrado.
    """
    if df.empty:
        return df
    mask = (
        df["id"].astype(str).str.strip().str.len() > 0
        if "id" in df.columns
        else pd.Series([True] * len(df))
    )
    if "serviço" in df.columns:
        mask = mask & (df["serviço"].astype(str).str.strip().str.len() > 0)
    return df[mask].copy()


# ======================================================================
# Barra de filtros UI
# ======================================================================

def render_filtros(
    *,
    show_data: bool = True,
    show_militar: bool = True,
    show_servico: bool = True,
    show_tipo: bool = True,
    militares: List[str] | None = None,
    servicos: List[str] | None = None,
    tipos: List[str] | None = None,
    key_prefix: str = "filtro",
    data_min: date | None = None,
    data_max: date | None = None,
) -> Dict[str, Any]:
    """Renderiza barra de filtros e devolve dicionário com valores selecionados.

    Args:
        show_data: Mostrar filtro de data.
        show_militar: Mostrar filtro de militar.
        show_servico: Mostrar filtro de serviço.
        show_tipo: Mostrar filtro de tipo.
        militares: Lista de opções de militares.
        servicos: Lista de opções de serviços.
        tipos: Lista de tipos de serviço.
        key_prefix: Prefixo para as keys do Streamlit.
        data_min: Data mínima permitida.
        data_max: Data máxima permitida.

    Returns:
        Dicionário com os filtros selecionados::

            {
                "data": date | None,
                "militar": str | None,
                "servico": str | None,
                "tipo": str | None,
            }

    Exemplo::

        filtros = render_filtros(
            militares=["101 Cabo Silva", "202 Cabo Santos"],
            servicos=["Patrulha", "Atendimento", "Folga"],
        )
        if filtros["data"]:
            df = carregar_escala(filtros["data"])
    """
    filtros: Dict[str, Any] = {
        "data": None,
        "militar": None,
        "servico": None,
        "tipo": None,
    }

    if tipos is None:
        tipos = [
            "Todos",
            "Patrulha",
            "Atendimento",
            "Remunerado",
            "Folga",
            "Ausência",
            "Tribunal",
            "ADM",
        ]

    # Layout em colunas
    cols = st.columns([2, 2, 2, 2, 1])

    with cols[0]:
        if show_data:
            filtros["data"] = st.date_input(
                "📅 Data",
                value=datetime.now().date(),
                min_value=data_min,
                max_value=data_max,
                key=f"{key_prefix}_data",
            )

    with cols[1]:
        if show_militar and militares:
            opcoes_mil = ["Todos"] + militares
            sel = st.selectbox(
                "👤 Militar",
                opcoes_mil,
                key=f"{key_prefix}_militar",
            )
            filtros["militar"] = sel if sel != "Todos" else None

    with cols[2]:
        if show_servico and servicos:
            opcoes_serv = ["Todos"] + servicos
            sel = st.selectbox(
                "📋 Serviço",
                opcoes_serv,
                key=f"{key_prefix}_servico",
            )
            filtros["servico"] = sel if sel != "Todos" else None

    with cols[3]:
        if show_tipo:
            sel = st.selectbox(
                "🏷️ Tipo",
                tipos,
                key=f"{key_prefix}_tipo",
            )
            filtros["tipo"] = sel if sel != "Todos" else None

    with cols[4]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Limpar", key=f"{key_prefix}_reset", use_container_width=True):
            filtros = {"data": None, "militar": None, "servico": None, "tipo": None}

    return filtros


# ======================================================================
# Caixa de pesquisa
# ======================================================================

def render_search_box(
    label: str = "🔍 Pesquisar",
    placeholder: str = "Escreve para pesquisar...",
    key: str = "search_box",
) -> str:
    """Renderiza caixa de pesquisa com text input.

    Args:
        label: Label do campo.
        placeholder: Placeholder do campo.
        key: Key Streamlit.

    Returns:
        Texto introduzido pelo utilizador.
    """
    return st.text_input(
        label,
        placeholder=placeholder,
        key=key,
    )


# ======================================================================
# Aplicar filtros a DataFrame
# ======================================================================

def aplicar_filtros(
    df: pd.DataFrame,
    filtros: Dict[str, Any],
    *,
    coluna_id: str = "id",
    coluna_servico: str = "serviço",
) -> pd.DataFrame:
    """Aplica filtros a um DataFrame de escala.

    Args:
        df: DataFrame de escala.
        filtros: Dicionário de filtros (resultado de ``render_filtros()``).
        coluna_id: Nome da coluna de ID do militar.
        coluna_servico: Nome da coluna de serviço.

    Returns:
        DataFrame filtrado.
    """
    if df.empty:
        return df

    resultado = df.copy()

    # Filtro por militar
    if filtros.get("militar"):
        mil_id = filtros["militar"].split(" ")[0]  # Extrai ID do formato "ID Nome"
        resultado = resultado[resultado[coluna_id].astype(str).str.strip() == mil_id]

    # Filtro por serviço
    if filtros.get("servico"):
        resultado = resultado[
            resultado[coluna_servico].str.lower().str.contains(
                filtros["servico"].lower(), na=False
            )
        ]

    # Filtro por tipo
    tipo_patterns = {
        "Patrulha": r"po|patrulha|ronda|vtr|giro",
        "Atendimento": r"atendimento",
        "Remunerado": r"remu|grat",
        "Folga": r"folga",
        "Ausência": r"ferias|licen|doente|convalesc|baixa",
        "Tribunal": r"tribunal|dilig",
        "ADM": r"pronto|secretaria|inquer|comando",
    }
    if filtros.get("tipo") and filtros["tipo"] in tipo_patterns:
        pattern = tipo_patterns[filtros["tipo"]]
        resultado = resultado[
            resultado[coluna_servico].str.lower().str.contains(pattern, na=False)
        ]

    return resultado
