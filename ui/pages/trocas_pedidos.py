"""
Página «Trocas» – Solicitar, receber e consultar histórico de trocas.

Três tabs:
1. Solicitar (troca simples, dar/fazer remunerado, mudar folga)
2. Pedidos Recebidos (aceitar/rejeitar)
3. Histórico pessoal
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import IMPEDIMENTOS
from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm, parse_horario as _parse_horario
from models.usuario import Usuario
from services.data_loader import DataLoader
from services.troca_service import TrocaService
from services.validation_service import ValidationService
from ui.components.alerts import render_alert


# ───────────────────────────────────────
# Helpers
# ───────────────────────────────────────

IMPEDIMENTOS_PATTERN = r'férias|licença|convalescença|dilig|tribunal|pronto|secretaria|inquérito|outras licenças|fcaa'


def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or 'id' not in df_util.columns:
        return mid
    row = df_util[df_util['id'].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _get_nome_curto(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or 'id' not in df_util.columns:
        return mid
    row = df_util[df_util['id'].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    nomes = str(r.get('nome', '')).strip().split()
    return f"{nomes[0]} {nomes[-1]}" if len(nomes) > 1 else ' '.join(nomes)


def _salvar_troca_gsheet(linha: list) -> bool:
    """Guarda um novo pedido de troca na Google Sheet."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        ws.append_row(linha)
        return True
    except Exception as e:
        st.error(f"Erro ao guardar troca: {e}")
        return False


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
    """Limpa cache de trocas."""
    try:
        st.cache_data.clear()
    except Exception:
        pass


def _aplicar_trocas_df(df_alvo: pd.DataFrame, data_str: str, df_trocas: pd.DataFrame) -> pd.DataFrame:
    """Aplica trocas aprovadas a um DataFrame de escala."""
    if df_alvo.empty or df_trocas.empty:
        return df_alvo
    tr = df_trocas[
        (df_trocas['data'] == data_str) &
        (df_trocas['status'] == 'Aprovada') &
        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
    ]
    mask_rem = df_alvo['serviço'].str.lower().str.contains('remu|grat', na=False)
    for _, t in tr.iterrows():
        id_o = str(t['id_origem']).strip()
        id_d2 = str(t['id_destino']).strip()
        s_o = t['servico_origem']
        s_d2 = t['servico_destino']
        serv_o = s_o.rsplit('(', 1)[0].strip()
        hor_o = s_o.rsplit('(', 1)[1].rstrip(')') if '(' in s_o else ''
        serv_d2 = s_d2.rsplit('(', 1)[0].strip()
        hor_d2 = s_d2.rsplit('(', 1)[1].rstrip(')') if '(' in s_d2 else ''
        m_o = (df_alvo['id'].astype(str).str.strip() == id_o) & ~mask_rem
        if m_o.any():
            df_alvo.loc[m_o, 'serviço'] = serv_d2
            if hor_d2:
                df_alvo.loc[m_o, 'horário'] = hor_d2
        m_d = (df_alvo['id'].astype(str).str.strip() == id_d2) & ~mask_rem
        if m_d.any():
            df_alvo.loc[m_d, 'serviço'] = serv_o
            if hor_o:
                df_alvo.loc[m_d, 'horário'] = hor_o
    return df_alvo


def _verificar_descanso_troca(
    u_id: str, id_d: str, dt_s, meu_serv_nome: str, meu_hor_val: str,
    serv_d_nome: str, hor_d_val: str,
    df_dia: pd.DataFrame, df_ant: pd.DataFrame, df_seg: pd.DataFrame,
) -> list:
    """Verifica se a troca respeita o descanso mínimo de 6h.

    Retorna lista de erros (vazia = OK).
    """
    erros = []
    try:
        vs = ValidationService(loader=DataLoader(db=GoogleSheetsClient()))
        erros = vs.validar_descanso_troca(
            u_id, id_d, dt_s,
            meu_serv_nome, meu_hor_val,
            serv_d_nome, hor_d_val,
            df_dia, df_ant, df_seg,
        )
    except Exception:
        pass
    return erros


# ───────────────────────────────────────
# Tab 1: Solicitar
# ───────────────────────────────────────

def _render_tab_solicitar(
    u_id: str,
    loader: DataLoader,
    df_trocas: pd.DataFrame,
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_folgas: pd.DataFrame,
    feriados: list,
) -> None:
    """Tab de solicitar nova troca."""
    st.title("🔄 Solicitar Troca de Serviço")

    tipo_troca = st.radio(
        "Tipo de pedido:",
        ["🔄 Troca Simples", "💶 Fazer Remunerado", "💶 Dar Remunerado", "📅 Mudar Folga"],
        horizontal=True,
    )
    st.markdown("---")

    dt_s = st.date_input("Data:", format="DD/MM/YYYY")
    try:
        df_d = loader.carregar_escala(dt_s)
    except Exception:
        df_d = pd.DataFrame()

    if df_d.empty:
        st.info("Não existem dados para esta data.")
        return

    df_d = df_d.copy()
    try:
        df_ant = loader.carregar_escala(dt_s - timedelta(days=1))
        df_ant = df_ant.copy() if not df_ant.empty else df_ant
    except Exception:
        df_ant = pd.DataFrame()
    try:
        df_seg = loader.carregar_escala(dt_s + timedelta(days=1))
        df_seg = df_seg.copy() if not df_seg.empty else df_seg
    except Exception:
        df_seg = pd.DataFrame()

    # Aplicar trocas aprovadas
    servico_override = None
    if not df_trocas.empty:
        data_str_d = dt_s.strftime('%d/%m/%Y')
        data_str_ant = (dt_s - timedelta(days=1)).strftime('%d/%m/%Y')
        data_str_seg = (dt_s + timedelta(days=1)).strftime('%d/%m/%Y')
        df_d = _aplicar_trocas_df(df_d, data_str_d, df_trocas)
        df_ant = _aplicar_trocas_df(df_ant, data_str_ant, df_trocas)
        df_seg = _aplicar_trocas_df(df_seg, data_str_seg, df_trocas)
        tr_dia = df_trocas[
            (df_trocas['data'] == data_str_d) &
            (df_trocas['status'] == 'Aprovada') &
            (df_trocas['servico_origem'] != 'MATAR_REMUNERADO')
        ]
        for _, t in tr_dia.iterrows():
            if str(t['id_origem']).strip() == u_id.strip():
                servico_override = t['servico_destino']
            elif str(t['id_destino']).strip() == u_id.strip():
                servico_override = t['servico_origem']

    meu = df_d[df_d['id'].astype(str) == u_id]

    # IDs com troca pendente nesse dia
    ids_com_troca: set = set()
    if not df_trocas.empty:
        tr_ocupados = df_trocas[
            (df_trocas['data'] == dt_s.strftime('%d/%m/%Y')) &
            (df_trocas['status'].isin(['Pendente_Militar', 'Pendente_Admin']))
        ]
        ids_com_troca = set(
            tr_ocupados['id_origem'].astype(str).tolist() +
            tr_ocupados['id_destino'].astype(str).tolist()
        )
        ids_com_troca.discard(u_id)

    # IDs sem remunerado (cedentes aprovados)
    ids_sem_remunerado: set = set()
    if not df_trocas.empty:
        rem_apr = df_trocas[
            (df_trocas['data'] == dt_s.strftime('%d/%m/%Y')) &
            (df_trocas['status'] == 'Aprovada') &
            (df_trocas['servico_origem'] == 'MATAR_REMUNERADO')
        ]
        ids_sem_remunerado.update(rem_apr['id_destino'].astype(str).tolist())

    def _tem_rem_nao_cedido(mid):
        mid = str(mid).strip()
        rows_rem = df_d[
            (df_d['id'].astype(str).str.strip() == mid) &
            (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))
        ]
        if rows_rem.empty:
            return False
        return mid not in ids_sem_remunerado

    # ── TROCA SIMPLES ──
    if tipo_troca == "🔄 Troca Simples":
        # Se não há escala publicada, verificar folga no mapa
        _folga_mapa_tr = ''
        if meu.empty:
            ano_atual = datetime.now().year
            _df_folgas_tr = loader.carregar_folgas(ano_atual)
            _grupos_tr = loader.carregar_grupos_folga()
            _feriados_tr = feriados
            _folga_mapa_tr = DataLoader.militar_de_folga(u_id, dt_s, _df_folgas_tr, _grupos_tr, _feriados_tr)
            if not _folga_mapa_tr:
                st.warning("Não tens serviço escalado neste dia.")
                return
        if not meu.empty or _folga_mapa_tr:
            if _folga_mapa_tr and meu.empty:
                # Folga do mapa -- simular linha de escala
                meu_s = _folga_mapa_tr
                meu_serv_orig = _folga_mapa_tr
                meu_hor_orig = ''
                estou_de_folga = True
            else:
                meu_s = servico_override if servico_override else f"{meu.iloc[0]['serviço']} ({meu.iloc[0]['horário']})"
                st.info(f"📋 O teu serviço: **{meu_s}**")
                meu_serv_orig = meu.iloc[0]['serviço']
                meu_hor_orig = meu.iloc[0]['horário']
                estou_de_folga = 'folga' in meu_serv_orig.lower()

        # IDs de militares com serviço Pronto
        ids_pronto: set = set()
        if not df_folgas.empty:
            col_id_f = 'id' if 'id' in df_folgas.columns else df_folgas.columns[0]
            col_sv_f = 'serviço' if 'serviço' in df_folgas.columns else None
            if col_sv_f:
                ids_pronto = set(
                    df_folgas[df_folgas[col_sv_f].apply(norm).str.contains('pronto', na=False)][col_id_f]
                    .astype(str).str.strip().tolist()
                )

        base_mask = (
            (df_d['id'].astype(str).str.strip() != u_id) &
            (df_d['id'].astype(str).str.strip() != '') &
            (df_d['id'].astype(str).str.strip() != 'nan') &
            (~df_d['id'].astype(str).str.strip().isin(ids_com_troca)) &
            ~((df_d['serviço'] == meu_serv_orig) & (df_d['horário'] == meu_hor_orig)) &
            ~(estou_de_folga & df_d['serviço'].str.lower().str.contains('folga', na=False))
        )
        mask_folga = df_d['serviço'].str.lower().str.contains('folga', na=False)
        mask_imp = (
            df_d['serviço'].str.lower().str.contains(IMPEDIMENTOS_PATTERN, na=False) |
            df_d['id'].astype(str).str.strip().isin(ids_pronto)
        )
        mask_rem_nao_cedido = df_d['id'].astype(str).apply(_tem_rem_nao_cedido)

        cols_folga = df_d[base_mask & mask_folga]
        cols = df_d[base_mask & ~mask_folga & ~mask_imp & ~mask_rem_nao_cedido]

        if cols.empty and cols_folga.empty:
            st.warning("Não há militares disponíveis para troca neste dia.")
            return

        meu_serv_nome = meu_s.rsplit('(', 1)[0].strip()
        meu_hor_val = meu_s.rsplit('(', 1)[1].rstrip(')') if '(' in meu_s else meu.iloc[0]['horário']
        opts = []

        for _, row_c in cols_folga.iterrows():
            id_c = str(row_c['id'])
            serv_c = str(row_c['serviço'])
            hor_c = str(row_c['horário'])
            erros = _verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg)
            erros_dest = [e for e in erros if e.startswith("O militar de destino")]
            if not erros_dest:
                nome_c = _get_nome_curto(df_util, id_c)
                opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")

        for _, row_c in cols.iterrows():
            id_c = str(row_c['id'])
            serv_c = str(row_c['serviço'])
            hor_c = str(row_c['horário'])
            if not _verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg):
                nome_c = _get_nome_curto(df_util, id_c)
                opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c})")

        # Militares com remunerado não cedido
        cols_com_rem = df_d[
            base_mask & ~mask_folga & ~mask_imp & mask_rem_nao_cedido &
            ~df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False)
        ]
        for _, row_c in cols_com_rem.iterrows():
            id_c = str(row_c['id'])
            serv_c = str(row_c['serviço'])
            hor_c = str(row_c['horário'])
            if not _verificar_descanso_troca(u_id, id_c, dt_s, meu_serv_nome, meu_hor_val, serv_c, hor_c, df_d, df_ant, df_seg):
                rem_rows_c = df_d[
                    (df_d['id'].astype(str).str.strip() == id_c) &
                    (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))
                ]
                if not rem_rows_c.empty:
                    rem_hor_c = str(rem_rows_c.iloc[0]['horário']).strip()
                    nome_c = _get_nome_curto(df_util, id_c)
                    opts.append(f"{id_c} {nome_c} - {serv_c} ({hor_c}) 💶[{rem_hor_c}]")

        if not opts:
            st.warning("Não há militares disponíveis para troca neste dia (restrições de descanso).")
            return

        alvo = st.selectbox("👤 Trocar com:", opts, key="sel_alvo_troca")
        incluir_rem = False
        if alvo and '💶[' in alvo:
            rem_hor_aviso = alvo.split('💶[')[1].rstrip(']')
            incluir_rem = st.checkbox(
                f"⚠️ Este militar tem remunerado ({rem_hor_aviso}). Incluir transferência do remunerado?",
                key="chk_incluir_rem",
            )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📨 ENVIAR PEDIDO", use_container_width=True, key="btn_enviar_troca"):
            id_d = alvo.split(" ")[0]
            s_d_raw = alvo.split(" - ", 1)[1]
            s_d = s_d_raw.split(" 💶[")[0] if " 💶[" in s_d_raw else s_d_raw
            obs_troca = "INCLUIR_REMUNERADO" if incluir_rem else ""
            if _salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), u_id, meu_s, id_d, s_d, "Pendente_Militar", obs_troca]):
                st.success("✅ Pedido enviado com sucesso!")

    # ── DAR REMUNERADO ──
    elif tipo_troca == "💶 Dar Remunerado":
        meu_rem = df_d[
            (df_d['id'].astype(str).str.strip() == u_id) &
            (df_d['serviço'].str.lower().str.contains('remu|grat', na=False))
        ]
        if meu_rem.empty:
            st.warning("Não tens nenhum remunerado escalado nesse dia.")
            return
        rem_row = meu_rem.iloc[0]
        rem_serv = str(rem_row.get('serviço', '')).strip()
        rem_hor = str(rem_row.get('horário', '')).strip()
        st.info(f"📋 O teu remunerado: **{rem_serv} ({rem_hor})**")

        _imp_dar = r'ferias|licen|convalesc|dilig|tribunal|inquer|secretaria|pronto'
        outros_dar = df_d[
            (df_d['id'].astype(str).str.strip() != u_id) &
            (df_d['id'].astype(str).str.strip() != '') &
            (df_d['id'].astype(str).str.strip() != 'nan')
        ]
        outros_dar = outros_dar[~outros_dar['serviço'].str.lower().apply(norm).str.contains(_imp_dar, na=False)]
        outros_dar = outros_dar[~outros_dar['id'].astype(str).apply(
            lambda mid: DataLoader.militar_de_ferias(mid, dt_s, df_ferias, feriados)
        )]

        opts_dar = []
        ini_rem, fim_rem = _parse_horario(rem_hor)
        for _, r_dar in outros_dar.iterrows():
            mid_dar = str(r_dar['id']).strip()
            hor_dar = str(r_dar.get('horário', '')).strip()
            if ini_rem is not None and hor_dar:
                ini_d_h, fim_d_h = _parse_horario(hor_dar)
                if ini_d_h is not None and not (fim_rem <= ini_d_h or ini_rem >= fim_d_h):
                    continue
            nome_dar = _get_nome_curto(df_util, mid_dar)
            opts_dar.append(f"{mid_dar} {nome_dar} -- {r_dar['serviço']} ({hor_dar})")

        if not opts_dar:
            st.warning("Não há militares disponíveis para ceder o remunerado.")
            return

        with st.form("dar_rem"):
            st.info("Seleciona o militar a quem queres ceder o remunerado.")
            dar_sel = st.selectbox("Militar:", opts_dar)
            if st.form_submit_button("💶 CEDER REMUNERADO", use_container_width=True):
                id_dest_dar = dar_sel.split(" ")[0]
                serv_completo = f"{rem_serv} ({rem_hor})"
                if _salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), id_dest_dar, "MATAR_REMUNERADO", u_id, serv_completo, "Pendente_Militar", ""]):
                    st.success("✅ Pedido enviado! Aguarda aceitação do militar.")

    # ── FAZER REMUNERADO ──
    elif tipo_troca == "💶 Fazer Remunerado":
        _imp_rem = r'ferias|licen|convalesc|dilig|tribunal|pronto|secretaria|inquer'
        _motivo_imp = ''
        if not meu.empty and re.search(_imp_rem, norm(meu.iloc[0]['serviço'])):
            _motivo_imp = meu.iloc[0]['serviço']
        elif DataLoader.militar_de_ferias(u_id, dt_s, df_ferias, feriados):
            _motivo_imp = 'Férias'
        if _motivo_imp:
            st.warning(f"Não podes fazer remunerados — estás com **{_motivo_imp}**.")
            return

        rem_dia = df_d[
            (df_d['id'].astype(str).str.strip() != u_id) &
            (df_d['id'].astype(str).str.strip() != '') &
            (df_d['id'].astype(str).str.strip() != 'nan') &
            (~df_d['id'].astype(str).str.strip().isin(ids_sem_remunerado)) &
            (df_d['serviço'].str.lower().str.contains(r'remu|grat', na=False))
        ]
        if rem_dia.empty:
            st.info("Não há serviços remunerados escalados neste dia.")
            return

        meu_ini, meu_fim = (None, None)
        meu_hor_real = None
        if servico_override and '(' in servico_override:
            meu_hor_real = servico_override.rsplit('(', 1)[1].rstrip(')')
        elif not meu.empty and meu.iloc[0]['horário']:
            meu_hor_real = meu.iloc[0]['horário']
        if meu_hor_real:
            meu_ini, meu_fim = _parse_horario(meu_hor_real)

        opts_rem = []
        for _, r in rem_dia.iterrows():
            hor_rem = str(r['horário']).strip()
            if meu_ini is not None and hor_rem:
                ini_r, fim_r = _parse_horario(hor_rem)
                if ini_r is not None and not (fim_r <= meu_ini or ini_r >= meu_fim):
                    continue
            nome_r = _get_nome_curto(df_util, str(r["id"]))
            opts_rem.append(f"{r['id']} {nome_r} - {r['serviço']} ({hor_rem})")

        if not opts_rem:
            st.warning("Não há remunerados disponíveis sem sobreposição de horário.")
            return

        with st.form("matar_rem"):
            st.info("Seleciona o remunerado que queres fazer.")
            rem_sel = st.selectbox("Serviço remunerado:", opts_rem)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("✅ QUERO FAZER ESTE REMUNERADO", use_container_width=True):
                id_d = rem_sel.split(" ")[0]
                s_d = rem_sel.split(" - ", 1)[1]
                if _salvar_troca_gsheet([dt_s.strftime('%d/%m/%Y'), u_id, "MATAR_REMUNERADO", id_d, s_d, "Pendente_Militar", ""]):
                    st.success("✅ Pedido enviado! Aguarda aceitação do militar.")

    # ── MUDAR FOLGA ──
    elif tipo_troca == "📅 Mudar Folga":
        ano_tf = datetime.now().year
        df_folgas_tf = loader.carregar_folgas(ano_tf)
        grupos_tf = loader.carregar_grupos_folga()

        meus_dias_folga = []
        for i_tf in range(60):
            dt_tf = datetime.now().date() + timedelta(days=i_tf)
            tipo_tf = DataLoader.militar_de_folga(u_id, dt_tf, df_folgas_tf, grupos_tf, feriados)
            if tipo_tf:
                meus_dias_folga.append((dt_tf, tipo_tf))

        if not meus_dias_folga:
            st.warning("Não tens dias de folga nos próximos 60 dias.")
            return

        opts_meus = {f"{d.strftime('%d/%m/%Y')} -- {t}": (d, t) for d, t in meus_dias_folga}
        meu_dia_sel = st.selectbox("Folga que queres mudar:", list(opts_meus.keys()), key="tf_meu_dia")
        meu_dia_tf, meu_tipo_tf = opts_meus[meu_dia_sel]

        novo_dia_tf = st.date_input("Novo dia de folga:", format="DD/MM/YYYY", key="tf_novo_dia",
                                     value=meu_dia_tf + timedelta(days=1))

        tipo_novo = DataLoader.militar_de_folga(u_id, novo_dia_tf, df_folgas_tf, grupos_tf, feriados)
        if tipo_novo:
            st.warning(f"Já estás de {tipo_novo} nesse dia.")
        else:
            st.info(f"📋 Mover folga de **{meu_dia_tf.strftime('%d/%m/%Y')}** ({meu_tipo_tf}) para **{novo_dia_tf.strftime('%d/%m/%Y')}**")
            if st.button("📅 SOLICITAR MUDANÇA DE FOLGA", use_container_width=True, key="btn_tf"):
                serv_orig_tf = f"Folga {meu_dia_tf.strftime('%d/%m/%Y')} ({meu_tipo_tf})"
                serv_dest_tf = f"Folga {novo_dia_tf.strftime('%d/%m/%Y')} ({meu_tipo_tf})"
                if _salvar_troca_gsheet([meu_dia_tf.strftime('%d/%m/%Y'), u_id, serv_orig_tf, u_id, serv_dest_tf, "Pendente_Admin", ""]):
                    st.success("✅ Pedido enviado para validação!")


# ───────────────────────────────────────
# Tab 2: Pedidos Recebidos
# ───────────────────────────────────────

def _render_tab_pedidos_recebidos(
    u_id: str,
    df_trocas: pd.DataFrame,
    df_util: pd.DataFrame,
    loader: DataLoader,
) -> None:
    """Tab de pedidos de troca recebidos."""
    st.title("📥 Pedidos de Troca Recebidos")

    # Processar ação pendente
    acao_ped = st.session_state.pop('pedido_acao', None)
    if acao_ped:
        _atualizar_status_gsheet(acao_ped['idx'], acao_ped['status'])
        _invalidar_trocas()
        st.rerun()

    if df_trocas.empty:
        st.info("Sem dados de trocas.")
        return

    m = df_trocas[
        (df_trocas['status'] == 'Pendente_Militar') &
        (df_trocas['id_destino'].astype(str) == u_id)
    ]
    if m.empty:
        st.success("✅ Não tens pedidos pendentes.")
        return

    st.markdown(f"**{len(m)} pedido(s) aguardam a tua resposta:**")
    for idx, r in m.iterrows():
        nome_orig = _get_nome_militar(df_util, r['id_origem'])
        is_matar = str(r['servico_origem']) == 'MATAR_REMUNERADO'
        try:
            dt_r = datetime.strptime(r['data'], '%d/%m/%Y')
            dia_sem_r = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][dt_r.weekday()]
            data_fmt = f"{r['data']} ({dia_sem_r})"
        except Exception:
            data_fmt = r['data']

        if is_matar:
            st.markdown(
                f'<div class="card-servico card-troca">'
                f'<h3>📅 {data_fmt}</h3>'
                f'<p>👤 <b>{nome_orig}</b> quer fazer o teu remunerado</p>'
                f'<p>🔴 O teu remunerado: <b>{r["servico_destino"]}</b></p>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            obs_r = str(r.get('observações', '') or '').strip()
            tem_rem_troca = obs_r == 'INCLUIR_REMUNERADO'
            st.markdown(
                f'<div class="card-servico card-troca">'
                f'<h3>📅 {data_fmt}</h3>'
                f'<p>👤 <b>{nome_orig}</b> quer trocar contigo</p>'
                f'<p>🟢 Recebes: <b>{r["servico_origem"]}</b></p>'
                f'<p>🔴 Dás: <b>{r["servico_destino"]}</b></p>'
                + (f'<p>💶 Inclui transferência do teu remunerado para {nome_orig}</p>' if tem_rem_troca else '') +
                f'</div>',
                unsafe_allow_html=True,
            )

        c1, c2 = st.columns(2)
        if c1.button("✅ ACEITAR", key=f"ac_{idx}", use_container_width=True):
            obs_r = str(r.get('observações', '') or '').strip()
            if obs_r == 'INCLUIR_REMUNERADO':
                try:
                    df_dia_rem_t = loader.carregar_escala(datetime.strptime(r['data'], '%d/%m/%Y'))
                    rem_meu = df_dia_rem_t[
                        (df_dia_rem_t['id'].astype(str).str.strip() == u_id) &
                        (df_dia_rem_t['serviço'].str.lower().str.contains(r'remu|grat', na=False))
                    ]
                    if not rem_meu.empty:
                        serv_rem = f"{rem_meu.iloc[0]['serviço']} ({rem_meu.iloc[0]['horário']})"
                        _salvar_troca_gsheet([r['data'], u_id, 'MATAR_REMUNERADO', r['id_origem'], serv_rem, 'Pendente_Admin', ''])
                except Exception:
                    pass
            st.session_state['pedido_acao'] = {'idx': idx, 'status': 'Pendente_Admin'}
            st.rerun()
        if c2.button("❌ RECUSAR", key=f"re_{idx}", use_container_width=True):
            st.session_state['pedido_acao'] = {'idx': idx, 'status': 'Recusada'}
            st.rerun()


# ───────────────────────────────────────
# Tab 3: Histórico
# ───────────────────────────────────────

def _render_tab_historico(
    u_id: str,
    df_trocas: pd.DataFrame,
    df_util: pd.DataFrame,
) -> None:
    """Tab de histórico pessoal de trocas."""
    st.title("📋 Histórico das Minhas Trocas")
    if df_trocas.empty:
        st.info("Não existem trocas registadas.")
        return

    minhas = df_trocas[
        (df_trocas['id_origem'].astype(str) == u_id) |
        (df_trocas['id_destino'].astype(str) == u_id)
    ].copy()
    minhas['_data_ord'] = pd.to_datetime(minhas['data'], format='%d/%m/%Y', errors='coerce')
    minhas = minhas.sort_values('_data_ord', ascending=False).drop(columns='_data_ord')

    if minhas.empty:
        st.info("Não tens trocas registadas.")
        return

    estados = ["Todos"] + sorted(minhas['status'].dropna().unique().tolist())
    filtro = st.selectbox("Filtrar por estado:", estados)
    if filtro != "Todos":
        minhas = minhas[minhas['status'] == filtro]
    st.caption(f"{len(minhas)} registo(s)")

    for idx, r in minhas.iterrows():
        fui_origem = str(r['id_origem']) == u_id
        outro_id = r['id_destino'] if fui_origem else r['id_origem']
        outro_nome = _get_nome_militar(df_util, outro_id)
        meu_serv = r['servico_origem'] if fui_origem else r['servico_destino']
        outro_serv = r['servico_destino'] if fui_origem else r['servico_origem']
        is_matar = str(r['servico_origem']) == 'MATAR_REMUNERADO'
        status = r.get('status', '')
        cor = "🟢" if status == "Aprovada" else ("🔴" if status in ("Rejeitada", "Cancelada") else "🟡")

        if is_matar:
            papel = "Requerente" if fui_origem else "Cedente"
            titulo = f"{cor} {r['data']} — Fazer Remunerado: {outro_serv} ({status})"
        else:
            papel = "Requerente" if fui_origem else "Substituto"
            titulo = f"{cor} {r['data']} — {meu_serv} ↔ {outro_serv} ({status})"

        with st.expander(titulo, expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**O meu papel:** {papel}")
                if not is_matar:
                    st.markdown(f"**O meu serviço:** `{meu_serv}`")
            with col2:
                st.markdown(f"**Contraparte:** {outro_nome}")
                st.markdown(f"**Remunerado:** `{outro_serv}`" if is_matar else f"**Serviço contraparte:** `{outro_serv}`")
            if status == "Aprovada":
                st.caption(f"⚖️ Validado por **{r.get('validador', 'N/A')}** em {r.get('data_validacao', 'N/A')}")
            elif status in ("Pendente_Militar", "Pendente_Admin") and fui_origem:
                if st.button("🚫 Cancelar pedido", key=f"cancel_{idx}"):
                    if _atualizar_status_gsheet(idx, "Cancelada"):
                        _invalidar_trocas()
                        st.success("Pedido cancelado.")
                        st.rerun()


# ───────────────────────────────────────
# Render principal
# ───────────────────────────────────────

def render_trocas_pedidos(usuario: Usuario) -> None:
    """Renderiza a página completa de Trocas com 3 tabs.

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        u_id = str(usuario.id)

        loader = DataLoader(db=GoogleSheetsClient())
        df_trocas = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()
        ano_atual = datetime.now().year
        df_ferias = loader.carregar_ferias(ano_atual)
        df_folgas = loader.carregar_folgas(ano_atual)
        feriados = loader.carregar_feriados(ano_atual)

        st.title("🔄 Trocas")
        tab_sol, tab_ped, tab_hist = st.tabs(["📨 Solicitar", "📥 Pedidos Recebidos", "📋 Histórico"])

        with tab_sol:
            _render_tab_solicitar(u_id, loader, df_trocas, df_util, df_ferias, df_folgas, feriados)

        with tab_ped:
            _render_tab_pedidos_recebidos(u_id, df_trocas, df_util, loader)

        with tab_hist:
            _render_tab_historico(u_id, df_trocas, df_util)

    except Exception as e:
        render_alert(f"Erro na página de trocas: {e}", tipo="error")
