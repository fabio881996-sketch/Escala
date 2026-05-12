"""
Página «Gerar Escala» – Admin Only.

Contém 3 sub‑tabs:
  1. ⚙️ Escala Automática – carregar tabela do dia, editar, gerar auto, confirmar
  2. ✏️ Editar Escala      – seleccionar 1‑2 dias, carregar, editar via data_editor
  3. 💶 Remunerados        – nomear, cancelar e substituir remunerados

É a maior secção do portal (~2 000 linhas originais).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import streamlit as st

from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm, parse_horario as _parse_horario
from services.data_loader import DataLoader


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _nc(s: str) -> str:
    """Normaliza cabeçalho: lowercase, strip, remove acentos básicos."""
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


def _get_nome_curto(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or "id" not in df_util.columns:
        return mid
    row = df_util[df_util["id"].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    nome = str(row.iloc[0].get("nome", "")).strip()
    partes = nome.split()
    return partes[-1] if partes else mid


# ── Mapa de abreviaturas ──
ABREV_MAP: Dict[str, Tuple[str, str]] = {
    "A1": ("Atendimento", "00-08"),
    "A2": ("Atendimento", "08-16"),
    "A3": ("Atendimento", "16-24"),
    "PO1": ("Patrulha Ocorrências", "00-08"),
    "PO2": ("Patrulha Ocorrências", "08-16"),
    "PO3": ("Patrulha Ocorrências", "16-24"),
    "AA2": ("Apoio Atendimento", "08-16"),
    "AA3": ("Apoio Atendimento", "16-24"),
}

ABREV_FWD: Dict[str, str] = {
    "Atendimento 00-08": "A1",
    "Atendimento 08-16": "A2",
    "Atendimento 16-24": "A3",
    "Patrulha Ocorrências 00-08": "PO1",
    "Patrulha Ocorrências 08-16": "PO2",
    "Patrulha Ocorrências 16-24": "PO3",
    "Apoio Atendimento 08-16": "AA2",
    "Apoio Atendimento 16-24": "AA3",
}

SLOTS_DEFAULT: List[Tuple[str, str, int]] = [
    ("Atendimento", "00-08", 1),
    ("Atendimento", "08-16", 1),
    ("Atendimento", "16-24", 1),
    ("Patrulha Ocorrências", "00-08", 2),
    ("Patrulha Ocorrências", "08-16", 2),
    ("Patrulha Ocorrências", "16-24", 2),
    ("Apoio Atendimento", "08-16", 1),
    ("Apoio Atendimento", "16-24", 1),
]


def _to_abrev(serv: str, hor: str) -> str:
    """Converte serviço+horário para abreviatura (ex: 'A1'), se existir."""
    abrev_norm = {f"{norm(k.rsplit(' ', 1)[0])} {k.rsplit(' ', 1)[1]}": v for k, v in ABREV_FWD.items()}
    chave_norm = f"{norm(serv)} {hor}".strip()
    return abrev_norm.get(chave_norm, serv)


def _aplicar_abrev_reverso(df: pd.DataFrame) -> pd.DataFrame:
    """Converte abreviaturas de volta para serviço+horário no df."""
    for idx, row in df.iterrows():
        sv = str(row.get("serviço", "")).strip()
        hor = str(row.get("horário", "")).strip()
        if sv in ABREV_MAP:
            serv_real, hor_real = ABREV_MAP[sv]
            df.at[idx, "serviço"] = serv_real
            if not hor or hor == "nan":
                df.at[idx, "horário"] = hor_real
    return df


# ─────────────────────────────────────────
# TAB 1: Escala Automática
# ─────────────────────────────────────────

def _render_tab_auto(
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_folgas: pd.DataFrame,
    df_licencas: pd.DataFrame,
    feriados: Set,
    grupos_folga: Any,
) -> None:
    """Renderiza a tab de escala automática."""
    from services.escala_service import EscalaService

    d_gerar = st.date_input("Data a escalar:", format="DD/MM/YYYY", key="d_gerar_input")
    aba_dia = d_gerar.strftime("%d-%m")

    # Carregar serviços por militar
    militares_servicos = data_loader.carregar_servicos()
    serv_headers = list(set(s for servs in militares_servicos.values() for s in servs))
    todos_servicos = [""] + sorted(set(serv_headers))

    # ── Botão carregar tabela ──
    if st.button("📋 Carregar tabela do dia", key="btn_carregar_tabela", use_container_width=True):
        _carregar_tabela_dia(
            data_loader, df_util, df_ferias, df_folgas, df_licencas,
            feriados, grupos_folga, d_gerar, aba_dia, militares_servicos,
        )

    # ── Mostrar tabela editável ──
    if "tabela_escala" in st.session_state and st.session_state.get("tabela_dia") == aba_dia:
        _mostrar_tabela_editavel(
            data_loader, df_util, df_ferias, df_folgas, df_licencas,
            feriados, grupos_folga, d_gerar, aba_dia, militares_servicos,
        )


def _carregar_tabela_dia(
    data_loader, df_util, df_ferias, df_folgas, df_licencas,
    feriados, grupos_folga, d_gerar, aba_dia, militares_servicos,
) -> None:
    """Carrega/reseta a tabela do dia para o session_state."""
    sh_tab = get_sheet()
    abas_existentes = data_loader.carregar_lista_abas()

    # Criar aba se não existir
    if aba_dia not in abas_existentes:
        aba_modelo = next((t for t in abas_existentes if re.match(r"^\d{2}-\d{2}$", t)), None)
        if aba_modelo:
            hdrs_modelo = sh_tab.worksheet(aba_modelo).row_values(1)
            hdrs_nc = [_nc(h) for h in hdrs_modelo]
            if "giro" not in hdrs_nc:
                hdrs_modelo.append("giro")
            if "viatura" not in hdrs_nc:
                hdrs_modelo.append("viatura")
            ws_nova = sh_tab.add_worksheet(title=aba_dia, rows=200, cols=len(hdrs_modelo))
            ws_nova.update("A1", [hdrs_modelo])
        else:
            hdrs_pad = ["id", "serviço", "horário", "indicativo rádio", "rádio", "viatura", "giro", "observações"]
            ws_nova = sh_tab.add_worksheet(title=aba_dia, rows=200, cols=len(hdrs_pad))
            ws_nova.update("A1", [hdrs_pad])

    # Ler aba do dia
    mapa_existente: Dict[str, list] = {}
    try:
        ws_dia = sh_tab.worksheet(aba_dia)
        vals = ws_dia.get_all_values()
        if vals and len(vals) > 1:
            hdrs = [h.strip().lower() for h in vals[0]]
            ix_id = hdrs.index("id") if "id" in hdrs else 0
            ix_sv = hdrs.index("serviço") if "serviço" in hdrs else 1
            ix_hr = hdrs.index("horário") if "horário" in hdrs else 2
            ix_in = hdrs.index("indicativo rádio") if "indicativo rádio" in hdrs else (hdrs.index("indicativo") if "indicativo" in hdrs else None)
            ix_ra = hdrs.index("rádio") if "rádio" in hdrs else None
            ix_gi = hdrs.index("giro") if "giro" in hdrs else None
            ix_ob = hdrs.index("observações") if "observações" in hdrs else None
            ix_vt = hdrs.index("viatura") if "viatura" in hdrs else None

            def _gt(row, ix):
                return str(row[ix]).strip().replace("nan", "") if ix is not None and ix < len(row) else ""

            for row_t in vals[1:]:
                id_raw = _gt(row_t, ix_id)
                if not id_raw:
                    continue
                sv_t = _gt(row_t, ix_sv)
                if not sv_t:
                    continue
                dados_t = {
                    "serviço": sv_t,
                    "horário": _gt(row_t, ix_hr),
                    "indicativo": _gt(row_t, ix_in),
                    "rádio": _gt(row_t, ix_ra),
                    "giro": _gt(row_t, ix_gi),
                    "viatura": _gt(row_t, ix_vt),
                    "observações": _gt(row_t, ix_ob),
                }
                for mid in re.split(r"[;,\n]+", id_raw):
                    mid = mid.strip()
                    if mid:
                        mapa_existente.setdefault(mid, []).append(dados_t)
    except Exception:
        pass

    # Construir linhas
    linhas: list = []
    for _, row_u in df_util.iterrows():
        mid = str(row_u.get("id", "")).strip()
        if not mid or mid == "nan":
            continue
        nome = str(row_u.get("nome", "")).strip()
        posto = str(row_u.get("posto", "")).strip()

        # Filtrar férias e dispensas
        if data_loader.militar_de_ferias(mid, d_gerar, df_ferias, feriados):
            continue
        if data_loader.militar_de_licenca(mid, d_gerar, df_licencas):
            continue

        if mid in mapa_existente:
            lista_dados = mapa_existente[mid]
            servs_normais = [d for d in lista_dados if not re.search(r"remu|grat", norm(d.get("serviço", "")))]
            servs_rem = [d for d in lista_dados if re.search(r"remu|grat", norm(d.get("serviço", "")))]
            dados = servs_normais[0] if servs_normais else {"serviço": "", "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""}

            if not str(dados.get("serviço", "")).strip() or str(dados.get("serviço", "")).strip() == "nan":
                tipo_folga = data_loader.militar_de_folga(mid, d_gerar, df_folgas, grupos_folga, feriados)
                if tipo_folga:
                    dados = {**dados, "serviço": tipo_folga}
                elif not df_folgas.empty and "serviço" in df_folgas.columns:
                    col_id_f = "id" if "id" in df_folgas.columns else df_folgas.columns[0]
                    linha_f = df_folgas[df_folgas[col_id_f].astype(str).str.strip() == mid]
                    if not linha_f.empty:
                        sv_f = str(linha_f.iloc[0].get("serviço", "")).strip()
                        if sv_f and sv_f != "nan":
                            dados = {**dados, "serviço": sv_f}

            linhas.append({
                "id": mid, "nome": f"{posto} {nome}".strip(),
                "serviço": dados["serviço"], "horário": dados["horário"],
                "indicativo": dados["indicativo"], "rádio": dados["rádio"],
                "giro": dados["giro"], "viatura": dados.get("viatura", ""),
                "observações": dados["observações"],
            })
            for d_rem in servs_rem:
                linhas.append({
                    "id": mid, "nome": f"{posto} {nome}".strip(),
                    "serviço": d_rem["serviço"], "horário": d_rem["horário"],
                    "indicativo": d_rem["indicativo"], "rádio": d_rem["rádio"],
                    "giro": d_rem["giro"], "viatura": d_rem.get("viatura", ""),
                    "observações": d_rem["observações"],
                })
            continue
        else:
            tipo_folga = data_loader.militar_de_folga(mid, d_gerar, df_folgas, grupos_folga, feriados)
            if tipo_folga:
                dados = {"serviço": tipo_folga, "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""}
            else:
                serv_defeito = ""
                if not df_folgas.empty and "serviço" in df_folgas.columns:
                    col_id_f = "id" if "id" in df_folgas.columns else df_folgas.columns[0]
                    linha_f = df_folgas[df_folgas[col_id_f].astype(str).str.strip() == mid]
                    if not linha_f.empty:
                        sv_f = str(linha_f.iloc[0].get("serviço", "")).strip()
                        if sv_f and sv_f != "nan":
                            serv_defeito = sv_f
                dados = {"serviço": serv_defeito, "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""}

        linhas.append({
            "id": mid, "nome": f"{posto} {nome}".strip(),
            "serviço": dados["serviço"], "horário": dados["horário"],
            "indicativo": dados["indicativo"], "rádio": dados["rádio"],
            "giro": dados["giro"], "viatura": dados.get("viatura", ""),
            "observações": dados["observações"],
        })

    st.session_state["tabela_escala"] = linhas
    st.session_state["tabela_dia"] = aba_dia
    st.rerun()


def _mostrar_tabela_editavel(
    data_loader, df_util, df_ferias, df_folgas, df_licencas,
    feriados, grupos_folga, d_gerar, aba_dia, militares_servicos,
) -> None:
    """Mostra a tabela editável com data_editor e botões de acção."""
    linhas = st.session_state["tabela_escala"]

    col_cnt1, col_cnt2 = st.columns(2)
    with col_cnt1:
        st.markdown(f"**{len(linhas)} militares — {d_gerar.strftime('%d/%m/%Y')}**")
    with col_cnt2:
        n_disp = sum(1 for l in linhas if not str(l.get("serviço", "")).strip() or str(l.get("serviço", "")).strip() == "nan")
        st.markdown(f"**{n_disp} disponíveis**")

    if "debug_confirmar" in st.session_state:
        st.warning(f"🔍 {st.session_state.pop('debug_confirmar')}")
    st.caption("Preenche os serviços, gera a escala automática e edita conforme necessário.")

    pesq = st.text_input("🔍 Pesquisar por ID ou nome:", placeholder="ex: 507 ou Silva", key="pesq_tabela", label_visibility="collapsed")

    df_edit = pd.DataFrame(linhas)

    # Carregar listas para dropdowns
    _listas = data_loader.carregar_listas()
    _hor = _listas.get("Horário", ["", "00-08", "08-16", "16-24"])
    _ind = _listas.get("Indicativo", [""])
    _rad = _listas.get("Rádio", [""])
    _vtr = _listas.get("Viatura", [""])
    _gir = _listas.get("Giro", [""])
    if len(_hor) <= 1:
        _hor = ["", "00-08", "08-16", "16-24"]

    _extras_listas = [s for s in (_listas.get("Serviço", []) or [])
                      if s and s not in ("", "Atendimento", "Patrulha Ocorrências", "Apoio Atendimento")]
    _sv_opts = ["", "A1", "A2", "A3", "PO1", "PO2", "PO3", "AA2", "AA3"] + _extras_listas

    # Converter para abreviaturas no display
    df_edit_abrev = df_edit.copy()
    df_edit_abrev["serviço"] = df_edit.apply(
        lambda r: _to_abrev(str(r["serviço"]).strip(), str(r["horário"]).strip()), axis=1
    )

    if pesq.strip():
        mask_pesq = (
            df_edit_abrev["id"].astype(str).str.contains(pesq.strip(), case=False, na=False)
            | df_edit_abrev["nome"].astype(str).str.contains(pesq.strip(), case=False, na=False)
        )
        df_edit_show = df_edit_abrev[mask_pesq].copy()
    else:
        df_edit_show = df_edit_abrev.copy()

    # Data editor
    df_editado_show = st.data_editor(
        df_edit_show,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
            "nome": st.column_config.TextColumn("Nome", disabled=True, width="medium"),
            "serviço": st.column_config.SelectboxColumn("Serviço", options=_sv_opts, width="small"),
            "horário": st.column_config.SelectboxColumn("Horário", options=_hor, width="small"),
            "indicativo": st.column_config.SelectboxColumn("Indicativo", options=_ind, width="small"),
            "rádio": st.column_config.SelectboxColumn("Rádio", options=_rad, width="small"),
            "giro": st.column_config.SelectboxColumn("Giro", options=_gir, width="small"),
            "viatura": st.column_config.SelectboxColumn("Viatura", options=_vtr, width="small"),
            "observações": st.column_config.TextColumn("Observações", width="large"),
        },
        hide_index=True, use_container_width=True,
        key="editor_escala", num_rows="fixed",
        height=min(50 + len(df_edit_show) * 35, 2000),
    )

    # ── Converter abreviaturas de volta ──
    df_editado = df_edit.copy()
    for _, row_ed in df_editado_show.iterrows():
        mid_ed = str(row_ed["id"]).strip()
        idx_ed = df_editado[df_editado["id"].astype(str).str.strip() == mid_ed].index
        if len(idx_ed) == 0:
            continue
        i = idx_ed[0]
        sv_ed = str(row_ed.get("serviço", "")).strip()
        hor_ed = str(row_ed.get("horário", "")).strip()
        if sv_ed in ABREV_MAP:
            serv_real, hor_real = ABREV_MAP[sv_ed]
            df_editado.at[i, "serviço"] = serv_real
            df_editado.at[i, "horário"] = hor_ed if (hor_ed and hor_ed != "nan") else hor_real
        else:
            df_editado.at[i, "serviço"] = sv_ed
            df_editado.at[i, "horário"] = hor_ed
        for col_ed in ["indicativo", "rádio", "giro", "viatura", "observações"]:
            if col_ed in row_ed.index:
                df_editado.at[i, col_ed] = row_ed[col_ed]

    # Persistir edições durante pesquisa
    if pesq.strip():
        tabela_df = pd.DataFrame(st.session_state.get("tabela_escala", linhas))
        for _, row_ed in df_editado_show.iterrows():
            mid_ed = str(row_ed["id"]).strip()
            idx_t = tabela_df[tabela_df["id"].astype(str).str.strip() == mid_ed].index
            if len(idx_t) > 0:
                i_t = idx_t[0]
                sv_t = str(row_ed.get("serviço", "")).strip()
                hor_t = str(row_ed.get("horário", "")).strip()
                if sv_t in ABREV_MAP:
                    serv_r, hor_r = ABREV_MAP[sv_t]
                    tabela_df.at[i_t, "serviço"] = serv_r
                    tabela_df.at[i_t, "horário"] = hor_t if (hor_t and hor_t != "nan") else hor_r
                else:
                    tabela_df.at[i_t, "serviço"] = sv_t
                    tabela_df.at[i_t, "horário"] = hor_t
                for col_t in ["indicativo", "rádio", "giro", "viatura", "observações"]:
                    if col_t in row_ed.index:
                        tabela_df.at[i_t, col_t] = row_ed[col_t]
        st.session_state["tabela_escala"] = tabela_df.to_dict("records")

    col_g1, col_g2, col_g3 = st.columns(3)

    # ── Limpar ──
    with col_g3:
        if st.button("🗑️ Limpar escala", use_container_width=True, key="btn_limpar_escala"):
            _limpar_escala(data_loader, d_gerar, df_folgas, grupos_folga, feriados)

    # ── Gerar Automática ──
    with col_g1:
        if st.button("⚙️ Gerar escala automática", use_container_width=True, key="btn_gerar_auto"):
            _gerar_auto(data_loader, df_util, df_editado, d_gerar, aba_dia, militares_servicos, df_licencas, feriados)

    # ── Confirmar ──
    with col_g2:
        if st.button("✅ CONFIRMAR E GUARDAR", use_container_width=True, type="primary", key="btn_confirmar_tabela"):
            _confirmar_guardar(data_loader, df_util, df_editado, df_ferias, df_licencas, feriados, d_gerar, aba_dia)


def _limpar_escala(data_loader, d_gerar, df_folgas, grupos_folga, feriados) -> None:
    """Limpa a escala mantendo férias/folgas."""
    linhas_atuais = st.session_state.get("tabela_escala", [])
    _serv_manter = {"férias", "folga semanal", "folga complementar"}
    _serv_remover = {"remu", "grat"}
    mids_vistos: set = set()
    linhas_limpas: list = []

    for row_l in linhas_atuais:
        sv_l = str(row_l.get("serviço", "")).strip().lower()
        mid_l = str(row_l.get("id", "")).strip()
        if any(x in sv_l for x in _serv_remover):
            continue
        if mid_l in mids_vistos:
            continue
        mids_vistos.add(mid_l)
        if sv_l in _serv_manter:
            linhas_limpas.append(row_l)
        else:
            tipo_folga = data_loader.militar_de_folga(mid_l, d_gerar, df_folgas, grupos_folga, feriados)
            if tipo_folga:
                linhas_limpas.append({**row_l, "serviço": tipo_folga, "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""})
            else:
                serv_def = ""
                if not df_folgas.empty and "serviço" in df_folgas.columns:
                    col_id_fl = "id" if "id" in df_folgas.columns else df_folgas.columns[0]
                    linha_fl = df_folgas[df_folgas[col_id_fl].astype(str).str.strip() == mid_l]
                    if not linha_fl.empty:
                        sv_fl = str(linha_fl.iloc[0].get("serviço", "")).strip()
                        if sv_fl and sv_fl != "nan":
                            serv_def = sv_fl
                linhas_limpas.append({**row_l, "serviço": serv_def, "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""})

    st.session_state["tabela_escala"] = linhas_limpas
    st.session_state.pop("ordem_gerada", None)
    st.rerun()


def _gerar_auto(data_loader, df_util, df_editado, d_gerar, aba_dia, militares_servicos, df_licencas, feriados) -> None:
    """Gera a escala automática preenchendo slots vazios."""
    with st.spinner("A gerar..."):
        try:
            sh_g = get_sheet()

            df_editado = _aplicar_abrev_reverso(df_editado.copy())

            # Indisponíveis
            ids_indisponiveis: set = set()
            for _, row_e in df_editado.iterrows():
                mid = str(row_e["id"]).strip()
                serv = str(row_e["serviço"]).strip()
                if serv and serv != "nan" and not any(x in norm(serv) for x in ["remu", "grat"]):
                    ids_indisponiveis.add(mid)

            # Carregar ordem_escala
            aba_ordem = f"ordem_escala {aba_dia}"
            aba_ordem_ant = f"ordem_escala {(d_gerar - timedelta(days=1)).strftime('%d-%m')}"
            try:
                ws_ordem = sh_g.worksheet(aba_ordem)
            except Exception:
                try:
                    ws_ordem = sh_g.worksheet(aba_ordem_ant)
                except Exception:
                    abas_disp = data_loader.carregar_lista_abas()
                    abas_ord = [a for a in abas_disp if "ordem" in a.lower()]
                    st.error(f"Não encontrei ordem_escala. A procurar: '{aba_ordem}' ou '{aba_ordem_ant}'. Abas ordem disponíveis: {abas_ord}")
                    st.stop()

            ordem_vals = ws_ordem.get_all_values()
            ordem_headers = [str(h).strip() for h in ordem_vals[0]]
            ordem_g: Dict[str, list] = {h: [] for h in ordem_headers}
            for row_o in ordem_vals[1:]:
                for i, h in enumerate(ordem_headers):
                    val = str(row_o[i]).strip() if i < len(row_o) else ""
                    if val:
                        ordem_g[h].append(val)

            df_ant = data_loader.carregar_data_direto(sh_g, (d_gerar - timedelta(days=1)).strftime("%d-%m"))

            # Contar slots preenchidos
            slots_preenchidos: Dict = {}
            for _, row_e in df_editado.iterrows():
                sv_e = str(row_e["serviço"]).strip()
                hr_e = str(row_e["horário"]).strip()
                if sv_e and sv_e != "nan" and hr_e and hr_e != "nan":
                    chave = (norm(sv_e), hr_e)
                    slots_preenchidos[chave] = slots_preenchidos.get(chave, 0) + 1

            slots_ajustados = []
            for sv_s, hr_s, num_s in SLOTS_DEFAULT:
                ja = slots_preenchidos.get((norm(sv_s), hr_s), 0)
                vagas = max(0, num_s - ja)
                if vagas > 0:
                    slots_ajustados.append((sv_s, hr_s, vagas))

            ids_escalados: set = set()
            novas_linhas = {str(row_e["id"]): dict(row_e) for _, row_e in df_editado.iterrows()}

            for servico, horario, num in slots_ajustados:
                col_key = f"{servico} {horario}"
                if col_key not in ordem_g:
                    continue
                colocados = []
                for mid in ordem_g[col_key]:
                    if len(colocados) >= num:
                        break
                    motivo = None
                    if mid in ids_indisponiveis:
                        motivo = "indisponivel"
                    elif mid in ids_escalados:
                        motivo = "ja_escalado"
                    elif data_loader.militar_tem_dispensa_slot(mid, d_gerar, df_licencas, servico, horario):
                        motivo = "dispensa_slot"
                    elif servico not in militares_servicos.get(mid, []):
                        motivo = f"sem_servico:{militares_servicos.get(mid, [])}"
                    else:
                        ini_novo, _ = _parse_horario(horario)
                        ok = True
                        if not df_ant.empty:
                            rows_ant = df_ant[df_ant["id"].astype(str).str.strip() == mid]
                            rows_ant = rows_ant[~rows_ant["serviço"].apply(norm).str.contains("remu|grat", na=False)]
                            for _, r_ant in rows_ant.iterrows():
                                _, fim_ant = _parse_horario(str(r_ant.get("horário", "")))
                                if fim_ant and ini_novo is not None:
                                    if (1440 - fim_ant) + ini_novo < 480:
                                        ok = False
                                        break
                        if not ok:
                            motivo = "descanso"

                    if motivo:
                        pass
                    else:
                        if mid not in novas_linhas:
                            continue
                        colocados.append(mid)
                        ids_escalados.add(mid)

                for mid in colocados:
                    novas_linhas[mid]["serviço"] = servico
                    novas_linhas[mid]["horário"] = horario
                    if servico == "Patrulha Ocorrências":
                        novas_linhas[mid]["indicativo"] = "031.6A"
                        novas_linhas[mid]["viatura"] = "BT-05-NX"
                        novas_linhas[mid]["giro"] = "I"
                        if horario == "00-08":
                            novas_linhas[mid]["rádio"] = "4110201"
                        elif horario == "08-16":
                            novas_linhas[mid]["rádio"] = "4110203"
                        elif horario == "16-24":
                            novas_linhas[mid]["rádio"] = "4110204"
                    ordem_g[col_key].remove(mid)
                    ordem_g[col_key].append(mid)

            st.session_state["tabela_escala"] = list(novas_linhas.values())
            st.session_state["ordem_gerada"] = ordem_g
            st.session_state["ordem_headers_gerada"] = ordem_headers
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao gerar: {e}")


def _confirmar_guardar(data_loader, df_util, df_editado, df_ferias, df_licencas, feriados, d_gerar, aba_dia) -> None:
    """Confirma e guarda a escala no Google Sheets."""
    with st.spinner("A guardar..."):
        try:
            df_editado = _aplicar_abrev_reverso(df_editado.copy())
            sh_c = get_sheet()
            ws_dia = sh_c.worksheet(aba_dia)
            todas_linhas = ws_dia.get_all_values()
            hdrs_raw = [h.strip() for h in todas_linhas[0]] if todas_linhas else ["id", "serviço", "horário", "indicativo", "rádio", "giro", "viatura", "observações"]
            hdrs_c = [h.lower() for h in hdrs_raw]

            # Preservar remunerados
            linhas_rem_preservar = []
            if len(todas_linhas) > 1:
                ix_sv_p = hdrs_c.index("serviço") if "serviço" in hdrs_c else 1
                for row_p in todas_linhas[1:]:
                    sv_p = norm(str(row_p[ix_sv_p]).strip()) if ix_sv_p < len(row_p) else ""
                    if any(x in sv_p for x in ["remu", "grat"]):
                        linhas_rem_preservar.append(row_p)

            ws_dia.resize(rows=1)
            if not todas_linhas:
                ws_dia.update("A1", [hdrs_raw])

            # Agrupar por serviço+horário+obs
            grupos_sv: Dict = {}
            for _, row_e in df_editado.iterrows():
                sv_e = str(row_e.get("serviço", "")).strip()
                if not sv_e or sv_e == "nan":
                    continue
                mid_e = str(row_e["id"]).strip()
                if not mid_e or mid_e == "nan":
                    continue
                hr_e = str(row_e.get("horário", "")).strip()
                obs_e = str(row_e.get("observações", "")).strip()
                chave = (sv_e, hr_e, obs_e)
                if chave not in grupos_sv:
                    grupos_sv[chave] = {"ids": [], "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": obs_e}
                grupos_sv[chave]["ids"].append(mid_e)
                for campo in ["indicativo", "rádio", "giro", "viatura"]:
                    val = str(row_e.get(campo, "")).strip()
                    if val and val != "nan" and not grupos_sv[chave][campo]:
                        grupos_sv[chave][campo] = val

            nova_data = []
            for (sv_e, hr_e, obs_e), dados_g in grupos_sv.items():
                linha_nova = [""] * len(hdrs_raw)
                for col_nome, val in [
                    ("id", ";".join(dados_g["ids"])),
                    ("serviço", sv_e), ("horário", hr_e),
                    ("indicativo", dados_g["indicativo"]),
                    ("rádio", dados_g["rádio"]),
                    ("giro", dados_g["giro"]),
                    ("viatura", dados_g["viatura"]),
                    ("observações", dados_g["observações"]),
                ]:
                    idx_col = next((i for i, h in enumerate(hdrs_c) if col_nome in h), None)
                    if idx_col is not None:
                        linha_nova[idx_col] = val
                nova_data.append(linha_nova)
            if nova_data:
                ws_dia.append_rows(nova_data)
            if linhas_rem_preservar:
                ws_dia.append_rows(linhas_rem_preservar)

            # Militares sem serviço → Disponível / Férias / Licença
            ids_escalados = set()
            for (sv_e, hr_e, obs_e), dados_g in grupos_sv.items():
                for mid_e in dados_g["ids"]:
                    ids_escalados.add(str(mid_e).strip())

            linhas_disp = []
            for _, row_u in df_util.iterrows():
                mid_u = str(row_u.get("id", "")).strip()
                if not mid_u or mid_u == "nan" or mid_u in ids_escalados:
                    continue
                if data_loader.militar_de_ferias(mid_u, d_gerar, df_ferias, feriados):
                    sv_reg = "Férias"
                else:
                    lic_raw = data_loader.militar_de_licenca(mid_u, d_gerar, df_licencas)
                    if lic_raw:
                        sv_reg = lic_raw.split("|")[0] if "|" in lic_raw else lic_raw
                    else:
                        sv_reg = "Disponível"
                linha_disp = [""] * len(hdrs_raw)
                idx_id_c = next((i for i, h in enumerate(hdrs_c) if "id" in h), None)
                idx_sv_c = next((i for i, h in enumerate(hdrs_c) if "servi" in h), None)
                if idx_id_c is not None:
                    linha_disp[idx_id_c] = mid_u
                if idx_sv_c is not None:
                    linha_disp[idx_sv_c] = sv_reg
                linhas_disp.append(linha_disp)
            if linhas_disp:
                ws_dia.append_rows(linhas_disp)

            # Gerar ordem_escala do dia seguinte
            data_loader.gerar_ordem_escala_dia_seguinte(sh_c, aba_dia, d_gerar)

            data_loader.limpar_cache()
            del st.session_state["tabela_escala"]
            st.session_state.pop("ordem_gerada", None)
            st.session_state.pop("tabela_dia", None)
            st.success("✅ Escala guardada!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao guardar: {e}")


# ─────────────────────────────────────────
# TAB 2: Editar Escala
# ─────────────────────────────────────────

def _render_tab_editar(
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_licencas: pd.DataFrame,
    feriados: Set,
) -> None:
    """Renderiza a tab de edição manual da escala."""
    st.markdown("#### ✏️ Editar Escala")
    st.caption("Seleciona até 2 dias para ver e editar em simultâneo.")

    _listas = data_loader.carregar_listas()
    _mil_servicos = data_loader.carregar_servicos()
    _extras_e = [
        "Férias", "Folga Semanal", "Folga Complementar", "Outras Licenças",
        "Convalescença", "Diligência", "Inquéritos", "Secretaria",
        "Pronto", "Tribunal", "Disponível",
        "Patrulha Auto", "Patrulha Apeada", "EG", "Tiro",
    ]
    _hdrs_e = list(set(s for servs in _mil_servicos.values() for s in servs))
    todos_servicos_e = [""] + sorted(set(_hdrs_e + _extras_e))
    opts_hor_e = [""] + sorted(set(str(s) for s in _listas.get("Horário", ["00-08", "08-16", "16-24"]) if str(s).strip()))
    opts_rad_e = [""] + sorted(set(str(s) for s in _listas.get("Rádio", []) if str(s).strip()))
    opts_ind_e = [""] + sorted(set(str(s) for s in _listas.get("Indicativo", []) if str(s).strip()))
    opts_vtr_e = [""] + sorted(set(str(s) for s in _listas.get("Viatura", []) if str(s).strip()))
    opts_gir_e = [""] + sorted(set(str(s) for s in _listas.get("Giro", []) if str(s).strip()))
    opts_sv_e = _listas.get("Serviço", todos_servicos_e) or todos_servicos_e
    opts_sv_e = [""] + sorted(set(str(s) for s in opts_sv_e if str(s).strip()))
    if len(opts_hor_e) <= 1:
        opts_hor_e = ["", "00-08", "08-16", "16-24"]

    def _adicionar_lista(campo: str, valor: str) -> None:
        try:
            sh_l = get_sheet()
            ws_l = sh_l.worksheet("listas")
            vals_l = ws_l.get_all_values()
            if not vals_l:
                return
            hdrs_l = [h.strip() for h in vals_l[0]]
            if campo not in hdrs_l:
                return
            col_idx = hdrs_l.index(campo)
            col_vals = [str(row[col_idx]).strip() for row in vals_l[1:] if col_idx < len(row)]
            if valor not in col_vals:
                next_row = len([v for v in col_vals if v]) + 2
                cl = chr(ord("A") + col_idx)
                ws_l.update(f"{cl}{next_row}", [[valor]])
                data_loader.limpar_cache()
        except Exception:
            pass

    col_e1, col_e2, col_e3 = st.columns([2, 2, 1])
    with col_e1:
        d_e1 = st.date_input("Dia 1:", format="DD/MM/YYYY", key="d_edit1")
    with col_e2:
        d_e2 = st.date_input("Dia 2:", format="DD/MM/YYYY", key="d_edit2", value=None)
    with col_e3:
        _ord_carregar = st.selectbox("Ordenar por:", ["ID", "Nome", "Serviço", "Horário"], key="ord_carregar")

    dias_editar = [d for d in [d_e1, d_e2] if d is not None]

    if st.button("📋 Carregar dias", key="btn_carregar_editar", use_container_width=True):
        _carregar_dias_editar(
            data_loader, df_util, df_ferias, df_licencas, feriados,
            dias_editar, _ord_carregar, opts_hor_e, opts_ind_e, opts_rad_e,
            opts_gir_e, opts_vtr_e, opts_sv_e,
        )

    if "debug_upds" in st.session_state:
        st.info(st.session_state.pop("debug_upds"))

    # ── Mostrar tabelas editáveis ──
    if "editar_escala" in st.session_state:
        _mostrar_editor_dias(
            data_loader, df_util, opts_sv_e, opts_hor_e, opts_ind_e,
            opts_rad_e, opts_gir_e, opts_vtr_e, _adicionar_lista,
        )


def _carregar_dias_editar(
    data_loader, df_util, df_ferias, df_licencas, feriados,
    dias_editar, ord_carregar, opts_hor_e, opts_ind_e, opts_rad_e,
    opts_gir_e, opts_vtr_e, opts_sv_e,
) -> None:
    """Carrega dados dos dias seleccionados para edição."""
    st.session_state["ord_editar"] = ord_carregar
    sh_e = get_sheet()
    abas_existentes = data_loader.carregar_lista_abas()

    aba_modelo = next((t for t in abas_existentes if re.match(r"^\d{2}-\d{2}$", t)), None)
    if aba_modelo:
        hdrs_modelo = sh_e.worksheet(aba_modelo).row_values(1)
        hdrs_modelo_nc = [_nc(h) for h in hdrs_modelo]
        if "giro" not in hdrs_modelo_nc:
            hdrs_modelo.append("giro")
        if "viatura" not in hdrs_modelo_nc:
            hdrs_modelo.append("viatura")
    else:
        hdrs_modelo = ["id", "serviço", "horário", "indicativo rádio", "rádio", "viatura", "giro", "observações"]

    for d_e in dias_editar:
        aba_chk = d_e.strftime("%d-%m")
        if aba_chk not in abas_existentes:
            ws_chk = sh_e.add_worksheet(title=aba_chk, rows=200, cols=len(hdrs_modelo))
            ws_chk.update("A1", [hdrs_modelo])

    # Cache férias
    ferias_cache: Dict = {}
    if "id" not in df_util.columns:
        st.error("Erro ao carregar utilizadores. Tenta novamente.")
        st.stop()
    for d_e in dias_editar:
        em_ferias = set()
        for mid in df_util["id"].astype(str).str.strip():
            if data_loader.militar_de_ferias(mid, d_e, df_ferias, feriados):
                em_ferias.add(mid)
        ferias_cache[d_e] = em_ferias

    dados_editar: Dict = {}
    for d_e in dias_editar:
        aba_e = d_e.strftime("%d-%m")
        mapa_e: Dict = {}
        try:
            ws_raw = sh_e.worksheet(aba_e)
            vals_raw = ws_raw.get_all_values()
            if vals_raw and len(vals_raw) > 1:
                hdrs_raw = [h.strip().lower() for h in vals_raw[0]]
                ix_id = hdrs_raw.index("id") if "id" in hdrs_raw else 0
                ix_sv = hdrs_raw.index("serviço") if "serviço" in hdrs_raw else 1
                ix_hr = hdrs_raw.index("horário") if "horário" in hdrs_raw else 2
                ix_in = hdrs_raw.index("indicativo rádio") if "indicativo rádio" in hdrs_raw else (hdrs_raw.index("indicativo") if "indicativo" in hdrs_raw else None)
                ix_ra = hdrs_raw.index("rádio") if "rádio" in hdrs_raw else None
                ix_gi = hdrs_raw.index("giro") if "giro" in hdrs_raw else None
                ix_vt = hdrs_raw.index("viatura") if "viatura" in hdrs_raw else None
                ix_ob = hdrs_raw.index("observações") if "observações" in hdrs_raw else None

                def _get(row, ix):
                    return str(row[ix]).strip().replace("nan", "") if ix is not None and ix < len(row) else ""

                # Recolher opções
                opts_hor_s = set(opts_hor_e)
                opts_ind_s = set(opts_ind_e)
                opts_rad_s = set(opts_rad_e)
                opts_gir_s = set(opts_gir_e)
                opts_vtr_s = set(opts_vtr_e)
                opts_sv_s = set(opts_sv_e)

                for row_r in vals_raw[1:]:
                    v_sv = _get(row_r, ix_sv)
                    v_hr = _get(row_r, ix_hr)
                    v_in = _get(row_r, ix_in)
                    v_ra = _get(row_r, ix_ra)
                    v_gi = _get(row_r, ix_gi)
                    v_vt = _get(row_r, ix_vt)
                    if v_sv: opts_sv_s.add(v_sv)
                    if v_hr: opts_hor_s.add(v_hr)
                    if v_in: opts_ind_s.add(v_in)
                    if v_ra: opts_rad_s.add(v_ra)
                    if v_gi: opts_gir_s.add(v_gi)
                    if v_vt: opts_vtr_s.add(v_vt)

                    id_raw = _get(row_r, ix_id)
                    if not id_raw:
                        continue
                    dados_r = {
                        "serviço": v_sv, "horário": v_hr,
                        "indicativo": v_in, "rádio": v_ra,
                        "giro": v_gi, "viatura": v_vt,
                        "observações": _get(row_r, ix_ob),
                    }
                    for mid in re.split(r"[;,\n]+", id_raw):
                        mid = mid.strip()
                        if mid:
                            mapa_e.setdefault(mid, []).append(dados_r)

                st.session_state["opts_hor_e"] = [""] + sorted(opts_hor_s - {""})
                st.session_state["opts_ind_e"] = [""] + sorted(opts_ind_s - {""})
                st.session_state["opts_rad_e"] = [""] + sorted(opts_rad_s - {""})
                st.session_state["opts_gir_e"] = [""] + sorted(opts_gir_s - {""})
                st.session_state["opts_vtr_e"] = [""] + sorted(opts_vtr_s - {""})
                st.session_state["opts_sv_e"] = [""] + sorted(opts_sv_s - {""})
        except Exception as _err:
            st.warning(f"Erro ao ler {aba_e}: {_err}")

        em_ferias_e = ferias_cache[d_e]
        linhas_e_raw = []
        for _, row_u in df_util.iterrows():
            mid = str(row_u.get("id", "")).strip()
            if not mid or mid == "nan":
                continue
            nome = str(row_u.get("nome", "")).strip()
            partes = nome.split()
            apelido = partes[-1] if partes else nome

            if mid in mapa_e:
                lista_e = mapa_e[mid]
                servs_normais = [d for d in lista_e if not norm(d.get("serviço", "")).startswith("remu") and not norm(d.get("serviço", "")).startswith("grat")]
                dados = servs_normais[0] if servs_normais else lista_e[0]
            elif mid in em_ferias_e:
                dados = {"serviço": "Férias", "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""}
            else:
                _lic_raw = data_loader.militar_de_licenca(mid, d_e, df_licencas)
                if _lic_raw:
                    _lic_tipo = _lic_raw.split("|")[0] if "|" in _lic_raw else _lic_raw
                    _lic_obs = _lic_raw.split("|")[1] if "|" in _lic_raw else ""
                    dados = {"serviço": _lic_tipo, "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": _lic_obs}
                else:
                    dados = {"serviço": "Disponível", "horário": "", "indicativo": "", "rádio": "", "giro": "", "viatura": "", "observações": ""}

            linhas_e_raw.append({
                "id": mid, "apelido": apelido,
                "serviço": dados.get("serviço", ""), "horário": dados.get("horário", ""),
                "indicativo": dados.get("indicativo", ""), "rádio": dados.get("rádio", ""),
                "giro": dados.get("giro", ""), "viatura": dados.get("viatura", ""),
                "observações": dados.get("observações", ""),
            })

        # Agrupar
        grupos_e: Dict = {}
        linhas_e: list = []
        for r in linhas_e_raw:
            sv = r["serviço"]
            hr = r["horário"]
            if sv and hr:
                chave = (sv, hr, r["indicativo"], r["rádio"], r["giro"], r["viatura"], r["observações"])
                if chave in grupos_e:
                    idx = grupos_e[chave]
                    linhas_e[idx]["id"] += ";" + r["id"]
                    linhas_e[idx]["nome"] += ", " + r["apelido"]
                else:
                    grupos_e[chave] = len(linhas_e)
                    linhas_e.append({"id": r["id"], "nome": r["apelido"], "serviço": sv, "horário": hr, "indicativo": r["indicativo"], "rádio": r["rádio"], "giro": r["giro"], "viatura": r["viatura"], "observações": r["observações"]})
            else:
                linhas_e.append({"id": r["id"], "nome": r["apelido"], "serviço": sv, "horário": hr, "indicativo": r["indicativo"], "rádio": r["rádio"], "giro": r["giro"], "viatura": r["viatura"], "observações": r["observações"]})

        dados_editar[aba_e] = {"linhas": linhas_e, "data": d_e}

        # Remunerados agrupados
        grupos_rem_e: Dict = {}
        for mid_rem, lista_rem in mapa_e.items():
            for d_rem in lista_rem:
                if not re.search(r"remu|grat", norm(d_rem.get("serviço", ""))):
                    continue
                sv_r = d_rem["serviço"]
                hr_r = d_rem["horário"]
                chave_r = (sv_r, hr_r, d_rem.get("indicativo", ""), d_rem.get("rádio", ""), d_rem.get("giro", ""), d_rem.get("viatura", ""), d_rem.get("observações", ""))
                apelido_rem = ""
                row_u_rem = df_util[df_util["id"].astype(str).str.strip() == mid_rem]
                if not row_u_rem.empty:
                    nome_rem = str(row_u_rem.iloc[0].get("nome", "")).strip()
                    partes_rem = nome_rem.split()
                    apelido_rem = partes_rem[-1] if partes_rem else nome_rem
                if chave_r not in grupos_rem_e:
                    grupos_rem_e[chave_r] = {"ids": [mid_rem], "nomes": [apelido_rem], "indicativo": d_rem.get("indicativo", ""), "rádio": d_rem.get("rádio", ""), "giro": d_rem.get("giro", ""), "viatura": d_rem.get("viatura", ""), "observações": d_rem.get("observações", "")}
                else:
                    if mid_rem not in grupos_rem_e[chave_r]["ids"]:
                        grupos_rem_e[chave_r]["ids"].append(mid_rem)
                        grupos_rem_e[chave_r]["nomes"].append(apelido_rem)

        for (sv_r, hr_r, *_rest), g_r in grupos_rem_e.items():
            linhas_e.append({
                "id": ";".join(g_r["ids"]), "nome": ", ".join(g_r["nomes"]),
                "serviço": sv_r, "horário": hr_r,
                "indicativo": g_r["indicativo"], "rádio": g_r["rádio"],
                "giro": g_r["giro"], "viatura": g_r["viatura"],
                "observações": g_r["observações"],
            })

    st.session_state["editar_escala"] = dados_editar
    st.rerun()


def _guardar_sheets(data_loader, editados_dict: Dict) -> None:
    """Agrupa e escreve dados editados no Sheets."""
    sh_gc = get_sheet()
    for aba_g, df_g in editados_dict.items():
        for tentativa in range(3):
            try:
                ws_g = sh_gc.worksheet(aba_g)
                todas_g = ws_g.get_all_values()
                break
            except Exception as ex:
                if "429" in str(ex) and tentativa < 2:
                    time.sleep(20 * (tentativa + 1))
                else:
                    raise
        if not todas_g:
            continue
        hdrs_raw = [h.strip() for h in todas_g[0]]
        hdrs_g = [h.lower() for h in hdrs_raw]

        editor_map: Dict = {}
        for _, r in df_g.iterrows():
            mid = str(r["id"]).strip()
            if not mid or mid == "nan":
                continue
            serv_r = str(r.get("serviço", "") or "").strip()
            if re.search(r"remu|grat", norm(serv_r)):
                continue
            editor_map[mid] = {
                "serviço": serv_r,
                "horário": str(r.get("horário", "") or "").strip(),
                "indicativo": str(r.get("indicativo", "") or "").strip(),
                "rádio": str(r.get("rádio", "") or "").strip(),
                "giro": str(r.get("giro", "") or "").strip(),
                "viatura": str(r.get("viatura", "") or "").strip(),
                "observações": str(r.get("observações", "") or "").strip(),
            }

        hdrs_nc = [_nc(h) for h in hdrs_raw]
        _mc = {
            "id": next((i for i, h in enumerate(hdrs_nc) if h == "id"), 0),
            "servico": next((i for i, h in enumerate(hdrs_nc) if "servi" in h), 1),
            "horario": next((i for i, h in enumerate(hdrs_nc) if h == "horario"), 2),
            "indicativo": next((i for i, h in enumerate(hdrs_nc) if h in ("indicativo", "indicativo radio")), None),
            "radio": next((i for i, h in enumerate(hdrs_nc) if h == "radio"), None),
            "viatura": next((i for i, h in enumerate(hdrs_nc) if h == "viatura"), None),
            "giro": next((i for i, h in enumerate(hdrs_nc) if h == "giro"), None),
            "obs": next((i for i, h in enumerate(hdrs_nc) if "obs" in h), None),
        }

        # Remunerados do editor
        linhas_rem_g = []
        for _, r_novo in df_g.iterrows():
            id_raw = str(r_novo.get("id", "") or "").strip()
            serv_n = str(r_novo.get("serviço", "") or "").strip()
            if not id_raw or id_raw == "nan" or not re.search(r"remu|grat", norm(serv_n)):
                continue
            linha_nova = [""] * len(hdrs_raw)
            for chave_n, val_n in [
                ("id", id_raw), ("servico", serv_n),
                ("horario", str(r_novo.get("horário", "") or "").strip()),
                ("indicativo", str(r_novo.get("indicativo", "") or "").strip()),
                ("radio", str(r_novo.get("rádio", "") or "").strip()),
                ("giro", str(r_novo.get("giro", "") or "").strip()),
                ("viatura", str(r_novo.get("viatura", "") or "").strip()),
                ("obs", str(r_novo.get("observações", "") or "").strip()),
            ]:
                idx_n = _mc.get(chave_n)
                if idx_n is not None:
                    linha_nova[idx_n] = val_n
            linhas_rem_g.append(linha_nova)

        # Agrupar normais
        grupos_novos: Dict = {}
        for mid, dados in editor_map.items():
            sv = dados["serviço"]
            if not sv:
                continue
            hr = dados["horário"]
            chave = (sv, hr, dados["indicativo"], dados["rádio"], dados["giro"], dados["viatura"], dados["observações"])
            if chave not in grupos_novos:
                grupos_novos[chave] = {"ids": [], **{k: dados[k] for k in ["indicativo", "rádio", "giro", "viatura", "observações"]}}
            grupos_novos[chave]["ids"].append(mid)

        novas_linhas = []
        for (sv, hr, *_), d in grupos_novos.items():
            linha = [""] * len(hdrs_raw)
            for chave_mc, val in [
                ("id", ";".join(d["ids"])), ("servico", sv), ("horario", hr),
                ("indicativo", d["indicativo"]), ("radio", d["rádio"]),
                ("giro", d["giro"]), ("viatura", d["viatura"]), ("obs", d["observações"]),
            ]:
                idx_col = _mc.get(chave_mc)
                if idx_col is not None:
                    linha[idx_col] = val
            novas_linhas.append(linha)

        tudo = [hdrs_raw] + novas_linhas + linhas_rem_g
        ws_g.clear()
        ws_g.update("A1", tudo)

        # Atualizar ordem_escala
        try:
            time.sleep(2)
            aba_data = datetime.strptime(f"{aba_g}-{datetime.now().year}", "%d-%m-%Y")
            data_loader.atualizar_ordem_escala_em_cadeia(sh_gc, aba_g, aba_data)
        except Exception:
            pass


def _mostrar_editor_dias(
    data_loader, df_util, opts_sv_e, opts_hor_e, opts_ind_e,
    opts_rad_e, opts_gir_e, opts_vtr_e, adicionar_lista_fn,
) -> None:
    """Mostra os data_editors para os dias carregados."""
    dados_editar = st.session_state["editar_escala"]
    abas_lista = list(dados_editar.items())
    dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

    if len(abas_lista) == 2:
        _mostrar_editor_2dias(data_loader, df_util, abas_lista, dias_pt, opts_sv_e, opts_hor_e)
    else:
        _mostrar_editor_1dia(data_loader, df_util, abas_lista, dias_pt, opts_sv_e, opts_hor_e, opts_ind_e, opts_rad_e, opts_gir_e, opts_vtr_e, adicionar_lista_fn)


def _mostrar_editor_2dias(data_loader, df_util, abas_lista, dias_pt, opts_sv_e, opts_hor_e) -> None:
    """Editor unificado para 2 dias."""
    aba_1, info_1 = abas_lista[0]
    aba_2, info_2 = abas_lista[1]
    d1, d2 = info_1["data"], info_2["data"]
    label_1 = f"Serviço {d1.strftime('%d/%m')} {dias_pt[d1.weekday()]}"
    label_h1 = f"Horário {d1.strftime('%d/%m')}"
    label_2 = f"Serviço {d2.strftime('%d/%m')} {dias_pt[d2.weekday()]}"
    label_h2 = f"Horário {d2.strftime('%d/%m')}"
    mapa_1 = {r["id"]: r for r in info_1["linhas"]}
    mapa_2 = {r["id"]: r for r in info_2["linhas"]}

    linhas_uni = []
    for mid in [r["id"] for r in info_1["linhas"]]:
        r1 = mapa_1.get(mid, {})
        r2 = mapa_2.get(mid, {})
        linhas_uni.append({
            "id": mid, "nome": r1.get("nome", ""),
            label_1: r1.get("serviço", ""), label_h1: r1.get("horário", ""),
            label_2: r2.get("serviço", ""), label_h2: r2.get("horário", ""),
        })

    df_uni = pd.DataFrame(linhas_uni)
    df_editado_uni = st.data_editor(
        df_uni,
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
            "nome": st.column_config.TextColumn("Nome", disabled=True, width="small"),
            label_1: st.column_config.SelectboxColumn(label_1, options=st.session_state.get("opts_sv_e", opts_sv_e), width="medium"),
            label_h1: st.column_config.SelectboxColumn(label_h1, options=opts_hor_e, width="small"),
            label_2: st.column_config.SelectboxColumn(label_2, options=st.session_state.get("opts_sv_e", opts_sv_e), width="medium"),
            label_h2: st.column_config.SelectboxColumn(label_h2, options=opts_hor_e, width="small"),
        },
        hide_index=True, use_container_width=True,
        key="editor_unificado", num_rows="dynamic",
        height=min(50 + len(df_uni) * 35, 2000),
    )

    if st.button("✅ GUARDAR ALTERAÇÕES", use_container_width=True, type="primary", key="btn_guardar_editar"):
        with st.spinner("A guardar..."):
            try:
                rows_1, rows_2 = [], []
                for _, row_u in df_editado_uni.iterrows():
                    mid = str(row_u["id"])
                    r1o = dict(mapa_1.get(mid, {"id": mid, "nome": "", "serviço": "", "horário": "", "indicativo": "", "rádio": "", "giro": "", "observações": ""}))
                    r2o = dict(mapa_2.get(mid, {"id": mid, "nome": "", "serviço": "", "horário": "", "indicativo": "", "rádio": "", "giro": "", "observações": ""}))
                    r1o["id"] = mid; r2o["id"] = mid
                    r1o["serviço"] = str(row_u.get(label_1) or "")
                    r1o["horário"] = str(row_u.get(label_h1) or "")
                    r2o["serviço"] = str(row_u.get(label_2) or "")
                    r2o["horário"] = str(row_u.get(label_h2) or "")
                    rows_1.append(r1o); rows_2.append(r2o)
                _guardar_sheets(data_loader, {aba_1: pd.DataFrame(rows_1), aba_2: pd.DataFrame(rows_2)})
                data_loader.limpar_cache()
                del st.session_state["editar_escala"]
                st.session_state.pop("editar_escala_original", None)
                st.success("✅ Guardado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")


def _mostrar_editor_1dia(data_loader, df_util, abas_lista, dias_pt, opts_sv_e, opts_hor_e, opts_ind_e, opts_rad_e, opts_gir_e, opts_vtr_e, adicionar_lista_fn) -> None:
    """Editor para 1 dia."""
    aba_e, info_e = abas_lista[0]
    d_e = info_e["data"]
    st.markdown(f"**📅 {d_e.strftime('%d/%m/%Y')} -- {dias_pt[d_e.weekday()]}**")
    st.caption("💡 O campo ID aceita vários militares separados por `;` (ex: `507;1185`). Podes adicionar ou remover linhas.")

    df_s = pd.DataFrame(info_e["linhas"])
    _ord_col = {"ID": "id", "Nome": "nome", "Serviço": "serviço", "Horário": "horário"}.get(st.session_state.get("ord_editar", "ID"), "id")
    if _ord_col in df_s.columns:
        if _ord_col == "id":
            df_s = df_s.sort_values("id", key=lambda x: pd.to_numeric(x, errors="coerce").fillna(999999)).reset_index(drop=True)
        else:
            df_s = df_s.sort_values(_ord_col, key=lambda x: x.astype(str).str.lower()).reset_index(drop=True)

    df_editado_s = st.data_editor(
        df_s,
        column_config={
            "id": st.column_config.TextColumn("ID(s)", width="small"),
            "nome": st.column_config.TextColumn("Nome", disabled=True, width="small"),
            "serviço": st.column_config.SelectboxColumn("Serviço", options=st.session_state.get("opts_sv_e", opts_sv_e), width="medium"),
            "horário": st.column_config.SelectboxColumn("Horário", options=opts_hor_e, width="small"),
            "indicativo": st.column_config.SelectboxColumn("Indicativo", options=opts_ind_e, width="small"),
            "rádio": st.column_config.SelectboxColumn("Rádio", options=opts_rad_e, width="small"),
            "giro": st.column_config.SelectboxColumn("Giro", options=opts_gir_e, width="small"),
            "viatura": st.column_config.SelectboxColumn("Viatura", options=opts_vtr_e, width="small"),
            "observações": st.column_config.TextColumn("Observações", width="medium"),
        },
        hide_index=True, use_container_width=True,
        key=f"editor_{aba_e}", num_rows="dynamic",
        height=min(50 + len(df_s) * 35, 2000),
    )

    if st.button("✅ GUARDAR ALTERAÇÕES", use_container_width=True, type="primary", key="btn_guardar_editar"):
        with st.spinner("A guardar..."):
            try:
                for _, row_e in df_editado_s.iterrows():
                    for campo, col in [("Horário", "horário"), ("Indicativo", "indicativo"), ("Rádio", "rádio"), ("Giro", "giro"), ("Viatura", "viatura")]:
                        val = str(row_e.get(col, "") or "").strip()
                        if val:
                            opts = {"Horário": opts_hor_e, "Indicativo": opts_ind_e, "Rádio": opts_rad_e, "Giro": opts_gir_e, "Viatura": opts_vtr_e}[campo]
                            if val not in opts:
                                adicionar_lista_fn(campo, val)
                _guardar_sheets(data_loader, {aba_e: df_editado_s})
                data_loader.limpar_cache()
                del st.session_state["editar_escala"]
                st.session_state.pop("editar_escala_original", None)
                st.success("✅ Guardado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")


# ─────────────────────────────────────────
# TAB 3: Remunerados
# ─────────────────────────────────────────

def _render_tab_remunerados(
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    feriados: Set,
) -> None:
    """Renderiza a tab de gestão de remunerados."""
    st.markdown("#### 💶 Remunerados")

    df_ord_rem = data_loader.carregar_ordem_remunerados()
    if df_ord_rem.empty:
        st.error("Aba 'ordem_remunerados' não encontrada ou vazia.")
        st.stop()

    # ── Formulário de nomeação ──
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    with col_r1:
        d_rem = st.date_input("Data:", format="DD/MM/YYYY", key="d_rem")
    with col_r2:
        tab_rem_sel = st.selectbox("Tabela:", ["A", "B"], key="tab_rem_sel")
    with col_r3:
        hor_rem = st.text_input("Horário:", placeholder="ex: 09-13", key="hor_rem")
    with col_r4:
        n_rem = st.number_input("Nº militares:", min_value=1, max_value=10, value=2, key="n_rem")

    obs_rem = st.text_input("Observação do remunerado:", placeholder="ex: Reg. Trânsito - Rua X", key="obs_rem")

    if st.button("🔍 Calcular Nomeação", use_container_width=True, key="btn_calc_rem"):
        _calcular_nomeacao(data_loader, df_util, df_ferias, feriados, df_ord_rem, d_rem, tab_rem_sel, hor_rem, n_rem, obs_rem)

    # Confirmar nomeação
    if "rem_nomeados" in st.session_state:
        _confirmar_nomeacao(data_loader, df_util)

    # Gestão de remunerados nomeados
    _render_gestao_remunerados(data_loader, df_util, df_ferias, feriados, df_ord_rem)


def _calcular_nomeacao(data_loader, df_util, df_ferias, feriados, df_ord_rem, d_rem, tab_rem_sel, hor_rem, n_rem, obs_rem) -> None:
    """Calcula a nomeação de militares para remunerado."""
    aba_rem = d_rem.strftime("%d-%m")
    sh_rem = get_sheet()
    df_dia_rem = data_loader.carregar_data_direto(sh_rem, aba_rem)
    data_str = d_rem.strftime("%d/%m/%Y")

    is_fds = d_rem.weekday() >= 5
    if tab_rem_sel == "B":
        col_total, col_ultimo = "total_ano_b", "ultimo_b"
    elif is_fds:
        col_total, col_ultimo = "total_ano_a_fds", "ultimo_a_fds"
    else:
        col_total, col_ultimo = "total_ano_a_semana", "ultimo_a_semana"

    hi_rem, hf_rem, horas_rem = None, None, 0
    if hor_rem and "-" in hor_rem:
        hi_rem, hf_rem = _parse_horario(hor_rem)
        if hi_rem is not None and hf_rem is not None:
            horas_rem = round((hf_rem - hi_rem) / 60, 1) if hf_rem > hi_rem else round((1440 - hi_rem + hf_rem) / 60, 1)

    for col in ["disponivel", "voluntario", "folga", "prescinde_descanso", col_total, col_ultimo]:
        if col not in df_ord_rem.columns:
            df_ord_rem[col] = ""

    for bcol in ["disponivel", "voluntario", "folga", "prescinde_descanso"]:
        df_ord_rem[bcol] = df_ord_rem[bcol].astype(str).str.strip().str.lower().isin(["true", "1", "sim", "yes"])

    df_ord_rem[col_total] = pd.to_numeric(df_ord_rem[col_total], errors="coerce").fillna(0)
    df_ord_rem[col_ultimo] = pd.to_datetime(df_ord_rem[col_ultimo], dayfirst=True, errors="coerce")

    def _sobreposicao(h1_ini, h1_fim, h2_ini, h2_fim):
        if None in (h1_ini, h1_fim, h2_ini, h2_fim):
            return False
        e1 = h1_fim if h1_fim > h1_ini else h1_fim + 1440
        e2 = h2_fim if h2_fim > h2_ini else h2_fim + 1440
        return h1_ini < e2 and h2_ini < e1

    def _verif_descanso(hi_s, hf_s, hi_n, hf_n):
        if None in (hi_s, hf_s, hi_n, hf_n):
            return True
        desc1 = (hi_n + 1440 - (hf_s if hf_s > hi_s else hf_s + 1440)) % 1440
        desc2 = (hi_s + 1440 - (hf_n if hf_n > hi_n else hf_n + 1440)) % 1440
        return desc1 >= 480 and desc2 >= 480

    _IMP = r"ferias|licen|convalesc|dilig|tribunal|inquer|secretaria|fcaa|cter|adm"
    servicos_dia: Dict = {}
    militares_com_servico: set = set()
    militares_de_folga: set = set()
    if not df_dia_rem.empty:
        for _, row_sd in df_dia_rem.iterrows():
            mid_sd = str(row_sd["id"]).strip()
            if not mid_sd:
                continue
            serv_norm = norm(str(row_sd.get("serviço", "")))
            if "folga semanal" in serv_norm or "folga complementar" in serv_norm:
                militares_de_folga.add(mid_sd)
            elif re.search(_IMP, serv_norm):
                pass
            elif not re.search(r"remu|grat", serv_norm):
                hor_sd = str(row_sd.get("horário", "")).strip()
                hi_sd, hf_sd = _parse_horario(hor_sd)
                servicos_dia.setdefault(mid_sd, []).append((hi_sd, hf_sd, str(row_sd.get("serviço", ""))))
                militares_com_servico.add(mid_sd)

    ausentes_dia: set = set()
    if not df_dia_rem.empty:
        aus_mask = df_dia_rem["serviço"].apply(norm).str.contains(_IMP, na=False)
        for mid_a in df_dia_rem[aus_mask]["id"].astype(str).str.strip().tolist():
            if mid_a:
                ausentes_dia.add(mid_a)
    for _, row_u in df_ord_rem.iterrows():
        mid_u = str(row_u.get("id", "")).strip()
        if mid_u and data_loader.militar_de_ferias(mid_u, d_rem, df_ferias, feriados):
            ausentes_dia.add(mid_u)

    df_disp = df_ord_rem[df_ord_rem["disponivel"] == True].copy()
    df_disp_sorted = df_disp.sort_values([col_ultimo, col_total], ascending=[True, True], na_position="first")

    def _pode_nomear(row_r, mid_r, skip):
        if mid_r in ausentes_dia:
            skip.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — ausente")
            return False
        for hi_s, hf_s, serv_s in servicos_dia.get(mid_r, []):
            if _sobreposicao(hi_rem, hf_rem, hi_s, hf_s):
                skip.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — sobreposição com {serv_s}")
                return False
        if not bool(row_r["prescinde_descanso"]):
            for hi_s, hf_s, serv_s in servicos_dia.get(mid_r, []):
                if not _verif_descanso(hi_s, hf_s, hi_rem, hf_rem):
                    skip.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — menos de 8h descanso com {serv_s}")
                    return False
        return True

    nomeados, avisos, skipped = [], [], []

    # GRUPO 1: voluntários com serviço normal ou disponíveis
    for _, row_r in df_disp_sorted.iterrows():
        if len(nomeados) >= n_rem:
            break
        mid_r = str(row_r.get("id", "")).strip()
        if not mid_r or mid_r in [n["id"] for n in nomeados]:
            continue
        if not bool(row_r["voluntario"]):
            continue
        if mid_r in ausentes_dia:
            skipped.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — ausente")
            continue
        if mid_r in militares_de_folga:
            continue
        if _pode_nomear(row_r, mid_r, skipped):
            grupo = "Voluntário c/ serviço" if mid_r in militares_com_servico else "Voluntário disponível"
            nomeados.append({"id": mid_r, "nome": _get_nome_curto(df_util, mid_r), "grupo": grupo, "total": int(row_r[col_total])})

    # GRUPO 2: voluntários de folga
    for _, row_r in df_disp_sorted.iterrows():
        if len(nomeados) >= n_rem:
            break
        mid_r = str(row_r.get("id", "")).strip()
        if not mid_r or mid_r in [n["id"] for n in nomeados]:
            continue
        if not bool(row_r["voluntario"]) or mid_r not in militares_de_folga:
            continue
        if mid_r in ausentes_dia:
            skipped.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — ausente")
            continue
        if not bool(row_r["folga"]):
            skipped.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — voluntário de folga mas folga=Não")
            continue
        nomeados.append({"id": mid_r, "nome": _get_nome_curto(df_util, mid_r), "grupo": "Voluntário de folga", "total": int(row_r[col_total])})

    # GRUPO 3: não voluntários
    for _, row_r in df_disp_sorted.iterrows():
        if len(nomeados) >= n_rem:
            break
        mid_r = str(row_r.get("id", "")).strip()
        if not mid_r or mid_r in [n["id"] for n in nomeados]:
            continue
        if bool(row_r["voluntario"]):
            continue
        if mid_r in ausentes_dia:
            skipped.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — ausente")
            continue
        if mid_r in militares_de_folga:
            skipped.append(f"{_get_nome_curto(df_util, mid_r)} ({mid_r}) — não voluntário de folga, não nomeável")
            continue
        if not _pode_nomear(row_r, mid_r, skipped):
            continue
        avisos.append(f"⚠️ **{_get_nome_curto(df_util, mid_r)} ({mid_r})** nomeado fora da lista de voluntários")
        nomeados.append({"id": mid_r, "nome": _get_nome_curto(df_util, mid_r), "grupo": "Não voluntário", "total": int(row_r[col_total])})

    tipo_col = "Tabela B" if tab_rem_sel == "B" else ("Tabela A — Fim de Semana" if d_rem.weekday() >= 5 else "Tabela A — Semana")
    if nomeados:
        st.success(f"✅ {len(nomeados)} militar(es) nomeado(s) · {tipo_col} · {hor_rem}:")
        for n in nomeados:
            st.markdown(f"- **{n['nome']} ({n['id']})** — {n['grupo']} | horas acumuladas: **{n['total']}h**")
        for av in avisos:
            st.warning(av)
        if skipped:
            with st.expander(f"ℹ️ {len(skipped)} militar(es) ignorado(s)"):
                for s in skipped:
                    st.caption(s)
        st.session_state["rem_nomeados"] = {
            "nomeados": nomeados, "data": data_str, "aba": aba_rem,
            "horario": hor_rem, "tabela": tab_rem_sel, "observacao": obs_rem,
            "col_total": col_total, "col_ultimo": col_ultimo, "horas_rem": horas_rem,
        }
    else:
        st.warning("Não foi possível nomear militares suficientes.")
        if skipped:
            with st.expander("ℹ️ Militares ignorados"):
                for s in skipped:
                    st.caption(s)


def _confirmar_nomeacao(data_loader, df_util) -> None:
    """Confirma a nomeação e escreve na escala."""
    dados_rem = st.session_state["rem_nomeados"]
    st.info(f"📋 Pronto a confirmar: {', '.join(n['nome'] for n in dados_rem['nomeados'])} — {dados_rem['horario']} — {dados_rem['data']}")

    if st.button("✅ CONFIRMAR NOMEAÇÃO E ESCREVER NA ESCALA", use_container_width=True, type="primary", key="btn_conf_rem"):
        try:
            sh = get_sheet()
            ws_dia = sh.worksheet(dados_rem["aba"])
            ids_nomeados = [n["id"] for n in dados_rem["nomeados"]]
            ws_dia.append_row([
                ", ".join(ids_nomeados),
                f"Svç Remunerado - Tabela {dados_rem['tabela']}",
                dados_rem["horario"], "", "", "",
                dados_rem["observacao"],
            ])

            # Atualizar horas e data
            ws_ord = sh.worksheet("ordem_remunerados")
            todos_vals = ws_ord.get_all_values()
            hdrs_ord = [_nc(h) for h in todos_vals[0]]
            col_id_idx = hdrs_ord.index("id") if "id" in hdrs_ord else 0
            col_tot_idx = hdrs_ord.index(dados_rem["col_total"]) if dados_rem["col_total"] in hdrs_ord else None
            col_ult_idx = hdrs_ord.index(dados_rem["col_ultimo"]) if dados_rem["col_ultimo"] in hdrs_ord else None
            horas_add = dados_rem.get("horas_rem", 0) or 1

            upds = []
            for i, row_o in enumerate(todos_vals[1:], start=2):
                mid_o = str(row_o[col_id_idx]).strip() if col_id_idx < len(row_o) else ""
                if mid_o in ids_nomeados:
                    if col_tot_idx is not None:
                        total_atual = int(str(row_o[col_tot_idx]).strip() or 0) if col_tot_idx < len(row_o) else 0
                        cl = chr(ord("A") + col_tot_idx)
                        upds.append({"range": f"{cl}{i}", "values": [[total_atual + horas_add]]})
                    if col_ult_idx is not None:
                        cl2 = chr(ord("A") + col_ult_idx)
                        upds.append({"range": f"{cl2}{i}", "values": [[dados_rem["data"]]]})
            if upds:
                ws_ord.batch_update(upds)

            # Histórico
            ws_hist = sh.worksheet("historico_remunerados")
            for mid_h in ids_nomeados:
                ws_hist.append_row([mid_h, dados_rem["data"], dados_rem["col_ultimo"]])

            data_loader.limpar_cache()
            del st.session_state["rem_nomeados"]
            st.success("✅ Nomeação confirmada e escala atualizada!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")


def _repor_data_ultimo(ws_ord, hdrs, ws_hist, mid, col_ult, data_cancelada) -> None:
    """Após cancelar/substituir, repõe a data do último remunerado do histórico."""
    hist_vals = ws_hist.get_all_values()
    if len(hist_vals) <= 1:
        data_repor = ""
    else:
        linhas_mil = [
            row for row in hist_vals[1:]
            if len(row) >= 3 and str(row[0]).strip() == mid
            and str(row[2]).strip() == col_ult
            and str(row[1]).strip() != data_cancelada
        ]
        if not linhas_mil:
            data_repor = ""
        else:
            datas_r = []
            for lr in linhas_mil:
                try:
                    datas_r.append((datetime.strptime(lr[1].strip(), "%d/%m/%Y"), lr[1].strip()))
                except Exception:
                    pass
            data_repor = max(datas_r, key=lambda x: x[0])[1] if datas_r else ""

    col_ult_idx = hdrs.index(col_ult) if col_ult in hdrs else None
    col_id_idx = hdrs.index("id") if "id" in hdrs else 0
    if col_ult_idx is None:
        return
    ord_vals = ws_ord.get_all_values()
    upds = []
    for i_r, row_r in enumerate(ord_vals[1:], start=2):
        mid_r = str(row_r[col_id_idx]).strip() if col_id_idx < len(row_r) else ""
        if mid_r == mid:
            cl = chr(ord("A") + col_ult_idx)
            upds.append({"range": f"{cl}{i_r}", "values": [[data_repor]]})
            break
    if upds:
        ws_ord.batch_update(upds)


def _render_gestao_remunerados(data_loader, df_util, df_ferias, feriados, df_ord_rem) -> None:
    """Renderiza a secção de gestão de remunerados nomeados."""
    st.divider()
    st.markdown("#### 📋 Remunerados Nomeados (hoje em diante)")

    col_gest1, col_gest2 = st.columns([3, 1])
    with col_gest2:
        if st.button("🔄 Carregar lista", key="btn_carregar_gest", use_container_width=True):
            st.session_state["gest_carregado"] = True

    if not st.session_state.get("gest_carregado"):
        st.info("Clica em **🔄 Carregar lista** para ver os remunerados nomeados.")
        return

    hoje = date.today()
    abas_existentes = data_loader.carregar_lista_abas()
    remunerados_lista: list = []

    with st.spinner("A carregar remunerados..."):
        sh_gest = get_sheet()
        for delta in range(15):
            d_g = hoje + timedelta(days=delta)
            aba_g = d_g.strftime("%d-%m")
            if aba_g not in abas_existentes:
                continue
            try:
                vals_g = sh_gest.worksheet(aba_g).get_all_values()
                if not vals_g:
                    continue
                hdrs_g = [_nc(c) for c in vals_g[0]]
                idx_id = hdrs_g.index("id") if "id" in hdrs_g else 0
                idx_serv = hdrs_g.index("servico") if "servico" in hdrs_g else 1
                idx_hor = hdrs_g.index("horario") if "horario" in hdrs_g else 2
                idx_obs = hdrs_g.index("observacoes") if "observacoes" in hdrs_g else 6
                for i, row_g in enumerate(vals_g[1:], start=2):
                    if len(row_g) <= idx_serv:
                        continue
                    serv_g = norm(str(row_g[idx_serv]))
                    if "remunerado" in serv_g:
                        tabela_g = "A" if "tabela a" in serv_g else ("B" if "tabela b" in serv_g else "?")
                        remunerados_lista.append({
                            "data": d_g.strftime("%d/%m/%Y"), "data_obj": d_g,
                            "aba": aba_g, "linha_idx": i,
                            "ids": str(row_g[idx_id]).strip() if idx_id < len(row_g) else "",
                            "horario": str(row_g[idx_hor]).strip() if idx_hor < len(row_g) else "",
                            "tabela": tabela_g,
                            "obs": str(row_g[idx_obs]).strip() if idx_obs < len(row_g) else "",
                        })
            except Exception:
                continue

    if not remunerados_lista:
        st.info("Não há remunerados nomeados nos próximos 15 dias.")
        return

    for rem_g in remunerados_lista:
        nomes_g = []
        for mid_g in rem_g["ids"].replace(";", ",").split(","):
            mid_g = mid_g.strip()
            if mid_g:
                nomes_g.append(f"{_get_nome_curto(df_util, mid_g)} ({mid_g})")
        label_g = f"📅 {rem_g['data']} | Tabela {rem_g['tabela']} | {rem_g['horario']} | {', '.join(nomes_g)}"
        if rem_g["obs"]:
            label_g += f" | {rem_g['obs']}"

        with st.expander(label_g):
            st.markdown(f"**Militares:** {', '.join(nomes_g)}")
            st.markdown(f"**Horário:** {rem_g['horario']} | **Tabela:** {rem_g['tabela']}")
            if rem_g["obs"]:
                st.markdown(f"**Obs:** {rem_g['obs']}")

            col_ga, col_gb = st.columns(2)
            chave_base = f"{rem_g['aba']}_{rem_g['linha_idx']}"

            with col_ga:
                if st.button("🗑️ Cancelar remunerado", key=f"canc_{chave_base}", use_container_width=True):
                    st.session_state[f"gest_acao_{chave_base}"] = "cancelar"
            with col_gb:
                if st.button("🔄 Substituir militar", key=f"subs_{chave_base}", use_container_width=True):
                    st.session_state[f"gest_acao_{chave_base}"] = "substituir"

            acao = st.session_state.get(f"gest_acao_{chave_base}")

            if acao == "cancelar":
                _cancelar_remunerado(data_loader, df_util, rem_g, chave_base)
            elif acao == "substituir":
                _substituir_remunerado(data_loader, df_util, df_ferias, feriados, df_ord_rem, rem_g, chave_base)


def _cancelar_remunerado(data_loader, df_util, rem_g, chave_base) -> None:
    """Cancela um remunerado e subtrai horas."""
    st.warning("Tens a certeza que queres cancelar este remunerado? As horas serão subtraídas.")
    if st.button("✅ Confirmar cancelamento", key=f"conf_canc_{chave_base}", use_container_width=True, type="primary"):
        try:
            sh = get_sheet()
            ws = sh.worksheet(rem_g["aba"])
            ws.delete_rows(rem_g["linha_idx"])

            is_fds = rem_g["data_obj"].weekday() >= 5
            if rem_g["tabela"] == "B":
                col_tot = "total_ano_b"
            elif is_fds:
                col_tot = "total_ano_a_fds"
            else:
                col_tot = "total_ano_a_semana"

            horas = 0
            if "-" in rem_g["horario"]:
                try:
                    hi = int(rem_g["horario"].split("-")[0].strip())
                    hf = int(rem_g["horario"].split("-")[1].strip())
                    horas = hf - hi if hf > hi else (24 - hi + hf)
                except Exception:
                    pass

            ws_ord = sh.worksheet("ordem_remunerados")
            vals_ord = ws_ord.get_all_values()
            hdrs = [_nc(h) for h in vals_ord[0]]
            col_id = hdrs.index("id") if "id" in hdrs else 0
            col_tot_idx = hdrs.index(col_tot) if col_tot in hdrs else None
            ids = [x.strip() for x in rem_g["ids"].replace(";", ",").split(",") if x.strip()]

            upds = []
            for i, row in enumerate(vals_ord[1:], start=2):
                mid = str(row[col_id]).strip() if col_id < len(row) else ""
                if mid in ids and col_tot_idx is not None:
                    tot = max(0, int(str(row[col_tot_idx]).strip() or 0) - horas)
                    cl = chr(ord("A") + col_tot_idx)
                    upds.append({"range": f"{cl}{i}", "values": [[tot]]})
            if upds:
                ws_ord.batch_update(upds)

            # Repor data último
            if rem_g["tabela"] == "B":
                col_ult = "ultimo_b"
            elif is_fds:
                col_ult = "ultimo_a_fds"
            else:
                col_ult = "ultimo_a_semana"

            hdrs2 = [_nc(h) for h in vals_ord[0]]
            ws_hist = sh.worksheet("historico_remunerados")
            hist_vals = ws_hist.get_all_values()
            data_cancel = rem_g["data"].strip() if isinstance(rem_g["data"], str) else rem_g["data_obj"].strftime("%d/%m/%Y")
            linhas_apagar = []
            for i_hc, row_hc in enumerate(hist_vals[1:], start=2):
                if (len(row_hc) >= 3 and str(row_hc[0]).strip() in ids and str(row_hc[1]).strip() == data_cancel and str(row_hc[2]).strip() == col_ult):
                    linhas_apagar.append(i_hc)
            for ln in reversed(linhas_apagar):
                ws_hist.delete_rows(ln)

            for mid in ids:
                _repor_data_ultimo(ws_ord, hdrs2, ws_hist, mid, col_ult, data_cancel)

            data_loader.limpar_cache()
            del st.session_state[f"gest_acao_{chave_base}"]
            st.success("✅ Remunerado cancelado e horas subtraídas.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")


def _substituir_remunerado(data_loader, df_util, df_ferias, feriados, df_ord_rem, rem_g, chave_base) -> None:
    """Substitui um militar num remunerado."""
    ids_atuais = [x.strip() for x in rem_g["ids"].replace(";", ",").split(",") if x.strip()]
    nomes_atuais = {mid: _get_nome_curto(df_util, mid) for mid in ids_atuais}

    mid_sair = st.selectbox(
        "Militar que sai:", ids_atuais,
        format_func=lambda x: f"{nomes_atuais.get(x, x)} ({x})",
        key=f"sair_{chave_base}",
    )

    is_fds = rem_g["data_obj"].weekday() >= 5
    if rem_g["tabela"] == "B":
        col_tot, col_ult = "total_ano_b", "ultimo_b"
    elif is_fds:
        col_tot, col_ult = "total_ano_a_fds", "ultimo_a_fds"
    else:
        col_tot, col_ult = "total_ano_a_semana", "ultimo_a_semana"

    df_dia_s = data_loader.carregar_data(rem_g["aba"])
    _IMP = r"ferias|licen|convalesc|dilig|tribunal|inquer|secretaria|fcaa|cter|adm"
    ausentes: set = set()
    militares_folga: set = set()
    servicos_s: Dict = {}
    if not df_dia_s.empty:
        for _, rs in df_dia_s.iterrows():
            mid_s = str(rs["id"]).strip()
            if not mid_s:
                continue
            sn = norm(str(rs.get("serviço", "")))
            if re.search(_IMP, sn):
                ausentes.add(mid_s)
            elif "folga semanal" in sn or "folga complementar" in sn:
                militares_folga.add(mid_s)
            elif not re.search(r"remu|grat", sn):
                hs = str(rs.get("horário", "")).strip()
                hi_s, hf_s = None, None
                if "-" in hs:
                    try:
                        hi_s = int(hs.split("-")[0])
                        hf_s = int(hs.split("-")[1])
                    except Exception:
                        pass
                servicos_s.setdefault(mid_s, []).append((hi_s, hf_s, str(rs.get("serviço", ""))))

    hi_rem, hf_rem = None, None
    if "-" in rem_g["horario"]:
        try:
            hi_rem = int(rem_g["horario"].split("-")[0].strip())
            hf_rem = int(rem_g["horario"].split("-")[1].strip())
        except Exception:
            pass

    # Elegíveis
    elegiveis = []
    df_disp = df_ord_rem[df_ord_rem["disponivel"] == True].copy()
    df_disp[col_tot] = pd.to_numeric(df_disp[col_tot], errors="coerce").fillna(0)
    if col_ult not in df_disp.columns:
        df_disp[col_ult] = pd.NaT
    else:
        df_disp[col_ult] = pd.to_datetime(df_disp[col_ult], dayfirst=True, errors="coerce")
    df_disp = df_disp.sort_values([col_ult, col_tot], ascending=[True, True], na_position="first")

    for _, row_s in df_disp.iterrows():
        mid_s = str(row_s.get("id", "")).strip()
        if not mid_s or mid_s in ids_atuais or mid_s in ausentes:
            continue
        is_vol = bool(row_s["voluntario"])
        aceita_folga = bool(row_s["folga"])
        if mid_s in militares_folga and (not is_vol or not aceita_folga):
            continue
        sobreposto = False
        for hi_x, hf_x, _ in servicos_s.get(mid_s, []):
            if hi_rem and hf_rem and hi_x and hf_x:
                def _sm(h, b=0):
                    return h * 60 + (1440 if h < b else 0)
                if _sm(hi_rem) < _sm(hf_rem, hi_rem) and _sm(hi_x) < _sm(hf_x, hi_x):
                    if _sm(hi_rem) < _sm(hf_x, hi_x) and _sm(hi_x) < _sm(hf_rem, hi_rem):
                        sobreposto = True
                        break
        if sobreposto:
            continue
        elegiveis.append({"id": mid_s, "nome": _get_nome_curto(df_util, mid_s), "voluntario": is_vol, "total": int(row_s[col_tot])})

    if elegiveis:
        sugerido = elegiveis[0]
        st.info(f"💡 Sugerido: **{sugerido['nome']} ({sugerido['id']})** — {sugerido['total']}h acumuladas")
        opcoes = [f"{e['nome']} ({e['id']}) — {e['total']}h" for e in elegiveis]
        escolha = st.selectbox("Confirmar ou escolher outro:", opcoes, key=f"esc_{chave_base}")
        mid_entra = elegiveis[opcoes.index(escolha)]["id"]
    else:
        st.warning("Não há substitutos elegíveis disponíveis.")
        mid_entra = None

    if mid_entra and st.button("✅ Confirmar substituição", key=f"conf_subs_{chave_base}", use_container_width=True, type="primary"):
        try:
            sh = get_sheet()
            ws = sh.worksheet(rem_g["aba"])
            ids_novos = [mid_entra if x == mid_sair else x for x in ids_atuais]
            ws.update_cell(rem_g["linha_idx"], 1, ", ".join(ids_novos))

            horas = 0
            if "-" in rem_g["horario"]:
                try:
                    hi = int(rem_g["horario"].split("-")[0].strip())
                    hf = int(rem_g["horario"].split("-")[1].strip())
                    horas = hf - hi if hf > hi else (24 - hi + hf)
                except Exception:
                    pass

            ws_ord = sh.worksheet("ordem_remunerados")
            vals_ord = ws_ord.get_all_values()
            hdrs = [_nc(h) for h in vals_ord[0]]
            col_id = hdrs.index("id") if "id" in hdrs else 0
            col_tot_idx = hdrs.index(col_tot) if col_tot in hdrs else None
            upds = []
            for i, row_ss in enumerate(vals_ord[1:], start=2):
                mid_ss = str(row_ss[col_id]).strip() if col_id < len(row_ss) else ""
                if col_tot_idx is None:
                    continue
                tot = int(str(row_ss[col_tot_idx]).strip() or 0) if col_tot_idx < len(row_ss) else 0
                cl = chr(ord("A") + col_tot_idx)
                if mid_ss == mid_sair:
                    upds.append({"range": f"{cl}{i}", "values": [[max(0, tot - horas)]]})
                elif mid_ss == mid_entra:
                    upds.append({"range": f"{cl}{i}", "values": [[tot + horas]]})
            if upds:
                ws_ord.batch_update(upds)

            # Histórico
            hdrs2 = [_nc(h) for h in vals_ord[0]]
            ws_hist = sh.worksheet("historico_remunerados")
            hist_vals = ws_hist.get_all_values()
            data_subs = rem_g["data"].strip() if isinstance(rem_g["data"], str) else rem_g["data_obj"].strftime("%d/%m/%Y")
            linhas_apagar = []
            for i_hs, row_hs in enumerate(hist_vals[1:], start=2):
                if (len(row_hs) >= 3 and str(row_hs[0]).strip() == mid_sair and str(row_hs[1]).strip() == data_subs and str(row_hs[2]).strip() == col_ult):
                    linhas_apagar.append(i_hs)
            for ln in reversed(linhas_apagar):
                ws_hist.delete_rows(ln)
            _repor_data_ultimo(ws_ord, hdrs2, ws_hist, mid_sair, col_ult, data_subs)

            ws_hist.append_row([mid_entra, data_subs, col_ult])
            col_ult_idx = hdrs2.index(col_ult) if col_ult in hdrs2 else None
            if col_ult_idx is not None:
                ord_vals2 = ws_ord.get_all_values()
                col_id2 = hdrs2.index("id") if "id" in hdrs2 else 0
                for i2, row_s2 in enumerate(ord_vals2[1:], start=2):
                    if str(row_s2[col_id2]).strip() == mid_entra:
                        ws_ord.update_cell(i2, col_ult_idx + 1, data_subs)
                        break

            data_loader.limpar_cache()
            del st.session_state[f"gest_acao_{chave_base}"]
            st.success(f"✅ {nomes_atuais.get(mid_sair, mid_sair)} substituído por {_get_nome_curto(df_util, mid_entra)}.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")


# ─────────────────────────────────────────
# Processamento de confirmação multi‑dia
# ─────────────────────────────────────────

def _processar_confirmacao_multi(data_loader) -> None:
    """Processa confirmação de escala gerada (executar antes dos widgets)."""
    if not (st.session_state.get("confirmar_escala", False) and "escala_gerada_multi" in st.session_state):
        return

    st.session_state["confirmar_escala"] = False
    dados_multi = st.session_state["escala_gerada_multi"]
    resultados = dados_multi["resultados"]
    ordem_headers = dados_multi["ordem_headers"]

    try:
        sh = get_sheet()
        for idx_res, res in enumerate(resultados):
            if idx_res > 0:
                time.sleep(8)
            aba_r = res["aba"]
            escalados_r = res["escalados"]
            ordem_r = res["ordem_atualizada"]
            data_r = res["data"]

            for _t in range(3):
                try:
                    ws_dia = sh.worksheet(aba_r)
                    break
                except Exception as _e:
                    if _t < 2:
                        time.sleep(20)
                    else:
                        raise _e

            todas_linhas = ws_dia.get_all_values()
            hdrs = [h.strip().lower() for h in todas_linhas[0]]
            ix_id = hdrs.index("id") if "id" in hdrs else 0
            ix_serv = hdrs.index("serviço") if "serviço" in hdrs else 1
            ix_hor = hdrs.index("horário") if "horário" in hdrs else 2

            agrupados = defaultdict(list)
            simples = []
            for mid, serv, hor in escalados_r:
                if serv == "Patrulha Ocorrências":
                    agrupados[(serv, hor)].append(mid)
                else:
                    simples.append((mid, serv, hor))

            emap = {}
            for (serv, hor), ids in agrupados.items():
                emap[(norm(serv), hor.strip())] = ";".join(ids)
            for mid, serv, hor in simples:
                emap[(norm(serv), hor.strip())] = mid

            upds = []
            for i, row in enumerate(todas_linhas[1:], start=2):
                sc = norm(row[ix_serv].strip()) if ix_serv < len(row) else ""
                hc = str(row[ix_hor]).strip() if ix_hor < len(row) else ""
                ic = str(row[ix_id]).strip() if ix_id < len(row) else ""
                ch = (sc, hc)
                if ch in emap and not ic:
                    cl = chr(ord("A") + ix_id)
                    upds.append({"range": f"{cl}{i}", "values": [[emap[ch]]]})
                    del emap[ch]
            if upds:
                ws_dia.batch_update(upds)

            disp_r = res.get("disponiveis", [])
            if disp_r:
                ids_disp_str = ";".join(disp_r)
                for i, row in enumerate(todas_linhas[1:], start=2):
                    sc_d = norm(row[ix_serv].strip()) if ix_serv < len(row) else ""
                    if sc_d == norm("Disponíveis") or sc_d == norm("Disponiveis"):
                        cl_d = chr(ord("A") + ix_id)
                        ws_dia.update(f"{cl_d}{i}", [[ids_disp_str]])
                        break

            # Atualizar ordem_escala do dia seguinte
            nome_prox = f"ordem_escala {(data_r + timedelta(days=1)).strftime('%d-%m')}"
            abas_existentes = data_loader.carregar_lista_abas()
            _slots_map = {
                (norm("Atendimento"), "00-08"): "Atendimento 00-08",
                (norm("Atendimento"), "08-16"): "Atendimento 08-16",
                (norm("Atendimento"), "16-24"): "Atendimento 16-24",
                (norm("Patrulha Ocorrências"), "00-08"): "Patrulha Ocorrências 00-08",
                (norm("Patrulha Ocorrências"), "08-16"): "Patrulha Ocorrências 08-16",
                (norm("Patrulha Ocorrências"), "16-24"): "Patrulha Ocorrências 16-24",
                (norm("Apoio Atendimento"), "08-16"): "Apoio Atendimento 08-16",
                (norm("Apoio Atendimento"), "16-24"): "Apoio Atendimento 16-24",
            }

            ordem_base = {h: list(v) for h, v in ordem_r.items()}
            ids_auto = set(m for m, _, _ in escalados_r)
            for col_key, lista in ordem_base.items():
                for mid_p in list(ids_auto):
                    if mid_p in lista:
                        lista.remove(mid_p)
                        lista.append(mid_p)

            for row_m in todas_linhas[1:]:
                serv_m = norm(row_m[ix_serv].strip()) if ix_serv < len(row_m) else ""
                hor_m = str(row_m[ix_hor]).strip() if ix_hor < len(row_m) else ""
                id_m = str(row_m[ix_id]).strip() if ix_id < len(row_m) else ""
                if not id_m or id_m == "nan":
                    continue
                col_key_m = _slots_map.get((serv_m, hor_m))
                if not col_key_m or col_key_m not in ordem_base:
                    continue
                for mid_m in re.split(r"[;,]", id_m):
                    mid_m = mid_m.strip()
                    if not mid_m or mid_m in ids_auto:
                        continue
                    if mid_m in ordem_base[col_key_m]:
                        ordem_base[col_key_m].remove(mid_m)
                        ordem_base[col_key_m].append(mid_m)

            nova_o = [ordem_headers]
            ml = max((len(v) for v in ordem_base.values()), default=1)
            for i in range(ml):
                nova_o.append([ordem_base[h][i] if i < len(ordem_base[h]) else "" for h in ordem_headers])

            if nome_prox in abas_existentes:
                ws_prox = sh.worksheet(nome_prox)
                ws_prox.clear()
                ws_prox.update("A1", nova_o)
                ws_prox.hide()
            else:
                ws_prox = sh.add_worksheet(title=nome_prox, rows=100, cols=len(ordem_headers))
                ws_prox.update("A1", nova_o)
                ws_prox.hide()

        data_loader.limpar_cache()
        del st.session_state["escala_gerada_multi"]
        st.session_state["escala_ok"] = True
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao escrever: {e}")


# ─────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────

def render_gerar_escala(
    usuario: "Usuario",
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_trocas: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_folgas: pd.DataFrame,
    df_licencas: pd.DataFrame,
    feriados: Set,
    grupos_folga: Any = None,
    is_admin: bool = False,
) -> None:
    """Renderiza a página «Gerar Escala»."""
    st.title("⚙️ Gerar Escala Automática")
    if not is_admin:
        st.warning("Acesso restrito a administradores.")
        st.stop()

    # Processar confirmação pendente
    _processar_confirmacao_multi(data_loader)

    if st.session_state.pop("escala_ok", False):
        st.success("✅ Escala gerada e guardada com sucesso!")

    tab_auto, tab_editar, tab_rem = st.tabs(["⚙️ Escala Automática", "✏️ Editar Escala", "💶 Remunerados"])

    with tab_auto:
        _render_tab_auto(data_loader, df_util, df_ferias, df_folgas, df_licencas, feriados, grupos_folga)

    with tab_editar:
        _render_tab_editar(data_loader, df_util, df_ferias, df_licencas, feriados)

    with tab_rem:
        _render_tab_remunerados(data_loader, df_util, df_ferias, feriados)
