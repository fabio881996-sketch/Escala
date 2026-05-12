"""
pdf
===
Módulo de geração de PDFs do Portal GNR.

Exporta:
    - ``BasePDF``       – Classe base com helpers comuns (header, footer, tabelas).
    - ``EscalaPDF``     – Gera PDF da escala diária.
    - ``TrocaPDF``      – Gera comprovativos de troca e cessão de remunerado.
"""

from pdf.base import BasePDF
from pdf.escala_pdf import EscalaPDF
from pdf.troca_pdf import TrocaPDF

__all__ = [
    "BasePDF",
    "EscalaPDF",
    "TrocaPDF",
]
