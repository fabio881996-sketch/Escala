"""Funções utilitárias reutilizáveis para a aplicação GNR.

Objetivo: manter compatibilidade com o comportamento original,
mas com funções pequenas, documentadas e tipadas.
"""

from __future__ import annotations

from datetime import date, datetime
import re
import unicodedata
from typing import Iterable

from config.settings import ATENDIMENTO_PATTERN


def norm(texto: object) -> str:
    """Normaliza texto para comparação.

    Remove acentos e converte para minúsculas.

    Args:
        texto: Valor a normalizar.

    Returns:
        String normalizada.
    """
    return (
        unicodedata.normalize("NFKD", str(texto).lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def normalizar_servico(servico: str) -> str:
    """Normaliza nome de serviço para apresentação.

    Mantém compatibilidade com a lógica original que substitui
    termos históricos por "Convalescença".

    Args:
        servico: Nome do serviço.

    Returns:
        Nome normalizado.
    """
    texto = str(servico).strip()
    for antigo, novo in [
        ("Baixa", "Convalescença"),
        ("Doente", "Convalescença"),
        ("baixa", "convalescença"),
        ("doente", "convalescença"),
    ]:
        texto = texto.replace(antigo, novo)
    return texto


# Alias de compatibilidade com o código legado
norm_servico = normalizar_servico


def normalizar_coluna(nome_coluna: object) -> str:
    """Normaliza nome de coluna.

    Args:
        nome_coluna: Nome original da coluna.

    Returns:
        Nome em minúsculas, sem acentos e sem espaços nas extremidades.
    """
    return (
        unicodedata.normalize("NFD", str(nome_coluna))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


# Alias de compatibilidade com o código legado
_nc = normalizar_coluna


def parse_horario(horario: str) -> tuple[int | None, int | None]:
    """Converte horário textual para minutos.

    Suporta formatos:
    - ``HH-HH`` (ex.: ``08-16``)
    - ``HH:MM-HH:MM`` (ex.: ``08:00-16:00``)

    Regras de compatibilidade:
    - ``00`` no final é tratado como ``24:00``.
    - Se ``fim < início`` assume passagem de meia-noite.

    Args:
        horario: String no formato esperado.

    Returns:
        ``(inicio_min, fim_min)`` ou ``(None, None)`` se inválido.
    """
    try:
        texto = str(horario).strip().replace(":", "")
        partes = texto.split("-")
        if len(partes) != 2:
            return None, None

        def to_min(valor: str) -> int:
            valor = valor.strip()
            if len(valor) <= 2:
                return int(valor) * 60
            return int(valor[:-2]) * 60 + int(valor[-2:])

        inicio = to_min(partes[0])
        fim = to_min(partes[1])

        if fim == 0:
            fim = 1440
        if fim < inicio:
            fim += 1440

        return inicio, fim
    except Exception:
        return None, None


# Alias de compatibilidade com o código legado
_parse_horario = parse_horario


def e_servico_atendimento(servico: str) -> bool:
    """Indica se o serviço está no grupo atendimento/apoio."""
    return bool(re.search(ATENDIMENTO_PATTERN, norm(servico)))


def formatar_data(data_valor: date | datetime, formato: str = "%d-%m") -> str:
    """Formata uma data para string.

    Args:
        data_valor: Data a formatar.
        formato: Máscara de formatação ``datetime``.

    Returns:
        Data formatada.
    """
    return data_valor.strftime(formato)


def parse_data_flexivel(valor: object, ano_default: int | None = None) -> date | None:
    """Converte string de data em vários formatos para ``date``.

    Compatível com formatos usados no código original.
    """
    texto = str(valor).strip()
    if not texto:
        return None

    formatos = (
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%m/%d/%Y",
    )
    for fmt in formatos:
        try:
            return datetime.strptime(texto, fmt).date()
        except Exception:
            continue

    try:
        parcial = datetime.strptime(texto, "%m/%d").date()
        return parcial.replace(year=ano_default or datetime.now().year)
    except Exception:
        return None


def validar_descanso(
    servico_novo: str,
    horario_novo: str,
    servicos_adjacentes: Iterable[dict[str, str]],
    descanso_min_horas: int = 8,
) -> tuple[bool, str]:
    """Valida regra de descanso entre serviços.

    Esta função é genérica para reutilização em serviços/páginas.

    Args:
        servico_novo: Nome do serviço novo.
        horario_novo: Horário do serviço novo.
        servicos_adjacentes: Iterável de dicionários com campos:
            ``servico``, ``horario`` e opcionalmente ``label``.
        descanso_min_horas: Mínimo de horas de descanso.

    Returns:
        ``(True, "")`` se válido, caso contrário ``(False, motivo)``.
    """
    if e_servico_atendimento(servico_novo):
        return True, ""

    ini_novo, fim_novo = parse_horario(horario_novo)
    if ini_novo is None:
        return True, ""

    min_descanso = descanso_min_horas * 60

    for item in servicos_adjacentes:
        servico = str(item.get("servico", ""))
        horario = str(item.get("horario", "")).strip()
        label = str(item.get("label", "serviço adjacente"))

        if not horario or e_servico_atendimento(servico):
            continue
        if re.search(r"remu|grat", norm(servico)):
            continue

        ini_adj, fim_adj = parse_horario(horario)
        if ini_adj is None:
            continue

        # Distância mínima em ambos os sentidos (timeline de 48h)
        fim_novo_abs = fim_novo
        ini_novo_abs = ini_novo
        descanso1 = abs(ini_novo_abs - fim_adj)
        descanso2 = abs(ini_adj - fim_novo_abs)
        descanso = min(descanso1, descanso2)

        if descanso < min_descanso:
            horas = descanso // 60
            mins = descanso % 60
            return False, f"Apenas {horas}h{mins:02d}m de descanso face ao {label} ({servico} {horario})"

    return True, ""
