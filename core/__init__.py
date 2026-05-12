"""Módulos core da aplicação GNR."""

from .auth import (
    check_session,
    hash_pin,
    init_auth_session,
    login,
    logout,
    migrate_legacy_pin,
    verify_pin,
)
from .database import GoogleSheetsClient, get_gsheet_client, get_sheet
from .utils import (
    _nc,
    _parse_horario,
    formatar_data,
    norm,
    normalizar_coluna,
    normalizar_servico,
    parse_horario,
    validar_descanso,
)

__all__ = [
    "GoogleSheetsClient",
    "get_gsheet_client",
    "get_sheet",
    "hash_pin",
    "verify_pin",
    "migrate_legacy_pin",
    "init_auth_session",
    "login",
    "logout",
    "check_session",
    "norm",
    "normalizar_servico",
    "normalizar_coluna",
    "_nc",
    "parse_horario",
    "_parse_horario",
    "validar_descanso",
    "formatar_data",
]
