"""Modelos da escala diária."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.utils import norm, parse_horario


@dataclass(slots=True)
class EntradaEscala:
    """Representa uma entrada (linha) da escala.

    A classe é compatível com os campos usados no código legado.
    """

    id_militar: str
    servico: str
    horario: str = ""
    indicativo: str = ""
    radio: str = ""
    giro: str = ""
    viatura: str = ""
    observacoes: str = ""
    nome: str = ""
    id_disp: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "EntradaEscala":
        """Cria entrada a partir de uma linha do DataFrame."""
        return cls(
            id_militar=str(row.get("id", "") or "").strip(),
            servico=str(row.get("serviço", row.get("servico", "")) or "").strip(),
            horario=str(row.get("horário", row.get("horario", "")) or "").strip(),
            indicativo=str(row.get("indicativo", row.get("indicativo rádio", "")) or "").strip(),
            radio=str(row.get("rádio", row.get("radio", "")) or "").strip(),
            giro=str(row.get("giro", "") or "").strip(),
            viatura=str(row.get("viatura", "") or "").strip(),
            observacoes=str(row.get("observações", row.get("observacoes", "")) or "").strip(),
            nome=str(row.get("nome", "") or "").strip(),
            id_disp=str(row.get("id_disp", "") or "").strip(),
            meta={k: v for k, v in row.items() if str(k).strip().lower() not in {"id", "serviço", "servico", "horário", "horario", "indicativo", "indicativo rádio", "rádio", "radio", "giro", "viatura", "observações", "observacoes", "nome", "id_disp"}},
        )

    def is_remunerado(self) -> bool:
        """Indica se o serviço é remunerado/gratificado."""
        texto = norm(self.servico)
        return "remu" in texto or "grat" in texto

    def is_folga(self) -> bool:
        """Indica se serviço é folga."""
        return "folga" in norm(self.servico)

    def is_vazia(self) -> bool:
        """Indica se linha não tem serviço atribuído."""
        return not bool(str(self.servico).strip())

    def validar(self) -> tuple[bool, str]:
        """Valida consistência mínima da entrada."""
        if not self.id_militar:
            return False, "ID do militar é obrigatório"
        if self.horario:
            ini, fim = parse_horario(self.horario)
            if ini is None or fim is None:
                return False, "Horário inválido"
        return True, ""

    def chave_slot(self) -> tuple[str, str]:
        """Devolve chave normalizada de slot (serviço, horário)."""
        return norm(self.servico), str(self.horario).strip()

    def formatar_servico_completo(self) -> str:
        """Retorna string no formato `Serviço (HH-HH)` quando aplicável."""
        if self.horario:
            return f"{self.servico} ({self.horario})"
        return self.servico

    def to_dict(self) -> dict[str, str]:
        """Serializa entrada para dicionário compatível com DataFrame."""
        payload = {
            "id": self.id_militar,
            "nome": self.nome,
            "serviço": self.servico,
            "horário": self.horario,
            "indicativo": self.indicativo,
            "rádio": self.radio,
            "giro": self.giro,
            "viatura": self.viatura,
            "observações": self.observacoes,
        }
        if self.id_disp:
            payload["id_disp"] = self.id_disp
        payload.update({str(k): str(v) for k, v in self.meta.items()})
        return payload
