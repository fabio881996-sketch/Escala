"""Model de utilizador (militar).

Data class com utilitários de validação e disponibilidade para escalamento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from core.utils import norm


@dataclass(slots=True)
class Usuario:
    """Representa um utilizador/militar.

    Args:
        id: Identificador único do militar.
        nome: Nome completo.
        posto: Posto (ex.: Cabo, Sargento).
        pin_hash: PIN em formato hash:salt ou legado.
        email: Email institucional.
        nim: Número interno opcional.
        telemovel: Contacto telefónico.
        is_admin: Indicador de permissões administrativas.
        ativo: Indicador lógico de utilizador ativo.
        meta: Campos adicionais de compatibilidade.
    """

    id: str
    nome: str
    posto: str = ""
    pin_hash: str = ""
    email: str = ""
    nim: str = ""
    telemovel: str = ""
    is_admin: bool = False
    ativo: bool = True
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any], admin_emails: set[str] | None = None) -> "Usuario":
        """Cria uma instância a partir de uma linha de DataFrame/dict."""
        email = str(row.get("email", "") or "").strip().lower()
        is_admin = bool(admin_emails and email in admin_emails)
        return cls(
            id=str(row.get("id", "") or "").strip(),
            nome=str(row.get("nome", "") or "").strip(),
            posto=str(row.get("posto", "") or "").strip(),
            pin_hash=str(row.get("pin", "") or "").strip(),
            email=email,
            nim=str(row.get("nim", "") or "").strip(),
            telemovel=str(row.get("telemóvel", row.get("telemovel", "")) or "").strip(),
            is_admin=is_admin,
            ativo=True,
            meta={k: v for k, v in row.items() if str(k).strip().lower() not in {"id", "nome", "posto", "pin", "email", "nim", "telemóvel", "telemovel"}},
        )

    def tem_folga(self, servico: str) -> bool:
        """Indica se o serviço atual é um tipo de folga."""
        texto = norm(servico)
        return "folga" in texto

    def esta_impedido(self, servico: str, impedimentos_pattern: str) -> bool:
        """Indica se está impedido no serviço atual por regra de negócio."""
        if not servico:
            return False
        return bool(re.search(impedimentos_pattern, norm(servico)))

    def pode_ser_escalado(
        self,
        servico_atual: str,
        *,
        esta_ferias: bool = False,
        tem_licenca: bool = False,
        tem_dispensa_slot: bool = False,
    ) -> bool:
        """Valida disponibilidade básica para ser escalado.

        Mantém semântica do código legado: férias/licenças/dispensas bloqueiam,
        e um serviço já preenchido (não-remunerado) também bloqueia.
        """
        if not self.ativo:
            return False
        if esta_ferias or tem_licenca or tem_dispensa_slot:
            return False

        sv = str(servico_atual or "").strip()
        if not sv:
            return True
        sv_norm = norm(sv)
        if "remu" in sv_norm or "grat" in sv_norm:
            return True
        return False

    def nome_curto(self) -> str:
        """Retorna representação curta `posto nome`."""
        if self.posto:
            return f"{self.posto} {self.nome}".strip()
        return self.nome.strip()

    def is_valido(self) -> bool:
        """Valida campos mínimos para uso na aplicação."""
        return bool(self.id and self.nome)

    def to_dict(self) -> dict[str, Any]:
        """Serializa utilizador para dicionário compatível com DataFrame."""
        payload = {
            "id": self.id,
            "nome": self.nome,
            "posto": self.posto,
            "pin": self.pin_hash,
            "email": self.email,
            "nim": self.nim,
            "telemóvel": self.telemovel,
            "is_admin": self.is_admin,
            "ativo": self.ativo,
        }
        payload.update(self.meta)
        return payload
