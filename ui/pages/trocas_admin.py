"""
Página «Validar Trocas» e «Trocas Validadas» – Admin.

- Validar Trocas: aprovar/rejeitar pedidos pendentes
- Trocas Validadas: histórico de trocas aprovadas com download de PDF
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from core.database import GoogleSheetsClient, get_sheet
from models.usuario import Usuario
from services.data_loader import DataLoader
from pdf.troca_pdf import TrocaPDF
from ui.components.alerts import render_alert


# ───────────────────────────────────────
# Helpers
# ───────────────────────────────────────

def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or 'id' not in df_util.columns:
        return mid
    row = df_util[df_util['id'].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _atualizar_status_gsheet(index_linha: int, novo_status: str, admin_nome: str = '') -> bool:
    """Atualiza o status de uma troca na Google Sheet."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        headers = [h.strip().lower() for h in ws.row_values(1)]
        col_status = headers.index('status') + 1
        ws.update_cell(index_linha + 2, col_status, novo_status)
        if admin_nome:
            if 'validador' in headers:
                col_val = headers.index('validador') + 1
                ws.update_cell(index_linha + 2, col_val, admin_nome)
            if 'data_validacao' in headers:
                col_dv = headers.index('data_validacao') + 1
                ws.update_cell(index_linha + 2, col_dv, datetime.now().strftime('%d/%m/%Y %H:%M'))
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")
        return False


def _invalidar_trocas():
    try:
        st.cache_data.clear()
    except Exception:
        pass


# ───────────────────────────────────────
# Validar Trocas (Admin)
# ───────────────────────────────────────

def render_trocas_admin(usuario: Usuario) -> None:
    """Renderiza a página de validação de trocas (admin).

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        if not usuario.is_admin:
            st.warning("Acesso restrito a administradores.")
            st.stop()
            return

        u_nome = usuario.nome
        loader = DataLoader(db=GoogleSheetsClient())
        df_trocas = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()

        st.title("⚖️ Validação Superior de Trocas")

        # Processar ação pendente ANTES de renderizar
        acao_val = st.session_state.pop('validar_acao', None)
        if acao_val:
            _atualizar_status_gsheet(acao_val['idx'], acao_val['status'], u_nome)
            _invalidar_trocas()
            st.rerun()

        if df_trocas.empty:
            st.info("Sem dados.")
            return

        # ── Aguardam aceitação do militar ──
        pnd_mil = df_trocas[
            (df_trocas['status'] == 'Pendente_Militar') &
            (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
        ]
        if not pnd_mil.empty:
            st.markdown(f"#### 🕐 Aguardam aceitação do militar ({len(pnd_mil)})")
            for idx, r in pnd_mil.sort_values('data').iterrows():
                n_o = _get_nome_militar(df_util, r['id_origem'])
                n_d = _get_nome_militar(df_util, r['id_destino'])
                with st.expander(f"📅 {r['data']}  |  {n_o} → {n_d}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Requerente:**\n\n{n_o}\n\n`{r['servico_origem']}`")
                    with col2:
                        st.warning(f"**Aguarda aceitação:**\n\n{n_d}\n\n`{r['servico_destino']}`")
            st.markdown("---")

        # ── Aguardam validação do admin ──
        pnd = df_trocas[df_trocas['status'] == 'Pendente_Admin']
        if pnd.empty:
            st.success("✅ Não há trocas pendentes de validação.")
        else:
            st.markdown(f"#### ⚖️ Aguardam validação ({len(pnd)})")
            for idx, r in pnd.iterrows():
                n_o = _get_nome_militar(df_util, r['id_origem'])
                n_d = _get_nome_militar(df_util, r['id_destino'])
                is_matar_v = str(r['servico_origem']) == 'MATAR_REMUNERADO'
                titulo = (
                    f"📅 {r['data']}  |  💶 {n_o} faz remunerado de {n_d}"
                    if is_matar_v
                    else f"📅 {r['data']}  |  {n_o} ↔️ {n_d}"
                )
                with st.expander(titulo, expanded=True):
                    col1, col2 = st.columns(2)
                    if is_matar_v:
                        with col1:
                            st.info(f"**Requerente:**\n\n{n_o}")
                        with col2:
                            st.success(f"**Cedente:**\n\n{n_d}\n\n`{r['servico_destino']}`")
                    else:
                        with col1:
                            st.info(f"**{n_o}**\n\n`{r['servico_origem']}`")
                        with col2:
                            st.success(f"**{n_d}**\n\n`{r['servico_destino']}`")
                    c1, c2 = st.columns(2)
                    if c1.button("✔️ VALIDAR", key=f"ok_{idx}", use_container_width=True):
                        st.session_state['validar_acao'] = {'idx': idx, 'status': 'Aprovada'}
                        st.rerun()
                    if c2.button("🚫 REJEITAR", key=f"no_{idx}", use_container_width=True):
                        st.session_state['validar_acao'] = {'idx': idx, 'status': 'Rejeitada'}
                        st.rerun()

    except Exception as e:
        render_alert(f"Erro na validação de trocas: {e}", tipo="error")


# ───────────────────────────────────────
# Trocas Validadas (Histórico admin)
# ───────────────────────────────────────

def render_trocas_validadas(usuario: Usuario) -> None:
    """Renderiza a página de histórico de trocas aprovadas com PDFs.

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        loader = DataLoader(db=GoogleSheetsClient())
        df_trocas = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()

        st.title("📜 Histórico de Trocas Aprovadas")
        if df_trocas.empty:
            st.info("Ainda não existem registos de trocas.")
            return

        aprv = df_trocas[df_trocas['status'] == 'Aprovada']
        if aprv.empty:
            st.write("Não existem trocas validadas.")
            return

        aprv = aprv.copy()
        aprv['_data_ord'] = pd.to_datetime(aprv['data'], format='%d/%m/%Y', errors='coerce')
        aprv = aprv.sort_values('_data_ord', ascending=False).drop(columns='_data_ord')

        pdf_gen = TrocaPDF()

        for idx, r in aprv.iterrows():
            n_o = _get_nome_militar(df_util, r['id_origem'])
            n_d = _get_nome_militar(df_util, r['id_destino'])
            is_matar = str(r['servico_origem']) == 'MATAR_REMUNERADO'
            titulo = (
                f"📅 {r['data']}  |  {n_o} 💶 {n_d}"
                if is_matar
                else f"📅 {r['data']}  |  {n_o} ↔️ {n_d}"
            )
            with st.expander(titulo):
                col1, col2 = st.columns(2)
                if is_matar:
                    with col1:
                        st.info(f"**Requerente:**\n\n{n_o}")
                        st.markdown("**Ação:** Fazer Remunerado")
                    with col2:
                        st.success(f"**Cedente:**\n\n{n_d}")
                        st.markdown(f"**Remunerado:**\n`{r['servico_destino']}`")
                else:
                    with col1:
                        st.info(f"**Requerente:**\n\n{n_o}")
                        st.markdown(f"**Serviço original:**\n`{r['servico_origem']}`")
                    with col2:
                        st.success(f"**Substituto:**\n\n{n_d}")
                        st.markdown(f"**Serviço destino:**\n`{r['servico_destino']}`")
                st.divider()
                val_por = r.get('validador', 'N/A')
                val_em = r.get('data_validacao', 'N/A')
                st.caption(f"⚖️ Validado por **{val_por}** em {val_em}")

                if not is_matar:
                    dados_pdf = {
                        "data": r['data'],
                        "id_origem": r['id_origem'], "nome_origem": n_o,
                        "serv_orig": r['servico_origem'],
                        "id_destino": r['id_destino'], "nome_destino": n_d,
                        "serv_dest": r['servico_destino'],
                        "validador": val_por, "data_val": val_em,
                    }
                    try:
                        pdf_bytes = pdf_gen.gerar_certificado_troca(dados_pdf)
                        st.download_button(
                            label="📥 Descarregar Guia de Troca",
                            data=pdf_bytes,
                            file_name=f"Guia_Troca_{r['data'].replace('/', '-')}.pdf",
                            mime="application/pdf",
                            key=f"hist_pdf_{idx}",
                        )
                    except Exception as e:
                        st.warning(f"Não foi possível gerar PDF: {e}")
                else:
                    dados_pdf_rem = {
                        "data": r['data'],
                        "id_requerente": r['id_origem'], "nome_requerente": n_o,
                        "id_cedente": r['id_destino'], "nome_cedente": n_d,
                        "remunerado": r['servico_destino'],
                        "validador": val_por, "data_val": val_em,
                    }
                    try:
                        pdf_bytes = pdf_gen.gerar_certificado_remunerado(dados_pdf_rem)
                        st.download_button(
                            label="📥 Descarregar Comprovativo",
                            data=pdf_bytes,
                            file_name=f"Remunerado_{r['data'].replace('/', '-')}.pdf",
                            mime="application/pdf",
                            key=f"rem_pdf_{idx}",
                        )
                    except Exception as e:
                        st.warning(f"Não foi possível gerar PDF: {e}")

    except Exception as e:
        render_alert(f"Erro no histórico de trocas: {e}", tipo="error")
