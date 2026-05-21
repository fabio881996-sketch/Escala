"""Camada de acesso a dados (Google Sheets).

Compatível com Streamlit e FastAPI — sem imports de st no topo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import time
from typing import Any, Callable, Iterable, Sequence, TypeVar

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

from config.settings import SHEETS_SCOPES, get_secret, get_sheet_url
from core.utils import normalizar_coluna, normalizar_servico

T = TypeVar("T")

# Cache simples em memória para quando não há Streamlit
_client_cache: gspread.Client | None = None
_sheet_cache: gspread.Spreadsheet | None = None


def _build_gspread_client() -> gspread.Client:
    """Cria o cliente gspread com cache."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    service_account_info = get_secret("gcp_service_account")
    if not service_account_info:
        raise RuntimeError("'gcp_service_account' não encontrado")

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SHEETS_SCOPES,
    )
    _client_cache = gspread.authorize(creds)
    return _client_cache


def _build_spreadsheet() -> gspread.Spreadsheet:
    """Abre a spreadsheet principal com cache."""
    global _sheet_cache
    if _sheet_cache is not None:
        return _sheet_cache
    client = _build_gspread_client()
    _sheet_cache = client.open_by_url(get_sheet_url())
    return _sheet_cache


def _try_st_cache_resource(fn):
    """Aplica @st.cache_resource se Streamlit estiver disponível."""
    try:
        import streamlit as st
        return st.cache_resource(fn)
    except Exception:
        return fn


def df_from_records(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).astype(str)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.fillna("")
    if "serviço" in df.columns:
        df["serviço"] = df["serviço"].apply(normalizar_servico)
    if "id" in df.columns:
        df["id"] = df["id"].str.split(r"[,;]")
        df = df.explode("id")
        df["id"] = df["id"].str.strip()
        df = df[df["id"] != ""].reset_index(drop=True)
    return df


def df_from_values(values: Sequence[Sequence[Any]]) -> pd.DataFrame:
    if not values or len(values) < 2:
        return pd.DataFrame()
    headers = [str(h).strip().lower() for h in values[0]]
    rows: list[dict[str, str]] = []
    for row in values[1:]:
        row_ext = list(row) + [""] * (len(headers) - len(row))
        rows.append({headers[i]: str(row_ext[i]).strip() for i in range(len(headers))})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).fillna("")
    if "serviço" in df.columns:
        df["serviço"] = df["serviço"].apply(normalizar_servico)
    if "id" in df.columns:
        df["id"] = df["id"].str.split(r"[,;]")
        df = df.explode("id")
        df["id"] = df["id"].str.strip()
        df = df[df["id"] != ""].reset_index(drop=True)
    return df


@dataclass(slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_factor: float = 2.0


class GoogleSheetsClient:
    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self.retry_policy = retry_policy or RetryPolicy()

    @staticmethod
    def get_client() -> gspread.Client:
        return _build_gspread_client()

    @staticmethod
    def get_sheet() -> gspread.Spreadsheet:
        return _build_spreadsheet()

    def _with_retry(self, operation: Callable[[], T]) -> T:
        delay = self.retry_policy.initial_delay_seconds
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt >= self.retry_policy.max_attempts:
                    break
                time.sleep(delay)
                delay *= self.retry_policy.backoff_factor
        raise RuntimeError(f"Falha após {self.retry_policy.max_attempts} tentativas") from last_error

    def get_worksheet(self, worksheet_name: str) -> gspread.Worksheet:
        return self._with_retry(lambda: self.get_sheet().worksheet(worksheet_name))

    def load_data(self, worksheet_or_date: str | date | datetime, *, use_cache: bool = True) -> pd.DataFrame:
        del use_cache
        if isinstance(worksheet_or_date, (date, datetime)):
            worksheet_name = worksheet_or_date.strftime("%d-%m")
        else:
            worksheet_name = str(worksheet_or_date)

        def _op() -> pd.DataFrame:
            worksheet = self.get_worksheet(worksheet_name)
            return df_from_values(worksheet.get_all_values())

        try:
            return self._with_retry(_op)
        except Exception:
            return pd.DataFrame()

    def save_data(self, worksheet_name: str, data: pd.DataFrame, *, clear_before_write: bool = True) -> bool:
        try:
            worksheet = self.get_worksheet(worksheet_name)
            payload = [list(data.columns)] + data.fillna("").astype(str).values.tolist()
            def _op() -> None:
                if clear_before_write:
                    worksheet.clear()
                if payload:
                    worksheet.update("A1", payload)
            self._with_retry(_op)
            return True
        except Exception:
            return False

    def append_rows(self, worksheet_name: str, rows: Sequence[Sequence[Any]]) -> bool:
        if not rows:
            return True
        try:
            worksheet = self.get_worksheet(worksheet_name)
            self._with_retry(lambda: worksheet.append_rows(list(rows)))
            return True
        except Exception:
            return False

    def batch_update(self, worksheet_name: str, updates: Iterable[dict[str, Any]]) -> bool:
        try:
            worksheet = self.get_worksheet(worksheet_name)
            payload = list(updates)
            if not payload:
                return True
            self._with_retry(lambda: worksheet.batch_update(payload))
            return True
        except Exception:
            return False

    def get_headers(self, worksheet_name: str) -> list[str]:
        worksheet = self.get_worksheet(worksheet_name)
        headers = self._with_retry(lambda: worksheet.row_values(1))
        return [normalizar_coluna(h) for h in headers]


# --- Wrappers de compatibilidade ---
def get_gsheet_client() -> gspread.Client:
    return GoogleSheetsClient.get_client()


def get_sheet() -> gspread.Spreadsheet:
    return GoogleSheetsClient.get_sheet()


def load_data(aba_nome: str | date | datetime) -> pd.DataFrame:
    """Wrapper com cache — usa st.cache_data se disponível, senão directo."""
    try:
        import streamlit as st
        @st.cache_data(ttl=300)
        def _cached(nome):
            return GoogleSheetsClient().load_data(nome)
        if isinstance(aba_nome, (date, datetime)):
            return _cached(aba_nome.strftime("%d-%m"))
        return _cached(str(aba_nome))
    except Exception:
        return GoogleSheetsClient().load_data(aba_nome)


def save_data(aba_nome: str, data: pd.DataFrame, *, clear_before_write: bool = True) -> bool:
    return GoogleSheetsClient().save_data(aba_nome, data, clear_before_write=clear_before_write)


def batch_update(aba_nome: str, updates: Iterable[dict[str, Any]]) -> bool:
    return GoogleSheetsClient().batch_update(aba_nome, updates)
