"""
ui/components/calendar.py
=========================
Vista de calendário mensal para o Portal GNR.

Renderiza lista de day-cards compactos, com cores por tipo de serviço,
destaque de hoje, feriados e fins-de-semana.

Funções:
    - ``get_calendar_day_style()`` — determina cores e ícone para um dia.
    - ``render_calendar_day()`` — renderiza card de um dia com serviço.
    - ``render_calendar_day_empty()`` — renderiza dia sem serviço.
    - ``render_calendar_view()`` — renderiza calendário mensal completo.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import streamlit as st

from core.utils import norm
from ui.components.styles import (
    COR_AMBER_BG,
    COR_AMBER_ESCURO,
    COR_AMBER_TEXT,
    COR_AZUL_CLARO,
    COR_AZUL_FORTE,
    COR_CINZA_APP,
    COR_CINZA_BORDA,
    COR_CINZA_CARD,
    COR_CINZA_CLARO,
    COR_CINZA_ESCURO,
    COR_CINZA_MEDIO,
    COR_ROXO,
    COR_ROXO_BG,
    COR_VERDE_BG,
    COR_VERDE_ESCURO,
    COR_VERMELHO,
    COR_VERMELHO_BG,
)


# ======================================================================
# Nomes em português
# ======================================================================

NOMES_MES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

NOMES_DIA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ======================================================================
# Estilos por contexto de dia
# ======================================================================

def get_border_style(
    is_hoje: bool,
    is_feriado: bool,
    is_fds: bool,
) -> str:
    """Devolve CSS de borda esquerda conforme o contexto do dia.

    Args:
        is_hoje: Se é o dia de hoje.
        is_feriado: Se é feriado.
        is_fds: Se é fim-de-semana (Sábado/Domingo).

    Returns:
        String CSS para ``border-left``.
    """
    if is_hoje:
        return f"4px solid {COR_AZUL_FORTE}"
    if is_feriado:
        return f"3px solid {COR_VERMELHO}"
    if is_fds:
        return f"3px solid {COR_AMBER_TEXT}"
    return f"3px solid {COR_CINZA_APP}"


def get_text_colors(
    is_feriado: bool,
    is_fds: bool,
) -> Tuple[str, str]:
    """Devolve cores de texto (número do dia, nome do dia da semana).

    Args:
        is_feriado: Se é feriado.
        is_fds: Se é fim-de-semana.

    Returns:
        Tupla ``(cor_numero, cor_nome_dia)``.
    """
    if is_feriado:
        return COR_VERMELHO, COR_VERMELHO
    if is_fds:
        return COR_AMBER_TEXT, COR_AMBER_TEXT
    return COR_CINZA_ESCURO, COR_CINZA_CLARO


def get_service_color(
    servico: str,
    *,
    is_troca: bool = False,
    is_fds: bool = False,
) -> Tuple[str, str, str]:
    """Devolve (background, cor_texto, ícone) para um tipo de serviço.

    Args:
        servico: Nome do serviço.
        is_troca: Se é resultado de troca aprovada.
        is_fds: Se é fim-de-semana (ajusta bg para serviço normal).

    Returns:
        Tupla ``(bg_color, text_color, icone)``.
    """
    if is_troca:
        return COR_AMBER_BG, COR_AMBER_ESCURO, "🔄"

    s_n = norm(servico)

    if any(x in s_n for x in ["ferias", "licen", "doente"]):
        return COR_CINZA_CARD, COR_CINZA_CLARO, "🏖️"
    if "folga" in s_n:
        return COR_ROXO_BG, COR_ROXO, "😴"
    if any(x in s_n for x in ["tribunal", "dilig"]):
        return COR_VERMELHO_BG, COR_VERMELHO, "⚖️"
    if any(x in s_n for x in ["remu", "grat"]):
        return COR_VERDE_BG, COR_VERDE_ESCURO, "💰"

    bg = COR_AMBER_BG if is_fds else COR_AZUL_CLARO
    return bg, COR_AZUL_FORTE, "🛡️"


# ======================================================================
# Badge de HOJE
# ======================================================================

def _hoje_badge(is_hoje: bool) -> str:
    """Devolve HTML do badge 'HOJE' se aplicável."""
    if not is_hoje:
        return ""
    return (
        f" <span style='background:{COR_AZUL_FORTE};color:white;"
        f"font-size:0.65rem;padding:1px 6px;border-radius:10px'>HOJE</span>"
    )


# ======================================================================
# Renderização de dia individual
# ======================================================================

def render_calendar_day(
    dia: int,
    dia_semana: str,
    servico: str,
    horario: str,
    *,
    bg: str,
    cor_txt: str,
    icone: str,
    borda_esq: str,
    cor_num: str,
    cor_dia: str,
    is_hoje: bool = False,
    is_fds: bool = False,
    remunerados: List[str] | None = None,
) -> None:
    """Renderiza card de um dia do calendário com serviço.

    Args:
        dia: Número do dia.
        dia_semana: Abreviatura do dia da semana (Seg, Ter, ...).
        servico: Nome do serviço.
        horario: Horário do serviço.
        bg: Cor de fundo.
        cor_txt: Cor do texto do serviço.
        icone: Ícone do serviço.
        borda_esq: CSS da borda esquerda.
        cor_num: Cor do número do dia.
        cor_dia: Cor do nome do dia da semana.
        is_hoje: Se é hoje.
        is_fds: Se é fim-de-semana.
        remunerados: Lista de strings de remunerados (ex: "💰 Rem GNR (18-22)").
    """
    hoje_badge = _hoje_badge(is_hoje)
    fw_dia = "700" if is_fds else "400"

    rem_html = ""
    if remunerados:
        rem_html = "".join(
            f"<div style='font-size:0.75rem;color:{COR_VERDE_ESCURO};margin-top:2px'>{r}</div>"
            for r in remunerados
        )

    st.markdown(
        f"<div style='background:{bg};border-left:{borda_esq};"
        f"border-radius:8px;padding:8px 12px;margin-bottom:6px;"
        f"display:flex;align-items:center;gap:12px'>"
        f"<div style='min-width:48px;text-align:center'>"
        f"<div style='font-size:1.2rem;font-weight:800;color:{cor_num};line-height:1'>{dia}</div>"
        f"<div style='font-size:0.7rem;color:{cor_dia};font-weight:{fw_dia}'>{dia_semana}</div>"
        f"</div>"
        f"<div>"
        f"<div style='font-size:0.9rem;font-weight:700;color:{cor_txt}'>{icone} {servico}{hoje_badge}</div>"
        f"<div style='font-size:0.8rem;color:#475569'>🕒 {horario}</div>"
        f"{rem_html}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_calendar_day_empty(
    dia: int,
    dia_semana: str,
    *,
    borda_esq: str,
    is_hoje: bool = False,
) -> None:
    """Renderiza card de dia sem serviço escalado (só aparece se for hoje).

    Args:
        dia: Número do dia.
        dia_semana: Abreviatura.
        borda_esq: CSS da borda esquerda.
        is_hoje: Se é hoje.
    """
    hoje_badge = _hoje_badge(is_hoje)

    st.markdown(
        f"<div style='background:{COR_CINZA_CARD};border-left:{borda_esq};"
        f"border-radius:8px;padding:8px 12px;margin-bottom:6px;"
        f"display:flex;align-items:center;gap:12px'>"
        f"<div style='min-width:48px;text-align:center'>"
        f"<div style='font-size:1.2rem;font-weight:800;color:{COR_CINZA_BORDA};line-height:1'>{dia}</div>"
        f"<div style='font-size:0.7rem;color:{COR_CINZA_BORDA}'>{dia_semana}</div>"
        f"</div>"
        f"<div style='color:{COR_CINZA_BORDA};font-size:0.85rem'>"
        f"Sem serviço escalado{hoje_badge}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# Vista de calendário mensal completa
# ======================================================================

def render_calendar_view(
    ano: int,
    mes: int,
    servicos_mes: Dict[int, Dict[str, Any]],
    feriados: Set[date] | None = None,
) -> bool:
    """Renderiza vista de calendário mensal como lista de day-cards.

    Args:
        ano: Ano.
        mes: Mês (1-12).
        servicos_mes: Dicionário dia → {serviço, horário, troca, obs, remunerados}.
            Cada entrada deve ter as chaves:
            - ``serviço`` (str): nome do serviço
            - ``horário`` (str): horário
            - ``troca`` (bool): se é resultado de troca
            - ``obs`` (str): observações
            - ``remunerados`` (list[str]): lista de remunerados formatados
        feriados: Conjunto de datas de feriados.

    Returns:
        True se algum dia tem serviço, False caso contrário.

    Exemplo::

        servicos = {
            1: {"serviço": "Patrulha", "horário": "08-16", "troca": False, "obs": "", "remunerados": []},
            5: {"serviço": "Folga", "horário": "", "troca": False, "obs": "", "remunerados": []},
        }
        render_calendar_view(2026, 5, servicos, feriados={date(2026, 5, 1)})
    """
    if feriados is None:
        feriados = set()

    hoje_d = datetime.now().date()
    n_dias = calendar.monthrange(ano, mes)[1]

    st.markdown(f"### {NOMES_MES[mes]} {ano}")

    tem_servicos = False

    for d in range(1, n_dias + 1):
        dt_cel = date(ano, mes, d)
        is_hoje = dt_cel == hoje_d
        weekday = dt_cel.weekday()
        dia_sem = NOMES_DIA[weekday]
        is_fds = weekday >= 5
        is_feriado = dt_cel in feriados

        borda_esq = get_border_style(is_hoje, is_feriado, is_fds)
        cor_num, cor_dia = get_text_colors(is_feriado, is_fds)

        if d in servicos_mes:
            tem_servicos = True
            info = servicos_mes[d]
            bg, cor_txt, icone = get_service_color(
                info["serviço"],
                is_troca=info.get("troca", False),
                is_fds=is_fds,
            )

            render_calendar_day(
                dia=d,
                dia_semana=dia_sem,
                servico=info["serviço"],
                horario=info["horário"],
                bg=bg,
                cor_txt=cor_txt,
                icone=icone,
                borda_esq=borda_esq,
                cor_num=cor_num,
                cor_dia=cor_dia,
                is_hoje=is_hoje,
                is_fds=is_fds,
                remunerados=info.get("remunerados", []),
            )
        elif is_hoje:
            render_calendar_day_empty(
                dia=d,
                dia_semana=dia_sem,
                borda_esq=borda_esq,
                is_hoje=True,
            )

    if not tem_servicos:
        st.info("Não foram encontrados serviços escalados neste mês.")

    return tem_servicos
