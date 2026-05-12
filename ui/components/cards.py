"""
ui/components/cards.py
======================
Componentes reutilizáveis para renderizar cards de serviço no Portal GNR.

Funções:
    - ``get_service_style()`` — determina classe CSS, ícone e cores com base no tipo de serviço.
    - ``render_servico_card()`` — renderiza card de serviço individual.
    - ``render_troca_card()`` — renderiza card de troca aprovada.
    - ``render_remunerado_card()`` — renderiza card de remunerado.
    - ``render_ausencia_card()`` — renderiza card de ausência (férias, etc.).
    - ``format_colegas_html()`` — formata lista de colegas para exibição no card.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from core.utils import norm


# ======================================================================
# Mapeamento de tipos de serviço → estilo
# ======================================================================

# Tipo: (card_class, ícone)
SERVICE_STYLES: Dict[str, Tuple[str, str]] = {
    "ausencia": ("card-ausencia", "🏖️"),
    "folga": ("card-folga", "😴"),
    "tribunal": ("card-tribunal", "⚖️"),
    "remunerado": ("card-rem", "💰"),
    "troca": ("card-troca", "🔄"),
    "normal": ("card-meu", "🛡️"),
}


def get_service_style(servico: str, *, is_troca: bool = False) -> Tuple[str, str]:
    """Determina classe CSS e ícone com base no tipo de serviço.

    Args:
        servico: Nome do serviço (será normalizado internamente).
        is_troca: Se True, força estilo de troca.

    Returns:
        Tupla ``(card_class, icone)``.

    Exemplo::

        card_class, icone = get_service_style("Patrulha Ocorrências")
        # -> ('card-meu', '🛡️')
    """
    if is_troca:
        return SERVICE_STYLES["troca"]

    s_norm = norm(servico)

    if any(x in s_norm for x in ["ferias", "licen", "doente", "baixa", "convalesc"]):
        return SERVICE_STYLES["ausencia"]
    if "folga" in s_norm:
        return SERVICE_STYLES["folga"]
    if any(x in s_norm for x in ["tribunal", "dilig"]):
        return SERVICE_STYLES["tribunal"]
    if any(x in s_norm for x in ["remu", "grat"]):
        return SERVICE_STYLES["remunerado"]

    return SERVICE_STYLES["normal"]


# ======================================================================
# Formatação de colegas
# ======================================================================

def format_colegas_html(
    ids: List[str],
    df_util: pd.DataFrame,
    *,
    style: str = "font-size:0.78rem;color:#475569",
) -> str:
    """Formata lista de IDs de colegas em HTML.

    Args:
        ids: Lista de IDs de militares.
        df_util: DataFrame de utilizadores (colunas: id, nome, posto).
        style: CSS inline para o parágrafo.

    Returns:
        String HTML (vazia se ``ids`` estiver vazio).
    """
    if not ids:
        return ""

    partes: List[str] = []
    for c_id in sorted(ids):
        c_id = str(c_id).strip()
        c_row = pd.DataFrame()
        if not df_util.empty and "id" in df_util.columns:
            c_row = df_util[df_util["id"].astype(str).str.strip() == c_id]
        if not c_row.empty:
            c_posto = c_row.iloc[0].get("posto", "")
            c_nome_completo = c_row.iloc[0].get("nome", "")
            c_nomes = c_nome_completo.strip().split()
            c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else c_nome_completo
            partes.append(f"{c_id} {c_posto} {c_nome_curto}")
        else:
            partes.append(c_id)

    return f'<p style="{style}">👥 {" | ".join(partes)}</p>'


# ======================================================================
# Card de serviço genérico
# ======================================================================

def render_servico_card(
    label: str,
    servico: str,
    horario: str,
    *,
    card_class: str | None = None,
    icone: str | None = None,
    colegas_html: str = "",
    obs: str = "",
    extra_html: str = "",
) -> None:
    """Renderiza card de serviço individual.

    Args:
        label: Texto do label (ex: "🟢 HOJE", "🔵 AMANHÃ", "15/05 (QUI)").
        servico: Nome do serviço.
        horario: Horário (ex: "08-16").
        card_class: Classe CSS do card (se None, determina automaticamente).
        icone: Ícone do serviço (se None, determina automaticamente).
        colegas_html: HTML pré-formatado dos colegas.
        obs: Observações (texto simples).
        extra_html: HTML adicional a inserir no final do card.
    """
    if card_class is None or icone is None:
        _cc, _ic = get_service_style(servico)
        card_class = card_class or _cc
        icone = icone or _ic

    obs_html = f"<p>📝 {obs}</p>" if obs else ""

    st.markdown(
        f'<div class="card-servico {card_class}">'
        f"<p><b>{label}</b></p>"
        f"<h3>{icone} {servico}</h3>"
        f"<p>🕒 {horario}</p>"
        f"{colegas_html}"
        f"{obs_html}"
        f"{extra_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# Card de troca aprovada
# ======================================================================

def render_troca_card(
    label: str,
    servico_novo: str,
    horario_novo: str,
    nome_parceiro: str,
    *,
    colegas_html: str = "",
    obs: str = "",
) -> None:
    """Renderiza card de troca de serviço aprovada.

    Args:
        label: Label do dia (ex: "🟢 HOJE").
        servico_novo: Nome do novo serviço (após troca).
        horario_novo: Novo horário.
        nome_parceiro: Nome do militar com quem se fez a troca.
        colegas_html: HTML dos colegas no novo serviço.
        obs: Observações.
    """
    obs_html = f"<p>📝 {obs}</p>" if obs else ""

    st.markdown(
        f'<div class="card-servico card-troca">'
        f'<p><b>{label}</b> &nbsp;·&nbsp; '
        f'<span style="color:#92400E;">Troca Aprovada</span></p>'
        f"<h3>🔄 {servico_novo}</h3>"
        f"<p>🕒 {horario_novo}</p>"
        f"{colegas_html}"
        f'<p style="font-size:0.78rem;color:#92400E">🔄 c/ {nome_parceiro}</p>'
        f"{obs_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# Card de remunerado
# ======================================================================

def render_remunerado_card(
    label: str,
    servico: str,
    horario: str,
    *,
    colegas_html: str = "",
    matar_html: str = "",
    obs: str = "",
) -> None:
    """Renderiza card de serviço remunerado.

    Args:
        label: Label do dia.
        servico: Nome do serviço remunerado.
        horario: Horário.
        colegas_html: HTML dos colegas.
        matar_html: HTML de info sobre cessão de remunerado.
        obs: Observações.
    """
    obs_html = f"<p>📝 {obs}</p>" if obs else ""

    st.markdown(
        f'<div class="card-servico card-rem">'
        f'<p><b>{label}</b> &nbsp;·&nbsp; '
        f'<span style="color:#059669;">💶 Remunerado</span></p>'
        f"<h3>💰 {servico}</h3>"
        f"<p>🕒 {horario}</p>"
        f"{colegas_html}"
        f"{matar_html}"
        f"{obs_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# Card de ausência
# ======================================================================

def render_ausencia_card(
    label: str,
    tipo: str = "Férias",
    *,
    icone: str = "🏖️",
) -> None:
    """Renderiza card de ausência (férias, licença, etc.).

    Args:
        label: Label do dia.
        tipo: Tipo de ausência.
        icone: Ícone a exibir.
    """
    st.markdown(
        f'<div class="card-servico card-ausencia">'
        f"<p><b>{label}</b></p>"
        f"<h3>{icone} {tipo}</h3>"
        f"</div>",
        unsafe_allow_html=True,
    )
