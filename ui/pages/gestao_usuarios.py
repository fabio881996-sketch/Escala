"""
Página «Gerir Utilizadores» – Admin only.

Permite:
- Gerir PINs (definir, alterar, remover)
- Adicionar novos militares ao efetivo
- Remover militares do efetivo
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from core.database import get_sheet
from core.auth import hash_pin, verify_pin
from services.data_loader import DataLoader


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _nc(s: str) -> str:
    """Normaliza header (lowercase, sem acentos)."""
    import unicodedata
    s = str(s).strip().lower()
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    """Retorna nome formatado do militar."""
    mid = str(mid).strip()
    if df_util.empty or "id" not in df_util.columns:
        return mid
    row = df_util[df_util["id"].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


# ─────────────────────────────────────────
# Tab: Gerir PIN
# ─────────────────────────────────────────

def _render_tab_pin(df_util: pd.DataFrame) -> None:
    """Tab para gerir PINs de militares."""
    if df_util.empty:
        st.info("Sem utilizadores.")
        return

    militares_opts = {
        f"{r.get('posto', '')} {r.get('nome', '')} (ID: {r.get('id', '')})": r
        for _, r in df_util.iterrows()
        if str(r.get("id", "")).strip() and str(r.get("id", "")).strip() != "nan"
    }
    if not militares_opts:
        st.info("Sem militares disponíveis.")
        return

    sel_u = st.selectbox("Selecionar militar:", list(militares_opts.keys()), key="sel_u_pin")
    row_u = militares_opts[sel_u]
    email_u = str(row_u.get("email", "")).strip()
    pin_atual = str(row_u.get("pin", "")).strip()
    tem_pin = bool(pin_atual and pin_atual != "nan")
    estado_pin = "✅ PIN definido" if tem_pin else "❌ Sem PIN"
    st.info(f"**Email:** {email_u}  |  **PIN:** {estado_pin}")

    st.markdown("---")
    st.markdown("#### 🔑 Definir / Alterar PIN")
    with st.form("form_admin_pin"):
        novo_pin = st.text_input("Novo PIN (4 dígitos)", type="password", max_chars=4)
        conf_pin = st.text_input("Confirmar PIN", type="password", max_chars=4)
        if st.form_submit_button("💾 GUARDAR PIN", use_container_width=True):
            if not novo_pin or not conf_pin:
                st.warning("Preenche os dois campos.")
            elif len(novo_pin) != 4 or not novo_pin.isdigit():
                st.warning("O PIN deve ter exatamente 4 dígitos numéricos.")
            elif novo_pin != conf_pin:
                st.error("❌ Os PINs não coincidem.")
            else:
                pin_dup = False
                for _, r_check in df_util.iterrows():
                    if str(r_check.get("email", "")).strip().lower() == email_u.lower():
                        continue
                    if verify_pin(novo_pin, str(r_check.get("pin", ""))):
                        pin_dup = True
                        break
                if pin_dup:
                    st.error("❌ Este PIN já está a ser usado por outro militar.")
                else:
                    try:
                        sh_u = get_sheet()
                        ws_u = sh_u.worksheet("utilizadores")
                        headers_u = [h.strip().lower() for h in ws_u.row_values(1)]
                        col_pin_u = headers_u.index("pin") + 1
                        col_email_u = headers_u.index("email") + 1
                        emails_col = ws_u.col_values(col_email_u)
                        linha_u = None
                        for i, ev in enumerate(emails_col):
                            if ev.strip().lower() == email_u.lower():
                                linha_u = i + 1
                                break
                        if linha_u:
                            h_u, salt_u = hash_pin(novo_pin)
                            ws_u.update_cell(linha_u, col_pin_u, f"{h_u}:{salt_u}")
                            st.success(f"✅ PIN de **{row_u.get('nome', '')}** atualizado!")
                        else:
                            st.error("❌ Utilizador não encontrado na Sheet.")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    if tem_pin:
        st.markdown("---")
        if st.button("🗑️ Remover PIN", use_container_width=True, key="btn_rem_pin"):
            try:
                sh_u = get_sheet()
                ws_u = sh_u.worksheet("utilizadores")
                headers_u = [h.strip().lower() for h in ws_u.row_values(1)]
                col_pin_u = headers_u.index("pin") + 1
                col_email_u = headers_u.index("email") + 1
                emails_col = ws_u.col_values(col_email_u)
                for i, ev in enumerate(emails_col):
                    if ev.strip().lower() == email_u.lower():
                        ws_u.update_cell(i + 1, col_pin_u, "")
                        st.success("✅ PIN removido.")
                        st.rerun()
                        break
            except Exception as e:
                st.error(f"Erro: {e}")


# ─────────────────────────────────────────
# Tab: Adicionar Militar
# ─────────────────────────────────────────

def _render_tab_adicionar(df_util: pd.DataFrame) -> None:
    """Tab para adicionar novo militar ao efetivo."""
    st.markdown("#### ➕ Adicionar Novo Militar")
    st.caption(
        "O militar é adicionado ao efetivo e colocado no topo de todos os "
        "slots do ordem_escala mais recente."
    )
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        novo_id = st.text_input("ID:", key="add_id")
        novo_nome = st.text_input("Nome:", key="add_nome")
    with col_a2:
        novo_posto = st.text_input("Posto:", key="add_posto")
        novo_email = st.text_input("Email:", key="add_email")

    if st.button("➕ ADICIONAR", use_container_width=True, type="primary", key="btn_add_mil"):
        if not novo_id.strip() or not novo_nome.strip():
            st.warning("ID e Nome são obrigatórios.")
        elif novo_id.strip() in df_util["id"].astype(str).str.strip().values:
            st.error(f"❌ Já existe um militar com o ID {novo_id.strip()}.")
        else:
            try:
                sh_add = get_sheet()
                ws_util_add = sh_add.worksheet("utilizadores")
                hdrs_add = [h.strip().lower() for h in ws_util_add.row_values(1)]
                nova_linha_add = [""] * len(hdrs_add)
                for campo, valor in [
                    ("id", novo_id.strip()),
                    ("nome", novo_nome.strip()),
                    ("posto", novo_posto.strip()),
                    ("email", novo_email.strip()),
                ]:
                    if campo in hdrs_add:
                        nova_linha_add[hdrs_add.index(campo)] = valor
                ws_util_add.append_row(nova_linha_add)

                # Adicionar ao topo do ordem_escala mais recente
                loader = DataLoader(sheets_client=GoogleSheetsClient())  # type: ignore[arg-type]
                abas_todas = loader.carregar_lista_abas()
                abas_ordem = sorted(
                    [a for a in abas_todas if a.startswith("ordem_escala ")],
                    key=lambda x: datetime.strptime(
                        x.replace("ordem_escala ", "") + f"-{datetime.now().year}",
                        "%d-%m-%Y",
                    ),
                    reverse=True,
                )
                if abas_ordem:
                    ws_ord_add = sh_add.worksheet(abas_ordem[0])
                    vals_ord = ws_ord_add.get_all_values()
                    if vals_ord:
                        hdrs_ord = vals_ord[0]
                        nova_rows = [hdrs_ord]
                        nova_rows.append([novo_id.strip()] * len(hdrs_ord))
                        nova_rows.extend(vals_ord[1:])
                        ws_ord_add.clear()
                        ws_ord_add.update("A1", nova_rows)

                st.success(
                    f"✅ Militar **{novo_nome.strip()}** (ID: {novo_id.strip()}) "
                    f"adicionado com sucesso!"
                )
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao adicionar: {e}")


# ─────────────────────────────────────────
# Tab: Remover Militar
# ─────────────────────────────────────────

def _render_tab_remover(df_util: pd.DataFrame) -> None:
    """Tab para remover militar do efetivo."""
    st.markdown("#### 🗑️ Remover Militar do Efetivo")
    st.caption("O militar é removido dos utilizadores e do ordem_escala mais recente.")

    if df_util.empty:
        st.info("Sem utilizadores.")
        return

    militares_opts_rem = {
        f"{r.get('posto', '')} {r.get('nome', '')} (ID: {r.get('id', '')})": r
        for _, r in df_util.iterrows()
        if str(r.get("id", "")).strip() and str(r.get("id", "")).strip() != "nan"
    }
    if not militares_opts_rem:
        st.info("Sem militares disponíveis.")
        return

    sel_rem = st.selectbox(
        "Selecionar militar a remover:", list(militares_opts_rem.keys()), key="sel_u_rem"
    )
    row_rem = militares_opts_rem[sel_rem]
    mid_rem = str(row_rem.get("id", "")).strip()
    nome_rem = str(row_rem.get("nome", "")).strip()

    st.warning(
        f"⚠️ Tens a certeza que queres remover **{nome_rem}** (ID: {mid_rem}) do efetivo?"
    )

    if st.button("🗑️ CONFIRMAR REMOÇÃO", use_container_width=True, type="primary", key="btn_conf_rem"):
        try:
            sh_rem = get_sheet()

            # Remover da aba utilizadores
            ws_util_rem = sh_rem.worksheet("utilizadores")
            vals_util_rem = ws_util_rem.get_all_values()
            hdrs_util_rem = [h.strip().lower() for h in vals_util_rem[0]]
            ix_id_rem = hdrs_util_rem.index("id") if "id" in hdrs_util_rem else 0
            linha_rem = None
            for i, row_v in enumerate(vals_util_rem[1:], start=2):
                if str(row_v[ix_id_rem]).strip() == mid_rem:
                    linha_rem = i
                    break
            if linha_rem:
                ws_util_rem.delete_rows(linha_rem)

            # Remover do ordem_escala mais recente
            loader = DataLoader(sheets_client=GoogleSheetsClient())  # type: ignore[arg-type]
            abas_todas_rem = loader.carregar_lista_abas()
            abas_ordem_rem = sorted(
                [a for a in abas_todas_rem if a.startswith("ordem_escala ")],
                key=lambda x: datetime.strptime(
                    x.replace("ordem_escala ", "") + f"-{datetime.now().year}",
                    "%d-%m-%Y",
                ),
                reverse=True,
            )
            if abas_ordem_rem:
                ws_ord_rem = sh_rem.worksheet(abas_ordem_rem[0])
                vals_ord_rem = ws_ord_rem.get_all_values()
                if vals_ord_rem:
                    hdrs_ord_rem = vals_ord_rem[0]
                    novas_cols: dict[str, list[str]] = {h: [] for h in hdrs_ord_rem}
                    for row_v in vals_ord_rem[1:]:
                        for ci, h in enumerate(hdrs_ord_rem):
                            val = str(row_v[ci]).strip() if ci < len(row_v) else ""
                            if val and val != mid_rem:
                                novas_cols[h].append(val)
                    ml_rem = max((len(v) for v in novas_cols.values()), default=1)
                    nova_ord = [hdrs_ord_rem]
                    for i in range(ml_rem):
                        nova_ord.append(
                            [novas_cols[h][i] if i < len(novas_cols[h]) else "" for h in hdrs_ord_rem]
                        )
                    ws_ord_rem.clear()
                    ws_ord_rem.update("A1", nova_ord)

            st.success(f"✅ **{nome_rem}** removido do efetivo e do ordem_escala.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao remover: {e}")


# ─────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────

def render_gestao_usuarios(
    usuario: "Usuario",
    df_util: pd.DataFrame,
    is_admin: bool = False,
) -> None:
    """Renderiza a página de gestão de utilizadores com tabs."""
    st.title("👤 Gerir Utilizadores")
    if not is_admin:
        st.warning("Acesso restrito a administradores.")
        st.stop()

    tab_pin, tab_add, tab_rem = st.tabs(
        ["🔑 Gerir PIN", "➕ Adicionar Militar", "🗑️ Remover Militar"]
    )

    with tab_pin:
        _render_tab_pin(df_util)

    with tab_add:
        _render_tab_adicionar(df_util)

    with tab_rem:
        _render_tab_remover(df_util)
