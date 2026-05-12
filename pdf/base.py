"""
pdf/base.py
===========
Classe base para geração de PDFs do Portal GNR.

Encapsula configurações comuns (cores, fontes, margens), header GNR,
footer com timestamp, e métodos auxiliares reutilizáveis para desenhar
títulos de secção, tabelas, linhas de IDs e assinaturas.

Utiliza ReportLab (canvas) para desenho de baixo nível.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph


# ---------------------------------------------------------------------------
# Constantes de cor e layout
# ---------------------------------------------------------------------------
AZUL_ESCURO = HexColor("#1a2b4a")
AZUL_HEADER = HexColor("#1a1a1a")
CINZA_ALTERNADO = HexColor("#f0f0f0")
CINZA_BORDA = HexColor("#999999")
CINZA_TEXTO = HexColor("#444444")
CINZA_TIMESTAMP = HexColor("#646464")
HEADER_BG = HexColor("#e0e0e0")
SIDEBAR_ALT = HexColor("#efefef")
SIDEBAR_BORDER = HexColor("#cccccc")


class BasePDF:
    """Classe base com configurações e helpers comuns para PDFs GNR.

    Subclasses devem implementar ``gerar()`` que devolve ``bytes``.
    """

    # Tamanho de página
    PAGE_W, PAGE_H = A4

    # Fontes padrão
    FONT_NORMAL = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    FONT_ITALIC = "Helvetica-Oblique"

    # Tamanhos de fonte
    FONT_SIZE_TITLE = 16
    FONT_SIZE_SUBTITLE = 11
    FONT_SIZE_BODY = 11
    FONT_SIZE_TABLE = 8.5
    FONT_SIZE_SMALL = 7
    FONT_SIZE_FOOTER = 8

    # Cores (acessíveis como atributos de instância)
    COR_AZUL_ESCURO = AZUL_ESCURO
    COR_HEADER_BG = AZUL_HEADER
    COR_FILL_ALT = CINZA_ALTERNADO
    COR_BORDA = CINZA_BORDA
    COR_TEXTO = CINZA_TEXTO
    COR_TIMESTAMP = CINZA_TIMESTAMP

    def __init__(self) -> None:
        self._buf: io.BytesIO = io.BytesIO()
        self._canvas: Optional[rl_canvas.Canvas] = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def _criar_canvas(self) -> rl_canvas.Canvas:
        """Cria e devolve um novo canvas A4."""
        self._buf = io.BytesIO()
        self._canvas = rl_canvas.Canvas(self._buf, pagesize=A4)
        return self._canvas

    def _finalizar(self) -> bytes:
        """Salva o canvas e devolve os bytes do PDF."""
        if self._canvas is None:
            raise RuntimeError("Canvas não inicializado. Chame _criar_canvas() primeiro.")
        self._canvas.save()
        return self._buf.getvalue()

    # ------------------------------------------------------------------
    # Header GNR (barra azul escura no topo)
    # ------------------------------------------------------------------

    def desenhar_header_gnr(self, titulo: str) -> None:
        """Desenha barra azul escura no topo com título centrado a branco.

        Args:
            titulo: Texto do título (ex: "GNR - Comprovativo de Troca de Serviço").
        """
        c = self._canvas
        w, h = self.PAGE_W, self.PAGE_H
        c.setFillColor(AZUL_ESCURO)
        c.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.FONT_BOLD, self.FONT_SIZE_TITLE)
        c.drawCentredString(w / 2, h - 18 * mm, titulo)

    # ------------------------------------------------------------------
    # Footer com timestamp
    # ------------------------------------------------------------------

    def desenhar_footer_timestamp(self) -> None:
        """Desenha rodapé com data/hora de geração no canto inferior direito."""
        c = self._canvas
        c.setFont(self.FONT_ITALIC, self.FONT_SIZE_FOOTER)
        c.setFillColor(CINZA_TIMESTAMP)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        c.drawRightString(self.PAGE_W - 20 * mm, 15 * mm, f"Gerado em: {ts}")

    # ------------------------------------------------------------------
    # Parágrafos com wrap (Platypus)
    # ------------------------------------------------------------------

    def desenhar_paragrafo(
        self,
        texto: str,
        y_start: float,
        *,
        x: float = 20 * mm,
        largura: float = 170 * mm,
        font_name: str = "Helvetica",
        font_size: int = 11,
        leading: int = 16,
        space_after: float = 6 * mm,
    ) -> float:
        """Desenha texto com wrapping automático via Platypus Paragraph.

        Args:
            texto: Texto (pode conter ``\\n``).
            y_start: Posição Y inicial (topo do primeiro parágrafo).
            x: Margem esquerda.
            largura: Largura máxima do texto.
            font_name: Nome da fonte.
            font_size: Tamanho da fonte.
            leading: Espaçamento entre linhas.
            space_after: Espaço após cada parágrafo.

        Returns:
            Nova posição Y após o último parágrafo.
        """
        c = self._canvas
        style = ParagraphStyle(
            "body",
            fontName=font_name,
            fontSize=font_size,
            leading=leading,
            spaceAfter=10,
        )
        y = y_start
        for linha in texto.split("\n"):
            if not linha.strip():
                continue
            p = Paragraph(linha, style)
            pw, ph = p.wrap(largura, self.PAGE_H)
            p.drawOn(c, x, y - ph)
            y -= ph + space_after
        return y

    # ------------------------------------------------------------------
    # Título de secção (usado na escala diária)
    # ------------------------------------------------------------------

    def sec_title(
        self,
        y: float,
        label: str,
        x: float | None = None,
        w: float | None = None,
    ) -> float:
        """Desenha título de secção com bordas laterais e linha subtil.

        Args:
            y: Posição Y do topo.
            label: Texto do título.
            x: Posição X esquerda.
            w: Largura da secção.

        Returns:
            Nova posição Y abaixo do título.
        """
        c = self._canvas
        if x is None or w is None:
            raise ValueError("x e w devem ser fornecidos")

        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.line(x, y, x + w, y)              # topo
        c.line(x, y, x, y - 5.5 * mm)       # esquerda
        c.line(x + w, y, x + w, y - 5.5 * mm)  # direita

        c.setFillColor(black)
        c.setFont(self.FONT_BOLD, 9)
        c.drawString(x + 2 * mm, y - 4 * mm, f"  {label.upper()}")

        # Linha subtil separadora
        c.setStrokeColor(CINZA_BORDA)
        c.setLineWidth(0.4)
        c.line(x, y - 5.5 * mm, x + w, y - 5.5 * mm)

        return y - 6.5 * mm

    def close_section(
        self,
        y_top: float,
        y_bottom: float,
        x: float,
        w: float,
    ) -> None:
        """Fecha bloco de secção com borda completa.

        Args:
            y_top: Y do topo da secção.
            y_bottom: Y do fundo da secção.
            x: Posição X esquerda.
            w: Largura.
        """
        c = self._canvas
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.line(x, y_bottom, x + w, y_bottom)  # fundo
        c.line(x, y_top, x, y_bottom)          # esquerda
        c.line(x + w, y_top, x + w, y_bottom)  # direita

    # ------------------------------------------------------------------
    # Tabela — header e row
    # ------------------------------------------------------------------

    def tbl_header(
        self,
        y: float,
        cols: List[str],
        widths: List[float],
        x: float,
    ) -> float:
        """Desenha header de tabela com fundo cinza.

        Args:
            y: Posição Y do topo.
            cols: Nomes das colunas.
            widths: Larguras das colunas.
            x: Posição X esquerda.

        Returns:
            Nova posição Y abaixo do header.
        """
        c = self._canvas
        c.setFillColor(HEADER_BG)
        c.rect(x, y - 5 * mm, sum(widths), 5 * mm, fill=1, stroke=0)
        c.setFillColor(black)
        c.setFont(self.FONT_BOLD, self.FONT_SIZE_TABLE)
        xi = x
        for col, cw in zip(cols, widths):
            c.drawCentredString(xi + cw / 2, y - 3.5 * mm, col)
            xi += cw
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.line(x, y - 5 * mm, x + sum(widths), y - 5 * mm)
        return y - 5 * mm

    def tbl_row(
        self,
        y: float,
        vals: List[str],
        widths: List[float],
        fill: bool = False,
        x: float | None = None,
        h: float | None = None,
    ) -> float:
        """Desenha linha de tabela com wrapping por célula.

        Args:
            y: Posição Y do topo da linha.
            vals: Valores das células.
            widths: Larguras das colunas.
            fill: Se True, preenche com cor alternada.
            x: Posição X esquerda.
            h: Altura fixa (se None, calcula automaticamente).

        Returns:
            Nova posição Y abaixo da linha.
        """
        c = self._canvas
        if x is None:
            raise ValueError("x deve ser fornecido")

        c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
        linhas_por_cel: List[List[str]] = []
        for val, cw in zip(vals, widths):
            txt = str(val)
            max_pts = cw - 3 * mm
            # Suporte a quebra de linha explícita com " / "
            if " / " in txt:
                linhas = txt.split(" / ")
            else:
                words = txt.split(", ")
                curr, linhas = "", []
                for word in words:
                    test = (curr + ", " + word).strip(", ") if curr else word
                    if c.stringWidth(test, self.FONT_NORMAL, self.FONT_SIZE_TABLE) < max_pts:
                        curr = test
                    else:
                        if curr:
                            linhas.append(curr)
                        curr = word
                if curr:
                    linhas.append(curr)
            linhas_por_cel.append(linhas if linhas else [""])

        row_h = h if h else max(5 * mm, max(len(l) for l in linhas_por_cel) * 5 * mm)

        if fill:
            c.setFillColor(CINZA_ALTERNADO)
            c.rect(x, y - row_h, sum(widths), row_h, fill=1, stroke=0)

        c.setFillColor(black)
        c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
        xi = x
        for linhas, cw in zip(linhas_por_cel, widths):
            for li, ln in enumerate(linhas):
                c.drawCentredString(xi + cw / 2, y - (li * 5 * mm) - 3.5 * mm, ln)
            xi += cw

        c.setStrokeColor(CINZA_BORDA)
        c.line(x, y - row_h, x + sum(widths), y - row_h)
        return y - row_h

    # ------------------------------------------------------------------
    # Linha de IDs agrupados (ex: "Férias: 101, 102, 103")
    # ------------------------------------------------------------------

    def draw_ids_line(
        self,
        y: float,
        label: str,
        ids: List[str],
        x: float,
        w: float,
    ) -> float:
        """Desenha linha com label e lista de IDs.

        Args:
            y: Posição Y do topo.
            label: Nome do grupo (ex: "Férias").
            ids: Lista de IDs de militares.
            x: Posição X esquerda.
            w: Largura disponível.

        Returns:
            Nova posição Y abaixo da linha.
        """
        c = self._canvas
        c.setFont(self.FONT_BOLD, self.FONT_SIZE_TABLE)
        c.setFillColor(AZUL_HEADER)
        c.drawString(x + 2 * mm, y - 3.5 * mm, f"  {label}:")
        c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
        c.setFillColor(black)
        ids_txt = ", ".join(ids)
        c.drawString(x + 35 * mm, y - 3.5 * mm, ids_txt[:80])
        return y - 5 * mm

    # ------------------------------------------------------------------
    # Wrap de texto manual
    # ------------------------------------------------------------------

    def wrap_text(self, txt: str, max_pts: float) -> List[str]:
        """Quebra texto em linhas que cabem em ``max_pts`` pontos.

        Args:
            txt: Texto a quebrar.
            max_pts: Largura máxima em pontos.

        Returns:
            Lista de linhas.
        """
        c = self._canvas
        lines: List[str] = []
        for paragrafo in str(txt).split("\n"):
            words = paragrafo.split()
            curr = ""
            for word in words:
                test = (curr + " " + word).strip()
                if c.stringWidth(test, self.FONT_NORMAL, self.FONT_SIZE_TABLE) < max_pts:
                    curr = test
                else:
                    if curr:
                        lines.append(curr)
                    curr = word
            if curr:
                lines.append(curr)
        return lines if lines else [""]

    # ------------------------------------------------------------------
    # Utilitário: converter para string segura
    # ------------------------------------------------------------------

    @staticmethod
    def s(txt: Any) -> str:
        """Converte qualquer valor para string (safe cast).

        Args:
            txt: Valor a converter.

        Returns:
            Representação em string.
        """
        return str(txt)
