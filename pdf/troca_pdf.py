"""
pdf/troca_pdf.py
================
Geração de PDFs de comprovativos de troca de serviço e de remunerado.

Extrai ``gerar_pdf_troca()`` e ``gerar_pdf_fazer_remunerado()``
do original_code.py, encapsulados na classe ``TrocaPDF(BasePDF)``.
"""

from __future__ import annotations

from typing import Any, Dict

from pdf.base import BasePDF


class TrocaPDF(BasePDF):
    """Gera comprovativos PDF de trocas de serviço e cessão de remunerados.

    Exemplo de uso::

        pdf = TrocaPDF()
        # Troca de serviço
        dados_troca = {
            "data": "15/05/2026",
            "id_origem": "101",
            "nome_origem": "Cabo Silva",
            "serv_orig": "Patrulha (08-16)",
            "id_destino": "202",
            "nome_destino": "Cabo Santos",
            "serv_dest": "Atendimento (08-16)",
            "validador": "Sargento Carmo",
            "data_val": "14/05/2026",
        }
        pdf_bytes = pdf.gerar_certificado_troca(dados_troca)

        # Remunerado
        dados_rem = {
            "data": "15/05/2026",
            "id_cedente": "101",
            "nome_cedente": "Cabo Silva",
            "remunerado": "Remunerado GNR (18-22)",
            "id_requerente": "303",
            "nome_requerente": "Guarda Costa",
            "validador": "Sargento Carmo",
            "data_val": "14/05/2026",
        }
        pdf_bytes = pdf.gerar_certificado_remunerado(dados_rem)
    """

    # ------------------------------------------------------------------
    # Comprovativo de troca de serviço
    # ------------------------------------------------------------------

    def gerar_certificado_troca(self, dados: Dict[str, Any]) -> bytes:
        """Gera PDF de comprovativo de troca de serviço.

        Args:
            dados: Dicionário com as chaves:
                - data: data da troca (dd/mm/YYYY)
                - id_origem: ID do militar que pediu a troca
                - nome_origem: nome completo do militar de origem
                - serv_orig: serviço de origem (nome + horário)
                - id_destino: ID do militar de destino
                - nome_destino: nome completo do militar de destino
                - serv_dest: serviço de destino
                - validador: quem validou
                - data_val: data de validação

        Returns:
            Bytes do PDF.
        """
        s = self.s
        self._criar_canvas()
        h = self.PAGE_H

        # Header GNR
        self.desenhar_header_gnr("GNR - Comprovativo de Troca de Serviço")

        # Corpo
        self._canvas.setFillColor(self.COR_HEADER_BG)
        texto = (
            f"Certifica-se que o militar {s(dados['nome_origem'])} "
            f"(ID {s(dados['id_origem'])}), "
            f"requereu a troca do serviço '{s(dados['serv_orig'])}' "
            f"pelo serviço '{s(dados['serv_dest'])}' "
            f"do militar {s(dados['nome_destino'])} "
            f"(ID {s(dados['id_destino'])}), "
            f"para o dia {s(dados['data'])}.\n\n"
            f"O pedido foi aceite pelo militar de destino e validado "
            f"superiormente por {s(dados['validador'])} "
            f"no dia {s(dados['data_val'])}."
        )

        self.desenhar_paragrafo(texto, h - 50 * self._mm)

        # Footer
        self.desenhar_footer_timestamp()

        return self._finalizar()

    # ------------------------------------------------------------------
    # Comprovativo de cessão de remunerado
    # ------------------------------------------------------------------

    def gerar_certificado_remunerado(self, dados: Dict[str, Any]) -> bytes:
        """Gera PDF de comprovativo de cessão de remunerado.

        Args:
            dados: Dicionário com as chaves:
                - data: data do remunerado (dd/mm/YYYY)
                - id_cedente: ID de quem cede
                - nome_cedente: nome de quem cede
                - remunerado: nome do serviço remunerado
                - id_requerente: ID de quem fica com o remunerado
                - nome_requerente: nome de quem fica
                - validador: quem validou
                - data_val: data de validação

        Returns:
            Bytes do PDF.
        """
        s = self.s
        self._criar_canvas()
        h = self.PAGE_H

        # Header GNR
        self.desenhar_header_gnr("GNR - Comprovativo de Remunerado")

        # Corpo
        self._canvas.setFillColor(self.COR_HEADER_BG)
        texto = (
            f"Certifica-se que o militar {s(dados['nome_cedente'])} "
            f"(ID {s(dados['id_cedente'])}) "
            f"cedeu o serviço remunerado '{s(dados['remunerado'])}' "
            f"do dia {s(dados['data'])} "
            f"ao militar {s(dados['nome_requerente'])} "
            f"(ID {s(dados['id_requerente'])}).\n\n"
            f"O pedido foi aceite pelo militar cedente e validado "
            f"superiormente por {s(dados['validador'])} "
            f"no dia {s(dados['data_val'])}."
        )

        self.desenhar_paragrafo(texto, h - 50 * self._mm)

        # Footer
        self.desenhar_footer_timestamp()

        return self._finalizar()

    # ------------------------------------------------------------------
    # Propriedade auxiliar
    # ------------------------------------------------------------------

    @property
    def _mm(self) -> float:
        """Atalho para a unidade mm do ReportLab."""
        from reportlab.lib.units import mm
        return mm
