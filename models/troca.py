"""Modelos para registos de troca de serviço."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Troca:
    """Representa uma troca/remunerado/mudança de folga.

    Args:
        id: Índice lógico do registo (opcional no sheet).
        tipo: Tipo funcional (``troca_simples``, ``fazer_remunerado``, etc.).
        militar_origem: ID do requerente/origem.
        militar_destino: ID de destino/cedente/substituto.
        data: Data da troca no formato ``dd/mm/YYYY``.
        servico_origem: Serviço origem serializado.
        servico_destino: Serviço destino serializado.
        status: Estado da troca.
        observacoes: Campo livre e flags internas.
        validador: Nome de quem validou.
        data_validacao: Timestamp de validação.
    """

    id: int | None
    tipo: str
    militar_origem: str
    militar_destino: str
    data: str
    servico_origem: str
    servico_destino: str
    status: str
    observacoes: str = ""
    validador: str = ""
    data_validacao: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any], idx: int | None = None) -> "Troca":
        """Cria troca a partir de uma linha de DataFrame/dict."""
        tipo = "troca_simples"
        sv_orig = str(row.get("servico_origem", "") or "").strip()
        if sv_orig == "MATAR_REMUNERADO":
            tipo = "remunerado"
        elif sv_orig.startswith("Folga "):
            tipo = "troca_folga"

        return cls(
            id=idx,
            tipo=tipo,
            militar_origem=str(row.get("id_origem", "") or "").strip(),
            militar_destino=str(row.get("id_destino", "") or "").strip(),
            data=str(row.get("data", "") or "").strip(),
            servico_origem=sv_orig,
            servico_destino=str(row.get("servico_destino", "") or "").strip(),
            status=str(row.get("status", "") or "").strip(),
            observacoes=str(row.get("observações", row.get("observacoes", "")) or "").strip(),
            validador=str(row.get("validador", "") or "").strip(),
            data_validacao=str(row.get("data_validacao", "") or "").strip(),
            meta={k: v for k, v in row.items() if str(k).strip().lower() not in {"data", "id_origem", "servico_origem", "id_destino", "servico_destino", "status", "observações", "observacoes", "validador", "data_validacao"}},
        )

    def is_pendente(self) -> bool:
        """Indica se a troca está pendente (militar/admin)."""
        return self.status in {"Pendente_Militar", "Pendente_Admin"}

    def is_aprovada(self) -> bool:
        """Indica se troca está aprovada."""
        return self.status == "Aprovada"

    def is_rejeitada(self) -> bool:
        """Indica se troca está rejeitada/cancelada."""
        return self.status in {"Rejeitada", "Recusada", "Cancelada"}

    def is_matar_remunerado(self) -> bool:
        """Indica se o registo representa operação de remunerado."""
        return self.servico_origem == "MATAR_REMUNERADO"

    def is_troca_folga(self) -> bool:
        """Indica se o registo é troca/mudança de folga."""
        return self.servico_origem.startswith("Folga ") and self.servico_destino.startswith("Folga ")

    def validar_campos_obrigatorios(self) -> tuple[bool, str]:
        """Valida integridade mínima de campos da troca."""
        if not self.data:
            return False, "Data obrigatória"
        if not self.militar_origem or not self.militar_destino:
            return False, "Militar de origem/destino obrigatório"
        if not self.servico_origem:
            return False, "Serviço de origem obrigatório"
        if not self.status:
            return False, "Status obrigatório"
        return True, ""

    def validar_data(self) -> tuple[bool, str]:
        """Valida formato de data esperado pelo sistema legado."""
        try:
            datetime.strptime(self.data, "%d/%m/%Y")
            return True, ""
        except Exception:
            return False, "Formato de data inválido (esperado DD/MM/YYYY)"

    def pode_transicionar_para(self, novo_status: str) -> bool:
        """Valida transições básicas de estado."""
        if self.status == "Pendente_Militar":
            return novo_status in {"Pendente_Admin", "Recusada", "Cancelada"}
        if self.status == "Pendente_Admin":
            return novo_status in {"Aprovada", "Rejeitada", "Cancelada"}
        return False

    def to_row(self) -> list[str]:
        """Serializa na ordem da worksheet `registos_trocas`."""
        return [
            self.data,
            self.militar_origem,
            self.servico_origem,
            self.militar_destino,
            self.servico_destino,
            self.status,
            self.observacoes,
            self.validador,
            self.data_validacao,
        ]
