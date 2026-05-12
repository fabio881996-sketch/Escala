"""Serviço de gestão de trocas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
import re

import pandas as pd

from models.troca import Troca
from services.data_loader import DataLoader
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrocaService:
    """Orquestra criação, validação e aplicação de trocas."""

    data_loader: DataLoader
    validation_service: ValidationService

    def criar_pedido_troca(self, troca: Troca) -> bool:
        """Cria pedido de troca na worksheet `registos_trocas`."""
        ok, motivo = troca.validar_campos_obrigatorios()
        if not ok:
            logger.warning("Pedido de troca inválido: %s", motivo)
            return False
        ok_data, _ = troca.validar_data()
        if not ok_data:
            return False

        try:
            ws = self.data_loader.sheets_client.get_worksheet("registos_trocas")
            ws.append_row(troca.to_row())
            return True
        except Exception as exc:
            logger.exception("Erro ao guardar troca: %s", exc)
            return False

    def validar_troca(
        self,
        troca: Troca,
        df_dia: pd.DataFrame,
        df_anterior: pd.DataFrame | None = None,
        df_seguinte: pd.DataFrame | None = None,
    ) -> tuple[bool, list[str]]:
        """Valida troca segundo regras de descanso e consistência."""
        ok, motivo = troca.validar_campos_obrigatorios()
        if not ok:
            return False, [motivo]

        if troca.is_matar_remunerado() or troca.is_troca_folga():
            return True, []

        try:
            dt = datetime.strptime(troca.data, "%d/%m/%Y")
        except Exception:
            return False, ["Data da troca inválida"]

        serv_o_nome = troca.servico_origem.rsplit("(", 1)[0].strip()
        hor_o = troca.servico_origem.rsplit("(", 1)[1].rstrip(")") if "(" in troca.servico_origem else ""
        serv_d_nome = troca.servico_destino.rsplit("(", 1)[0].strip()
        hor_d = troca.servico_destino.rsplit("(", 1)[1].rstrip(")") if "(" in troca.servico_destino else ""

        erros = self.validation_service.validar_descanso_troca(
            militar_origem=troca.militar_origem,
            militar_destino=troca.militar_destino,
            data_ref=dt,
            servico_origem_nome=serv_o_nome,
            horario_origem=hor_o,
            servico_destino_nome=serv_d_nome,
            horario_destino=hor_d,
            df_dia=df_dia,
            df_anterior=df_anterior,
            df_seguinte=df_seguinte,
        )
        return len(erros) == 0, erros

    def aprovar_troca(self, index_linha: int, admin_nome: str = "") -> bool:
        """Aprova troca e aplica efeitos secundários (folga)."""
        ok = self._atualizar_status(index_linha, "Aprovada", admin_nome=admin_nome)
        if not ok:
            return False

        try:
            self._aplicar_efeitos_troca_folga(index_linha)
        except Exception as exc:
            logger.warning("Falha em efeitos secundários da troca de folga: %s", exc)
        return True

    def rejeitar_troca(self, index_linha: int, admin_nome: str = "") -> bool:
        """Rejeita troca pendente de admin."""
        return self._atualizar_status(index_linha, "Rejeitada", admin_nome=admin_nome)

    def _atualizar_status(self, index_linha: int, novo_status: str, admin_nome: str = "") -> bool:
        """Atualiza status da troca mantendo compatibilidade com layout legado."""
        try:
            ws = self.data_loader.sheets_client.get_worksheet("registos_trocas")
            row = index_linha + 2
            if admin_nome:
                dt_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                ws.batch_update(
                    [
                        {"range": f"F{row}", "values": [[novo_status]]},
                        {"range": f"H{row}", "values": [[admin_nome]]},
                        {"range": f"I{row}", "values": [[dt_agora]]},
                    ]
                )
            else:
                ws.update_cell(row, 6, novo_status)
            return True
        except Exception as exc:
            logger.exception("Erro ao atualizar status da troca: %s", exc)
            return False

    def aplicar_troca_na_escala(self, df_alvo: pd.DataFrame, data_str: str, df_trocas: pd.DataFrame) -> pd.DataFrame:
        """Aplica trocas aprovadas a um DataFrame de escala (lógica do legado)."""
        if df_alvo.empty or df_trocas.empty:
            return df_alvo

        tr = df_trocas[
            (df_trocas["data"] == data_str)
            & (df_trocas["status"] == "Aprovada")
            & (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
        ]
        mask_rem = df_alvo["serviço"].str.lower().str.contains("remu|grat", na=False)
        df_out = df_alvo.copy()

        for _, row in tr.iterrows():
            id_o = str(row["id_origem"]).strip()
            id_d = str(row["id_destino"]).strip()
            s_o = str(row["servico_origem"]) or ""
            s_d = str(row["servico_destino"]) or ""

            serv_o = s_o.rsplit("(", 1)[0].strip()
            hor_o = s_o.rsplit("(", 1)[1].rstrip(")") if "(" in s_o else ""
            serv_d = s_d.rsplit("(", 1)[0].strip()
            hor_d = s_d.rsplit("(", 1)[1].rstrip(")") if "(" in s_d else ""

            m_o = (df_out["id"].astype(str).str.strip() == id_o) & ~mask_rem
            if m_o.any():
                df_out.loc[m_o, "serviço"] = serv_d
                if hor_d:
                    df_out.loc[m_o, "horário"] = hor_d

            m_d = (df_out["id"].astype(str).str.strip() == id_d) & ~mask_rem
            if m_d.any():
                df_out.loc[m_d, "serviço"] = serv_o
                if hor_o:
                    df_out.loc[m_d, "horário"] = hor_o

        return df_out

    def _aplicar_efeitos_troca_folga(self, index_linha: int) -> None:
        """Aplica atualização de folgas após aprovação (compatível com legado)."""
        ws_t = self.data_loader.sheets_client.get_worksheet("registos_trocas")
        todos = ws_t.get_all_values()
        if not todos or len(todos) <= index_linha + 1:
            return

        hdrs = [h.strip().lower() for h in todos[0]]
        row = todos[index_linha + 1]

        def _get(nome: str) -> str:
            if nome in hdrs:
                pos = hdrs.index(nome)
                return str(row[pos]).strip() if pos < len(row) else ""
            return ""

        serv_o = _get("servico_origem")
        serv_d = _get("servico_destino")
        id_o = _get("id_origem")
        id_d = _get("id_destino")

        if not (serv_o.startswith("Folga ") and serv_d.startswith("Folga ")):
            return

        def _extrair_dia(s: str) -> str | None:
            m = re.search(r"(\d{2}/\d{2}/\d{4})", s)
            if not m:
                return None
            return datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%d-%m")

        dia_o = _extrair_dia(serv_o)
        dia_d = _extrair_dia(serv_d)
        if not dia_o or not dia_d:
            return

        ano = datetime.now().year
        df_folgas = self.data_loader.carregar_folgas(ano)
        if df_folgas.empty:
            return

        ws_f = self.data_loader.sheets_client.get_worksheet(f"folgas_{ano}")
        ws_grp = self.data_loader.sheets_client.get_worksheet("grupos_folga")
        vals_f = [list(df_folgas.columns)] + df_folgas.astype(str).values.tolist()
        hdrs_f = [h.strip().lower() for h in vals_f[0]]

        ix_id_f = hdrs_f.index("id") if "id" in hdrs_f else 0
        ix_grp_f = hdrs_f.index("grupo") if "grupo" in hdrs_f else None

        def _get_grupo(mid: str) -> str | None:
            for row_f in vals_f[1:]:
                if str(row_f[ix_id_f]).strip() == mid and ix_grp_f is not None:
                    return str(row_f[ix_grp_f]).strip()
            return None

        if id_o == id_d:
            m_tipo = re.search(r"\(([^)]+)\)", serv_o)
            tipo_orig = m_tipo.group(1) if m_tipo else ""
            nova_exc = f"{dia_o}({tipo_orig})→{dia_d}"
            col_exc = "exceções" if "exceções" in hdrs_f else ("excecoes" if "excecoes" in hdrs_f else None)
            if col_exc:
                ix_exc = hdrs_f.index(col_exc)
                for i_f, row_f in enumerate(vals_f[1:], start=2):
                    if str(row_f[ix_id_f]).strip() == id_o:
                        exc_atual = str(row_f[ix_exc]).strip() if ix_exc < len(row_f) else ""
                        exc_atual = "" if exc_atual == "nan" else exc_atual
                        nova_lista = (exc_atual + ";" + nova_exc).strip(";")
                        cl = chr(ord("A") + ix_exc)
                        ws_f.update(f"{cl}{i_f}", [[nova_lista]])
                        break
            return

        vals_grp = ws_grp.get_all_values()
        if not vals_grp:
            return
        hdrs_grp = [h.strip() for h in vals_grp[0]]
        tipos_grp = [h for h in hdrs_grp if h != "grupo"]

        grp_from = _get_grupo(id_o)
        grp_to = _get_grupo(id_d)
        updates: list[dict[str, list[list[str]]]] = []

        for i_grp, row_grp in enumerate(vals_grp[1:], start=2):
            grp_nome = str(row_grp[0]).strip()
            for tipo_g in tipos_grp:
                ix_t = hdrs_grp.index(tipo_g)
                dias_str = str(row_grp[ix_t]).strip() if ix_t < len(row_grp) else ""
                dias_list = [d.strip() for d in re.split(r"[;,]+", dias_str) if d.strip()]
                mudou = False

                if grp_from and grp_nome == grp_from and dia_o in dias_list:
                    dias_list.remove(dia_o)
                    dias_list.append(dia_d)
                    mudou = True
                if grp_to and grp_nome == grp_to and dia_d in dias_list:
                    dias_list.remove(dia_d)
                    dias_list.append(dia_o)
                    mudou = True

                if mudou:
                    cl = chr(ord("A") + ix_t)
                    updates.append({"range": f"{cl}{i_grp}", "values": [[";".join(sorted(dias_list))]]})

        if updates:
            ws_grp.batch_update(updates)

    def construir_troca(
        self,
        *,
        tipo: str,
        militar_origem: str,
        militar_destino: str,
        data_ref: date | datetime,
        servico_origem: str,
        servico_destino: str,
        status: str,
        observacoes: str = "",
    ) -> Troca:
        """Factory utilitária para criação de objeto de troca."""
        data_txt = data_ref.strftime("%d/%m/%Y") if isinstance(data_ref, (date, datetime)) else str(data_ref)
        return Troca(
            id=None,
            tipo=tipo,
            militar_origem=str(militar_origem).strip(),
            militar_destino=str(militar_destino).strip(),
            data=data_txt,
            servico_origem=servico_origem,
            servico_destino=servico_destino,
            status=status,
            observacoes=observacoes,
        )

    @staticmethod
    def filtrar_pendentes_para_militar(df_trocas: pd.DataFrame, militar_id: str) -> pd.DataFrame:
        """Filtra pedidos pendentes para resposta do militar destino."""
        if df_trocas.empty:
            return df_trocas
        return df_trocas[
            (df_trocas["status"] == "Pendente_Militar")
            & (df_trocas["id_destino"].astype(str).str.strip() == str(militar_id).strip())
        ]

    @staticmethod
    def aplicar_trocas_aprovadas_no_periodo(
        escalas: dict[str, pd.DataFrame],
        df_trocas: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """Aplica trocas aprovadas em múltiplos dias (`DD-MM` -> dataframe)."""
        if not escalas:
            return {}

        resultado: dict[str, pd.DataFrame] = {}
        for aba, df in escalas.items():
            try:
                dt = datetime.strptime(aba, "%d-%m").replace(year=datetime.now().year)
                data_str = dt.strftime("%d/%m/%Y")
            except Exception:
                resultado[aba] = df
                continue

            if df.empty:
                resultado[aba] = df
                continue

            tr = df_trocas[
                (df_trocas["data"] == data_str)
                & (df_trocas["status"] == "Aprovada")
                & (df_trocas["servico_origem"] != "MATAR_REMUNERADO")
            ]
            if tr.empty:
                resultado[aba] = df
                continue

            mask_rem = df["serviço"].str.lower().str.contains("remu|grat", na=False)
            out = df.copy()
            for _, t in tr.iterrows():
                id_o = str(t["id_origem"]).strip()
                id_d = str(t["id_destino"]).strip()
                s_o = str(t["servico_origem"])
                s_d = str(t["servico_destino"])

                serv_o = s_o.rsplit("(", 1)[0].strip()
                hor_o = s_o.rsplit("(", 1)[1].rstrip(")") if "(" in s_o else ""
                serv_d = s_d.rsplit("(", 1)[0].strip()
                hor_d = s_d.rsplit("(", 1)[1].rstrip(")") if "(" in s_d else ""

                m_o = (out["id"].astype(str).str.strip() == id_o) & ~mask_rem
                if m_o.any():
                    out.loc[m_o, "serviço"] = serv_d
                    if hor_d:
                        out.loc[m_o, "horário"] = hor_d

                m_d = (out["id"].astype(str).str.strip() == id_d) & ~mask_rem
                if m_d.any():
                    out.loc[m_d, "serviço"] = serv_o
                    if hor_o:
                        out.loc[m_d, "horário"] = hor_o

            resultado[aba] = out
        return resultado
