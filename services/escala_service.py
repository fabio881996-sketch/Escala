"""Serviço de geração e validação de escala."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import re
from typing import Any

import pandas as pd

from core.utils import norm, parse_horario
from models.escala import EntradaEscala
from services.data_loader import DataLoader
from services.validation_service import ValidationService

logger = logging.getLogger(__name__)


_ABREV_HOR: dict[str, tuple[str, str]] = {
    "A1": ("Atendimento", "00-08"),
    "A2": ("Atendimento", "08-16"),
    "A3": ("Atendimento", "16-24"),
    "PO1": ("Patrulha Ocorrências", "00-08"),
    "PO2": ("Patrulha Ocorrências", "08-16"),
    "PO3": ("Patrulha Ocorrências", "16-24"),
    "AA2": ("Apoio Atendimento", "08-16"),
    "AA3": ("Apoio Atendimento", "16-24"),
}

_SLOTS_BASE: list[tuple[str, str, int]] = [
    ("Atendimento", "00-08", 1),
    ("Atendimento", "08-16", 1),
    ("Atendimento", "16-24", 1),
    ("Patrulha Ocorrências", "00-08", 2),
    ("Patrulha Ocorrências", "08-16", 2),
    ("Patrulha Ocorrências", "16-24", 2),
    ("Apoio Atendimento", "08-16", 1),
    ("Apoio Atendimento", "16-24", 1),
]

_SLOTS_AUTO: dict[tuple[str, str], str] = {
    (norm("Atendimento"), "00-08"): "Atendimento 00-08",
    (norm("Atendimento"), "08-16"): "Atendimento 08-16",
    (norm("Atendimento"), "16-24"): "Atendimento 16-24",
    (norm("Patrulha Ocorrências"), "00-08"): "Patrulha Ocorrências 00-08",
    (norm("Patrulha Ocorrências"), "08-16"): "Patrulha Ocorrências 08-16",
    (norm("Patrulha Ocorrências"), "16-24"): "Patrulha Ocorrências 16-24",
    (norm("Apoio Atendimento"), "08-16"): "Apoio Atendimento 08-16",
    (norm("Apoio Atendimento"), "16-24"): "Apoio Atendimento 16-24",
}


@dataclass(slots=True)
class EscalaService:
    """Motor de geração automática e validação de escalas."""

    data_loader: DataLoader
    validation_service: ValidationService

    def gerar_escala_automatica(
        self,
        data_ref: date | datetime,
        df_editado: pd.DataFrame,
        ordem_escala: dict[str, list[str]],
        militares_servicos: dict[str, list[str]],
        df_licencas: pd.DataFrame,
        df_dia_anterior: pd.DataFrame | None = None,
    ) -> tuple[list[EntradaEscala], dict[str, list[str]]]:
        """Gera escala automática replicando a lógica do monólito.

        Returns:
            Tuplo ``(entradas_atualizadas, ordem_atualizada)``.
        """
        df_base = df_editado.copy()

        for idx, row in df_base.iterrows():
            sv = str(row.get("serviço", "")).strip()
            hr = str(row.get("horário", "")).strip()
            if sv in _ABREV_HOR:
                serv_real, hor_real = _ABREV_HOR[sv]
                df_base.at[idx, "serviço"] = serv_real
                if not hr or hr == "nan":
                    df_base.at[idx, "horário"] = hor_real

        ids_indisponiveis: set[str] = set()
        for _, row in df_base.iterrows():
            mid = str(row.get("id", "")).strip()
            serv = str(row.get("serviço", "")).strip()
            serv_norm = norm(serv)
            if serv and serv != "nan" and not any(x in serv_norm for x in ["remu", "grat"]):
                ids_indisponiveis.add(mid)

        slots_preenchidos: dict[tuple[str, str], int] = {}
        for _, row in df_base.iterrows():
            sv = str(row.get("serviço", "")).strip()
            hr = str(row.get("horário", "")).strip()
            if sv and sv != "nan" and hr and hr != "nan":
                chave = (norm(sv), hr)
                slots_preenchidos[chave] = slots_preenchidos.get(chave, 0) + 1

        slots_ajustados: list[tuple[str, str, int]] = []
        for sv, hr, limite in _SLOTS_BASE:
            ja = slots_preenchidos.get((norm(sv), hr), 0)
            vagas = max(0, limite - ja)
            if vagas > 0:
                slots_ajustados.append((sv, hr, vagas))

        ids_escalados: set[str] = set()
        novas_linhas: dict[str, dict[str, Any]] = {
            str(row["id"]): dict(row) for _, row in df_base.iterrows() if str(row.get("id", "")).strip()
        }
        ordem_atualizada = {k: list(v) for k, v in ordem_escala.items()}

        for servico, horario, numero in slots_ajustados:
            col_key = f"{servico} {horario}"
            if col_key not in ordem_atualizada:
                continue

            colocados: list[str] = []
            for mid in ordem_atualizada[col_key]:
                if len(colocados) >= numero:
                    break
                ok, _ = self.verificar_disponibilidade(
                    militar_id=mid,
                    data_ref=data_ref,
                    servico=servico,
                    horario=horario,
                    ids_indisponiveis=ids_indisponiveis,
                    ids_escalados=ids_escalados,
                    militares_servicos=militares_servicos,
                    df_licencas=df_licencas,
                    df_dia_anterior=df_dia_anterior,
                )
                if not ok:
                    continue
                if mid not in novas_linhas:
                    continue
                colocados.append(mid)
                ids_escalados.add(mid)

            for mid in colocados:
                novas_linhas[mid]["serviço"] = servico
                novas_linhas[mid]["horário"] = horario

                if servico == "Patrulha Ocorrências":
                    novas_linhas[mid]["indicativo"] = "031.6A"
                    novas_linhas[mid]["viatura"] = "BT-05-NX"
                    novas_linhas[mid]["giro"] = "I"
                    if horario == "00-08":
                        novas_linhas[mid]["rádio"] = "4110201"
                    elif horario == "08-16":
                        novas_linhas[mid]["rádio"] = "4110203"
                    elif horario == "16-24":
                        novas_linhas[mid]["rádio"] = "4110204"

                ordem_atualizada[col_key] = self.aplicar_rotacao(ordem_atualizada[col_key], mid)

        entradas = [EntradaEscala.from_row(row) for row in novas_linhas.values()]
        return entradas, ordem_atualizada

    def verificar_disponibilidade(
        self,
        *,
        militar_id: str,
        data_ref: date | datetime,
        servico: str,
        horario: str,
        ids_indisponiveis: set[str],
        ids_escalados: set[str],
        militares_servicos: dict[str, list[str]],
        df_licencas: pd.DataFrame,
        df_dia_anterior: pd.DataFrame | None,
    ) -> tuple[bool, str]:
        """Replica regras de disponibilidade do gerador automático."""
        if militar_id in ids_indisponiveis:
            return False, "indisponivel"
        if militar_id in ids_escalados:
            return False, "ja_escalado"

        data_ref_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref

        # Regra de hoje: militares 812/868 são tratados via dispensa de slot (sem hardcode de exceções).
        if militar_id in {"812", "868"} and self.data_loader.militar_tem_dispensa_slot(
            militar_id,
            data_ref_d,
            df_licencas,
            servico,
            horario,
        ):
            return False, "dispensa_slot_812_868"

        if self.data_loader.militar_tem_dispensa_slot(
            militar_id,
            data_ref_d,
            df_licencas,
            servico,
            horario,
        ):
            return False, "dispensa_slot"

        if servico not in militares_servicos.get(militar_id, []):
            return False, f"sem_servico:{militares_servicos.get(militar_id, [])}"

        ini_novo, _ = parse_horario(horario)
        if ini_novo is None:
            return True, ""

        if df_dia_anterior is not None and not df_dia_anterior.empty:
            rows_ant = df_dia_anterior[df_dia_anterior["id"].astype(str).str.strip() == str(militar_id).strip()]
            rows_ant = rows_ant[~rows_ant["serviço"].apply(norm).str.contains("remu|grat", na=False)]
            for _, row in rows_ant.iterrows():
                _, fim_ant = parse_horario(str(row.get("horário", "")))
                if fim_ant and (1440 - fim_ant) + ini_novo < 480:
                    return False, "descanso"

        return True, ""

    @staticmethod
    def aplicar_rotacao(ordem_slot: list[str], militar_id: str) -> list[str]:
        """Move o militar para o fim da fila do slot."""
        fila = list(ordem_slot)
        if militar_id in fila:
            fila.remove(militar_id)
            fila.append(militar_id)
        return fila

    def atualizar_ordem_escala_dia(
        self,
        ordem_base: dict[str, list[str]],
        df_escala_dia: pd.DataFrame,
    ) -> dict[str, list[str]]:
        """Atualiza ordem por slot com base no efetivamente escalado num dia."""
        ordem = {k: list(v) for k, v in ordem_base.items()}
        if df_escala_dia.empty:
            return ordem

        for _, row in df_escala_dia.iterrows():
            servico = norm(str(row.get("serviço", "")).strip())
            horario = str(row.get("horário", "")).strip()
            ids_raw = str(row.get("id", "")).strip()

            col_key = _SLOTS_AUTO.get((servico, horario))
            if not col_key or not ids_raw or ids_raw == "nan":
                continue

            for militar_id in re.split(r"[;,]+", ids_raw):
                militar_id = militar_id.strip()
                if not militar_id or col_key not in ordem:
                    continue
                ordem[col_key] = self.aplicar_rotacao(ordem[col_key], militar_id)

        return ordem

    def atualizar_ordem_escala_em_cadeia(
        self,
        ordem_inicial: dict[str, list[str]],
        escalas_por_aba: dict[str, pd.DataFrame],
        dia_inicial: date | datetime,
        max_dias: int = 9,
    ) -> dict[str, dict[str, list[str]]]:
        """Recalcula cadeia de ordem_escala por até 9 dias consecutivos.

        Returns:
            Mapa ``{aba_dd-mm: ordem_escala_para_o_dia}``.
        """
        cadeia: dict[str, dict[str, list[str]]] = {}
        d_ref = dia_inicial.date() if isinstance(dia_inicial, datetime) else dia_inicial
        ordem_atual = {k: list(v) for k, v in ordem_inicial.items()}

        for offset in range(max_dias):
            aba_atual = (d_ref + timedelta(days=offset)).strftime("%d-%m")
            aba_prox = (d_ref + timedelta(days=offset + 1)).strftime("%d-%m")
            df_dia = escalas_por_aba.get(aba_atual)
            if df_dia is None:
                break
            ordem_atual = self.atualizar_ordem_escala_dia(ordem_atual, df_dia)
            cadeia[aba_prox] = {k: list(v) for k, v in ordem_atual.items()}

        return cadeia

    def preencher_disponibilidade_confirmacao(
        self,
        df_escala: pd.DataFrame,
        df_util: pd.DataFrame,
        *,
        data_ref: date | datetime,
        df_ferias: pd.DataFrame,
        df_licencas: pd.DataFrame,
        feriados: list[date] | None = None,
    ) -> pd.DataFrame:
        """Preenche militares sem serviço com Disponível/Férias/Licença."""
        if df_util.empty:
            return df_escala

        data_d = data_ref.date() if isinstance(data_ref, datetime) else data_ref
        feriados = feriados or []
        df_out = df_escala.copy() if df_escala is not None else pd.DataFrame()

        ids_escalados: set[str] = set()
        if not df_out.empty and "id" in df_out.columns and "serviço" in df_out.columns:
            for _, row in df_out.iterrows():
                serv = norm(str(row.get("serviço", "")).strip())
                if not serv or serv == "nan":
                    continue
                for militar_id in re.split(r"[;,]+", str(row.get("id", "")).strip()):
                    militar_id = militar_id.strip()
                    if militar_id:
                        ids_escalados.add(militar_id)

        for _, row_u in df_util.iterrows():
            militar_id = str(row_u.get("id", "")).strip()
            if not militar_id or militar_id == "nan" or militar_id in ids_escalados:
                continue

            if self.data_loader.militar_de_ferias(militar_id, data_d, df_ferias, feriados):
                servico_reg = "Férias"
            else:
                lic_raw = self.data_loader.militar_de_licenca(militar_id, data_d, df_licencas)
                servico_reg = lic_raw.split("|", 1)[0] if lic_raw else "Disponível"

            nova_linha: dict[str, Any] = {c: "" for c in df_out.columns} if not df_out.empty else {}
            nova_linha.update({"id": militar_id, "serviço": servico_reg, "horário": ""})
            df_out = pd.concat([df_out, pd.DataFrame([nova_linha])], ignore_index=True)

        return df_out

    # TODO: quando houver regras adicionais de confirmação (ex.: prioridades por posto),
    # centralizar aqui para evitar lógica distribuída na camada de UI.

    def validar_escala(
        self,
        entradas: list[EntradaEscala],
        *,
        data_ref: date | datetime,
        df_licencas: pd.DataFrame | None = None,
        descanso_min_horas: int = 8,
    ) -> tuple[bool, list[str]]:
        """Valida conflitos de escala (sobreposição + regras de descanso)."""
        conflitos = self.detectar_conflitos(
            entradas,
            data_ref=data_ref,
            df_licencas=df_licencas,
            descanso_min_horas=descanso_min_horas,
        )
        return len(conflitos) == 0, conflitos

    def detectar_conflitos(
        self,
        entradas: list[EntradaEscala],
        *,
        data_ref: date | datetime,
        df_licencas: pd.DataFrame | None = None,
        descanso_min_horas: int = 8,
    ) -> list[str]:
        """Deteta sobreposição, dispensa e descanso insuficiente."""
        conflitos: list[str] = []

        conflitos.extend(self.validation_service.validar_sobreposicoes(entradas))

        if df_licencas is not None and not df_licencas.empty:
            for entrada in entradas:
                if not entrada.horario:
                    continue
                ok_disp, motivo_disp = self.validation_service.validar_dispensas(
                    entrada.id_militar,
                    data_ref if isinstance(data_ref, date) else data_ref.date(),
                    entrada.servico,
                    entrada.horario,
                    df_licencas,
                )
                if not ok_disp:
                    conflitos.append(f"{entrada.id_militar}: {motivo_disp} ({entrada.formatar_servico_completo()})")

        for entrada in entradas:
            if not entrada.horario:
                continue
            ok_desc, motivo_desc = self.validation_service.validar_descanso_minimo(
                militar_id=entrada.id_militar,
                data_ref=data_ref,
                servico_novo=entrada.servico,
                horario_novo=entrada.horario,
                descanso_min_horas=descanso_min_horas,
            )
            if not ok_desc:
                conflitos.append(f"{entrada.id_militar}: {motivo_desc}")

        return conflitos

    @staticmethod
    def entradas_para_dataframe(entradas: list[EntradaEscala]) -> pd.DataFrame:
        """Converte entradas para DataFrame."""
        if not entradas:
            return pd.DataFrame()
        return pd.DataFrame([e.to_dict() for e in entradas])
