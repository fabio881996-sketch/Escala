"""
Página «Definições» – Agrupa secções menores do portal.

Sub‑páginas (admin):
  - 🏥 Dispensas (geral + slot)
  - 📢 Publicar Escala
  - 🚨 Alertas
  - 🔄 Giros
  - 👥 Efetivo
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import streamlit as st

from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm, parse_horario as _parse_horario
from services.data_loader import DataLoader
from config.settings import DISPENSA_SLOTS


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _nc(s: str) -> str:
    import unicodedata
    s = str(s).strip().lower()
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or "id" not in df_util.columns:
        return mid
    row = df_util[df_util["id"].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _render_tabela_html(df: pd.DataFrame, expandivel: bool = False) -> str:
    """Renderiza um DataFrame como tabela HTML simples."""
    if df.empty:
        return "<p>Sem dados.</p>"
    AZUL = "#1E3A5F"
    AZUL_MED = "#C9DCF2"
    AZUL_CLARO = "#E8F1FB"
    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;border-bottom:2px solid {AZUL};"
    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;border-bottom:1px solid #dde6f7;"
    td_a = td_s + f"background:{AZUL_CLARO};"

    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:4px;margin-bottom:4px'>"
    html += "<table style='width:100%;border-collapse:collapse'><thead><tr>"
    for c in df.columns:
        html += f"<th style='{th_s}'>{c}</th>"
    html += "</tr></thead><tbody>"
    for i, (_, row) in enumerate(df.iterrows()):
        td = td_a if i % 2 == 0 else td_s
        html += "<tr>"
        for c in df.columns:
            val = str(row.get(c, "")).replace("nan", "").strip()
            html += f"<td style='{td}'>{val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


# ─────────────────────────────────────────
# Dispensas
# ─────────────────────────────────────────

def render_dispensas(
    usuario: "Usuario",
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    is_admin: bool = False,
) -> None:
    """Renderiza a página de dispensas (licenças gerais + slot)."""
    st.title("🏥 Dispensas")
    if not is_admin:
        st.warning("Acesso restrito a administradores.")
        st.stop()

    df_licencas = data_loader.carregar_licencas()
    if df_licencas.empty:
        st.info("Não há dispensas registadas.")
        return

    # ── Dispensas gerais ──
    st.markdown("#### 📋 Dispensas Gerais")
    cols_lic = df_licencas.columns.tolist()
    id_col = "id" if "id" in cols_lic else cols_lic[0]

    # Adicionar nome
    df_show = df_licencas.copy()
    df_show["nome"] = df_show[id_col].astype(str).str.strip().apply(lambda x: _get_nome_militar(df_util, x))
    cols_display = ["nome"] + [c for c in cols_lic if c != id_col]
    st.dataframe(df_show[cols_display], use_container_width=True, hide_index=True)

    # ── Dispensas por slot ──
    st.divider()
    st.markdown("#### 🎯 Dispensas por Slot (Serviço + Horário)")
    st.caption("Militares dispensados de serviços específicos em determinados horários.")

    # Detectar colunas de slot
    slot_tokens = list(DISPENSA_SLOTS.keys()) + [sv for sv, _ in DISPENSA_SLOTS.values()]
    slot_cols = [c for c in cols_lic if any(tok.lower() in c.lower() for tok in slot_tokens)] if DISPENSA_SLOTS else []

    if slot_cols:
        for slot_c in slot_cols:
            with st.expander(f"📌 {slot_c}"):
                df_slot = df_licencas[df_licencas[slot_c].astype(str).str.strip().str.lower().isin(["sim", "yes", "true", "1", "x"])]
                if df_slot.empty:
                    st.info("Nenhum militar com esta dispensa.")
                else:
                    for _, row in df_slot.iterrows():
                        mid = str(row.get(id_col, "")).strip()
                        st.markdown(f"- {_get_nome_militar(df_util, mid)} ({mid})")
    else:
        st.info("Não foram encontradas colunas de dispensa por slot.")


# ─────────────────────────────────────────
# Publicar Escala
# ─────────────────────────────────────────

def render_publicar_escala(
    usuario: "Usuario",
    data_loader: "DataLoader",
    is_admin: bool = False,
) -> None:
    """Renderiza a página de publicar escala."""
    st.title("📢 Publicar Escala")
    if not is_admin:
        st.warning("Acesso restrito a administradores.")
        st.stop()

    abas = data_loader.carregar_lista_abas()
    abas_dia = sorted([a for a in abas if re.match(r"^\d{2}-\d{2}$", a)])
    dias_pub = data_loader.carregar_dias_publicados()

    st.markdown(f"**{len(dias_pub)} dia(s) publicado(s)** atualmente.")

    # Seleccionar dias a publicar
    dias_disponiveis = [a for a in abas_dia if a not in dias_pub]
    if not dias_disponiveis:
        st.info("Todas as escalas disponíveis já estão publicadas.")
    else:
        sel_dias = st.multiselect("Selecionar dias a publicar:", dias_disponiveis)
        if sel_dias and st.button("📢 Publicar", use_container_width=True, type="primary"):
            try:
                sh = get_sheet()
                try:
                    ws_pub = sh.worksheet("dias_publicados")
                except Exception:
                    ws_pub = sh.add_worksheet(title="dias_publicados", rows=100, cols=1)
                    ws_pub.update("A1", [["dia"]])

                for dia in sel_dias:
                    ws_pub.append_row([dia])

                data_loader.limpar_cache()
                st.success(f"✅ {len(sel_dias)} dia(s) publicado(s)!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    # Despublicar
    if dias_pub:
        st.divider()
        st.markdown("#### 🔒 Despublicar dias")
        sel_despub = st.multiselect("Dias a despublicar:", sorted(dias_pub))
        if sel_despub and st.button("🔒 Despublicar", use_container_width=True):
            try:
                sh = get_sheet()
                ws_pub = sh.worksheet("dias_publicados")
                vals = ws_pub.get_all_values()
                linhas_apagar = []
                for i, row in enumerate(vals[1:], start=2):
                    if str(row[0]).strip() in sel_despub:
                        linhas_apagar.append(i)
                for ln in reversed(linhas_apagar):
                    ws_pub.delete_rows(ln)
                data_loader.limpar_cache()
                st.success(f"✅ {len(sel_despub)} dia(s) despublicado(s)!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")


# ─────────────────────────────────────────
# Alertas
# ─────────────────────────────────────────

def render_alertas(
    usuario: "Usuario",
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    feriados: Set,
    is_admin: bool = False,
) -> None:
    """Renderiza a página de alertas da escala."""
    st.title("🚨 Alertas da Escala")
    if not is_admin:
        st.warning("Acesso restrito a administradores.")
        st.stop()

    hoje = datetime.now()
    alertas_duplos: List[str] = []
    alertas_descanso: List[str] = []
    alertas_esquecidos: List[str] = []

    ids_ativos = set(df_util["id"].astype(str).str.strip().tolist()) if not df_util.empty else set()

    def _ids_de_ferias_no_dia(dt):
        em_ferias: set = set()
        if df_ferias.empty:
            return em_ferias
        cols = df_ferias.columns.tolist()
        ini_cols = [c for c in cols if "ini" in c.lower()]
        fim_cols = [c for c in cols if "fim" in c.lower()]
        id_col = "id" if "id" in cols else cols[0]
        data = dt.date() if hasattr(dt, "date") else dt
        for _, row in df_ferias.iterrows():
            mid = str(row.get(id_col, "")).strip()
            if not mid or mid == "nan":
                continue
            for ini_c, fim_c in zip(ini_cols, fim_cols):
                ini_s = str(row.get(ini_c, "")).strip()
                fim_s = str(row.get(fim_c, "")).strip()
                if not ini_s or not fim_s or ini_s == "nan" or fim_s == "nan":
                    continue
                if data_loader.militar_de_ferias(mid, data, df_ferias, feriados):
                    em_ferias.add(mid)
                    break
        return em_ferias

    with st.spinner("A verificar escalas..."):
        dias_sem = 0
        j = 0
        df_ant_cache: Dict = {}

        while dias_sem < 2 and j < 10:
            dt_a = hoje + timedelta(days=j)
            aba_a = dt_a.strftime("%d-%m")
            df_a = data_loader.carregar_data(aba_a)
            j += 1
            if df_a.empty:
                dias_sem += 1
                continue
            dias_sem = 0
            d_s = dt_a.strftime("%d/%m/%Y")

            # Alerta: duplos
            df_a_serv = df_a[~df_a["serviço"].apply(norm).str.contains("remu|grat", na=False)]
            contagem = df_a_serv[df_a_serv["id"].astype(str).str.strip() != ""].groupby("id").size()
            for mid, count in contagem.items():
                if count > 1:
                    n = _get_nome_militar(df_util, mid)
                    servs = df_a_serv[df_a_serv["id"].astype(str) == str(mid)][["serviço", "horário"]].values.tolist()
                    alertas_duplos.append(f"**{d_s}** -- {n}: {' / '.join([f'{s} ({h})' for s, h in servs])}")

            # Alerta: descanso
            aba_ant = (dt_a - timedelta(days=1)).strftime("%d-%m")
            if aba_ant not in df_ant_cache:
                df_ant_cache[aba_ant] = data_loader.carregar_data(aba_ant)
            df_ant_a = df_ant_cache[aba_ant]
            if not df_ant_a.empty:
                df_ant_serv = df_ant_a[~df_ant_a["serviço"].apply(norm).str.contains("remu|grat|folga|ferias|licen|doente", na=False)]
                ids_hoje = set(df_a_serv[df_a_serv["id"].astype(str).str.strip() != ""]["id"].astype(str))
                ids_ant = set(df_ant_serv[df_ant_serv["id"].astype(str).str.strip() != ""]["id"].astype(str))
                for mid in ids_hoje & ids_ant:
                    rows_h = df_a_serv[df_a_serv["id"].astype(str) == mid]
                    rows_a = df_ant_serv[df_ant_serv["id"].astype(str) == mid]
                    for _, rh in rows_h.iterrows():
                        ini_h, _ = _parse_horario(rh["horário"])
                        if ini_h is None:
                            continue
                        for _, ra in rows_a.iterrows():
                            _, fim_a = _parse_horario(ra["horário"])
                            if fim_a is None:
                                continue
                            descanso = (ini_h + 1440) - fim_a
                            if 0 <= descanso < 480:
                                n = _get_nome_militar(df_util, mid)
                                h2, m2 = descanso // 60, descanso % 60
                                alertas_descanso.append(
                                    f"**{d_s}** -- {n}: {h2}h{m2:02d}m entre "
                                    f"`{ra['serviço']} ({ra['horário']})` e `{rh['serviço']} ({rh['horário']})`"
                                )

            # Alerta: não escalados
            ids_na_escala = set(df_a[df_a["id"].astype(str).str.strip() != ""]["id"].astype(str).str.strip())
            em_ferias_hoje = _ids_de_ferias_no_dia(dt_a)
            for mid in sorted(ids_ativos - ids_na_escala - em_ferias_hoje):
                n = _get_nome_militar(df_util, mid)
                alertas_esquecidos.append(f"**{d_s}** -- {n} ({mid})")

    with st.expander(f"👥 Militar escalado 2x ({len(alertas_duplos)})", expanded=len(alertas_duplos) > 0):
        if alertas_duplos:
            for a in alertas_duplos:
                st.warning(a)
        else:
            st.success("✅ Sem alertas")

    with st.expander(f"😴 Menos de 8h descanso ({len(alertas_descanso)})", expanded=len(alertas_descanso) > 0):
        if alertas_descanso:
            for a in alertas_descanso:
                st.warning(a)
        else:
            st.success("✅ Sem alertas")

    with st.expander(f"🔍 Não escalados ({len(alertas_esquecidos)})", expanded=len(alertas_esquecidos) > 0):
        if alertas_esquecidos:
            for a in alertas_esquecidos:
                st.warning(a)
        else:
            st.success("✅ Sem alertas")


# ─────────────────────────────────────────
# Giros
# ─────────────────────────────────────────

def render_giros(data_loader: "DataLoader") -> None:
    """Renderiza a página de giros."""
    st.title("🔄 Giros")
    try:
        sh = get_sheet()
        ws = sh.worksheet("giros")
        valores = ws.get_all_values()
        if not valores or len(valores) < 2:
            st.info("Não existem giros definidos.")
            return

        headers = [str(h).strip() for h in valores[0]]
        df_giros = pd.DataFrame(valores[1:], columns=headers)
        df_giros = df_giros[df_giros.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

        pesq = st.text_input("🔍 Pesquisar:", placeholder="nome, serviço...")
        df_g = df_giros.copy()
        if pesq:
            p = pesq.lower()
            mask = pd.Series([False] * len(df_g), index=df_g.index)
            for col in df_g.columns:
                mask |= df_g[col].astype(str).str.lower().str.contains(p, na=False)
            df_g = df_g[mask]

        st.markdown(_render_tabela_html(df_g, expandivel=True), unsafe_allow_html=True)
    except Exception:
        st.info("Aba 'giros' não encontrada na Google Sheet. Cria a aba e volta aqui.")


# ─────────────────────────────────────────
# Efetivo
# ─────────────────────────────────────────

def render_efetivo(df_util: pd.DataFrame) -> None:
    """Renderiza a página de efetivo / lista de contactos."""
    st.title("👥 Lista de Contactos")
    if df_util.empty:
        st.info("Sem dados.")
        return

    pesq = st.text_input("🔍 Pesquisar por nome, posto ou ID:", placeholder="ex: Cabo, Ferreira...")
    df_show = df_util.copy()
    if pesq:
        p = pesq.lower()
        df_show = df_show[
            df_show["nome"].str.lower().str.contains(p, na=False)
            | df_show["posto"].str.lower().str.contains(p, na=False)
            | df_show["id"].astype(str).str.contains(p, na=False)
        ]

    cols_show = [c for c in ["id", "nim", "posto", "nome", "telemóvel", "email"] if c in df_show.columns]
    st.markdown(f"**{len(df_show)} militar(es) encontrado(s)**")
    st.dataframe(df_show[cols_show], use_container_width=True, hide_index=True)
