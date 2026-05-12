"""Lógica de autenticação e sessão por PIN.

Inclui:
- hash/validação de PIN
- proteção anti brute-force
- gestão de sessão Streamlit
- migração de PIN legado (texto simples -> hash:salt)
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Any

import pandas as pd
import streamlit as st

from config.settings import (
    ADMINS,
    LOGIN_BLOCK_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    PIN_LENGTH,
    SESSION_IS_ADMIN,
    SESSION_LOGGED_IN,
    SESSION_LOGIN_MODE,
    SESSION_PIN_ATTEMPTS,
    SESSION_PIN_BLOCKED_UNTIL,
    SESSION_PIN_BUFFER,
    SESSION_PIN_ERROR,
    SESSION_USER_EMAIL,
    SESSION_USER_ID,
    SESSION_USER_NAME,
    USERS_SHEET_NAME,
)
from core.database import GoogleSheetsClient


def hash_pin(pin: str, salt: str | None = None) -> tuple[str, str]:
    """Gera hash SHA-256 com salt para um PIN.

    Args:
        pin: PIN original.
        salt: Salt opcional. Quando ausente, é gerado automaticamente.

    Returns:
        Tuplo ``(hash_hex, salt)``.
    """
    pin_normalizado = str(pin).strip().zfill(PIN_LENGTH)
    salt_final = salt or secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt_final}{pin_normalizado}".encode()).hexdigest()
    return hashed, salt_final


def verify_pin(pin_input: str, pin_guardado: str) -> bool:
    """Verifica PIN com suporte a formato novo e legado.

    Formatos suportados:
    - ``hash:salt`` (novo)
    - ``1234`` texto simples (legado, para migração gradual)

    Args:
        pin_input: PIN inserido.
        pin_guardado: Valor armazenado no backend.

    Returns:
        ``True`` quando válido.
    """
    pin_input = str(pin_input).strip().zfill(PIN_LENGTH)
    pin_guardado = str(pin_guardado).strip()

    if ":" in pin_guardado and len(pin_guardado) > 10:
        partes = pin_guardado.split(":", 1)
        if len(partes) == 2:
            h_guardado, salt = partes
            h_input, _ = hash_pin(pin_input, salt)
            return h_input == h_guardado

    return pin_guardado.zfill(PIN_LENGTH) == pin_input


# Alias de compatibilidade legado
verificar_pin = verify_pin


def init_auth_session() -> None:
    """Inicializa chaves de autenticação em ``st.session_state``."""
    defaults: dict[str, Any] = {
        SESSION_LOGGED_IN: False,
        SESSION_LOGIN_MODE: "pin",
        SESSION_PIN_BUFFER: "",
        SESSION_PIN_ERROR: False,
        SESSION_PIN_ATTEMPTS: 0,
        SESSION_PIN_BLOCKED_UNTIL: None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_login_blocked(now: datetime | None = None) -> tuple[bool, int]:
    """Verifica se o utilizador está temporariamente bloqueado.

    Args:
        now: Momento de referência (útil para testes).

    Returns:
        Tuplo ``(bloqueado, segundos_restantes)``.
    """
    ref = now or datetime.now()
    blocked_until = st.session_state.get(SESSION_PIN_BLOCKED_UNTIL)
    if blocked_until and ref < blocked_until:
        remaining = int((blocked_until - ref).total_seconds())
        return True, max(0, remaining)
    return False, 0


def register_failed_attempt(
    max_attempts: int = LOGIN_MAX_ATTEMPTS,
    block_seconds: int = LOGIN_BLOCK_SECONDS,
) -> None:
    """Regista tentativa falhada e ativa bloqueio quando necessário."""
    tentativas = int(st.session_state.get(SESSION_PIN_ATTEMPTS, 0)) + 1
    st.session_state[SESSION_PIN_ATTEMPTS] = tentativas
    st.session_state[SESSION_PIN_ERROR] = True
    st.session_state[SESSION_PIN_BUFFER] = ""

    if tentativas >= max_attempts:
        st.session_state[SESSION_PIN_BLOCKED_UNTIL] = datetime.now() + timedelta(seconds=block_seconds)
        st.session_state[SESSION_PIN_ATTEMPTS] = 0


def login(user_row: pd.Series, user_email: str) -> None:
    """Efetua login e popula estado de sessão.

    Args:
        user_row: Linha do utilizador com pelo menos ``id``.
        user_email: Email autenticado.
    """
    user_id = str(user_row.get("id", "")).strip()
    posto = str(user_row.get("posto", "")).strip()
    nome = str(user_row.get("nome", "")).strip()
    user_name = f"{posto} {nome}".strip() if posto else (nome or user_email)

    st.session_state.update(
        {
            SESSION_LOGGED_IN: True,
            SESSION_USER_ID: user_id,
            SESSION_USER_NAME: user_name,
            SESSION_USER_EMAIL: user_email,
            SESSION_IS_ADMIN: user_email in ADMINS,
            SESSION_PIN_ATTEMPTS: 0,
            SESSION_PIN_BLOCKED_UNTIL: None,
            SESSION_PIN_BUFFER: "",
            SESSION_PIN_ERROR: False,
        }
    )


def logout() -> None:
    """Termina sessão mantendo chaves de autenticação base."""
    st.session_state[SESSION_LOGGED_IN] = False
    st.session_state[SESSION_USER_ID] = ""
    st.session_state[SESSION_USER_NAME] = ""
    st.session_state[SESSION_USER_EMAIL] = ""
    st.session_state[SESSION_IS_ADMIN] = False
    st.session_state[SESSION_PIN_BUFFER] = ""
    st.session_state[SESSION_PIN_ERROR] = False


def check_session() -> bool:
    """Confirma se existe sessão autenticada ativa."""
    return bool(st.session_state.get(SESSION_LOGGED_IN, False))


def migrate_legacy_pin(
    email: str,
    pin_texto: str,
    sheets_client: GoogleSheetsClient | None = None,
) -> bool:
    """Migra PIN antigo (texto simples) para formato ``hash:salt``.

    Args:
        email: Email do utilizador.
        pin_texto: PIN em texto simples, já validado.
        sheets_client: Cliente de BD opcional para injeção em testes.

    Returns:
        ``True`` se a migração foi gravada com sucesso.
    """
    client = sheets_client or GoogleSheetsClient()

    try:
        worksheet = client.get_worksheet(USERS_SHEET_NAME)
        records = worksheet.get_all_records()
        headers = [str(h).strip().lower() for h in worksheet.row_values(1)]

        if "pin" not in headers or "email" not in headers:
            return False

        col_pin = headers.index("pin") + 1

        for row_idx, row in enumerate(records, start=2):
            row_email = str(row.get("email", "")).strip().lower()
            if row_email == email.strip().lower():
                hash_val, salt = hash_pin(pin_texto)
                worksheet.update_cell(row_idx, col_pin, f"{hash_val}:{salt}")
                return True
    except Exception:
        return False

    return False


# Alias legado
migrar_pin_para_hash = migrate_legacy_pin
fazer_login = login
fazer_logout = logout
