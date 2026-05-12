"""
pdf/escala_pdf.py
=================
Geração do PDF da escala diária em A4 retrato usando ReportLab.

Extrai toda a lógica de ``gerar_pdf_escala_dia()`` do original_code.py,
organizando-a na classe ``EscalaPDF(BasePDF)``.

Layout:
- Barra lateral esquerda (EFETIVO) com IDs e iniciais
- Header com posto territorial e caixa de assinatura do comandante
- Secções: Ausências/ADM, Atendimento/Apoio, Patrulha Ocorrências,
  Patrulhas e Policiamento, Outros Serviços, Remunerados, Observações
"""

from __future__ import annotations

from datetime import datetime as _dt
from typing import Dict, List, Optional, Tuple

import pandas as pd
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from core.utils import norm
from pdf.base import (
    AZUL_HEADER,
    CINZA_ALTERNADO,
    CINZA_BORDA,
    CINZA_TEXTO,
    SIDEBAR_ALT,
    SIDEBAR_BORDER,
    BasePDF,
)


class EscalaPDF(BasePDF):
    """Gera PDF completo da escala diária.

    Exemplo de uso::

        pdf = EscalaPDF()
        pdf_bytes = pdf.gerar_pdf_escala(data_str, df_escala, df_utilizadores)
    """

    # Configurações da sidebar
    SB_W = 24 * mm
    SB_X = 5 * mm
    SB_TM = 10 * mm

    # Nome e posto do comandante (parametrizável)
    COMANDANTE_NOME = "Hugo Alexandre Ferreira do Carmo"
    COMANDANTE_POSTO = "Sargento-Ajudante"
    POSTO_TERRITORIAL = "POSTO TERRITORIAL DE VILA NOVA DE FAMALICÃO"

    def __init__(
        self,
        *,
        comandante_nome: str | None = None,
        comandante_posto: str | None = None,
        posto_territorial: str | None = None,
    ) -> None:
        super().__init__()
        if comandante_nome:
            self.COMANDANTE_NOME = comandante_nome
        if comandante_posto:
            self.COMANDANTE_POSTO = comandante_posto
        if posto_territorial:
            self.POSTO_TERRITORIAL = posto_territorial

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_id(txt: str) -> str:
        """Formata ID com indicador de troca (🔄)."""
        t = str(txt)
        if "\U0001f504" in t:
            parts = t.split("\U0001f504")
            return f"{parts[0].strip()} (Troca c/{parts[1].strip()})"
        return t

    @staticmethod
    def _iniciais(mid: str, df_util: pd.DataFrame) -> str:
        """Devolve iniciais de um militar a partir do DataFrame de utilizadores."""
        if df_util.empty:
            return str(mid)
        row_u = df_util[df_util["id"].astype(str).str.strip() == str(mid).strip()]
        if row_u.empty:
            return str(mid)
        nome = str(row_u.iloc[0].get("nome", "")).strip()
        partes = nome.split()
        if len(partes) >= 2:
            return f"{partes[0][0]}.{partes[-1]}"
        elif len(partes) == 1:
            return partes[0]
        return str(mid)

    @staticmethod
    def _clean(v: str) -> str:
        """Remove valores nulos da representação em string."""
        return "" if str(v).strip() in ("nan", "None", "NaN") else str(v).strip()

    def _filtrar(self, pat: str, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Filtra DataFrame por padrão regex na coluna ``servico_col``."""
        mask = df["servico_col"].str.contains(pat, na=False)
        return df[mask].copy(), df[~mask].copy()

    # ------------------------------------------------------------------
    # Desenho da sidebar
    # ------------------------------------------------------------------

    def _draw_sidebar(self, y_top: float | None = None) -> None:
        """Desenha barra lateral com IDs e iniciais do efetivo."""
        c = self._canvas
        H = self.PAGE_H
        if y_top is None:
            y_top = H - self.SB_TM

        # Fundo branco
        c.setFillColor(white)
        c.rect(self.SB_X, self.SB_TM, self.SB_W, y_top - self.SB_TM, fill=1, stroke=0)

        # Cabeçalho EFETIVO
        c.setFillColor(AZUL_HEADER)
        c.rect(self.SB_X, y_top - 8 * mm, self.SB_W, 8 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.FONT_BOLD, 7)
        c.drawCentredString(self.SB_X + self.SB_W / 2, y_top - 5.5 * mm, "EFETIVO")

        # IDs e iniciais
        linha_h = min(5.5 * mm, (y_top - self.SB_TM - 12 * mm) / max(len(self._todos_ids), 1))
        y_sb = y_top - 12 * mm
        for idx_sb, mid in enumerate(self._todos_ids):
            ini = self._iniciais(mid, self._df_util)
            if idx_sb % 2 == 0:
                c.setFillColor(SIDEBAR_ALT)
                c.rect(self.SB_X, y_sb - linha_h, self.SB_W, linha_h, fill=1, stroke=0)
            c.setFillColor(AZUL_HEADER)
            c.setFont(self.FONT_BOLD, 7)
            c.drawString(self.SB_X + 1.5 * mm, y_sb - linha_h / 2 - 1.5 * mm, str(mid))
            c.setFont(self.FONT_NORMAL, 7)
            c.drawString(self.SB_X + 9 * mm, y_sb - linha_h / 2 - 1.5 * mm, ini)
            c.setStrokeColor(SIDEBAR_BORDER)
            c.setLineWidth(0.2)
            c.line(self.SB_X, y_sb - linha_h, self.SB_X + self.SB_W, y_sb - linha_h)
            y_sb -= linha_h
            if y_sb < self.SB_TM + 3 * mm:
                break

        # Borda direita subtil
        c.setStrokeColor(CINZA_BORDA)
        c.setLineWidth(0.5)
        c.line(self.SB_X + self.SB_W, self.SB_TM, self.SB_X + self.SB_W, y_top)

    # ------------------------------------------------------------------
    # Desenho do header (posto + assinatura)
    # ------------------------------------------------------------------

    def _draw_header(self, y: float) -> float:
        """Desenha header com nome do posto e caixa de assinatura."""
        c = self._canvas
        box_w = 50 * mm
        box_h = 20 * mm
        header_w = self._TW - box_w - 2 * mm

        # Cabeçalho com borda
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.rect(self._LM, y - box_h, header_w, box_h, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont(self.FONT_BOLD, 11)
        c.drawCentredString(self._LM + header_w / 2, y - 8 * mm, self.POSTO_TERRITORIAL)

        # Título com data
        try:
            dt_obj = _dt.strptime(self._data, "%d/%m/%Y")
            dias_pt = [
                "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
                "Sexta-feira", "Sábado", "Domingo",
            ]
            meses_pt = [
                "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
            ]
            titulo = (
                f"ESCALA DE SERVIÇO  |  {dias_pt[dt_obj.weekday()]}  "
                f"{dt_obj.day} de {meses_pt[dt_obj.month]} de {dt_obj.year}"
            )
        except Exception:
            titulo = f"ESCALA DE SERVIÇO  |  {self._data}"

        c.setFont(self.FONT_BOLD, 10)
        c.drawCentredString(self._LM + header_w / 2, y - 15 * mm, titulo)

        # Caixa de assinatura
        box_x = self._LM + header_w + 2 * mm
        box_y = y - box_h
        c.setStrokeColor(black)
        c.setLineWidth(0.8)
        c.rect(box_x, box_y, box_w, box_h, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont(self.FONT_BOLD, 7)
        c.drawCentredString(box_x + box_w / 2, box_y + box_h - 4 * mm, "O COMANDANTE")
        c.setFillColor(CINZA_TEXTO)
        c.setFont(self.FONT_NORMAL, 6.5)
        c.drawCentredString(box_x + box_w / 2, box_y + 3.5 * mm, self.COMANDANTE_NOME)
        c.drawCentredString(box_x + box_w / 2, box_y + 1 * mm, self.COMANDANTE_POSTO)
        c.setLineWidth(0.5)

        return y - box_h - 2 * mm

    # ------------------------------------------------------------------
    # Nova página
    # ------------------------------------------------------------------

    def _new_page(self) -> float:
        """Cria nova página e redesenha sidebar."""
        self._draw_sidebar(y_top=self.PAGE_H - self.SB_TM)
        self._canvas.showPage()
        self._draw_sidebar(y_top=self.PAGE_H - self.SB_TM)
        return self.PAGE_H - 10 * mm

    # ------------------------------------------------------------------
    # Secção de IDs agrupados (Ausências, ADM)
    # ------------------------------------------------------------------

    def _draw_grouped_ids(
        self,
        y: float,
        grupos: Dict[str, List[str]],
        x: float,
        col_w: float,
    ) -> float:
        """Desenha secção de IDs agrupados por serviço.

        Args:
            y: Posição Y inicial.
            grupos: Dicionário serviço → lista de IDs.
            x: Posição X esquerda.
            col_w: Largura da coluna.

        Returns:
            Nova posição Y.
        """
        c = self._canvas
        max_pts = col_w - 37 * mm
        label_w = 35 * mm
        idx = 0

        for serv, ids in grupos.items():
            ids_txt = ", ".join(ids)
            words = ids_txt.split(", ")
            curr_line, curr_w = [], 0
            linhas_ids: List[str] = []
            for w_id in words:
                tw = c.stringWidth(w_id + ", ", self.FONT_NORMAL, self.FONT_SIZE_TABLE)
                if curr_w + tw < max_pts:
                    curr_line.append(w_id)
                    curr_w += tw
                else:
                    if curr_line:
                        linhas_ids.append(", ".join(curr_line))
                    curr_line, curr_w = [w_id], tw
            if curr_line:
                linhas_ids.append(", ".join(curr_line))

            row_h = len(linhas_ids) * 5 * mm
            if idx % 2 == 0:
                c.setFillColor(CINZA_ALTERNADO)
                c.rect(x, y - row_h, col_w, row_h, fill=1, stroke=0)

            c.setFont(self.FONT_BOLD, self.FONT_SIZE_TABLE)
            c.setFillColor(AZUL_HEADER)
            c.drawString(x + 2 * mm, y - 3.5 * mm, f"  {serv}:")
            c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
            c.setFillColor(black)
            for li, ln in enumerate(linhas_ids):
                indent = x + label_w if li == 0 else x + 5 * mm
                c.drawString(indent, y - 3.5 * mm, ln)
                y -= 5 * mm
            idx += 1

        return y

    # ------------------------------------------------------------------
    # Secção de tabela com horário + militares + extra cols
    # ------------------------------------------------------------------

    def _draw_service_table(
        self,
        y: float,
        df: pd.DataFrame,
        sec_label: str,
        cols: List[str],
        widths: List[float],
        extra_cols: List[str],
    ) -> float:
        """Desenha secção de tabela para um tipo de serviço.

        Args:
            y: Posição Y do topo.
            df: DataFrame filtrado.
            sec_label: Título da secção.
            cols: Nomes das colunas.
            widths: Larguras.
            extra_cols: Colunas extra do DataFrame (ex: indicativo rádio, rádio, viatura, giro).

        Returns:
            Nova posição Y.
        """
        if df.empty:
            return y

        y_sec_top = y
        y = self.sec_title(y, sec_label, x=self._LM, w=self._TW)
        y = self.tbl_header(y, cols, widths, x=self._LM)
        fill = False

        grouped = (
            df.assign(_hor_sort=df["horário"].str.extract(r"^(\d+)")[0].astype(float))
            .sort_values("_hor_sort")
            .groupby("horário", sort=False)
        )

        for hor, grp in grouped:
            ids = ", ".join(grp["id_fmt"].tolist())
            vals = [hor, ids]
            if "serviço" in extra_cols:
                vals.append(grp["serviço"].iloc[0])
            for ec in extra_cols:
                if ec == "serviço":
                    continue
                val = str(grp[ec].iloc[0]).strip() if ec in grp.columns else ""
                vals.append(self._clean(val))
            y = self.tbl_row(y, vals, widths, fill, x=self._LM)
            fill = not fill
            if y < 20 * mm:
                y = self._new_page()

        self.close_section(y_sec_top, y, x=self._LM, w=self._TW)
        return y - 2 * mm

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def gerar_pdf_escala(
        self,
        data: str,
        df_raw: pd.DataFrame,
        df_util: pd.DataFrame | None = None,
    ) -> bytes:
        """Gera PDF da escala diária.

        Args:
            data: Data no formato "dd/mm/YYYY".
            df_raw: DataFrame com os dados da escala (colunas: id, serviço, horário, id_disp, ...).
            df_util: DataFrame de utilizadores (colunas: id, nome, posto, ...).

        Returns:
            Bytes do PDF gerado.
        """
        self._data = data
        self._df_util = df_util if df_util is not None else pd.DataFrame()
        c = self._criar_canvas()

        # Preparar dados
        df = df_raw.copy()
        df["servico_col"] = df["serviço"].apply(norm)
        df["id_fmt"] = df["id_disp"].apply(self._fmt_id) if "id_disp" in df.columns else df["id"].astype(str)
        df_com = df[df["id"].astype(str).str.strip().str.len() > 0].copy()

        # Filtrar por tipo de serviço
        df_aus, df_rest = self._filtrar(r"ferias|licen|doente|folga|baixa|convalesc", df_com)
        df_adm, df_rest = self._filtrar(r"pronto|secretaria|inquer|comando|dilig", df_rest)
        df_ap, df_rest = self._filtrar(r"apoio", df_rest)
        df_at, df_rest = self._filtrar(r"atendimento", df_rest)
        df_pat, df_rest = self._filtrar(r"po|patrulha|ronda|vtr|giro", df_rest)
        df_rem, df_rest = self._filtrar(r"remu|grat", df_rest)
        df_outros = df_rest

        # Separar patrulha ocorrências
        df_ocorr = df_pat[df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()
        df_outras_pat = df_pat[~df_pat["servico_col"].str.contains(r"ocorr", na=False)].copy()

        # IDs do efetivo
        if not self._df_util.empty and "id" in self._df_util.columns:
            self._todos_ids = [
                str(r).strip()
                for r in self._df_util["id"]
                if str(r).strip() and str(r).strip() != "nan"
            ]
        else:
            self._todos_ids = sorted(
                set(str(r).strip() for r in df["id"] if str(r).strip() and str(r).strip() != "nan"),
                key=lambda x: int(x) if x.isdigit() else 0,
            )

        # Margens
        self._LM = self.SB_X + self.SB_W + 3 * mm
        self._RM = 12 * mm
        self._TW = self.PAGE_W - self._LM - self._RM

        # ---- INÍCIO ----
        H = self.PAGE_H
        y = H - 15 * mm
        y = self._draw_header(y)
        y -= 2 * mm
        self._draw_sidebar(y_top=y)

        # ---- Ausências e ADM lado a lado ----
        CW_ESQ = self._TW * 0.60 - 1 * mm
        CW_DIR = self._TW * 0.40 - 1 * mm
        CW2 = self._TW / 2 - 1 * mm
        GAP = 2 * mm

        # Agrupar
        grupos_aus: Dict[str, List[str]] = {}
        for _, row in df_aus.iterrows():
            serv = str(row.get("serviço", "")).strip()
            mid = str(row.get("id_fmt", row.get("id", ""))).strip()
            grupos_aus.setdefault(serv, []).append(mid)

        grupos_adm: Dict[str, List[str]] = {}
        for _, row in df_adm.iterrows():
            serv = str(row.get("serviço", "")).strip()
            mid = str(row.get("id_fmt", row.get("id", ""))).strip()
            grupos_adm.setdefault(serv, []).append(mid)

        # Títulos
        y_col = y
        y_aus_top = y_col
        self.sec_title(y_col, "Ausências, Folgas e Licenças", x=self._LM, w=CW_ESQ)
        y_adm_top = y_col
        if grupos_adm:
            self.sec_title(y_col, "Outras Situações / ADM", x=self._LM + CW_ESQ + GAP, w=CW_DIR)
        y_col -= 6.5 * mm

        y_esq = self._draw_grouped_ids(y_col, grupos_aus, self._LM, CW_ESQ)
        y_dir = self._draw_grouped_ids(y_col, grupos_adm, self._LM + CW_ESQ + GAP, CW_DIR)

        y_aus_bottom = min(y_esq, y_dir)
        self.close_section(y_aus_top, y_aus_bottom, x=self._LM, w=CW_ESQ)
        if grupos_adm:
            self.close_section(y_adm_top, y_aus_bottom, x=self._LM + CW_ESQ + GAP, w=CW_DIR)
        y = y_aus_bottom - 2 * mm

        # ---- Atendimento e Apoio lado a lado ----
        if not df_at.empty or not df_ap.empty:
            y_at = y
            y_at_top = y_at
            cols_at = ["Horário", "Militar(es)"]

            if not df_at.empty:
                self.sec_title(y_at, "Atendimento", x=self._LM, w=CW2)
            if not df_ap.empty:
                self.sec_title(y_at, "Apoio ao Atendimento", x=self._LM + CW2 + GAP, w=CW2)
            y_at -= 6.5 * mm

            y_esq2 = y_at
            if not df_at.empty:
                wids_at_l = [20 * mm, CW2 - 20 * mm]
                y_esq2 = self.tbl_header(y_at, cols_at, wids_at_l, x=self._LM)
                fill = False
                for hor, grp in (
                    df_at.assign(_hs=df_at["horário"].str.extract(r"^(\d+)")[0].astype(float))
                    .sort_values("_hs")
                    .groupby("horário", sort=False)
                ):
                    ids = ", ".join(grp["id_fmt"].tolist())
                    y_esq2 = self.tbl_row(y_esq2, [hor, ids], wids_at_l, fill, x=self._LM)
                    fill = not fill

            y_dir2 = y_at
            if not df_ap.empty:
                wids_at_r = [20 * mm, CW2 - 20 * mm]
                x_dir2 = self._LM + CW2 + GAP
                y_dir2 = self.tbl_header(y_at, cols_at, wids_at_r, x=x_dir2)
                fill = False
                for hor, grp in (
                    df_ap.assign(_hs=df_ap["horário"].str.extract(r"^(\d+)")[0].astype(float))
                    .sort_values("_hs")
                    .groupby("horário", sort=False)
                ):
                    ids = ", ".join(grp["id_fmt"].tolist())
                    y_dir2 = self.tbl_row(y_dir2, [hor, ids], wids_at_r, fill, x=x_dir2)
                    fill = not fill

            y_at_bottom = min(y_esq2, y_dir2)
            if not df_at.empty:
                self.close_section(y_at_top, y_at_bottom, x=self._LM, w=CW2)
            if not df_ap.empty:
                self.close_section(y_at_top, y_at_bottom, x=self._LM + CW2 + GAP, w=CW2)
            y = y_at_bottom - 2 * mm

        # ---- Patrulha Ocorrências ----
        if not df_ocorr.empty:
            _w = self._TW - 16 * mm - 32 * mm - 40 * mm
            y = self._draw_service_table(
                y, df_ocorr, "Patrulha Ocorrências",
                ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"],
                [16 * mm, 32 * mm, 40 * mm, _w / 3, _w / 3, _w / 3],
                ["serviço", "indicativo rádio", "rádio", "viatura"],
            )

        # ---- Patrulhas e Policiamento ----
        if not df_outras_pat.empty:
            _wp = self._TW - 16 * mm - 32 * mm - 34 * mm - 14 * mm
            y = self._draw_service_table(
                y, df_outras_pat, "Patrulhas e Policiamento",
                ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura", "Giro"],
                [16 * mm, 32 * mm, 34 * mm, _wp / 3, _wp / 3, _wp / 3, 14 * mm],
                ["serviço", "indicativo rádio", "rádio", "viatura", "giro"],
            )

        # ---- Outros Serviços ----
        if not df_outros.empty:
            _wo = self._TW - 16 * mm - 32 * mm - 40 * mm
            y_sec_top = y
            y = self.sec_title(y, "Outros Serviços", x=self._LM, w=self._TW)
            cols_ot = ["Horário", "Militares", "Serviço", "Indicativo", "Rádio", "Viatura"]
            wids_ot = [16 * mm, 32 * mm, 40 * mm, _wo / 3, _wo / 3, _wo / 3]
            y = self.tbl_header(y, cols_ot, wids_ot, x=self._LM)
            fill = False
            for (hor, serv), grp in (
                df_outros.assign(_hs=df_outros["horário"].str.extract(r"^(\d+)")[0].astype(float))
                .sort_values(["_hs", "serviço"])
                .groupby(["horário", "serviço"], sort=False)
            ):
                ids = ", ".join(grp["id_fmt"].tolist())
                ind = self._clean(grp["indicativo rádio"].iloc[0]) if "indicativo rádio" in grp.columns else ""
                rad = self._clean(grp["rádio"].iloc[0]) if "rádio" in grp.columns else ""
                vtr = self._clean(grp["viatura"].iloc[0]) if "viatura" in grp.columns else ""
                y = self.tbl_row(y, [hor, ids, serv, ind, rad, vtr], wids_ot, fill, x=self._LM)
                fill = not fill
                if y < 20 * mm:
                    y = self._new_page()
            self.close_section(y_sec_top, y, x=self._LM, w=self._TW)
            y -= 2 * mm

        # ---- Remunerados ----
        if not df_rem.empty:
            y = self._draw_remunerados(y, df_rem)

        # ---- Observações ----
        y = self._draw_observacoes(y, df_pat, df_at, df_ap, df_outros)

        c.save()
        return self._buf.getvalue()

    # ------------------------------------------------------------------
    # Secção de remunerados (lógica complexa com merge de obs)
    # ------------------------------------------------------------------

    def _draw_remunerados(self, y: float, df_rem: pd.DataFrame) -> float:
        """Desenha secção de remunerados com células de obs fundidas."""
        c = self._canvas
        y_sec_top = y
        y = self.sec_title(y, "Serviços Remunerados / Gratificados", x=self._LM, w=self._TW)

        linhas_rem: List[dict] = []
        vistos: Dict = {}
        col_vtr = next((col for col in df_rem.columns if norm(col) == "viatura"), None)

        for _, row in df_rem.iterrows():
            hor = str(row.get("horário", "")).strip()
            obs = str(row.get("observações", "")) if "observações" in df_rem.columns else ""
            if obs == "nan":
                obs = ""
            chave = (hor, obs)
            if chave in vistos:
                continue
            vistos[chave] = True
            grp = df_rem[df_rem["horário"] == hor]
            if "observações" in df_rem.columns:
                grp = grp[grp["observações"].astype(str).str.strip().replace("nan", "") == obs]
            ids = ", ".join(grp["id_fmt"].tolist())
            vtr = ""
            if col_vtr:
                vtr_vals = grp[col_vtr].dropna().astype(str).str.strip()
                vtr_vals = vtr_vals[vtr_vals.str.len() > 0].unique().tolist()
                vtr = " / ".join(vtr_vals) if vtr_vals else ""
            linhas_rem.append({"hor": hor, "ids": ids, "obs": obs, "vtr": vtr})

        _vtr_w = 20 * mm if "viatura" in df_rem.columns else 0
        _hor_w = 22 * mm
        wids_rm = [_hor_w, 35 * mm, _vtr_w, self._TW - _hor_w - 35 * mm - _vtr_w]
        _obs_w = wids_rm[3]
        cols_rm = ["Horário", "Militares"] + (["Viatura"] if _vtr_w else []) + ["Observação"]
        y = self.tbl_header(y, cols_rm, wids_rm, x=self._LM)

        x_obs_start = self._LM + wids_rm[0] + wids_rm[1] + _vtr_w + 2 * mm
        x_obs_end = self._LM + self._TW - 2 * mm
        max_pts_rm = x_obs_end - x_obs_start
        x_obs_col = self._LM + wids_rm[0] + wids_rm[1] + _vtr_w

        # Calcular alturas
        alturas = []
        for r in linhas_rem:
            obs_lines = self.wrap_text(r["obs"], max_pts_rm) if r["obs"] else [""]
            ids_lines = self.wrap_text(r["ids"], wids_rm[1] - 2 * mm)
            vtr_lines = r["vtr"].split(" / ") if " / " in r["vtr"] else [r["vtr"]]
            alturas.append(max(5 * mm, max(len(obs_lines), len(ids_lines), len(vtr_lines)) * 5 * mm))

        # Spans de obs consecutivas iguais
        obs_spans: Dict[int, tuple] = {}
        i = 0
        while i < len(linhas_rem):
            obs_atual = linhas_rem[i]["obs"]
            j = i + 1
            while j < len(linhas_rem) and linhas_rem[j]["obs"] == obs_atual and obs_atual:
                j += 1
            obs_spans[i] = (obs_atual, j - i, sum(alturas[i:j]))
            i = j

        # Desenhar linhas
        y_grupo: Dict[int, float] = {}
        for idx, r in enumerate(linhas_rem):
            row_h = alturas[idx]
            if y - row_h < 20 * mm:
                y = self._new_page()
            if idx in obs_spans:
                y_grupo[idx] = y

            if idx > 0 and idx % 2 == 1:
                c.setFillColor(CINZA_ALTERNADO)
                c.rect(self._LM, y - row_h, wids_rm[0] + wids_rm[1] + _vtr_w, row_h, fill=1, stroke=0)

            c.setFillColor(black)
            c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
            ids_lines = self.wrap_text(r["ids"], wids_rm[1] - 2 * mm)
            total_ids_h = len(ids_lines) * 5 * mm
            row_h_real = max(row_h, 5 * mm)
            y_centro = y - row_h_real / 2 - 1.5 * mm
            c.drawCentredString(self._LM + wids_rm[0] / 2, y_centro, str(r["hor"]))

            y_ids_start = y - (row_h_real - total_ids_h) / 2 - 3.5 * mm
            for li, id_l in enumerate(ids_lines):
                c.drawCentredString(self._LM + wids_rm[0] + wids_rm[1] / 2, y_ids_start - (li * 5 * mm), id_l)

            if _vtr_w:
                vtr_txt = r.get("vtr", "")
                vtr_lines = vtr_txt.split(" / ") if " / " in vtr_txt else [vtr_txt]
                total_vtr_h = len(vtr_lines) * 5 * mm
                y_vtr = y - (row_h_real - total_vtr_h) / 2 - 3.5 * mm
                for li, vl in enumerate(vtr_lines):
                    c.drawCentredString(
                        self._LM + wids_rm[0] + wids_rm[1] + _vtr_w / 2,
                        y_vtr - (li * 5 * mm),
                        vl,
                    )

            c.setStrokeColor(CINZA_BORDA)
            x_fim_esq = self._LM + wids_rm[0] + wids_rm[1] + _vtr_w
            c.line(self._LM, y, x_fim_esq, y)
            c.line(self._LM, y - row_h, x_fim_esq, y - row_h)
            c.line(self._LM, y, self._LM, y - row_h)
            c.line(self._LM + wids_rm[0], y, self._LM + wids_rm[0], y - row_h)
            if _vtr_w:
                c.line(
                    self._LM + wids_rm[0] + wids_rm[1], y,
                    self._LM + wids_rm[0] + wids_rm[1], y - row_h,
                )
            y -= row_h

        # Desenhar obs fundidas
        for idx, (obs_txt, span_count, span_h) in obs_spans.items():
            if idx not in y_grupo:
                continue
            y_ini = y_grupo[idx]
            obs_lines_span = self.wrap_text(obs_txt, max_pts_rm) if obs_txt else [""]
            c.setFillColor(white)
            c.rect(x_obs_col, y_ini - span_h, _obs_w, span_h, fill=1, stroke=0)
            total_txt_h = len(obs_lines_span) * 5 * mm
            y_texto = y_ini - (span_h - total_txt_h) / 2 - 3.5 * mm
            c.setFillColor(black)
            c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
            for li, obs_l in enumerate(obs_lines_span):
                c.drawString(x_obs_start, y_texto - (li * 5 * mm), obs_l)
            c.setStrokeColor(CINZA_BORDA)
            c.line(x_obs_col, y_ini, x_obs_col, y_ini - span_h)
            c.line(x_obs_col, y_ini, self._LM + self._TW, y_ini)
            c.line(x_obs_col, y_ini - span_h, self._LM + self._TW, y_ini - span_h)

        self.close_section(y_sec_top, y, x=self._LM, w=self._TW)
        return y - 2 * mm

    # ------------------------------------------------------------------
    # Secção de observações gerais
    # ------------------------------------------------------------------

    def _draw_observacoes(
        self,
        y: float,
        df_pat: pd.DataFrame,
        df_at: pd.DataFrame,
        df_ap: pd.DataFrame,
        df_outros: pd.DataFrame,
    ) -> float:
        """Desenha secção de observações (excluindo remunerados)."""
        c = self._canvas
        obs_por_ind: Dict[str, Dict[str, set]] = {}

        for df_sec in [df_pat, df_at, df_ap, df_outros]:
            if df_sec.empty or "observações" not in df_sec.columns:
                continue
            for _, row in df_sec.iterrows():
                obs = str(row.get("observações", "")).strip()
                ind = str(row.get("indicativo rádio", "")).strip() if "indicativo rádio" in df_sec.columns else ""
                serv = str(row.get("serviço", "")).strip()
                hor = str(row.get("horário", "")).strip()
                label = ind if ind else serv
                if label not in obs_por_ind:
                    obs_por_ind[label] = {}
                obs_key = obs if (obs and obs != "nan") else ""
                if obs_key not in obs_por_ind[label]:
                    obs_por_ind[label][obs_key] = set()
                obs_por_ind[label][obs_key].add(hor)

        obs_lista: List[Tuple[str, str]] = []
        for label, obs_map in obs_por_ind.items():
            obs_com = {k: v for k, v in obs_map.items() if k}
            obs_sem = {k: v for k, v in obs_map.items() if not k}
            tem_multiplas = len(obs_com) > 1 or (obs_com and obs_sem)
            for obs_txt, hors in obs_com.items():
                if tem_multiplas:
                    hors_unicos = sorted(hors)
                    lbl = f"{label}\n{', '.join(hors_unicos)}"
                else:
                    lbl = label
                obs_lista.append((lbl, obs_txt))

        if not obs_lista:
            return y

        if y < 40 * mm:
            y = self._new_page()

        y_sec_top = y
        y = self.sec_title(y, "Observações", x=self._LM, w=self._TW)
        cols_ob = ["Indicativo / Serviço", "Detalhe"]
        wids_ob = [35 * mm, self._TW - 35 * mm]
        y = self.tbl_header(y, cols_ob, wids_ob, x=self._LM)
        fill = False
        max_pts_ob = wids_ob[1] - 3 * mm

        for lbl, obs in obs_lista:
            label_lines = lbl.split("\n")
            obs_lines = self.wrap_text(obs, max_pts_ob)
            row_h = max(5 * mm, max(len(obs_lines), len(label_lines)) * 5 * mm)
            if y - row_h < 20 * mm:
                y = self._new_page()
            if fill:
                c.setFillColor(CINZA_ALTERNADO)
                c.rect(self._LM, y - row_h, self._TW, row_h, fill=1, stroke=0)
            c.setFillColor(black)
            c.setFont(self.FONT_NORMAL, self.FONT_SIZE_TABLE)
            for li, l in enumerate(label_lines):
                c.drawCentredString(self._LM + wids_ob[0] / 2, y - (li * 5 * mm) - 3.5 * mm, l)
            for li, obs_l in enumerate(obs_lines):
                c.drawString(self._LM + wids_ob[0] + 2 * mm, y - (li * 5 * mm) - 3.5 * mm, obs_l)
            c.setStrokeColor(CINZA_BORDA)
            c.rect(self._LM, y - row_h, self._TW, row_h, fill=0, stroke=1)
            c.line(self._LM + wids_ob[0], y, self._LM + wids_ob[0], y - row_h)
            y -= row_h
            fill = not fill

        self.close_section(y_sec_top, y, x=self._LM, w=self._TW)
        return y - 2 * mm
