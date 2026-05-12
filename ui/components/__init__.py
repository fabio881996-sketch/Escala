"""
ui/components
=============
Componentes reutilizáveis da UI do Portal GNR.

Exporta todas as funções e constantes principais dos sub-módulos:
    - ``styles`` — CSS global, cards, calendário, formulários.
    - ``cards`` — Cards de serviço (normal, troca, remunerado, ausência).
    - ``calendar`` — Vista de calendário mensal.
    - ``filters`` — Barra de filtros e pesquisa.
    - ``alerts`` — Alertas, conflitos e notificações.
    - ``forms`` — Formulários de troca, remunerado, editor de escala.
"""

# Styles
from ui.components.styles import (
    CSS_CALENDAR,
    CSS_CARDS,
    CSS_FORMS,
    CSS_GLOBAL,
    CSS_LOGIN,
    CSS_TABLES,
    CSS_USER_BADGE,
    apply_custom_css,
)

# Cards
from ui.components.cards import (
    format_colegas_html,
    get_service_style,
    render_ausencia_card,
    render_remunerado_card,
    render_servico_card,
    render_troca_card,
)

# Calendar
from ui.components.calendar import (
    NOMES_DIA,
    NOMES_MES,
    get_border_style,
    get_service_color,
    get_text_colors,
    render_calendar_day,
    render_calendar_day_empty,
    render_calendar_view,
)

# Filters
from ui.components.filters import (
    aplicar_filtros,
    filtrar_secao,
    limpar_sem_militar,
    render_filtros,
    render_search_box,
)

# Alerts
from ui.components.alerts import (
    render_alert,
    render_conflitos,
    render_notificacao,
    render_pendentes_badge,
)

# Forms
from ui.components.forms import (
    render_escala_editor,
    render_remunerado_form,
    render_troca_form,
    render_validacao_form,
)

__all__ = [
    # Styles
    "CSS_GLOBAL",
    "CSS_CARDS",
    "CSS_USER_BADGE",
    "CSS_LOGIN",
    "CSS_CALENDAR",
    "CSS_FORMS",
    "CSS_TABLES",
    "apply_custom_css",
    # Cards
    "get_service_style",
    "format_colegas_html",
    "render_servico_card",
    "render_troca_card",
    "render_remunerado_card",
    "render_ausencia_card",
    # Calendar
    "NOMES_MES",
    "NOMES_DIA",
    "get_border_style",
    "get_text_colors",
    "get_service_color",
    "render_calendar_day",
    "render_calendar_day_empty",
    "render_calendar_view",
    # Filters
    "filtrar_secao",
    "limpar_sem_militar",
    "render_filtros",
    "render_search_box",
    "aplicar_filtros",
    # Alerts
    "render_alert",
    "render_conflitos",
    "render_pendentes_badge",
    "render_notificacao",
    # Forms
    "render_troca_form",
    "render_remunerado_form",
    "render_escala_editor",
    "render_validacao_form",
]
