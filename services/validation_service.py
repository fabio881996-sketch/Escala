"""Serviço central de validações de negócio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import re

import pandas as pd

from config.settings import IMPEDIMENTOS_PATTERN
from core.utils import e_servico_atendimento, norm, parse_horario
from models.escala import EntradaEscala
from services.data_loader import DataLoader

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationService:
    """Centraliza validações de descanso, sobreposição e conflitos."""

    data_loader: DataLoader

    def validar_descanso_minimo(
        self,
        militar_id: str,
        data_ref: date | datetime,
        servico_novo: str,
        horario_novo: str,
        *,
        servico_original_horario: str = "",
        descanso_min_horas: int = 8,
    ) -> tuple[bool, str]:
        """Replica a validação de descanso do código legado.

        Exceção: atendimento/apoio e remunerados não entram no cálculo.
        """
        if e_servico_atendimento(servico_novo):
            return True, ""

        ini_novo, fim_novo = parse_horario(horario_novo)
        if ini_novo is None:
            return True, ""

        dt_base = data_ref if isinstance(data_ref, datetime) else datetime.combine(data_ref, datetime.min.time())
        min_descanso = descanso_min_horas * 60

        for delta, label in [(-1, "dia anterior"), (1, "dia seguinte")]:
            dt_adj = dt_base + timedelta(days=delta)
            df_adj = self.data_loader.carregar_escala(dt_adj)
            if df_adj.empty:
                continue

            rows = df_adj[df_adj["id"].astype(str).str.strip() == str(militar_id).strip()]
            for _, row in rows.iterrows():
                serv_adj = str(row.get("serviço", ""))
                hor_adj = str(row.get("horário", "")).strip()
                if not hor_adj:
                    continue
                if servico_original_horario and hor_adj == servico_original_horario.strip():
                    continue
                if e_servico_atendimento(serv_adj):
                    continue
                if "remu" in norm(serv_adj) or "grat" in norm(serv_adj):
                    continue

                ini_adj, fim_adj = parse_horario(hor_adj)
                if ini_adj is None:
                    continue

                if delta == -1:
                    descanso = (1440 - fim_adj) + ini_novo
                else:
                    descanso = (1440 - fim_novo) + ini_adj

                if descanso < min_descanso:
                    h2, m2 = descanso // 60, descanso % 60
                    motivo = (
                        f"Apenas {h2}h{m2:02d}m de descanso face ao serviço do {label} "
                        f"({serv_adj} {hor_adj})"
                    )
                    return False, motivo

        return True, ""

    def validar_descanso_troca(
        self,
        militar_origem: str,
        militar_destino: str,
        data_ref: date | datetime,
        servico_origem_nome: str,
        horario_origem: str,
        servico_destino_nome: str,
        horario_destino: str,
        df_dia: pd.DataFrame,
        df_anterior: pd.DataFrame | None = None,
        df_seguinte: pd.DataFrame | None = None,
        descanso_min_horas: int = 6,
    ) -> list[str]:
        """Replica `verificar_descanso_troca` do monólito."""

        def _isento(servico: str) -> bool:
            s_n = norm(servico)
            return e_servico_atendimento(servico) or "remu" in s_n or "grat" in s_n

        def get_servicos_fixos(mil_id: str, horario_excluir: str) -> list[tuple[int, int, str, str]]:
            result: list[tuple[int, int, str, str]] = []
            for delta, offset, df_adj in [(-1, 0, df_anterior), (0, 1440, df_dia), (1, 2880, df_seguinte)]:
                if df_adj is None or df_adj.empty:
                    continue

                if "id_disp" in df_adj.columns:
                    mask = df_adj["id_disp"].astype(str).str.contains(str(mil_id), na=False)
                    mask2 = df_adj["id"].astype(str).str.strip() == str(mil_id).strip()
                    rows = df_adj[mask | mask2]
                else:
                    rows = df_adj[df_adj["id"].astype(str).str.strip() == str(mil_id).strip()]

                for _, row in rows.iterrows():
                    horario = str(row.get("horário", "")).strip()
                    serv = str(row.get("serviço", ""))
                    if not horario:
                        continue
                    if delta == 0 and horario == horario_excluir.strip():
                        continue
                    if _isento(serv):
                        continue
                    ini, fim = parse_horario(horario)
                    if ini is None:
                        continue
                    duracao = fim - ini
                    ini_abs = ini + offset
                    fim_abs = ini_abs + duracao
                    result.append((ini_abs, fim_abs, serv, horario))
            return result

        def validar_militar(
            mil_id: str,
            serv_novo: str,
            hor_novo: str,
            hor_excluir: str,
            label: str,
        ) -> list[str]:
            if _isento(serv_novo):
                return []
            ini_novo, fim_novo = parse_horario(hor_novo)
            if ini_novo is None:
                return []

            ini_novo_abs = ini_novo + 1440
            fim_novo_abs = ini_novo_abs + (fim_novo - ini_novo)
            minimo = descanso_min_horas * 60

            msgs: list[str] = []
            for ini_f, fim_f, serv_f, hor_f in get_servicos_fixos(mil_id, hor_excluir):
                if _isento(serv_f):
                    continue
                d1 = ini_novo_abs - fim_f
                d2 = ini_f - fim_novo_abs
                if d1 < minimo and fim_f <= fim_novo_abs:
                    d1_real = max(0, d1)
                    h2, m2 = d1_real // 60, d1_real % 60
                    msgs.append(
                        f"{label}: apenas {h2}h{m2:02d}m de descanso entre "
                        f"'{serv_f} ({hor_f})' e o serviço novo '{serv_novo} ({hor_novo})'"
                    )
                elif d2 < minimo and fim_novo_abs <= fim_f:
                    d2_real = max(0, d2)
                    h2, m2 = d2_real // 60, d2_real % 60
                    msgs.append(
                        f"{label}: apenas {h2}h{m2:02d}m de descanso entre o serviço novo "
                        f"'{serv_novo} ({hor_novo})' e '{serv_f} ({hor_f})'"
                    )
            return msgs

        erros = validar_militar(
            militar_origem,
            servico_destino_nome,
            horario_destino,
            horario_origem,
            "Não podes fazer esta troca",
        )
        erros += validar_militar(
            militar_destino,
            servico_origem_nome,
            horario_origem,
            horario_destino,
            "O militar de destino não pode fazer esta troca",
        )
        return erros

    @staticmethod
    def validar_sobreposicoes(entradas: list[EntradaEscala]) -> list[str]:
        """Valida sobreposições de horário por militar no mesmo dia."""
        alertas: list[str] = []
        por_id: dict[str, list[EntradaEscala]] = {}
        for e in entradas:
            if not e.id_militar or not e.horario:
                continue
            por_id.setdefault(e.id_militar, []).append(e)

        for mid, lista in por_id.items():
            slots: list[tuple[int, int, str]] = []
            for e in lista:
                ini, fim = parse_horario(e.horario)
                if ini is None:
                    continue
                slots.append((ini, fim, e.formatar_servico_completo()))

            for i in range(len(slots)):
                ini_a, fim_a, desc_a = slots[i]
                for j in range(i + 1, len(slots)):
                    ini_b, fim_b, desc_b = slots[j]
                    if not (fim_a <= ini_b or ini_a >= fim_b):
                        alertas.append(f"{mid}: sobreposição entre '{desc_a}' e '{desc_b}'")

        return alertas

    def validar_dispensas(
        self,
        militar_id: str,
        data_ref: date | datetime,
        servico: str,
        horario: str,
        df_licencas: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Valida dispensa por slot ativo."""
        tem = self.data_loader.militar_tem_dispensa_slot(
            militar_id,
            data_ref,
            df_licencas,
            servico,
            horario,
        )
        if tem:
            return False, "Militar com dispensa para este slot"
        return True, ""

    def gerar_alertas(
        self,
        escalas_por_dia: dict[str, pd.DataFrame],
        df_utilizadores: pd.DataFrame,
        df_ferias: pd.DataFrame,
        feriados: list[date],
    ) -> dict[str, list[str]]:
        """Gera alertas (duplos, descanso e não escalados) como no legado."""
        alertas_duplos: list[str] = []
        alertas_descanso: list[str] = []
        alertas_esquecidos: list[str] = []

        ids_ativos = set(df_utilizadores.get("id", pd.Series(dtype=str)).astype(str).str.strip().tolist())
        datas_ordenadas = sorted(escalas_por_dia.keys())

        for aba in datas_ordenadas:
            df = escalas_por_dia.get(aba, pd.DataFrame())
            if df.empty:
                continue
            try:
                dt = datetime.strptime(aba, "%d-%m").replace(year=datetime.now().year)
            except Exception:
                logger.debug("Aba '%s' fora do padrão de data", aba)
                continue

            d_s = dt.strftime("%d/%m/%Y")
            df_serv = df[~df["serviço"].apply(norm).str.contains("remu|grat", na=False)]
            contagem = df_serv[df_serv["id"].astype(str).str.strip() != ""].groupby("id").size()
            for mid, count in contagem.items():
                if count > 1:
                    servs = df_serv[df_serv["id"].astype(str) == str(mid)][["serviço", "horário"]].values.tolist()
                    alertas_duplos.append(f"**{d_s}** -- {mid}: {' / '.join([f'{s} ({h})' for s, h in servs])}")

            aba_ant = (dt - timedelta(days=1)).strftime("%d-%m")
            df_ant = escalas_por_dia.get(aba_ant, pd.DataFrame())
            if not df_ant.empty:
                df_ant_serv = df_ant[
                    ~df_ant["serviço"].apply(norm).str.contains("remu|grat|folga|ferias|licen|doente", na=False)
                ]
                ids_hoje = set(df_serv[df_serv["id"].astype(str).str.strip() != ""]["id"].astype(str))
                ids_ant = set(df_ant_serv[df_ant_serv["id"].astype(str).str.strip() != ""]["id"].astype(str))
                for mid in ids_hoje & ids_ant:
                    rows_h = df_serv[df_serv["id"].astype(str) == mid]
                    rows_a = df_ant_serv[df_ant_serv["id"].astype(str) == mid]
                    for _, rh in rows_h.iterrows():
                        ini_h, _ = parse_horario(str(rh.get("horário", "")))
                        if ini_h is None:
                            continue
                        for _, ra in rows_a.iterrows():
                            _, fim_a = parse_horario(str(ra.get("horário", "")))
                            if fim_a is None:
                                continue
                            descanso = (ini_h + 1440) - fim_a
                            if 0 <= descanso < 480:
                                h2, m2 = descanso // 60, descanso % 60
                                alertas_descanso.append(
                                    f"**{d_s}** -- {mid}: {h2}h{m2:02d}m entre "
                                    f"`{ra['serviço']} ({ra['horário']})` e `{rh['serviço']} ({rh['horário']})`"
                                )

            ids_na_escala = set(df[df["id"].astype(str).str.strip() != ""]["id"].astype(str).str.strip())
            em_ferias = set()
            for mid in ids_ativos:
                if self.data_loader.militar_de_ferias(mid, dt.date(), df_ferias, feriados):
                    em_ferias.add(mid)
            for mid in sorted(ids_ativos - ids_na_escala - em_ferias):
                alertas_esquecidos.append(f"**{d_s}** -- {mid}")

        return {
            "duplos": alertas_duplos,
            "descanso": alertas_descanso,
            "esquecidos": alertas_esquecidos,
        }

    @staticmethod
    def is_impedimento(servico: str) -> bool:
        """Indica se um serviço corresponde a impedimento de troca/escala."""
        return bool(re.search(IMPEDIMENTOS_PATTERN, norm(servico)))
