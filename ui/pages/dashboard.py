"""
Página Inicial / Dashboard.

Mostra resumo do utilizador: aniversários, notificações de trocas,
links rápidos e alertas importantes.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from config.settings import ADMINS, SESSION_USER_ID, SESSION_USER_NAME, SESSION_IS_ADMIN
from core.database import GoogleSheetsClient
from core.utils import norm, parse_horario as _parse_horario
from models.usuario import Usuario
from services.data_loader import DataLoader
from ui.components.alerts import render_alert, render_pendentes_badge


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_nome_militar(df_util: pd.DataFrame, mid: Any) -> str:
    """Devolve 'Posto Nome' a partir do ID."""
    mid = str(mid).strip()
    if df_util.empty or 'id' not in df_util.columns:
        return mid
    row = df_util[df_util['id'].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    return f"{r.get('posto', '')} {r.get('nome', '')}".strip() or mid


def _verificar_aniversarios(df_util: pd.DataFrame) -> list[tuple[str, int]]:
    """Devolve lista de (nome, idade) dos aniversariantes de hoje."""
    hoje = datetime.now()
    aniversariantes: list[tuple[str, int]] = []
    if 'nascimento' not in df_util.columns:
        return aniversariantes
    for _, row in df_util.iterrows():
        nasc = str(row.get('nascimento', '')).strip()
        if not nasc or nasc == 'nan':
            continue
        try:
            nasc_norm = nasc.replace("/", "-")
            dt_nasc = datetime.strptime(nasc_norm, "%d-%m-%Y")
            if dt_nasc.day == hoje.day and dt_nasc.month == hoje.month:
                idade = hoje.year - dt_nasc.year
                nome = f"{row.get('posto', '')} {row.get('nome', '')}".strip()
                aniversariantes.append((nome, idade))
        except Exception:
            continue
    return aniversariantes


def _verificar_trocas_afetadas(
    df_trocas: pd.DataFrame,
    u_id: str,
    df_util: pd.DataFrame,
    loader: DataLoader,
) -> list[str]:
    """Verifica trocas aprovadas cujo serviço pode já não existir na escala."""
    alertas: list[str] = []
    if df_trocas.empty:
        return alertas
    minhas_apr = df_trocas[
        (df_trocas['status'] == 'Aprovada') &
        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
        ((df_trocas['id_origem'].astype(str) == u_id) |
         (df_trocas['id_destino'].astype(str) == u_id))
    ]
    hoje_b = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for _, t in minhas_apr.iterrows():
        fui_origem = str(t['id_origem']) == u_id
        serv_meu_t = t['servico_origem'] if fui_origem else t['servico_destino']
        serv_nome = serv_meu_t.rsplit('(', 1)[0].strip().lower()
        hor_val = serv_meu_t.rsplit('(', 1)[1].rstrip(')') if '(' in serv_meu_t else ''
        try:
            dt_t = datetime.strptime(t['data'], '%d/%m/%Y')
        except Exception:
            continue
        if dt_t < hoje_b or (dt_t - hoje_b).days > 30:
            continue
        try:
            df_dia_t = loader.carregar_escala(dt_t)
        except Exception:
            continue
        if df_dia_t.empty:
            continue
        existe = df_dia_t[
            (df_dia_t['id'].astype(str) == u_id) &
            (df_dia_t['serviço'].astype(str).str.strip().str.lower() == serv_nome) &
            (df_dia_t['horário'].astype(str).str.strip() == hor_val.strip())
        ]
        if existe.empty:
            outro_nome = _get_nome_militar(
                df_util,
                t['id_destino'] if fui_origem else t['id_origem'],
            )
            alertas.append(
                f"⚠️ **Atenção!** A tua troca de **{t['data']}** com **{outro_nome}** "
                "pode estar afetada por uma alteração na escala. Contacta o teu superior."
            )
    return alertas


# ─────────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────────

def render_dashboard(usuario: Usuario) -> None:
    """Renderiza a página de Dashboard / Início.

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        u_id = str(usuario.id)
        u_nome = usuario.nome
        is_admin = usuario.is_admin

        loader = DataLoader(sheets_client=GoogleSheetsClient())
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()

        st.title("🏠 Painel Inicial")

        # ── Aniversários ──
        aniversariantes = _verificar_aniversarios(df_util)
        if aniversariantes:
            for nome, idade in aniversariantes:
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#FEF9C3,#FEF08A);border-left:4px solid #EAB308;
                border-radius:10px;padding:12px 16px;margin-bottom:10px;display:flex;align-items:center;gap:12px'>
                    <span style='font-size:1.8rem'>🎂</span>
                    <div>
                        <div style='font-weight:700;color:#713F12;font-size:0.95rem'>Hoje é o aniversário de {nome}!</div>
                        <div style='color:#92400E;font-size:0.82rem'>Completa {idade} anos — Parabéns! 🎉</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── Notificações de trocas pendentes ──
        if not df_trocas.empty:
            n_pend = len(df_trocas[
                (df_trocas['status'] == 'Pendente_Militar') &
                (df_trocas['id_destino'].astype(str) == u_id)
            ])
            if n_pend > 0:
                render_alert(
                    f"🔔 Tens **{n_pend} pedido(s) de troca** por responder! "
                    "Vai a **🔄 Trocas → 📥 Pedidos Recebidos**.",
                    tipo="warning",
                )
            if is_admin:
                n_admin = len(df_trocas[df_trocas['status'] == 'Pendente_Admin'])
                if n_admin > 0:
                    render_alert(
                        f"⚖️ {n_admin} troca(s) aguardam validação superior.",
                        tipo="info",
                    )

        # ── Alertas de trocas afetadas ──
        alertas_trocas = _verificar_trocas_afetadas(df_trocas, u_id, df_util, loader)
        for alerta in alertas_trocas:
            render_alert(alerta, tipo="error")

        # ── Resumo rápido ──
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                '<div style="text-align:center;padding:16px;background:#EFF6FF;border-radius:12px">'
                '<div style="font-size:2rem">📅</div>'
                '<div style="font-weight:700;color:#1E3A8A;margin-top:4px">Minha Escala</div>'
                '<div style="font-size:0.78rem;color:#475569">Ver serviços e calendário</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                '<div style="text-align:center;padding:16px;background:#FFFBEB;border-radius:12px">'
                '<div style="font-size:2rem">🔄</div>'
                '<div style="font-weight:700;color:#92400E;margin-top:4px">Trocas</div>'
                '<div style="font-size:0.78rem;color:#475569">Solicitar ou gerir trocas</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                '<div style="text-align:center;padding:16px;background:#ECFDF5;border-radius:12px">'
                '<div style="font-size:2rem">🏖️</div>'
                '<div style="font-weight:700;color:#065F46;margin-top:4px">Férias</div>'
                '<div style="font-size:0.78rem;color:#475569">Ver plano de férias</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Informações adicionais admin ──
        if is_admin:
            st.markdown("---")
            st.markdown("#### ⚙️ Atalhos Admin")
            ca, cb, cc = st.columns(3)
            with ca:
                if st.button("⚙️ Gerar Escala", use_container_width=True):
                    st.session_state['menu_target'] = '⚙️ Gerar Escala'
            with cb:
                if st.button("📢 Publicar Escala", use_container_width=True):
                    st.session_state['menu_target'] = '📢 Publicar Escala'
            with cc:
                if st.button("👤 Gerir Utilizadores", use_container_width=True):
                    st.session_state['menu_target'] = '👤 Gerir Utilizadores'

    except Exception as e:
        render_alert(f"Erro ao carregar o dashboard: {e}", tipo="error")
