"""Modelos de domínio da aplicação."""

from .escala import EntradaEscala
from .troca import Troca
from .usuario import Usuario

__all__ = ["Usuario", "Troca", "EntradaEscala"]
