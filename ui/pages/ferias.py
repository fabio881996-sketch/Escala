"""
Página «Férias» – Plano de Férias.

Permite visualizar períodos de férias por militar, com cálculo de
dias úteis e dias corridos (descontando feriados/fins‑de‑semana).
Admins podem seleccionar qualquer militar; não‑admins vêem apenas os seus.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st

from services.data_loader import DataLoader


# ─────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────

MESES_PT: List[str] = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    """Devolve 'Posto Nome' a partir do ID."""
    mid = str(mid).strip()
    if df_util.empty or "id" not in df_util.columns:
        return mid
    row = df_util[df_util["id"].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _fmt_data_ext(d, meses: List[str] = MESES_PT) -> str:
    """Formata data extenso: '5 de Junho de 2026'."""
    return f"{d.day} de {meses[d.month]} de {d.year}"


def _parse_data(s: str, ano_fallback: int):
    """Tenta interpretar múltiplos formatos de data."""
    s = str(s).strip()
    for fmt in (
        "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d",
        "%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
    ):
        try:
            d = datetime.strptime(s, fmt).date()
            if fmt == "%m/%d":
                d = d.replace(year=ano_fallback)
            return d
        except Exception:
            pass
    return None


def _dias_corridos_reais(ini_d, fim_d, feriados: Set) -> int:
    """Conta dias corridos reais, estendendo o fim se seguido de fds/feriado."""
    fim_ext = fim_d
    while True:
        proximo = fim_ext + timedelta(days=1)
        if proximo.weekday() >= 5 or proximo in feriados:
            fim_ext = proximo
        else:
            break
    return (fim_ext - ini_d).days + 1


def _render_periodos(
    row_f: pd.Series,
    ini_cols: List[str],
    fim_cols: List[str],
    feriados: Set,
    ano_sel: int,
) -> List[Tuple]:
    """
    Extrai períodos de férias de uma linha.

    Returns
    -------
    list of (ini_date, fim_date, dias_uteis, dias_corridos)
    """
    periodos: List[Tuple] = []
    for ini_c, fim_c in zip(ini_cols, fim_cols):
        ini_v = str(row_f.get(ini_c, "")).strip()
        fim_v = str(row_f.get(fim_c, "")).strip()
        if not ini_v or ini_v == "nan":
            continue
        ini_d = _parse_data(ini_v, ano_sel)
        fim_d = _parse_data(fim_v, ano_sel)
        if not ini_d or not fim_d:
            continue
        du = sum(
            1
            for n in range((fim_d - ini_d).days + 1)
            if (ini_d + timedelta(days=n)).weekday() < 5
            and (ini_d + timedelta(days=n)) not in feriados
        )
        dc = _dias_corridos_reais(ini_d, fim_d, feriados)
        periodos.append((ini_d, fim_d, du, dc))
    return periodos


# ─────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────

def render_ferias(
    usuario: "Usuario",
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    is_admin: bool = False,
) -> None:
    """Renderiza a página de férias."""
    st.title("🏖️ Plano de Férias")

    ano_atual = datetime.now().year
    ano_sel = st.selectbox("Ano:", [ano_atual, ano_atual + 1], index=0)

    df_f = data_loader.carregar_ferias(ano_sel)
    feriados = data_loader.carregar_feriados(ano_sel)

    if df_f.empty:
        st.info(f"Não há plano de férias para {ano_sel}.")
        return

    # ── Detectar colunas ──
    cols_f = df_f.columns.tolist()
    id_col_f = "id" if "id" in cols_f else cols_f[0]
    ini_cols = [c for c in cols_f if "ini" in c.lower()]
    fim_cols = [c for c in cols_f if "fim" in c.lower()]
    total_col = next((c for c in cols_f if "total" in c.lower()), None)

    u_id = str(usuario.id)

    # ── Selecção de militar (admins) ──
    if is_admin:
        militares_opts: Dict[str, str] = {
            f"{r['posto']} {r['nome']} (ID: {r['id']})": str(r["id"])
            for _, r in df_util.iterrows()
        }
        sel_mil = st.selectbox(
            "Selecionar militar:",
            ["-- O meu próprio --"] + list(militares_opts.keys()),
        )
        alvo_id = u_id if sel_mil == "-- O meu próprio --" else militares_opts[sel_mil]
    else:
        alvo_id = u_id

    # ── Filtrar militar ──
    mil_f = df_f[df_f[id_col_f].astype(str).str.strip() == alvo_id]
    if mil_f.empty:
        st.info("Não há férias planeadas para este militar.")
        return

    row_f = mil_f.iloc[0]
    nome_exibir = _get_nome_militar(df_util, alvo_id)
    periodos = _render_periodos(row_f, ini_cols, fim_cols, feriados, ano_sel)
    total_du = sum(p[2] for p in periodos)

    # ── Resumo no topo ──
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border-radius:12px;'
        f'padding:16px 20px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">'
        f'<div><div style="font-size:0.8rem;color:#065F46;font-weight:600">PLANO DE FÉRIAS {ano_sel}</div>'
        f'<div style="font-size:1.1rem;font-weight:800;color:#064E3B">{nome_exibir}</div></div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:1.8rem;font-weight:900;color:#059669">{total_du}</div>'
        f'<div style="font-size:0.75rem;color:#065F46">dias úteis</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Cards de períodos ──
    for i, (ini_d, fim_d, du, dc) in enumerate(periodos, 1):
        st.markdown(
            f'<div style="background:#F0FDF4;border-left:4px solid #16A34A;border-radius:10px;'
            f'padding:14px 18px;margin-bottom:10px">'
            f'<div style="font-size:0.72rem;color:#16A34A;font-weight:700;letter-spacing:0.08em;margin-bottom:6px">PERÍODO {i}</div>'
            f'<div style="font-size:1rem;font-weight:700;color:#14532D">🏖️ {_fmt_data_ext(ini_d)}</div>'
            f'<div style="font-size:0.85rem;color:#166534;margin:2px 0 10px 0">até {_fmt_data_ext(fim_d)}</div>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
            f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">📅 {dc} dias corridos</span>'
            f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">💼 {du} dias úteis</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
