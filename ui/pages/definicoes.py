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

    ano_atual = datetime.now().year
    tab_geral, tab_slot = st.tabs(["📋 Dispensas Gerais", "🔒 Serviços/Horários"])

    # ── Tab Dispensas Gerais ──
    with tab_geral:
        df_licencas = data_loader.carregar_licencas()
        hoje_lic = datetime.now().date()

        if not df_licencas.empty:
            cols_lic = df_licencas.columns.tolist()
            id_col = "id" if "id" in cols_lic else cols_lic[0]
            col_fim_l = next((c for c in cols_lic if "fim" in c.lower()), None)
            col_tp_l = "tipo" if "tipo" in cols_lic else None

            def _is_slot(tipo_str):
                codigos = [c.strip().upper() for c in str(tipo_str).replace(";", ",").split(",")]
                return all(c in DISPENSA_SLOTS for c in codigos if c)

            df_lic_geral = df_licencas.copy()
            if col_tp_l:
                df_lic_geral = df_lic_geral[~df_lic_geral[col_tp_l].apply(_is_slot)]

            def _em_vigor(fim_str):
                try:
                    if "/" in str(fim_str):
                        return datetime.strptime(str(fim_str).strip(), "%d/%m/%Y").date() >= hoje_lic
                    else:
                        return datetime.strptime(f"{fim_str.strip()}-{hoje_lic.year}", "%d-%m-%Y").date() >= hoje_lic
                except Exception:
                    return True

            if col_fim_l:
                df_show = df_lic_geral[df_lic_geral[col_fim_l].apply(_em_vigor)]
            else:
                df_show = df_lic_geral

            if not df_show.empty:
                df_show = df_show.copy()
                df_show["nome"] = df_show[id_col].astype(str).str.strip().apply(lambda x: _get_nome_militar(df_util, x))
                st.dataframe(df_show[["nome"] + [c for c in cols_lic if c != id_col]], use_container_width=True, hide_index=True)
            else:
                st.info("Sem licenças em vigor.")

        st.divider()
        st.markdown("#### ➕ Adicionar registo")
        mil_opts_l = {f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})".strip(): str(r.get('id',''))
                      for _, r in df_util.iterrows() if str(r.get('id','')).strip()}
        col_l1, col_l2 = st.columns(2)
        with col_l1:
            mil_sel_l = st.selectbox("Militar:", list(mil_opts_l.keys()), key="lic_mil")
            tipo_l = st.selectbox("Tipo:", ["Convalescença", "Licença", "Outras Licenças", "Diligência", "Tribunal", "FCAA CTer"], key="lic_tipo")
        with col_l2:
            ini_l = st.date_input("Data início:", format="DD/MM/YYYY", key="lic_ini")
            fim_l = st.date_input("Data fim:", format="DD/MM/YYYY", key="lic_fim")
        obs_l = st.text_input("Observações:", key="lic_obs")
        if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_lic"):
            try:
                sh_l = get_sheet()
                ws_l = sh_l.worksheet("Licenças")
                ws_l.append_row([mil_opts_l[mil_sel_l], tipo_l, ini_l.strftime("%d/%m/%Y"), fim_l.strftime("%d/%m/%Y"), obs_l.strip()])
                data_loader.limpar_cache()
                st.success("✅ Registo adicionado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

        if not df_licencas.empty and not df_lic_geral.empty:
            st.divider()
            st.markdown("#### 🗑️ Remover registo")
            id_col_r = "id" if "id" in df_lic_geral.columns else df_lic_geral.columns[0]
            col_tp_r = "tipo" if "tipo" in df_lic_geral.columns else None
            col_in_r = next((c for c in df_lic_geral.columns if "ini" in c.lower()), None)
            opts_rem = {f"{r[id_col_r]} -- {r.get(col_tp_r,'')} {r.get(col_in_r,'')}": i
                        for i, (_, r) in enumerate(df_lic_geral.iterrows())}
            if opts_rem:
                rem_sel = st.selectbox("Registo:", list(opts_rem.keys()), key="lic_rem")
                if st.button("🗑️ Remover", use_container_width=True, key="btn_rem_lic"):
                    try:
                        sh_l = get_sheet()
                        ws_l = sh_l.worksheet("Licenças")
                        ws_l.delete_rows(opts_rem[rem_sel] + 2)
                        data_loader.limpar_cache()
                        st.success("✅ Removido!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # ── Tab Serviços/Horários ──
    with tab_slot:
        st.markdown("#### 🔒 Dispensa de Serviço/Horário")
        st.caption("O militar é ignorado pelo gerar escala automático apenas para os slots seleccionados.")

        df_licencas_s = data_loader.carregar_licencas()
        if not df_licencas_s.empty and "tipo" in df_licencas_s.columns:
            def _is_slot2(tipo_str):
                codigos = [c.strip().upper() for c in str(tipo_str).replace(";", ",").split(",")]
                return any(c in DISPENSA_SLOTS for c in codigos if c)
            df_slot_show = df_licencas_s[df_licencas_s["tipo"].apply(_is_slot2)].copy()
            col_fim_s = next((c for c in df_licencas_s.columns if "fim" in c.lower()), None)
            if col_fim_s:
                df_slot_show = df_slot_show[df_slot_show[col_fim_s].apply(_em_vigor)]
            if not df_slot_show.empty:
                def _desc_slots(tipo_str):
                    codigos = [c.strip().upper() for c in str(tipo_str).replace(";", ",").split(",")]
                    return ", ".join(f"{c} ({DISPENSA_SLOTS[c][0]} {DISPENSA_SLOTS[c][1]})" for c in codigos if c in DISPENSA_SLOTS)
                df_slot_show["slots"] = df_slot_show["tipo"].apply(_desc_slots)
                df_slot_show["nome"] = df_slot_show["id"].astype(str).str.strip().apply(lambda x: _get_nome_militar(df_util, x))
                st.dataframe(df_slot_show[["nome", "id", "slots"]], use_container_width=True, hide_index=True)
            else:
                st.info("Sem dispensas de slot activas.")
        else:
            st.info("Sem dispensas de slot activas.")

        st.divider()
        st.markdown("#### ➕ Adicionar dispensa de slot")
        mil_opts_sl = {f"{r.get('posto','')} {r.get('nome','')} (ID: {r.get('id','')})".strip(): str(r.get('id',''))
                       for _, r in df_util.iterrows() if str(r.get('id','')).strip()}
        col_s1, col_s2 = st.columns(2)
        slots_opts = {
            "A1 — Atendimento 00-08": "A1", "A2 — Atendimento 08-16": "A2", "A3 — Atendimento 16-24": "A3",
            "PO1 — Patrulha Ocorrências 00-08": "PO1", "PO2 — Patrulha Ocorrências 08-16": "PO2", "PO3 — Patrulha Ocorrências 16-24": "PO3",
            "AA2 — Apoio Atendimento 08-16": "AA2", "AA3 — Apoio Atendimento 16-24": "AA3",
        }
        with col_s1:
            mil_sel_sl = st.selectbox("Militar:", list(mil_opts_sl.keys()), key="slot_mil")
            slots_sel = st.multiselect("Slots:", list(slots_opts.keys()), key="slot_sel")
        with col_s2:
            ini_sl = st.date_input("Data início:", format="DD/MM/YYYY", key="slot_ini")
            fim_sl = st.date_input("Data fim:", format="DD/MM/YYYY", key="slot_fim")
        if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_slot"):
            if not slots_sel:
                st.warning("Selecciona pelo menos um slot.")
            else:
                try:
                    sh_sl = get_sheet()
                    ws_sl = sh_sl.worksheet("Licenças")
                    codigos_sl = ",".join(slots_opts[s] for s in slots_sel)
                    ws_sl.append_row([mil_opts_sl[mil_sel_sl], codigos_sl, ini_sl.strftime("%d/%m/%Y"), fim_sl.strftime("%d/%m/%Y"), ""])
                    data_loader.limpar_cache()
                    st.success(f"✅ Dispensa adicionada: {codigos_sl}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

        if not df_licencas_s.empty and "tipo" in df_licencas_s.columns:
            df_slot_rem = df_licencas_s[df_licencas_s["tipo"].apply(_is_slot2)]
            if not df_slot_rem.empty:
                st.divider()
                st.markdown("#### 🗑️ Remover dispensa de slot")
                col_in_sl = next((c for c in df_slot_rem.columns if "ini" in c.lower()), None)
                opts_rem_sl = {f"{r['id']} -- {r['tipo']} {r.get(col_in_sl,'')}": i
                               for i, (_, r) in enumerate(df_slot_rem.iterrows())}
                rem_sel_sl = st.selectbox("Registo:", list(opts_rem_sl.keys()), key="slot_rem")
                if st.button("🗑️ Remover", use_container_width=True, key="btn_rem_slot"):
                    try:
                        sh_sl = get_sheet()
                        ws_sl = sh_sl.worksheet("Licenças")
                        ws_sl.delete_rows(opts_rem_sl[rem_sel_sl] + 2)
                        data_loader.limpar_cache()
                        st.success("✅ Removido!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")


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
                    ws_pub = sh.worksheet("escala_publicada")
                except Exception:
                    ws_pub = sh.add_worksheet(title="escala_publicada", rows=100, cols=1)
                    ws_pub.update("A1", [["data"]])

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
                ws_pub = sh.worksheet("escala_publicada")
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
            df_a = data_loader.carregar_escala(aba_a)
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
                df_ant_cache[aba_ant] = data_loader.carregar_escala(aba_ant)
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
