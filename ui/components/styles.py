"""
ui/components/styles.py
=======================
Estilos CSS centralizados para o Portal GNR.

Contém todas as constantes de CSS (global, cards, calendário, formulários)
e a função ``apply_custom_css()`` que injeta tudo via ``st.markdown()``.

Paleta de cores GNR (Tailwind-like):
- Azul escuro: #1A2B4A (principal), #243B5C, #1E3A8A
- Cinza: #64748B, #94A3B8, #E2E8F0, #F0F2F6
- Âmbar: #D97706, #F59E0B, #FFFBEB, #FEF3C7
- Verde: #059669, #065F46, #ECFDF5, #D1FAE5
- Roxo: #7C3AED, #F5F3FF, #EDE9FE
- Vermelho: #DC2626, #FFF1F2, #FFE4E6
"""

from __future__ import annotations

import streamlit as st

# ======================================================================
# Constantes de cor reutilizáveis
# ======================================================================

# Cores principais
COR_AZUL_ESCURO = "#1A2B4A"
COR_AZUL_MEDIO = "#243B5C"
COR_AZUL_FORTE = "#1E3A8A"
COR_AZUL_CLARO = "#EFF6FF"
COR_AZUL_CLARO2 = "#DBEAFE"

# Cinzas
COR_CINZA_ESCURO = "#1E293B"
COR_CINZA_MEDIO = "#475569"
COR_CINZA_CLARO = "#64748B"
COR_CINZA_BORDA = "#94A3B8"
COR_CINZA_FUNDO = "#E2E8F0"
COR_CINZA_APP = "#F0F2F6"
COR_CINZA_CARD = "#F8FAFC"

# Âmbar (trocas, fins-de-semana)
COR_AMBER_ESCURO = "#92400E"
COR_AMBER_MEDIO = "#D97706"
COR_AMBER_CLARO = "#F59E0B"
COR_AMBER_BG = "#FFFBEB"
COR_AMBER_BG2 = "#FEF3C7"
COR_AMBER_TEXT = "#B45309"

# Verde (remunerados)
COR_VERDE_ESCURO = "#065F46"
COR_VERDE_MEDIO = "#059669"
COR_VERDE_BG = "#ECFDF5"
COR_VERDE_BG2 = "#D1FAE5"

# Roxo (folgas)
COR_ROXO = "#7C3AED"
COR_ROXO_BG = "#F5F3FF"
COR_ROXO_BG2 = "#EDE9FE"

# Vermelho (tribunal, feriados)
COR_VERMELHO = "#DC2626"
COR_VERMELHO_BG = "#FFF1F2"
COR_VERMELHO_BG2 = "#FFE4E6"

# Tabelas internas da escala
AZUL_TABELA = "#14285f"
AZUL_TABELA_MED = "#cdd7f2"
AZUL_TABELA_CLARO = "#ebf1ff"


# ======================================================================
# CSS_GLOBAL — estilos globais da aplicação
# ======================================================================
CSS_GLOBAL = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

/* --- App Background --- */
.stApp { background-color: #F0F2F6 !important; }

/* --- Sidebar --- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A2B4A 0%, #243B5C 60%, #1E3A8A 100%) !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * { color: #E8EDF5 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.88rem !important;
    padding: 4px 0 !important;
}
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }

/* --- Títulos --- */
h1 { color: #1A2B4A !important; font-weight: 800 !important; font-size: 1.8rem !important; }
h2 { color: #1A2B4A !important; font-weight: 700 !important; }
h3 { color: #243B5C !important; font-weight: 600 !important; }

/* --- Botões --- */
.stButton > button {
    background: #1A2B4A !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 6px rgba(26,43,74,0.25) !important;
}
.stButton > button:hover {
    background: #243B5C !important;
    box-shadow: 0 4px 12px rgba(26,43,74,0.35) !important;
    transform: translateY(-1px) !important;
}

/* --- Métricas e expanders --- */
[data-testid="stMetricValue"] { color: #1A2B4A !important; font-weight: 700 !important; }
.streamlit-expanderHeader { font-weight: 600 !important; font-size: 0.9rem !important; }

/* --- Dataframe --- */
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; }

/* --- Divider --- */
hr { border-color: #E2E8F0 !important; }

/* --- Info / Warning / Success --- */
.stAlert { border-radius: 10px !important; }
"""


# ======================================================================
# CSS_CARDS — estilos para cards de serviço
# ======================================================================
CSS_CARDS = """
/* --- Cards de Serviço --- */
.card-servico {
    background: #FFFFFF;
    padding: 16px 20px;
    border-radius: 12px;
    border-left: 5px solid #94A3B8;
    margin-bottom: 12px;
    color: #1E293B;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    transition: box-shadow 0.2s ease;
}
.card-meu {
    border-left-color: #1E3A8A !important;
    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
}
.card-troca {
    border-left-color: #D97706 !important;
    background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%) !important;
}
.card-rem {
    border-left-color: #059669 !important;
    background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%) !important;
}
.card-folga {
    border-left-color: #7C3AED !important;
    background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%) !important;
}
.card-ausencia {
    border-left-color: #64748B !important;
    background: linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 100%) !important;
}
.card-tribunal {
    border-left-color: #DC2626 !important;
    background: linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%) !important;
}
.card-servico h3 { font-size: 1.1rem !important; margin: 4px 0 !important; }
.card-servico p  { margin: 2px 0 !important; font-size: 0.88rem !important; color: #475569; }
"""


# ======================================================================
# CSS_USER_BADGE — badge do utilizador na sidebar
# ======================================================================
CSS_USER_BADGE = """
/* --- Badge de utilizador na sidebar --- */
.user-badge {
    background: rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border: 1px solid rgba(255,255,255,0.08);
}
.user-badge .nome { font-weight: 700; font-size: 0.95rem; color: #FFFFFF !important; }
.user-badge .id   { font-size: 0.78rem; color: #94A3B8 !important; margin-top: 2px; }
.user-badge .role {
    font-size: 0.72rem; background: #1E3A8A; color: #93C5FD !important;
    padding: 2px 8px; border-radius: 20px; display: inline-block; margin-top: 4px;
}
"""


# ======================================================================
# CSS_LOGIN — estilos da página de login
# ======================================================================
CSS_LOGIN = """
/* --- Login Page --- */
.login-header {
    text-align: center;
    padding: 24px 0 16px 0;
}
.login-header .escudo {
    font-size: 3.8rem;
    display: block;
    filter: drop-shadow(0 4px 8px rgba(30,58,138,0.25));
}
.login-header h1 {
    font-size: 1.7rem !important;
    color: #1A2B4A !important;
    margin: 10px 0 6px 0 !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
}
.login-header .org-line {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 4px 0 2px 0;
}
.login-header .org-line::before,
.login-header .org-line::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, transparent, #CBD5E1);
}
.login-header .org-line::after {
    background: linear-gradient(to left, transparent, #CBD5E1);
}
.login-header .org-name {
    font-size: 0.82rem;
    color: #475569;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
}
.login-header .posto-name {
    font-size: 0.78rem;
    color: #64748B;
    margin: 0;
    letter-spacing: 0.02em;
}
.login-box {
    background: white;
    border-radius: 16px;
    padding: 32px 36px;
    box-shadow: 0 8px 30px rgba(26,43,74,0.12);
    border: 1px solid #E2E8F0;
}
"""


# ======================================================================
# CSS_CALENDAR — estilos para calendário mensal
# ======================================================================
CSS_CALENDAR = """
/* --- Calendar Day Card --- */
.cal-day-card {
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.cal-day-card .day-number {
    min-width: 48px;
    text-align: center;
}
.cal-day-card .day-num {
    font-size: 1.2rem;
    font-weight: 800;
    line-height: 1;
}
.cal-day-card .day-name {
    font-size: 0.7rem;
}
.cal-day-card .service-info {
    font-size: 0.9rem;
    font-weight: 700;
}
.cal-day-card .time-info {
    font-size: 0.8rem;
    color: #475569;
}
.cal-day-card .rem-info {
    font-size: 0.75rem;
    color: #065F46;
    margin-top: 2px;
}
.cal-hoje-badge {
    background: #1E3A8A;
    color: white;
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: 10px;
}
"""


# ======================================================================
# CSS_FORMS — estilos para formulários
# ======================================================================
CSS_FORMS = """
/* --- Formulários customizados --- */
.form-troca-header {
    background: linear-gradient(135deg, #1A2B4A 0%, #243B5C 100%);
    color: white;
    padding: 12px 16px;
    border-radius: 10px 10px 0 0;
    font-weight: 700;
    font-size: 0.95rem;
}
.form-troca-body {
    background: white;
    padding: 16px;
    border: 1px solid #E2E8F0;
    border-top: none;
    border-radius: 0 0 10px 10px;
}
.form-info-box {
    background: #EFF6FF;
    border: 1px solid #DBEAFE;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #1E3A8A;
    margin-bottom: 12px;
}
"""


# ======================================================================
# CSS_TABLES — estilos para tabelas da escala (vista admin)
# ======================================================================
CSS_TABLES = """
/* --- Tabelas de escala (vista admin) --- */
.escala-sec-header {
    background: #14285f;
    color: white;
    padding: 5px 10px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-top: 10px;
    margin-bottom: 0;
    border-radius: 4px 4px 0 0;
}
.escala-table-wrap {
    overflow-x: auto;
    border: 1px solid #cdd7f2;
    border-radius: 0 0 4px 4px;
    margin-bottom: 2px;
}
.escala-table {
    width: 100%;
    border-collapse: collapse;
}
.escala-table th {
    background: #cdd7f2;
    color: #14285f;
    padding: 5px 8px;
    text-align: left;
    font-size: 0.78rem;
    font-weight: 700;
    white-space: nowrap;
    border-bottom: 2px solid #14285f;
}
.escala-table td {
    padding: 5px 8px;
    font-size: 0.8rem;
    color: #1E293B;
    vertical-align: top;
    border-bottom: 1px solid #dde6f7;
    word-break: break-word;
}
.escala-table tr:nth-child(even) td {
    background: #ebf1ff;
}
"""


# ======================================================================
# Função principal: aplica todos os estilos
# ======================================================================

def apply_custom_css() -> None:
    """Injeta todos os estilos CSS customizados na aplicação Streamlit.

    Deve ser chamada uma vez no início da aplicação (após ``st.set_page_config``).

    Exemplo::

        from ui.components.styles import apply_custom_css
        apply_custom_css()
    """
    css = "\n".join([
        CSS_GLOBAL,
        CSS_CARDS,
        CSS_USER_BADGE,
        CSS_LOGIN,
        CSS_CALENDAR,
        CSS_FORMS,
        CSS_TABLES,
    ])
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
