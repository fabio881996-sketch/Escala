"""Camada de acesso a dados (Google Sheets).

Este módulo extrai as responsabilidades de ligação/autenticação,
leitura/escrita e operações batch do código monolítico.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import time
from typing import Any, Callable, Iterable, Sequence, TypeVar

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

from config.settings import SHEETS_SCOPES, get_secret, get_sheet_url
from core.utils import normalizar_coluna, normalizar_servico

T = TypeVar("T")


@st.cache_resource
def _build_gspread_client() -> gspread.Client:
    """Cria e cacheia o cliente ``gspread``.

    Returns:
        Cliente autenticado para acesso ao Google Sheets.

    Raises:
        RuntimeError: Se as credenciais não estiverem disponíveis.
    """
    service_account_info = get_secret("gcp_service_account")
    if not service_account_info:
        raise RuntimeError("'gcp_service_account' não encontrado em st.secrets")

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=SHEETS_SCOPES,
    )
    return gspread.authorize(creds)


@st.cache_resource
def _build_spreadsheet() -> gspread.Spreadsheet:
    """Abre e cacheia a spreadsheet principal."""
    client = _build_gspread_client()
    return client.open_by_url(get_sheet_url())


def df_from_records(records: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Converte ``records`` em DataFrame normalizado.

    Compatível com o comportamento do código original:
    - lower/strip nos nomes de colunas
    - normalização de serviço
    - expansão da coluna ``id`` quando contém múltiplos IDs

    Args:
        records: Resultado de ``worksheet.get_all_records()``.

    Returns:
        DataFrame normalizado.
    """
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
    """Converte ``get_all_values()`` em DataFrame normalizado.

    Args:
        values: Matriz de valores com header na primeira linha.

    Returns:
        DataFrame normalizado.
    """
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
    """Configuração de retry com exponential backoff."""

    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_factor: float = 2.0


class GoogleSheetsClient:
    """Cliente de alto nível para operações com Google Sheets.

    Esta classe encapsula leituras e escritas com:
    - autenticação com cache
    - retry com exponential backoff
    - suporte a operações batch
    """

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self.retry_policy = retry_policy or RetryPolicy()

    @staticmethod
    def get_client() -> gspread.Client:
        """Devolve instância cacheada de ``gspread.Client``."""
        return _build_gspread_client()

    @staticmethod
    def get_sheet() -> gspread.Spreadsheet:
        """Devolve instância cacheada da spreadsheet principal."""
        return _build_spreadsheet()

    def _with_retry(self, operation: Callable[[], T]) -> T:
        """Executa uma operação com retry + exponential backoff."""
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
        """Obtém worksheet por nome com retry."""
        return self._with_retry(lambda: self.get_sheet().worksheet(worksheet_name))

    def load_data(
        self,
        worksheet_or_date: str | date | datetime,
        *,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Carrega dados de uma worksheet.

        Args:
            worksheet_or_date: Nome da worksheet (ex.: ``"utilizadores"``)
                ou data (converte para ``"%d-%m"`` para compatibilidade).
            use_cache: Mantido por compatibilidade semântica; o cache já é
                aplicado nos recursos de conexão.

        Returns:
            DataFrame com dados normalizados.
        """
        del use_cache  # compatibilidade de assinatura

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

    def save_data(
        self,
        worksheet_name: str,
        data: pd.DataFrame,
        *,
        clear_before_write: bool = True,
    ) -> bool:
        """Guarda um DataFrame numa worksheet.

        Args:
            worksheet_name: Nome da worksheet destino.
            data: Dados a persistir.
            clear_before_write: Se ``True``, limpa worksheet antes de gravar.

        Returns:
            ``True`` em caso de sucesso, ``False`` caso contrário.
        """
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
        """Adiciona múltiplas linhas numa única operação de escrita."""
        if not rows:
            return True

        try:
            worksheet = self.get_worksheet(worksheet_name)
            self._with_retry(lambda: worksheet.append_rows(list(rows)))
            return True
        except Exception:
            return False

    def batch_update(self, worksheet_name: str, updates: Iterable[dict[str, Any]]) -> bool:
        """Executa ``batch_update`` numa worksheet.

        Args:
            worksheet_name: Nome da worksheet.
            updates: Lista de updates no formato esperado pelo gspread,
                por exemplo ``[{"range": "F2", "values": [["Aprovada"]]}]``.

        Returns:
            ``True`` em caso de sucesso.
        """
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
        """Obtém cabeçalhos normalizados (lower + sem acentos)."""
        worksheet = self.get_worksheet(worksheet_name)
        headers = self._with_retry(lambda: worksheet.row_values(1))
        return [normalizar_coluna(h) for h in headers]


# --- Wrappers de compatibilidade com o código legado ---
def get_gsheet_client() -> gspread.Client:
    """Wrapper legado para manter compatibilidade com `original_code.py`."""
    return GoogleSheetsClient.get_client()


def get_sheet() -> gspread.Spreadsheet:
    """Wrapper legado para manter compatibilidade com `original_code.py`."""
    return GoogleSheetsClient.get_sheet()



@st.cache_data(ttl=300)
def load_data(aba_nome: str | date | datetime) -> pd.DataFrame:
    """Wrapper compatível com a função legada ``load_data``.

    Mantém API simples de leitura com cache de 5 minutos.
    """
    return GoogleSheetsClient().load_data(aba_nome)


def save_data(aba_nome: str, data: pd.DataFrame, *, clear_before_write: bool = True) -> bool:
    """Wrapper compatível com escrita de dados numa aba."""
    return GoogleSheetsClient().save_data(aba_nome, data, clear_before_write=clear_before_write)


def batch_update(aba_nome: str, updates: Iterable[dict[str, Any]]) -> bool:
    """Wrapper de batch update para compatibilidade modular."""
    return GoogleSheetsClient().batch_update(aba_nome, updates)
