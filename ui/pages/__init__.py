"""
Exporta todas as funções render_* das páginas e o dicionário PAGE_ROUTES.
"""
from ui.pages.dashboard import render_dashboard
from ui.pages.minha_escala import render_minha_escala
from ui.pages.trocas_pedidos import render_trocas_pedidos as render_trocas
from ui.pages.trocas_admin import render_trocas_admin as render_validar_trocas
from ui.pages.trocas_admin import render_trocas_validadas
from ui.pages.remunerados import render_remunerados
from ui.pages.ferias import render_ferias
from ui.pages.gerar_escala import render_gerar_escala
from ui.pages.editar_escala import render_escala_geral
from ui.pages.gestao_usuarios import render_gestao_usuarios
from ui.pages.definicoes import (
    render_dispensas,
    render_publicar_escala,
    render_alertas,
    render_giros,
    render_efetivo,
)


# Mapeamento menu → função de renderização
PAGE_ROUTES = {
    "🏠 Dashboard":         render_dashboard,
    "📅 Minha Escala":      render_minha_escala,
    "🔍 Escala Geral":      render_escala_geral,
    "🔄 Trocas":            render_trocas,
    "✅ Validar Trocas":    render_validar_trocas,
    "💶 Remunerados":       render_remunerados,
    "🏖️ Férias":            render_ferias,
    "⚙️ Gerar Escala":      render_gerar_escala,
    "🏥 Dispensas":         render_dispensas,
    "📢 Publicar Escala":   render_publicar_escala,
    "🚨 Alertas":           render_alertas,
    "🔄 Giros":             render_giros,
    "👥 Efetivo":           render_efetivo,
    "👤 Gerir Utilizadores": render_gestao_usuarios,
    "📜 Trocas Validadas":  render_trocas_validadas,
}

__all__ = [
    "render_dashboard",
    "render_minha_escala",
    "render_trocas",
    "render_validar_trocas",
    "render_remunerados",
    "render_ferias",
    "render_gerar_escala",
    "render_escala_geral",
    "render_gestao_usuarios",
    "render_dispensas",
    "render_publicar_escala",
    "render_alertas",
    "render_giros",
    "render_efetivo",
    "render_trocas_validadas",
    "PAGE_ROUTES",
]
