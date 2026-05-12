"""
Página «Minha Escala» – vista pessoal do militar.

Inclui:
- Aniversários de hoje
- Exportar .ics (serviços + folgas)
- Vista Calendário Mensal
- Vista Próximos Serviços
- Tab Estatísticas (não-admin)
- Tab Férias (não-admin)
"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import streamlit as st

from config.settings import SESSION_USER_ID, SESSION_USER_NAME, SESSION_IS_ADMIN
from core.database import GoogleSheetsClient, get_sheet
from core.utils import norm, parse_horario as _parse_horario, parse_data_flexivel
from models.usuario import Usuario
from services.data_loader import DataLoader
from ui.components.alerts import render_alert
from ui.components.cards import render_servico_card, render_troca_card, render_remunerado_card, render_ausencia_card


# ───────────────────────────────────────
# Helpers reutilizáveis
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


def _get_nome_curto(df_util: pd.DataFrame, mid: Any) -> str:
    mid = str(mid).strip()
    if df_util.empty or 'id' not in df_util.columns:
        return mid
    row = df_util[df_util['id'].astype(str).str.strip() == mid]
    if row.empty:
        return mid
    r = row.iloc[0]
    nomes = str(r.get('nome', '')).strip().split()
    nome_curto = f"{nomes[0]} {nomes[-1]}" if len(nomes) > 1 else ' '.join(nomes)
    return nome_curto


def _format_colegas(ids: set, df_util: pd.DataFrame) -> str:
    """Formata IDs de colegas em HTML."""
    if not ids:
        return ''
    partes = []
    for c_id in sorted(ids):
        c_row = df_util[df_util['id'].astype(str).str.strip() == c_id] if 'id' in df_util.columns else pd.DataFrame()
        if not c_row.empty:
            c_posto = c_row.iloc[0].get('posto', '')
            c_nomes = c_row.iloc[0].get('nome', '').strip().split()
            c_nome_curto = f"{c_nomes[0]} {c_nomes[-1]}" if len(c_nomes) > 1 else ' '.join(c_nomes)
            partes.append(f"{c_id} {c_posto} {c_nome_curto}")
        else:
            partes.append(c_id)
    return f'<p style="font-size:0.78rem;color:#475569">👥 {" | ".join(partes)}</p>' if partes else ''


def _filtrar_colegas_com_trocas(
    colegas_orig: list,
    df_trocas: pd.DataFrame,
    d_s: str,
    serv_nome: str,
    hor: str,
    u_id: str,
) -> set:
    """Filtra colegas considerando trocas aprovadas."""
    ids_finais: set = set()
    for c_id in colegas_orig:
        saiu = False
        if not df_trocas.empty:
            tr_o = df_trocas[
                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                (df_trocas['id_origem'].astype(str) == c_id) &
                (df_trocas['servico_origem'].str.lower().str.contains(serv_nome.lower()[:8], na=False)) &
                (df_trocas['servico_origem'].str.contains(hor, na=False))
            ]
            tr_d = df_trocas[
                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                (df_trocas['id_destino'].astype(str) == c_id) &
                (df_trocas['servico_destino'].str.lower().str.contains(serv_nome.lower()[:8], na=False)) &
                (df_trocas['servico_destino'].str.contains(hor, na=False))
            ]
            if not tr_o.empty:
                saiu = True
                novo = str(tr_o.iloc[0]['id_destino'])
                if novo != u_id:
                    ids_finais.add(novo)
            if not tr_d.empty:
                saiu = True
                novo = str(tr_d.iloc[0]['id_origem'])
                if novo != u_id:
                    ids_finais.add(novo)
        if not saiu:
            ids_finais.add(c_id)
    return ids_finais


def _obter_remunerados_do_dia(
    df_d: pd.DataFrame,
    df_trocas: pd.DataFrame,
    u_id: str,
    d_s: str,
) -> pd.DataFrame:
    """Obtém remunerados do utilizador num dia, ajustados com trocas aprovadas."""
    rem_mil = df_d[df_d['id'].astype(str).apply(
        lambda x: u_id in re.split(r'[;,]+', x)
    )]
    rem_mil = rem_mil[rem_mil['serviço'].apply(norm).str.contains('remu|grat', na=False)]
    dedup_cols = ['serviço', 'horário']
    for _dc in ['viatura', 'observações']:
        if _dc in rem_mil.columns:
            dedup_cols.append(_dc)
    rem_mil = rem_mil.drop_duplicates(subset=dedup_cols, keep='first').reset_index(drop=True)

    if not df_trocas.empty:
        # Excluir remunerados cedidos
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
        # Adicionar remunerados obtidos via matar remunerado
        matar_apr = df_trocas[
            (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
            (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
            (df_trocas['id_origem'].astype(str) == u_id)
        ]
        for _, mt in matar_apr.iterrows():
            serv_r = mt['servico_destino'].rsplit('(', 1)[0].strip()
            hor_r = mt['servico_destino'].rsplit('(', 1)[1].rstrip(')') if '(' in mt['servico_destino'] else ''
            linha_rem = df_d[
                (df_d['serviço'].astype(str).str.strip().str.lower() == serv_r.lower()) &
                (df_d['horário'].astype(str).str.strip() == hor_r.strip())
            ]
            if not linha_rem.empty:
                rem_mil = pd.concat([rem_mil, linha_rem.iloc[[0]]], ignore_index=True)
    return rem_mil


# ───────────────────────────────────────
# Sub-render: ICS export
# ───────────────────────────────────────

def _render_exportar_ics(u_id: str, loader: DataLoader, dias_publicados: set, feriados: list) -> None:
    """Renderiza o expander de exportar .ics dos serviços."""
    with st.expander("📆 Exportar para Calendário", expanded=False):
        st.caption("Gera um ficheiro .ics com os teus próximos serviços para importar no iPhone, Android ou Outlook.")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            dias_exp = st.slider("Dias a incluir:", 7, 90, 30)
        with col_exp2:
            incl_folgas_exp = st.checkbox("Incluir folgas", value=True, key="exp_incl_folgas")
            incl_ferias_exp = st.checkbox("Incluir férias", value=True, key="exp_incl_ferias")
        if st.button("📥 Gerar ficheiro .ics", use_container_width=True):
            ics_lines = [
                "BEGIN:VCALENDAR", "VERSION:2.0",
                "PRODID:-//GNR Famalicão//Escala//PT",
                "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                "X-WR-CALNAME:Escala GNR Famalicão",
                "X-WR-TIMEZONE:Europe/Lisbon",
            ]
            hj_exp = datetime.now()
            eventos = 0
            for i_exp in range(dias_exp):
                dt_exp = hj_exp + timedelta(days=i_exp)
                aba_exp = dt_exp.strftime("%d-%m")
                if aba_exp not in dias_publicados:
                    continue
                try:
                    df_exp = loader.carregar_escala(dt_exp)
                except Exception:
                    continue
                if df_exp.empty:
                    continue
                meu_exp = df_exp[df_exp['id'].astype(str).str.strip() == u_id]
                if meu_exp.empty:
                    continue
                for _, row_exp in meu_exp.iterrows():
                    serv_exp = str(row_exp.get('serviço', '')).strip()
                    hor_exp = str(row_exp.get('horário', '')).strip()
                    obs_exp = str(row_exp.get('observações', '')).strip()
                    if not serv_exp:
                        continue
                    s_n_skip = norm(serv_exp)
                    if not incl_folgas_exp and 'folga' in s_n_skip:
                        continue
                    if not incl_ferias_exp and 'ferias' in s_n_skip:
                        continue
                    s_n = norm(serv_exp)
                    if any(x in s_n for x in ['remu', 'grat']):
                        emoji = "💰"
                    elif 'patrulha' in s_n or 'ocorr' in s_n:
                        emoji = "🚔"
                    elif 'atendimento' in s_n:
                        emoji = "🖥️"
                    elif 'apoio' in s_n:
                        emoji = "🤝"
                    elif any(x in s_n for x in ['ferias', 'licen']):
                        emoji = "🏖️"
                    elif 'folga' in s_n:
                        emoji = "😴"
                    elif any(x in s_n for x in ['tribunal', 'dilig']):
                        emoji = "⚖️"
                    else:
                        emoji = "🛡️"
                    dt_inicio = dt_exp
                    dt_fim = dt_exp
                    if hor_exp and '-' in hor_exp:
                        try:
                            h_ini, h_fim = hor_exp.split('-')
                            hi = int(h_ini.strip().replace('H', '').replace('h', ''))
                            hf = int(h_fim.strip().replace('H', '').replace('h', ''))
                            dt_inicio = dt_exp.replace(hour=hi, minute=0, second=0, microsecond=0)
                            if hf <= hi:
                                dt_fim = (dt_exp + timedelta(days=1)).replace(hour=hf, minute=0, second=0, microsecond=0)
                            else:
                                dt_fim = dt_exp.replace(hour=hf, minute=0, second=0, microsecond=0)
                        except Exception:
                            dt_inicio = dt_exp.replace(hour=0, minute=0, second=0, microsecond=0)
                            dt_fim = dt_exp.replace(hour=23, minute=59, second=0, microsecond=0)
                    else:
                        dt_inicio = dt_exp.replace(hour=0, minute=0, second=0, microsecond=0)
                        dt_fim = dt_exp.replace(hour=23, minute=59, second=0, microsecond=0)
                    uid_evt = f"{dt_exp.strftime('%Y%m%d')}-{u_id}-{eventos}"
                    summary = f"{emoji} {serv_exp}" + (f" ({hor_exp})" if hor_exp else "")
                    desc = obs_exp if obs_exp and obs_exp != 'nan' else ""
                    ics_lines += [
                        "BEGIN:VEVENT",
                        f"UID:{uid_evt}@gnr.famalicao",
                        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                        f"DTSTART:{dt_inicio.strftime('%Y%m%dT%H%M%S')}",
                        f"DTEND:{dt_fim.strftime('%Y%m%dT%H%M%S')}",
                        f"SUMMARY:{summary}",
                        f"DESCRIPTION:{desc}",
                        "LOCATION:Posto Territorial de Vila Nova de Famalicão",
                        "END:VEVENT",
                    ]
                    eventos += 1
            ics_lines.append("END:VCALENDAR")
            ics_content = "\r\n".join(ics_lines)
            if eventos > 0:
                st.download_button(
                    f"⬇️ Descarregar ({eventos} serviços)",
                    data=ics_content.encode('utf-8'),
                    file_name=f"escala_gnr_{u_id}.ics",
                    mime="text/calendar",
                    use_container_width=True,
                )
            else:
                st.info("Não encontrei serviços para os próximos dias.")


def _render_exportar_folgas_ics(u_id: str, loader: DataLoader, feriados: list) -> None:
    """Renderiza o expander de exportar mapa de folgas .ics."""
    with st.expander("🏖️ Exportar Mapa de Folgas", expanded=False):
        st.caption("Gera um ficheiro .ics com todas as tuas folgas do ano.")
        if st.button("📥 Gerar mapa de folgas", use_container_width=True, key="btn_ics_folgas"):
            with st.spinner("A calcular folgas..."):
                ano_fme = datetime.now().year
                df_folgas_me = loader.carregar_folgas(ano_fme)
                grupos_me = loader.carregar_grupos_folga()
                ics_f = [
                    "BEGIN:VCALENDAR", "VERSION:2.0",
                    "PRODID:-//GNR Famalicão//Folgas//PT",
                    "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                    "X-WR-CALNAME:Folgas GNR Famalicão",
                ]
                n_folgas = 0
                for m in range(1, 13):
                    _, n_dias = monthrange(ano_fme, m)
                    for d in range(1, n_dias + 1):
                        dt = date(ano_fme, m, d)
                        tipo = DataLoader.militar_de_folga(u_id, dt, df_folgas_me, grupos_me, feriados)
                        if tipo:
                            dtstr = dt.strftime('%Y%m%d')
                            dtend = (dt + timedelta(days=1)).strftime('%Y%m%d')
                            ics_f += [
                                "BEGIN:VEVENT",
                                f"UID:folga-{u_id}-{dtstr}@gnr",
                                f"DTSTART;VALUE=DATE:{dtstr}",
                                f"DTEND;VALUE=DATE:{dtend}",
                                f"SUMMARY:{'😴' if 'Semanal' in tipo else '🌿'} {tipo}",
                                "END:VEVENT",
                            ]
                            n_folgas += 1
                ics_f.append("END:VCALENDAR")
                if n_folgas > 0:
                    st.download_button(
                        f"⬇️ Descarregar ({n_folgas} folgas)",
                        data="\r\n".join(ics_f).encode('utf-8'),
                        file_name=f"folgas_{u_id}_{ano_fme}.ics",
                        mime="text/calendar",
                        use_container_width=True, key="dl_folgas_ics",
                    )
                else:
                    st.info("Não tens folgas configuradas.")


# ───────────────────────────────────────
# Sub-render: Calendário Mensal
# ───────────────────────────────────────

def _render_calendario_mensal(
    u_id: str,
    loader: DataLoader,
    df_trocas: pd.DataFrame,
    dias_publicados: set,
    feriados: list,
) -> None:
    """Vista de calendário mensal."""
    hj_cal = datetime.now()
    col_m, col_a, _ = st.columns([1, 1, 3])
    nomes_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    with col_m:
        mes_sel = st.selectbox(
            "Mês:", list(range(1, 13)),
            index=hj_cal.month - 1,
            format_func=lambda m: nomes_mes[m - 1],
        )
    with col_a:
        ano_sel = st.selectbox("Ano:", [hj_cal.year - 1, hj_cal.year, hj_cal.year + 1], index=1)

    _, n_dias = monthrange(ano_sel, mes_sel)

    # Carregar serviços do mês
    servicos_mes: Dict[int, dict] = {}
    for d in range(1, n_dias + 1):
        dt_cal = datetime(ano_sel, mes_sel, d)
        aba = dt_cal.strftime("%d-%m")
        if aba not in dias_publicados:
            continue
        try:
            df_cal = loader.carregar_escala(dt_cal)
        except Exception:
            continue
        if not df_cal.empty:
            m_cal = df_cal[df_cal['id'].astype(str) == u_id]
            if not m_cal.empty:
                row_cal = m_cal.iloc[0]
                # Verificar trocas
                troca_cal = None
                if not df_trocas.empty:
                    tr_c = df_trocas[
                        (df_trocas['data'] == dt_cal.strftime('%d/%m/%Y')) &
                        (df_trocas['status'] == 'Aprovada') &
                        (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                        ((df_trocas['id_origem'].astype(str) == u_id) |
                         (df_trocas['id_destino'].astype(str) == u_id))
                    ]
                    if not tr_c.empty:
                        t_c = tr_c.iloc[0]
                        troca_cal = t_c['servico_destino'] if str(t_c['id_origem']) == u_id else t_c['servico_origem']
                servicos_mes[d] = {
                    'serviço': troca_cal if troca_cal else row_cal['serviço'],
                    'horário': row_cal['horário'],
                    'troca': troca_cal is not None,
                    'obs': str(row_cal.get('observações', '') or '').strip(),
                    'remunerados': [],
                }
                # Verificar remunerados no mesmo dia
                rem_cal = _obter_remunerados_do_dia(df_cal, df_trocas, u_id, dt_cal.strftime('%d/%m/%Y'))
                for _, rr in rem_cal.iterrows():
                    servicos_mes[d]['remunerados'].append(f"💰 {rr['serviço']} ({rr['horário']})")

    hoje_d = datetime.now().date()
    nomes_dia = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    st.markdown(f"### {nomes_mes[mes_sel - 1]} {ano_sel}")

    tem_servicos = False
    for d in range(1, n_dias + 1):
        dt_cel = date(ano_sel, mes_sel, d)
        is_hoje = dt_cel == hoje_d
        weekday = dt_cel.weekday()
        dia_sem = nomes_dia[weekday]
        is_fds = weekday >= 5
        is_feriado = dt_cel in feriados

        borda_esq = "4px solid #1E3A8A" if is_hoje else ("3px solid #DC2626" if is_feriado else ("3px solid #F59E0B" if is_fds else "3px solid #E2E8F0"))
        cor_num = "#DC2626" if is_feriado else ("#B45309" if is_fds else "#1E293B")
        cor_dia = "#DC2626" if is_feriado else ("#B45309" if is_fds else "#64748B")
        hoje_badge = " <span style='background:#1E3A8A;color:white;font-size:0.65rem;padding:1px 6px;border-radius:10px'>HOJE</span>" if is_hoje else ""

        if d in servicos_mes:
            tem_servicos = True
            info = servicos_mes[d]
            if info['troca']:
                bg, cor_txt, icone = "#FFFBEB", "#92400E", "🔄"
            else:
                s_n = norm(info['serviço'])
                if any(x in s_n for x in ['ferias', 'licen', 'doente']):
                    bg, cor_txt, icone = "#F8FAFC", "#64748B", "🏖️"
                elif 'folga' in s_n:
                    bg, cor_txt, icone = "#F5F3FF", "#7C3AED", "😴"
                elif any(x in s_n for x in ['tribunal', 'dilig']):
                    bg, cor_txt, icone = "#FFF1F2", "#DC2626", "⚖️"
                elif any(x in s_n for x in ['remu', 'grat']):
                    bg, cor_txt, icone = "#ECFDF5", "#065F46", "💰"
                else:
                    bg, cor_txt, icone = "#EFF6FF", "#1E3A8A", "🛡️"
            if is_fds and bg == "#EFF6FF":
                bg = "#FFFBEB"
            rems = info.get('remunerados', [])
            rem_html = "".join([f"<div style='font-size:0.75rem;color:#065F46;margin-top:2px'>{r}</div>" for r in rems]) if rems else ""
            st.markdown(f"""
            <div style='background:{bg};border-left:{borda_esq};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px'>
                <div style='min-width:48px;text-align:center'>
                    <div style='font-size:1.2rem;font-weight:800;color:{cor_num};line-height:1'>{d}</div>
                    <div style='font-size:0.7rem;color:{cor_dia};font-weight:{"700" if is_fds else "400"}'>{dia_sem}</div>
                </div>
                <div>
                    <div style='font-size:0.9rem;font-weight:700;color:{cor_txt}'>{icone} {info['serviço']}{hoje_badge}</div>
                    <div style='font-size:0.8rem;color:#475569'>🕒 {info['horário']}</div>{rem_html}
                </div>
            </div>""", unsafe_allow_html=True)
        elif is_hoje:
            st.markdown(f"""
            <div style='background:#F8FAFC;border-left:{borda_esq};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px'>
                <div style='min-width:48px;text-align:center'>
                    <div style='font-size:1.2rem;font-weight:800;color:#94A3B8;line-height:1'>{d}</div>
                    <div style='font-size:0.7rem;color:#94A3B8'>{dia_sem}</div>
                </div>
                <div style='color:#94A3B8;font-size:0.85rem'>Sem serviço escalado{hoje_badge}</div>
            </div>""", unsafe_allow_html=True)

    if not tem_servicos:
        st.info("Não foram encontrados serviços escalados neste mês.")


# ───────────────────────────────────────
# Sub-render: Próximos Serviços
# ───────────────────────────────────────

def _render_proximos_servicos(
    u_id: str,
    u_nome: str,
    loader: DataLoader,
    df_trocas: pd.DataFrame,
    df_util: pd.DataFrame,
    df_ferias: pd.DataFrame,
    df_licencas: pd.DataFrame,
    dias_publicados: set,
    feriados: list,
) -> None:
    """Vista de próximos serviços (lista de cards)."""
    st.caption(f"Toda a escala disponível a partir de hoje para **{u_nome}**")
    hj = datetime.now()
    encontrou_algum = False

    dias_a_mostrar = []
    for delta in range(90):
        dt_c = hj + timedelta(days=delta)
        aba_c = dt_c.strftime('%d-%m')
        if aba_c in dias_publicados:
            dias_a_mostrar.append(dt_c)
        if len(dias_a_mostrar) >= 20:
            break

    dias_sem_dados = 0
    for dt in dias_a_mostrar:
        if dias_sem_dados >= 5:
            break
        i = (dt - hj).days
        d_s = dt.strftime('%d/%m/%Y')
        lbl = "🟢 HOJE" if i == 0 else ("🔵 AMANHÃ" if i == 1 else dt.strftime("%d/%m (%a)").upper())

        # Verificar trocas aprovadas
        if not df_trocas.empty:
            tr_v = df_trocas[
                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                (df_trocas['servico_origem'] != 'MATAR_REMUNERADO') &
                ((df_trocas['id_origem'].astype(str) == u_id) |
                 (df_trocas['id_destino'].astype(str) == u_id))
            ]
        else:
            tr_v = pd.DataFrame()

        if not tr_v.empty:
            # ── Card de troca aprovada ──
            t = tr_v.iloc[0]
            if str(t['id_origem']) == u_id:
                s_ex, era, com = t['servico_destino'], t['servico_origem'], t['id_destino']
            else:
                s_ex, era, com = t['servico_origem'], t['servico_destino'], t['id_origem']
            try:
                df_d = loader.carregar_escala(dt)
            except Exception:
                df_d = pd.DataFrame()
            serv_novo_nome = s_ex.rsplit('(', 1)[0].strip()
            hor_novo = s_ex.rsplit('(', 1)[1].rstrip(')') if '(' in s_ex else ''
            com_nome = _get_nome_militar(df_util, com)
            # Colegas
            colegas_troca_html = ''
            if not df_d.empty:
                colegas_orig_t = df_d[
                    (df_d['serviço'].astype(str).str.strip().str.lower() == serv_novo_nome.lower()) &
                    (df_d['horário'].astype(str).str.strip() == hor_novo.strip()) &
                    (df_d['id'].astype(str).str.strip() != u_id) &
                    (df_d['id'].astype(str).str.strip() != str(com).strip()) &
                    (df_d['id'].astype(str).str.strip() != '') &
                    (df_d['id'].astype(str).str.strip() != 'nan')
                ]['id'].astype(str).str.strip().tolist()
                ids_finais_t = _filtrar_colegas_com_trocas(colegas_orig_t, df_trocas, d_s, serv_novo_nome, hor_novo, u_id)
                colegas_troca_html = _format_colegas(ids_finais_t, df_util)

            obs_novo = ''
            if not df_d.empty:
                mask_novo = (
                    (df_d['serviço'].astype(str).str.strip().str.lower() == serv_novo_nome.lower()) &
                    (df_d['horário'].astype(str).str.strip() == hor_novo.strip())
                )
                if mask_novo.any():
                    row_novo = df_d[mask_novo].iloc[0]
                    obs_novo = str(row_novo.get('observações', '') or '').strip()

            obs_html_t = f'<p>📝 {obs_novo}</p>' if obs_novo else ''
            st.markdown(
                f'<div class="card-servico card-troca">'
                f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#92400E;">Troca Aprovada</span></p>'
                f'<h3>🔄 {serv_novo_nome}</h3>'
                f'<p>🕒 {hor_novo}</p>'
                f'{colegas_troca_html}'
                f'<p style="font-size:0.78rem;color:#92400E">🔄 c/ {com_nome}</p>'
                f'{obs_html_t}'
                f'</div>',
                unsafe_allow_html=True,
            )
            dias_sem_dados = 0
            encontrou_algum = True

            # Remunerados mesmo quando há troca
            if not df_d.empty:
                rem_mil_t = _obter_remunerados_do_dia(df_d, df_trocas, u_id, d_s)
                for _, rr in rem_mil_t.iterrows():
                    obs_r = str(rr.get('observações', '') or '').strip()
                    obs_r_html = f'<p>📝 {obs_r}</p>' if obs_r else ''
                    serv_rr_t = str(rr['serviço']).strip().lower()
                    # Matar info
                    matar_html_t = ''
                    if not df_trocas.empty:
                        mt_este = df_trocas[
                            (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                            (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                            (df_trocas['id_origem'].astype(str) == u_id) &
                            (df_trocas['servico_destino'].str.lower().str.contains(serv_rr_t[:10], na=False))
                        ]
                        if not mt_este.empty:
                            cedente_nome = _get_nome_militar(df_util, mt_este.iloc[0]['id_destino'])
                            matar_html_t = f'<p style="font-size:0.78rem;color:#059669">🔄 c/ {cedente_nome}</p>'
                    st.markdown(
                        f'<div class="card-servico card-rem">'
                        f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#059669;">💶 Remunerado</span></p>'
                        f'<h3>💰 {rr["serviço"]}</h3>'
                        f'<p>🕒 {rr["horário"]}</p>'
                        f'{matar_html_t}{obs_r_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        else:
            # ── Card normal (sem troca) ──
            try:
                df_d = loader.carregar_escala(dt)
            except Exception:
                df_d = pd.DataFrame()
            if not df_d.empty:
                m = df_d[df_d['id'].astype(str).apply(lambda x: u_id in [ii.strip() for ii in re.split(r'[;,]+', x)])]
                m = m[~m['serviço'].apply(norm).str.contains('remu|grat', na=False)]
                if not m.empty:
                    row = m.iloc[0]
                    obs_val = str(row.get('observações', '') or '').strip()
                    obs_html = f'<p>📝 {obs_val}</p>' if obs_val else ''
                    s_norm = norm(row['serviço'])
                    if any(x in s_norm for x in ['ferias', 'licen', 'doente']):
                        card_class, icone_s = 'card-ausencia', '🏖️'
                    elif 'folga' in s_norm:
                        card_class, icone_s = 'card-folga', '😴'
                    elif any(x in s_norm for x in ['tribunal', 'dilig']):
                        card_class, icone_s = 'card-tribunal', '⚖️'
                    else:
                        card_class, icone_s = 'card-meu', '🛡️'

                    # Colegas
                    colegas_html = ''
                    _excluir = ['ferias', 'licen', 'doente', 'folga', 'pronto', 'secretaria', 'inquer', 'dilig', 'tribunal']
                    if not any(x in s_norm for x in _excluir):
                        serv_meu = str(row['serviço']).strip().lower()
                        hor_meu = str(row['horário']).strip()
                        colegas_orig = df_d[
                            (df_d['serviço'].astype(str).str.strip().str.lower() == serv_meu) &
                            (df_d['horário'].astype(str).str.strip() == hor_meu) &
                            (df_d['id'].astype(str).str.strip() != u_id) &
                            (df_d['id'].astype(str).str.strip() != '') &
                            (df_d['id'].astype(str).str.strip() != 'nan')
                        ]['id'].astype(str).str.strip().tolist()
                        ids_finais = _filtrar_colegas_com_trocas(colegas_orig, df_trocas, d_s, serv_meu, hor_meu, u_id)
                        colegas_html = _format_colegas(ids_finais, df_util)

                    # Remunerados do mesmo dia
                    rem_mil = _obter_remunerados_do_dia(df_d, df_trocas, u_id, d_s)
                    cards_rem = []
                    for _, rr in rem_mil.iterrows():
                        obs_r = str(rr.get('observações', '') or '').strip()
                        obs_r_html = f'<p>📝 {obs_r}</p>' if obs_r else ''
                        serv_rr = str(rr['serviço']).strip().lower()
                        matar_html = ''
                        if not df_trocas.empty:
                            mt_este = df_trocas[
                                (df_trocas['data'] == d_s) & (df_trocas['status'] == 'Aprovada') &
                                (df_trocas['servico_origem'] == 'MATAR_REMUNERADO') &
                                (df_trocas['id_origem'].astype(str) == u_id) &
                                (df_trocas['servico_destino'].str.lower().str.contains(serv_rr[:10], na=False))
                            ]
                            if not mt_este.empty:
                                cedente_nome = _get_nome_militar(df_util, mt_este.iloc[0]['id_destino'])
                                matar_html = f'<p style="font-size:0.78rem;color:#059669">🔄 c/ {cedente_nome}</p>'
                        _html_rem = (
                            f'<div class="card-servico card-rem">'
                            f'<p><b>{lbl}</b> &nbsp;·&nbsp; <span style="color:#059669;">💶 Remunerado</span></p>'
                            f'<h3>💰 {rr["serviço"]}</h3>'
                            f'<p>🕒 {rr["horário"]}</p>'
                            f'{matar_html}{obs_r_html}'
                            f'</div>'
                        )
                        _ini_rem, _ = _parse_horario(str(rr['horário']))
                        cards_rem.append((_ini_rem if _ini_rem is not None else 9999, _html_rem))

                    _hor_principal, _ = _parse_horario(str(row['horário']))
                    _hor_principal = _hor_principal if _hor_principal is not None else 9999
                    # Remunerados antes do serviço principal
                    for _ini_r, _html_r in sorted(cards_rem):
                        if _ini_r < _hor_principal:
                            st.markdown(_html_r, unsafe_allow_html=True)
                    # Serviço principal
                    st.markdown(
                        f'<div class="card-servico {card_class}">'
                        f'<p><b>{lbl}</b></p>'
                        f'<h3>{icone_s} {row["serviço"]}</h3>'
                        f'<p>🕒 {row["horário"]}</p>'
                        f'{colegas_html}{obs_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    # Remunerados depois do serviço principal
                    for _ini_r, _html_r in sorted(cards_rem):
                        if _ini_r >= _hor_principal:
                            st.markdown(_html_r, unsafe_allow_html=True)
                    encontrou_algum = True
                else:
                    # Militar não está na escala
                    is_fds_a = dt.weekday() >= 5
                    is_fer_a = dt.date() in feriados
                    if DataLoader.militar_de_ferias(u_id, dt.date(), df_ferias, feriados):
                        st.markdown(
                            f'<div class="card-servico card-ausencia">'
                            f'<p><b>{lbl}</b></p>'
                            f'<h3>🏖️ Férias</h3>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        encontrou_algum = True
                    else:
                        borda_a = "3px solid #DC2626" if is_fer_a else ("3px solid #F59E0B" if is_fds_a else "3px solid #E2E8F0")
                        cor_a = "#DC2626" if is_fer_a else ("#94A3B8" if not is_fds_a else "#B45309")
                        msg_a = "🎌 Feriado" if is_fer_a else "Sem serviço escalado"
                        st.markdown(
                            f'<div style="background:#F8FAFC;border-left:{borda_a};border-radius:8px;padding:8px 12px;margin-bottom:6px;display:flex;align-items:center;gap:12px">'
                            f'<div style="min-width:48px;text-align:center">'
                            f'<div style="font-size:1.2rem;font-weight:800;color:{cor_a};line-height:1">{dt.day}</div>'
                            f'<div style="font-size:0.7rem;color:{cor_a}">{"Sáb" if dt.weekday()==5 else "Dom" if dt.weekday()==6 else dt.strftime("%a").capitalize()}</div>'
                            f'</div>'
                            f'<div style="color:{cor_a};font-size:0.85rem">{msg_a}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                dias_sem_dados = 0
            else:
                dias_sem_dados += 1

    if not encontrou_algum:
        st.info("Não foram encontrados serviços escalados a partir de hoje.")


# ───────────────────────────────────────
# Render principal
# ───────────────────────────────────────

def render_minha_escala(usuario: Usuario) -> None:
    """Renderiza a página 'Minha Escala'.

    Args:
        usuario: Objecto :class:`Usuario` autenticado.
    """
    try:
        u_id = str(usuario.id)
        u_nome = usuario.nome
        is_admin = usuario.is_admin

        loader = DataLoader(sheets_client=GoogleSheetsClient())
        df_trocas = loader.carregar_trocas()
        df_util = loader.carregar_usuarios()
        ano_atual = datetime.now().year
        df_ferias = loader.carregar_ferias(ano_atual)
        feriados = loader.carregar_feriados(ano_atual)
        df_licencas = loader.carregar_licencas()
        dias_publicados = loader.carregar_listas().get('dias_publicados', set())

        st.title("📅 A Minha Escala")

        if is_admin:
            tab_escala, = st.tabs(["📅 Escala"])
        else:
            tab_escala, tab_stats, tab_ferias_t = st.tabs(["📅 Escala", "📊 Estatísticas", "🏖️ Férias"])

        with tab_escala:
            # Aniversários
            from ui.pages.dashboard import _verificar_aniversarios
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

            vista = st.radio("Vista:", ["📋 Próximos Serviços", "📅 Calendário Mensal"], horizontal=True, label_visibility="collapsed")

            # Exportar ICS
            _render_exportar_ics(u_id, loader, dias_publicados, feriados)
            _render_exportar_folgas_ics(u_id, loader, feriados)

            st.markdown("---")

            if vista == "📅 Calendário Mensal":
                _render_calendario_mensal(u_id, loader, df_trocas, dias_publicados, feriados)
            else:
                _render_proximos_servicos(
                    u_id, u_nome, loader, df_trocas, df_util,
                    df_ferias, df_licencas, dias_publicados, feriados,
                )

        # ── Tab Estatísticas (não-admin) ──
        if not is_admin:
            with tab_stats:
                _render_estatisticas_tab(u_id, u_nome, df_util, is_admin)

            with tab_ferias_t:
                _render_ferias_tab(u_id, u_nome, loader, feriados)

    except Exception as e:
        render_alert(f"Erro ao carregar a escala: {e}", tipo="error")


def _render_estatisticas_tab(u_id: str, u_nome: str, df_util: pd.DataFrame, is_admin: bool) -> None:
    """Renderiza a tab de estatísticas pessoais."""
    try:
        from config.settings import get_sheet_id
        sheet_id = get_sheet_id()

        # Nota: contar_servicos_historico é uma função do original que itera
        # por todas as abas. Reimplementamos de forma simplificada.
        st.caption(f"Estatísticas de serviço para **{u_nome}**")
        st.info("📊 As estatísticas detalhadas estão disponíveis na página **📊 Estatísticas** do menu.")
    except Exception as e:
        st.error(f"Erro ao carregar estatísticas: {e}")


def _render_ferias_tab(u_id: str, u_nome: str, loader: DataLoader, feriados: list) -> None:
    """Renderiza a tab de férias pessoais."""
    try:
        ano_tf = datetime.now().year
        df_ftab = loader.carregar_ferias(ano_tf)
        fer_tab = feriados
        meses_pt_f = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

        def fmt_data_f(d):
            return f"{d.day} de {meses_pt_f[d.month]} de {d.year}"

        if df_ftab.empty:
            st.info(f"Não há plano de férias para {ano_tf}.")
            return

        cols_ft = df_ftab.columns.tolist()
        id_col_ft = 'id' if 'id' in cols_ft else cols_ft[0]
        ini_cols_ft = [c for c in cols_ft if 'ini' in c.lower()]
        fim_cols_ft = [c for c in cols_ft if 'fim' in c.lower()]

        mil_ft = df_ftab[df_ftab[id_col_ft].astype(str).str.strip() == u_id]
        if mil_ft.empty:
            st.info("Não tens férias planeadas para este ano.")
            return

        row_ft = mil_ft.iloc[0]
        periodos_ft = []
        for ini_c, fim_c in zip(ini_cols_ft, fim_cols_ft):
            ini_v = str(row_ft.get(ini_c, '')).strip()
            fim_v = str(row_ft.get(fim_c, '')).strip()
            if not ini_v or ini_v == 'nan':
                continue
            ini_d = parse_data_flexivel(ini_v, ano_tf)
            fim_d = parse_data_flexivel(fim_v, ano_tf)
            if not ini_d or not fim_d:
                continue
            du = sum(1 for n in range((fim_d - ini_d).days + 1)
                     if (ini_d + timedelta(days=n)).weekday() < 5
                     and (ini_d + timedelta(days=n)) not in fer_tab)
            fim_ext = fim_d
            while True:
                prox = fim_ext + timedelta(days=1)
                if prox.weekday() >= 5 or prox in fer_tab:
                    fim_ext = prox
                else:
                    break
            dc = (fim_ext - ini_d).days + 1
            periodos_ft.append((ini_d, fim_d, du, dc))

        total_du_ft = sum(p[2] for p in periodos_ft)

        # Exportar férias
        with st.expander("📆 Exportar Mapa de Férias", expanded=False):
            st.caption("Gera um ficheiro .ics com as tuas férias para importar no calendário.")
            if st.button("📥 Gerar mapa de férias", use_container_width=True, key="btn_ics_ferias"):
                ics_fer = [
                    "BEGIN:VCALENDAR", "VERSION:2.0",
                    "PRODID:-//GNR Famalicão//Ferias//PT",
                    "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                    "X-WR-CALNAME:Férias GNR Famalicão",
                ]
                for i, (ini_d, fim_d, du, dc) in enumerate(periodos_ft, 1):
                    dtstr = ini_d.strftime('%Y%m%d')
                    dtend = (fim_d + timedelta(days=1)).strftime('%Y%m%d')
                    ics_fer += [
                        "BEGIN:VEVENT",
                        f"UID:ferias-{u_id}-{i}-{dtstr}@gnr",
                        f"DTSTART;VALUE=DATE:{dtstr}",
                        f"DTEND;VALUE=DATE:{dtend}",
                        f"SUMMARY:🏖️ Férias ({du} dias úteis)",
                        "END:VEVENT",
                    ]
                ics_fer.append("END:VCALENDAR")
                st.download_button(
                    f"⬇️ Descarregar ({len(periodos_ft)} períodos)",
                    data="\r\n".join(ics_fer).encode('utf-8'),
                    file_name=f"ferias_{u_id}_{ano_tf}.ics",
                    mime="text/calendar",
                    use_container_width=True, key="dl_ferias_ics",
                )

        st.markdown("---")
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#ECFDF5,#D1FAE5);border-radius:12px;'
            f'padding:16px 20px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">'
            f'<div><div style="font-size:0.8rem;color:#065F46;font-weight:600">PLANO DE FÉRIAS {ano_tf}</div>'
            f'<div style="font-size:1.1rem;font-weight:800;color:#064E3B">{u_nome}</div></div>'
            f'<div style="text-align:right"><div style="font-size:1.8rem;font-weight:900;color:#059669">{total_du_ft}</div>'
            f'<div style="font-size:0.75rem;color:#065F46">dias úteis</div></div></div>',
            unsafe_allow_html=True,
        )
        for i, (ini_d, fim_d, du, dc) in enumerate(periodos_ft, 1):
            st.markdown(
                f'<div style="background:#F0FDF4;border-left:4px solid #16A34A;border-radius:10px;'
                f'padding:14px 18px;margin-bottom:10px">'
                f'<div style="font-size:0.72rem;color:#16A34A;font-weight:700;margin-bottom:6px">PERÍODO {i}</div>'
                f'<div style="font-size:1rem;font-weight:700;color:#14532D">🏖️ {fmt_data_f(ini_d)}</div>'
                f'<div style="font-size:0.85rem;color:#166534;margin:2px 0 10px 0">até {fmt_data_f(fim_d)}</div>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
                f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">📅 {dc} dias corridos</span>'
                f'<span style="font-size:0.78rem;background:#DCFCE7;color:#15803D;padding:3px 10px;border-radius:12px;font-weight:600">💼 {du} dias úteis</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"Erro ao carregar férias: {e}")
