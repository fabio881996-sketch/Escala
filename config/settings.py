"""Configurações centralizadas da aplicação GNR.

Compatível com Streamlit (st.secrets) e FastAPI (variáveis de ambiente).
"""

from __future__ import annotations

import os
from typing import Any


# ---------------------------
# Segurança / autenticação
# ---------------------------
ADMINS: list[str] = [
    "ferreira.fr@gnr.pt",
    "carmo.haf@gnr.pt",
    "veiga.hfp@gnr.pt",
]

PIN_LENGTH: int = 4
LOGIN_MAX_ATTEMPTS: int = 3
LOGIN_BLOCK_SECONDS: int = 30


# ---------------------------
# Regras de negócio
# ---------------------------
IMPEDIMENTOS: list[str] = [
    "férias",
    "licença",
    "convalescença",
    "diligência",
    "tribunal",
    "pronto",
    "secretaria",
    "inquérito",
    "outras licenças",
    "fcaa",
]
IMPEDIMENTOS_PATTERN: str = "|".join(IMPEDIMENTOS).lower()

ATENDIMENTO_PATTERN: str = r"atendimento|apoio"

DISPENSA_SLOTS: dict[str, tuple[str, str]] = {
    "A1": ("atendimento", "00-08"),
    "A2": ("atendimento", "08-16"),
    "A3": ("atendimento", "16-24"),
    "PO1": ("patrulha ocorrências", "00-08"),
    "PO2": ("patrulha ocorrências", "08-16"),
    "PO3": ("patrulha ocorrências", "16-24"),
    "AA2": ("apoio ao atendimento", "08-16"),
    "AA3": ("apoio ao atendimento", "16-24"),
}


# ---------------------------
# Google Sheets
# ---------------------------
SHEETS_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

USERS_SHEET_NAME: str = "utilizadores"
EXCHANGES_SHEET_NAME: str = "registos_trocas"


# ---------------------------
# Cache TTLs (segundos)
# ---------------------------
CACHE_TTL_SHORT: int = 60
CACHE_TTL_MEDIUM: int = 120
CACHE_TTL_DEFAULT: int = 300
CACHE_TTL_LONG: int = 3600
CACHE_TTL_DAY: int = 86400


# ---------------------------
# Session keys (Streamlit)
# ---------------------------
SESSION_LOGGED_IN: str = "logged_in"
SESSION_USER_ID: str = "user_id"
SESSION_USER_NAME: str = "user_nome"
SESSION_USER_EMAIL: str = "user_email"
SESSION_IS_ADMIN: str = "is_admin"
SESSION_PIN_ATTEMPTS: str = "pin_tentativas"
SESSION_PIN_BLOCKED_UNTIL: str = "pin_bloqueado_ate"
SESSION_PIN_BUFFER: str = "pin_buf"
SESSION_PIN_ERROR: str = "pin_erro"
SESSION_LOGIN_MODE: str = "login_modo"


def get_secret(key: str, default: Any | None = None) -> Any:
    """Obtém segredo — tenta st.secrets (Streamlit) e depois variáveis de ambiente.

    Compatível com Streamlit Cloud e FastAPI/produção.
    """
    # Tentar st.secrets primeiro (quando a correr no Streamlit)
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        pass

    # Fallback: variável de ambiente
    val = os.environ.get(key) or os.environ.get(key.upper())
    if val is not None:
        return val

    return default


def get_sheet_url() -> str:
    """Devolve a URL da Google Sheet principal."""
    url = get_secret("gsheet_url")
    if not url:
        raise ValueError("Chave 'gsheet_url' não encontrada em st.secrets nem em variáveis de ambiente")
    return str(url)


def get_sheet_id() -> str:
    """Extrai o ID da Google Sheet a partir da URL configurada."""
    url = get_sheet_url()
    if "/d/" not in url:
        raise ValueError(f"Formato inválido de gsheet_url: {url}")
    return url.split("/d/")[1].split("/")[0]
