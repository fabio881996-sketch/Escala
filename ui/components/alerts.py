"""
ui/components/alerts.py
=======================
Componentes reutilizáveis de alertas e notificações para o Portal GNR.

Funções:
    - ``render_alert()`` — alerta customizado (success, warning, error, info).
    - ``render_conflitos()`` — mostra lista de conflitos/alertas da escala.
    - ``render_pendentes_badge()`` — badge de pedidos pendentes.
    - ``render_notificacao()`` — notificação inline dismissible.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st


# ======================================================================
# Configuração de tipos de alerta
# ======================================================================

ALERT_CONFIG = {
    "success": {
        "bg": "#ECFDF5",
        "border": "#059669",
        "color": "#065F46",
        "icon": "✅",
    },
    "warning": {
        "bg": "#FFFBEB",
        "border": "#D97706",
        "color": "#92400E",
        "icon": "⚠️",
    },
    "error": {
        "bg": "#FFF1F2",
        "border": "#DC2626",
        "color": "#991B1B",
        "icon": "❌",
    },
    "info": {
        "bg": "#EFF6FF",
        "border": "#1E3A8A",
        "color": "#1E3A8A",
        "icon": "ℹ️",
    },
}


# ======================================================================
# Alerta customizado
# ======================================================================

def render_alert(
    mensagem: str,
    tipo: str = "info",
    *,
    icone: str | None = None,
    dismissible: bool = False,
    key: str | None = None,
) -> None:
    """Renderiza alerta customizado com ícone e cores por tipo.

    Args:
        mensagem: Texto da mensagem.
        tipo: Tipo do alerta: "success", "warning", "error", "info".
        icone: Ícone customizado (se None, usa o padrão do tipo).
        dismissible: Se True, mostra botão para fechar (usa session_state).
        key: Key para controlo de estado (necessário se dismissible=True).

    Exemplo::

        render_alert("Escala guardada com sucesso!", "success")
        render_alert("Atenção: conflito de horário detectado.", "warning")
    """
    config = ALERT_CONFIG.get(tipo, ALERT_CONFIG["info"])
    icon = icone or config["icon"]

    # Verificar se já foi descartado
    if dismissible and key:
        if st.session_state.get(f"_alert_dismissed_{key}", False):
            return

    st.markdown(
        f"<div style='"
        f"background:{config['bg']};"
        f"border-left:4px solid {config['border']};"
        f"border-radius:8px;"
        f"padding:12px 16px;"
        f"margin-bottom:12px;"
        f"color:{config['color']};"
        f"font-size:0.88rem;"
        f"display:flex;align-items:center;gap:8px;"
        f"'>"
        f"<span style='font-size:1.1rem'>{icon}</span>"
        f"<span>{mensagem}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if dismissible and key:
        if st.button("✕ Fechar", key=f"_alert_dismiss_{key}"):
            st.session_state[f"_alert_dismissed_{key}"] = True
            st.rerun()


# ======================================================================
# Lista de conflitos da escala
# ======================================================================

def render_conflitos(
    conflitos: List[Dict[str, str]],
    *,
    titulo: str = "⚠️ Conflitos Detectados",
    expandido: bool = True,
) -> None:
    """Mostra lista de conflitos/alertas da escala num expander.

    Args:
        conflitos: Lista de dicionários com chaves:
            - ``tipo`` (str): "error", "warning", "info"
            - ``mensagem`` (str): descrição do conflito
            - ``militar`` (str, optional): ID/nome do militar
            - ``detalhe`` (str, optional): detalhe adicional
        titulo: Título do expander.
        expandido: Se o expander começa aberto.

    Exemplo::

        conflitos = [
            {"tipo": "error", "mensagem": "Sobreposição de horário", "militar": "101"},
            {"tipo": "warning", "mensagem": "Descanso insuficiente", "militar": "202"},
        ]
        render_conflitos(conflitos)
    """
    if not conflitos:
        render_alert("Nenhum conflito detectado. ✓", "success")
        return

    n_erros = sum(1 for c in conflitos if c.get("tipo") == "error")
    n_avisos = sum(1 for c in conflitos if c.get("tipo") == "warning")
    n_info = sum(1 for c in conflitos if c.get("tipo") == "info")

    subtitulo = []
    if n_erros:
        subtitulo.append(f"🔴 {n_erros} erro(s)")
    if n_avisos:
        subtitulo.append(f"🟡 {n_avisos} aviso(s)")
    if n_info:
        subtitulo.append(f"🔵 {n_info} info")

    with st.expander(f"{titulo}  ({' · '.join(subtitulo)})", expanded=expandido):
        for i, conflito in enumerate(conflitos):
            tipo = conflito.get("tipo", "warning")
            msg = conflito.get("mensagem", "")
            militar = conflito.get("militar", "")
            detalhe = conflito.get("detalhe", "")

            config = ALERT_CONFIG.get(tipo, ALERT_CONFIG["warning"])
            icon = config["icon"]

            mil_html = (
                f"<span style='font-weight:700;margin-right:6px'>[{militar}]</span>"
                if militar
                else ""
            )
            det_html = (
                f"<div style='font-size:0.78rem;color:{config['color']};opacity:0.8;"
                f"margin-top:2px;padding-left:26px'>{detalhe}</div>"
                if detalhe
                else ""
            )

            st.markdown(
                f"<div style='"
                f"background:{config['bg']};"
                f"border-left:3px solid {config['border']};"
                f"border-radius:6px;"
                f"padding:8px 12px;"
                f"margin-bottom:6px;"
                f"color:{config['color']};"
                f"font-size:0.85rem;"
                f"'>"
                f"<div style='display:flex;align-items:center;gap:6px'>"
                f"<span>{icon}</span>"
                f"{mil_html}"
                f"<span>{msg}</span>"
                f"</div>"
                f"{det_html}"
                f"</div>",
                unsafe_allow_html=True,
            )


# ======================================================================
# Badge de pedidos pendentes
# ======================================================================

def render_pendentes_badge(
    n_pendentes: int,
    *,
    tipo: str = "troca",
) -> None:
    """Mostra badge/aviso de pedidos pendentes.

    Args:
        n_pendentes: Número de pedidos pendentes.
        tipo: Tipo de pedido ("troca", "remunerado", "geral").
    """
    if n_pendentes <= 0:
        return

    labels = {
        "troca": "pedido(s) de troca",
        "remunerado": "pedido(s) de remunerado",
        "geral": "pedido(s)",
    }
    label = labels.get(tipo, labels["geral"])

    render_alert(
        f"🔔 Tens **{n_pendentes} {label}** por responder! "
        f"Vai a **📥 Pedidos Recebidos**.",
        "warning",
    )


# ======================================================================
# Notificação inline
# ======================================================================

def render_notificacao(
    mensagem: str,
    tipo: str = "info",
    *,
    icone: str | None = None,
) -> None:
    """Renderiza notificação inline compacta.

    Args:
        mensagem: Texto da notificação.
        tipo: Tipo ("success", "warning", "error", "info").
        icone: Ícone customizado.
    """
    config = ALERT_CONFIG.get(tipo, ALERT_CONFIG["info"])
    icon = icone or config["icon"]

    st.markdown(
        f"<div style='"
        f"background:{config['bg']};"
        f"border:1px solid {config['border']};"
        f"border-radius:6px;"
        f"padding:8px 12px;"
        f"margin:4px 0;"
        f"color:{config['color']};"
        f"font-size:0.82rem;"
        f"display:flex;align-items:center;gap:6px;"
        f"'>"
        f"{icon} {mensagem}"
        f"</div>",
        unsafe_allow_html=True,
    )
