"""
Página «Remunerados» – Gestão de serviços remunerados.

- Ver próximos remunerados
- Consultar ordem de rotação
- Histórico de remunerados realizados
- Admin: editar ordem de rotação
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm
from models.usuario import Usuario
from services.data_loader import DataLoader
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


def _load_ordem_remunerados() -> pd.DataFrame:
    """Carrega a ordem de remunerados da Google Sheet."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("ordem_remunerados")
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


# ───────────────────────────────────────
# Render principal
# ───────────────────────────────────────

def render_remunerados(usuario: Usuario) -> None:
    """Renderiza a página de gestão de remunerados.

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        u_id = str(usuario.id)
        is_admin = usuario.is_admin

        loader = DataLoader(sheets_client=GoogleSheetsClient())
        df_util = loader.carregar_usuarios()
        df_trocas = loader.carregar_trocas()

        st.title("💶 Remunerados")

        tab_proximos, tab_ordem, tab_historico = st.tabs([
            "📅 Próximos", "📊 Ordem de Rotação", "📋 Histórico"
        ])

        # ── Tab Próximos Remunerados ──
        with tab_proximos:
            st.markdown("#### 📅 Próximos Remunerados")
            dias_pub = loader.carregar_dias_publicados()
            hj = datetime.now()
            encontrou = False

            for delta in range(30):
                dt = hj + timedelta(days=delta)
                aba = dt.strftime('%d-%m')
                if aba not in dias_pub:
                    continue
                try:
                    df_d = loader.carregar_escala(dt)
                except Exception:
                    continue
                if df_d.empty:
                    continue

                # Filtrar remunerados do utilizador
                rem_mil = df_d[
                    df_d['id'].astype(str).apply(lambda x: u_id in re.split(r'[;,]+', x))
                ]
                rem_mil = rem_mil[rem_mil['serviço'].apply(norm).str.contains('remu|grat', na=False)]

                if not rem_mil.empty:
                    d_s = dt.strftime('%d/%m/%Y')
                    # Excluir cedidos
                    if not df_trocas.empty:
                        cedidos = df_trocas[
                            (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                            (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                            (df_trocas['id_destino'].astype(str) == u_id)
                        ]
                        for _, cd in cedidos.iterrows():
                            serv_cd = cd['servico_destino'].rsplit('(', 1)[0].strip()
                            hor_cd = cd['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in cd['servico_destino'] else ''
                            rem_mil = rem_mil[
                                ~((rem_mil['serviço'].astype(str).str.strip().str.lower() == serv_cd.lower()) &
                                  (rem_mil['horário'].astype(str).str.strip() == hor_cd.strip()))
                            ]

                    for _, rr in rem_mil.iterrows():
                        i = (dt - hj).days
                        lbl = "🟢 HOJE" if i == 0 else ("🔵 AMANHÃ" if i == 1 else dt.strftime("%d/%m (%a)").upper())
                        obs_r = str(rr.get('observações', '') or '').strip()
                        obs_html = f'<p>📝 {obs_r}</p>' if obs_r else ''
                        st.markdown(
                            f'<div class="card-servico card-rem">'
                            f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#059669;">💶 Remunerado</span></p>'
                            f'<h3>💰 {rr["serviço"]}</h3>'
                            f'<p>🕒 {rr["horário"]}</p>'
                            f'{obs_html}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        encontrou = True

            if not encontrou:
                st.info("Não tens remunerados escalados nos próximos 30 dias.")

        # ── Tab Ordem de Rotação ──
        with tab_ordem:
            st.markdown("#### 📊 Ordem de Rotação de Remunerados")
            df_ordem = _load_ordem_remunerados()
            if df_ordem.empty:
                st.info("Não há dados de ordem de remunerados.")
            else:
                # Enriquecer com nomes
                if 'id' in df_ordem.columns:
                    df_ordem_show = df_ordem.copy()
                    df_ordem_show['nome'] = df_ordem_show['id'].astype(str).apply(
                        lambda mid: _get_nome_militar(df_util, mid)
                    )
                    # Reordenar colunas
                    cols_first = ['id', 'nome']
                    cols_rest = [c for c in df_ordem_show.columns if c not in cols_first]
                    df_ordem_show = df_ordem_show[cols_first + cols_rest]
                else:
                    df_ordem_show = df_ordem

                pesq = st.text_input("🔍 Pesquisar:", placeholder="ID ou nome...", key="pesq_ordem_rem")
                if pesq:
                    p = pesq.lower()
                    mask = pd.Series([False] * len(df_ordem_show), index=df_ordem_show.index)
                    for col in df_ordem_show.columns:
                        mask |= df_ordem_show[col].astype(str).str.lower().str.contains(p, na=False)
                    df_ordem_show = df_ordem_show[mask]

                st.dataframe(df_ordem_show, use_container_width=True, hide_index=True)

                # Admin: editar ordem
                if is_admin:
                    st.markdown("---")
                    st.markdown("#### ✏️ Editar Ordem")
                    st.caption("Usa o editor abaixo para alterar a ordem de rotação.")
                    df_edited = st.data_editor(
                        df_ordem,
                        use_container_width=True,
                        hide_index=True,
                        key="editor_ordem_rem",
                    )
                    if st.button("💾 Guardar Alterações", use_container_width=True, key="btn_save_ordem"):
                        try:
                            sh = get_sheet()
                            ws = sh.worksheet("ordem_remunerados")
                            ws.clear()
                            headers = df_edited.columns.tolist()
                            rows = [headers] + df_edited.values.tolist()
                            ws.update('A1', rows)
                            st.success("✅ Ordem de remunerados atualizada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao guardar: {e}")

        # ── Tab Histórico ──
        with tab_historico:
            st.markdown("#### 📋 Histórico de Remunerados")
            if df_trocas.empty:
                st.info("Sem dados de trocas.")
            else:
                # Filtrar trocas de remunerado aprovadas
                rem_hist = df_trocas[
                    (df_trocas['status'] == 'Aprovada') &
                    (df_trocas['servico_origem'] == 'MATAR_REMUNERADO')
                ].copy()

                if not is_admin:
                    rem_hist = rem_hist[
                        (rem_hist['id_origem'].astype(str) == u_id) |
                        (rem_hist['id_destino'].astype(str) == u_id)
                    ]

                if rem_hist.empty:
                    st.info("Sem histórico de transferências de remunerados.")
                else:
                    rem_hist['_data_ord'] = pd.to_datetime(rem_hist['data'], format='%d/%m/%Y', errors='coerce')
                    rem_hist = rem_hist.sort_values('_data_ord', ascending=False).drop(columns='_data_ord')
                    for _, r in rem_hist.iterrows():
                        n_req = _get_nome_militar(df_util, r['id_origem'])
                        n_ced = _get_nome_militar(df_util, r['id_destino'])
                        with st.expander(f"📅 {r['data']} | {n_req} 💶 {n_ced}"):
                            st.markdown(f"**Requerente:** {n_req}")
                            st.markdown(f"**Cedente:** {n_ced}")
                            st.markdown(f"**Remunerado:** `{r['servico_destino']}`")
                            val_por = r.get('validador', 'N/A')
                            val_em = r.get('data_validacao', 'N/A')
                            st.caption(f"⚖️ Validado por **{val_por}** em {val_em}")

    except Exception as e:
        render_alert(f"Erro na página de remunerados: {e}", tipo="error")
