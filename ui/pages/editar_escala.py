"""
Página «Escala Geral» – Visualização da escala por dia.

Tabs:
  1. 📅 Escala do Dia – vista formatada por secções + PDF download
  2. 🔎 Historial por Serviço – pesquisa do último serviço de um militar (admin)
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

import pandas as pd
import streamlit as st

from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm, parse_horario as _parse_horario
from services.data_loader import DataLoader
from pdf.escala_pdf import EscalaPDF
from ui.components.filters import filtrar_secao, limpar_sem_militar


# ─────────────────────────────────────────
# Constantes de estilo
# ─────────────────────────────────────────
AZUL = "#1E3A5F"
AZUL_MED = "#C9DCF2"
AZUL_CLARO = "#E8F1FB"


# ─────────────────────────────────────────
# Helpers de renderização
# ─────────────────────────────────────────

def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or "id" not in df_util.columns:
        return mid
    row = df_util[df_util["id"].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _sec_header(titulo: str) -> str:
    """Gera HTML de cabeçalho de secção."""
    return (
        f'<div style="background:linear-gradient(135deg,{AZUL},#2B5A8C);color:white;'
        f'padding:6px 14px;border-radius:8px 8px 0 0;font-weight:700;font-size:0.85rem;'
        f'margin-top:12px">{titulo}</div>'
    )


def _render_ids_linha(grupos: Dict[str, list]) -> str:
    """Renderiza grupos de IDs em formato compacto."""
    html = f'<div style="border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;padding:8px 12px;margin-bottom:2px">'
    for serv, ids in grupos.items():
        ids_str = ", ".join(ids)
        html += f'<div style="font-size:0.82rem;margin-bottom:4px"><b>{serv}:</b> {ids_str}</div>'
    html += "</div>"
    return html


def _render_tabela(df: pd.DataFrame, esconder_servico: bool = False,
                   mostrar_extras: bool = False, excluir_cols: list = None) -> str:
    """Renderiza DataFrame como tabela HTML estilizada."""
    if df.empty:
        return ""
    excluir = set(excluir_cols or [])
    cols = []
    for c in df.columns:
        if c in excluir or c == "id":
            continue
        if c == "serviço" and esconder_servico:
            continue
        cols.append(c)

    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;border-bottom:2px solid {AZUL};"
    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;border-bottom:1px solid #dde6f7;"
    td_a = td_s + f"background:{AZUL_CLARO};"

    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;margin-bottom:2px'>"
    html += "<table style='width:100%;border-collapse:collapse'><thead><tr>"
    # Sempre mostrar id_disp como "Militar"
    html += f"<th style='{th_s}'>Militar</th>"
    for c in cols:
        label = c.replace("_", " ").title()
        html += f"<th style='{th_s}'>{label}</th>"
    html += "</tr></thead><tbody>"

    for i, (_, row) in enumerate(df.iterrows()):
        td = td_a if i % 2 == 0 else td_s
        mid = str(row.get("id_disp", row.get("id", ""))).strip()
        html += f"<tr><td style='{td}'>{mid}</td>"
        for c in cols:
            val = str(row.get(c, "")).replace("nan", "").strip()
            html += f"<td style='{td}'>{val}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


def mostrar_secao(titulo: str, df: pd.DataFrame, **kwargs) -> None:
    """Mostra uma secção se o df não estiver vazio."""
    if df.empty:
        return
    st.markdown(_sec_header(titulo), unsafe_allow_html=True)
    st.markdown(_render_tabela(df, **kwargs), unsafe_allow_html=True)


def _aplicar_trocas_df(df: pd.DataFrame, df_trocas: pd.DataFrame, data_str: str) -> pd.DataFrame:
    """Aplica trocas aprovadas ao DataFrame da escala."""
    df["id_disp"] = df["id"].astype(str)
    if df_trocas.empty:
        return df

    # Trocas normais
    tr_v = df_trocas[
        (df_trocas["data"] == data_str)
        & (df_trocas["status"] == "Aprovada")
        & (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
    ]
    mask_rem = df["serviço"].str.lower().str.contains("remu|grat", na=False)
    for _, t in tr_v.iterrows():
        m_o = (df["id"].astype(str) == str(t["id_origem"])) & ~mask_rem
        if m_o.any():
            df.loc[m_o, "id_disp"] = f"{t['id_destino']} 🔄 {t['id_origem']}"
        m_d = (df["id"].astype(str) == str(t["id_destino"])) & ~mask_rem
        if m_d.any():
            df.loc[m_d, "id_disp"] = f"{t['id_origem']} 🔄 {t['id_destino']}"

    # Matar remunerado
    matar = df_trocas[
        (df_trocas["data"] == data_str)
        & (df_trocas["status"] == "Aprovada")
        & (df_trocas["servico_origem"] == "MATAR_REMUNERADO")
    ]
    for _, mt in matar.iterrows():
        serv_r = mt["servico_destino"].rsplit("(", 1)[0].strip()
        hor_r = mt["servico_destino"].rsplit("(", 1)[1].rstrip(")") if "(" in mt["servico_destino"] else ""
        m_ced = (
            (df["serviço"].astype(str).str.strip().str.lower() == serv_r.lower())
            & (df["horário"].astype(str).str.strip() == hor_r.strip())
            & (df["id"].astype(str) == str(mt["id_destino"]))
        )
        if m_ced.any():
            df.loc[m_ced, "id_disp"] = f"{mt['id_origem']} 🔄 {mt['id_destino']}"

    return df


def _adicionar_ferias(df: pd.DataFrame, df_ferias: pd.DataFrame,
                      df_util: pd.DataFrame, data_loader, d_sel, feriados) -> pd.DataFrame:
    """Adiciona militares de férias não presentes na escala."""
    if df_ferias.empty or df_util.empty:
        return df
    ids_na_escala = set(df["id"].astype(str).str.strip().tolist())
    cols_f = df_ferias.columns.tolist()
    id_col_f = "id" if "id" in cols_f else cols_f[0]
    for _, row_f in df_ferias.iterrows():
        mid_f = str(row_f.get(id_col_f, "")).strip()
        if not mid_f or mid_f in ids_na_escala:
            continue
        if data_loader.militar_de_ferias(mid_f, d_sel, df_ferias, feriados):
            nova = {c: "" for c in df.columns}
            nova["id"] = mid_f
            nova["id_disp"] = mid_f
            nova["serviço"] = "Férias"
            nova["horário"] = ""
            df = pd.concat([df, pd.DataFrame([nova])], ignore_index=True)
    return df


# ─────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────

def render_escala_geral(
    usuario: "Usuario",
    data_loader: "DataLoader",
    df_util: pd.DataFrame,
    df_trocas: pd.DataFrame,
    df_ferias: pd.DataFrame,
    feriados: Set,
    dias_publicados: Set[str],
    is_admin: bool = False,
) -> None:
    """Renderiza a página Escala Geral."""
    st.title("🔍 Escala Geral")

    if is_admin:
        tab_eg, tab_hist = st.tabs(["📅 Escala do Dia", "🔎 Historial por Serviço"])
    else:
        tab_eg = st.container()
        tab_hist = None

    with tab_eg:
        d_sel = st.date_input("Seleciona a data:", format="DD/MM/YYYY")
        aba_sel = d_sel.strftime("%d-%m")

    if aba_sel not in dias_publicados:
        st.info("A escala para este dia ainda não foi publicada.")
    else:
        df_dia = data_loader.carregar_escala(aba_sel)
        if df_dia.empty:
            st.info("Não existem dados para esta data.")
        else:
            df_at = df_dia.copy()
            df_at = _aplicar_trocas_df(df_at, df_trocas, d_sel.strftime("%d/%m/%Y"))
            df_at = _adicionar_ferias(df_at, df_ferias, df_util, data_loader, d_sel, feriados)

            # PDF
            pdf_bytes = EscalaPDF.gerar_pdf_escala(d_sel.strftime("%d/%m/%Y"), df_at, df_util)
            col_pdf, col_full, _ = st.columns([1, 1, 3])
            with col_pdf:
                st.download_button(
                    "📥 Escala do Dia", pdf_bytes,
                    file_name=f"Escala_{d_sel.strftime('%d_%m')}.pdf",
                    mime="application/pdf",
                )
            with col_full:
                if st.button("📥 Escala Completa", use_container_width=True):
                    _gerar_escala_completa(data_loader, df_trocas, df_ferias, df_util, feriados, col_full)

            # Limpar e separar secções
            df_at = limpar_sem_militar(df_at)
            df_aus, df_res = filtrar_secao(["férias", "licença", "convalescença"], df_at)
            df_cmd, df_res = filtrar_secao(["pronto", "secretaria", "inquérito", "diligência"], df_res)
            df_apoi, df_res = filtrar_secao(["apoio"], df_res)
            df_aten, df_res = filtrar_secao(["atendimento"], df_res)
            df_pat, df_res = filtrar_secao(["po", "patrulha", "ronda", "vtr", "giro"], df_res)
            df_remu, df_res = filtrar_secao(["remu", "grat"], df_res)
            df_folga, df_res = filtrar_secao(["folga"], df_res)
            df_outros = df_res
            df_pat_ocorr, df_pat_outras = filtrar_secao(["ocorr"], df_pat)

            # 1. Ausências e ADM
            col_aus, col_adm = st.columns(2)
            with col_aus:
                grupos_aus: Dict = {}
                for _, row in df_aus.iterrows():
                    serv = str(row.get("serviço", "")).strip()
                    mid = str(row.get("id_disp", row.get("id", ""))).strip()
                    grupos_aus.setdefault(serv, []).append(mid)
                for _, row in df_folga.iterrows():
                    serv = str(row.get("serviço", "")).strip()
                    mid = str(row.get("id_disp", row.get("id", ""))).strip()
                    grupos_aus.setdefault(serv, []).append(mid)
                if grupos_aus:
                    st.markdown(_sec_header("Ausências, Folgas e Licenças"), unsafe_allow_html=True)
                    st.markdown(_render_ids_linha(grupos_aus), unsafe_allow_html=True)
            with col_adm:
                grupos_adm: Dict = {}
                for _, row in df_cmd.iterrows():
                    serv = str(row.get("serviço", "")).strip()
                    mid = str(row.get("id_disp", row.get("id", ""))).strip()
                    grupos_adm.setdefault(serv, []).append(mid)
                if grupos_adm:
                    st.markdown(_sec_header("Outras Situações / ADM"), unsafe_allow_html=True)
                    st.markdown(_render_ids_linha(grupos_adm), unsafe_allow_html=True)

            # 2-4. Secções operacionais
            mostrar_secao("Atendimento", df_aten, esconder_servico=True)
            mostrar_secao("Apoio ao Atendimento", df_apoi, esconder_servico=True)
            mostrar_secao("Patrulha Ocorrências", df_pat_ocorr, mostrar_extras=True, esconder_servico=True)
            mostrar_secao("Patrulhas", df_pat_outras, mostrar_extras=True)
            mostrar_secao("Outros Serviços", df_outros, mostrar_extras=True, excluir_cols=["giro"])

            # 5. Remunerados
            if not df_remu.empty:
                _render_remunerados_secao(df_remu)

    # ── Tab Historial ──
    if is_admin and tab_hist is not None:
        with tab_hist:
            _render_historial_servico(data_loader, df_util)


def _render_remunerados_secao(df_remu: pd.DataFrame) -> None:
    """Renderiza a secção de remunerados com rowspan nas observações."""
    st.markdown(_sec_header("Serviços Remunerados / Gratificados"), unsafe_allow_html=True)
    df_remu = df_remu.copy()
    for col in ["viatura", "observações", "giro"]:
        if col in df_remu.columns:
            df_remu[col] = df_remu[col].astype(str).replace({"nan": "", "None": ""}).str.strip()

    cols_rem = ["horário"]
    for c in ["viatura", "observações"]:
        if c in df_remu.columns:
            cols_rem.append(c)

    rows_rem = []
    for chave_rem, grp in df_remu.sort_values("horário").groupby(cols_rem, sort=False):
        if not isinstance(chave_rem, tuple):
            chave_rem = (chave_rem,)
        hor = chave_rem[0]
        vtr = chave_rem[1] if len(chave_rem) > 1 else ""
        obs = chave_rem[2] if len(chave_rem) > 2 else ""
        if str(vtr) == "nan": vtr = ""
        if str(obs) == "nan": obs = ""
        ids = ", ".join(grp["id_disp"].tolist())
        rows_rem.append({"horário": hor, "militares": ids, "vtr": str(vtr), "obs": str(obs)})

    # Rowspans
    obs_spans: Dict = {}
    i = 0
    while i < len(rows_rem):
        obs_atual = rows_rem[i]["obs"]
        j = i + 1
        if obs_atual:
            while j < len(rows_rem) and rows_rem[j]["obs"] == obs_atual:
                j += 1
        obs_spans[i] = (obs_atual, j - i)
        i = j

    th_s = f"background:{AZUL_MED};color:{AZUL};padding:5px 8px;text-align:left;font-size:0.78rem;font-weight:700;border-bottom:2px solid {AZUL};"
    td_s = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-bottom:1px solid #dde6f7;"
    td_a = td_s + f"background:{AZUL_CLARO};"
    td_hor = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-bottom:1px solid #dde6f7;white-space:nowrap;"
    td_hor_a = td_hor + f"background:{AZUL_CLARO};"
    td_obs = f"padding:5px 8px;font-size:0.8rem;color:#1E293B;vertical-align:middle;border-left:2px solid {AZUL_MED};"

    html = f"<div style='overflow-x:auto;border:1px solid {AZUL_MED};border-radius:0 0 4px 4px;margin-bottom:2px'>"
    html += "<table style='width:100%;border-collapse:collapse;'><thead><tr>"
    html += f"<th style='{th_s}'>Horário</th><th style='{th_s}'>Militares</th><th style='{th_s}'>Viatura</th><th style='{th_s}'>Observação</th>"
    html += "</tr></thead><tbody>"
    for i, r in enumerate(rows_rem):
        td = td_a if i % 2 == 0 else td_s
        td_h = td_hor_a if i % 2 == 0 else td_hor
        html += "<tr>"
        html += f"<td style='{td_h}'>{r['horário']}</td>"
        html += f"<td style='{td}'>{r['militares']}</td>"
        html += f"<td style='{td}'>{r.get('vtr', '')}</td>"
        if i in obs_spans:
            obs_txt, span = obs_spans[i]
            html += f"<td style='{td_obs}' rowspan='{span}'>{obs_txt}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


def _gerar_escala_completa(data_loader, df_trocas, df_ferias, df_util, feriados, col_full) -> None:
    """Gera PDF com todas as escalas disponíveis."""
    with st.spinner("A gerar PDF com todas as escalas disponíveis..."):
        try:
            from pypdf import PdfWriter, PdfReader
        except ImportError:
            from PyPDF2 import PdfWriter, PdfReader

        writer = PdfWriter()
        hj = datetime.now()
        dias_sem = 0
        j = 0
        paginas = 0

        while dias_sem < 5:
            dt = hj + timedelta(days=j)
            df_d = data_loader.carregar_escala(dt.strftime("%d-%m"))
            if not df_d.empty:
                df_d = _aplicar_trocas_df(df_d.copy(), df_trocas, dt.strftime("%d/%m/%Y"))
                df_d = _adicionar_ferias(df_d, df_ferias, df_util, data_loader, dt.date(), feriados)
                pb = EscalaPDF.gerar_pdf_escala(dt.strftime("%d/%m/%Y"), df_d, df_util)
                reader = PdfReader(io.BytesIO(pb))
                for pg in reader.pages:
                    writer.add_page(pg)
                paginas += 1
                dias_sem = 0
            else:
                dias_sem += 1
            j += 1

        if paginas > 0:
            buf = io.BytesIO()
            writer.write(buf)
            with col_full:
                st.download_button(
                    f"⬇️ Descarregar ({paginas} dias)",
                    data=buf.getvalue(),
                    file_name=f"Escala_Completa_{datetime.now().strftime('%d_%m_%Y')}.pdf",
                    mime="application/pdf",
                    key="dl_completa",
                )
        else:
            st.info("Não há escalas disponíveis.")


def _render_historial_servico(data_loader, df_util) -> None:
    """Renderiza a tab de historial por serviço."""
    st.markdown("#### 🔎 Historial por Serviço")
    st.caption("Seleciona um serviço e um militar para ver quando fez esse serviço.")

    try:
        ws_serv = get_sheet().worksheet("serviços")
        serv_vals = ws_serv.get_all_values()
        servicos_disponiveis = [str(h).strip() for h in serv_vals[0] if str(h).strip()]
    except Exception:
        servicos_disponiveis = []

    if not servicos_disponiveis:
        st.info("Não foi possível carregar a lista de serviços.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        serv_sel = st.selectbox("Serviço:", servicos_disponiveis, key="serv_sel_hist")
    with col2:
        col_id_u = "id_militar" if "id_militar" in df_util.columns else "id"
        col_nome_u = "nome" if "nome" in df_util.columns else col_id_u
        mil_opts: Dict[str, str] = {}
        for _, r in df_util.iterrows():
            mid = str(r.get(col_id_u, "")).strip()
            nome = str(r.get(col_nome_u, "")).strip()
            if mid and mid != "nan":
                mil_opts[f"{mid} -- {nome}"] = mid
        mil_sel = st.selectbox("Militar:", list(mil_opts.keys()), key="mil_sel_hist")
    with col3:
        hor_sel = st.text_input("Horário:", placeholder="ex: 00-08", key="hor_sel_hist")

    if st.button("🔍 Pesquisar último", key="btn_hist_serv", use_container_width=True):
        mid_h = str(mil_opts[mil_sel]).strip()
        with st.spinner("A pesquisar..."):
            abas_h = sorted(
                [t for t in data_loader.carregar_lista_abas() if re.match(r"^\d{2}-\d{2}$", t)],
                reverse=True,
            )
            resultado = None
            for aba_h in abas_h:
                df_h = data_loader.carregar_escala(aba_h)
                if df_h.empty:
                    continue
                mask_mil = df_h["id"].astype(str).str.strip() == mid_h
                mask_serv = df_h["serviço"].astype(str).str.strip().str.lower() == serv_sel.lower()
                mask_hor = (
                    df_h["horário"].astype(str).str.strip() == hor_sel.strip()
                    if hor_sel.strip()
                    else pd.Series([True] * len(df_h), index=df_h.index)
                )
                linhas = df_h[mask_mil & mask_serv & mask_hor]
                if not linhas.empty:
                    row_h = linhas.iloc[0]
                    try:
                        ano_h = datetime.now().year
                        dt_h = datetime.strptime(f"{aba_h}-{ano_h}", "%d-%m-%Y")
                        if dt_h.date() > datetime.now().date():
                            dt_h = datetime.strptime(f"{aba_h}-{ano_h - 1}", "%d-%m-%Y")
                        dia_sem = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][dt_h.weekday()]
                        data_fmt = f"{dt_h.strftime('%d/%m/%Y')} ({dia_sem})"
                    except Exception:
                        data_fmt = aba_h
                    resultado = {
                        "data": data_fmt,
                        "horario": str(row_h.get("horário", "")),
                        "obs": str(row_h.get("observações", "") or ""),
                    }
                    break

        if resultado:
            nome_mil = mil_sel.split("--")[1].strip() if "--" in mil_sel else mil_sel
            st.success("✅ Último serviço encontrado:")
            st.markdown(f"""
            | Campo | Valor |
            |-------|-------|
            | **Militar** | {nome_mil} |
            | **Serviço** | {serv_sel} |
            | **Data** | {resultado['data']} |
            | **Horário** | {resultado['horario']} |
            | **Observações** | {resultado['obs']} |
            """)
        else:
            st.info(f"Nenhum registo encontrado para **{serv_sel}** com este militar.")
