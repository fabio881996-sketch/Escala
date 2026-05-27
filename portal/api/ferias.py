"""Router de férias — plano do utilizador autenticado."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual

router = APIRouter()


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())


def _parse_data(valor: str, ano: int) -> str | None:
    """Converte MM/DD ou DD/MM para DD/MM/YYYY."""
    v = str(valor).strip()
    if not v or v in ("", "nan"):
        return None
    for fmt in ("%m/%d", "%d/%m", "%m-%d", "%d-%m"):
        try:
            dt = datetime.strptime(v, fmt)
            return f"{dt.day:02d}/{dt.month:02d}/{ano}"
        except ValueError:
            continue
    return None


def _dias_corridos(ini_str: str, fim_str: str, ano: int) -> int:
    """Calcula dias corridos entre duas datas DD/MM/YYYY."""
    try:
        ini = datetime.strptime(ini_str, "%d/%m/%Y")
        fim = datetime.strptime(fim_str, "%d/%m/%Y")
        return (fim - ini).days + 1
    except Exception:
        return 0


@router.get("/meu")
async def minhas_ferias(current_user: dict = Depends(obter_user_atual)):
    """Devolve o plano de férias do utilizador autenticado."""
    u_id = str(current_user.get("sub"))
    ano = datetime.now().year

    try:
        loader = get_loader()
        df = loader.carregar_ferias(ano)

        if df.empty:
            return {"ano": ano, "periodos": [], "total_dias_uteis": 0}

        # Encontrar linha do utilizador
        linha = df[df["id"].astype(str).str.strip() == u_id]
        if linha.empty:
            return {"ano": ano, "periodos": [], "total_dias_uteis": 0}

        row = linha.iloc[0]
        cols = [str(c).strip() for c in df.columns]

        periodos: list[dict[str, Any]] = []
        total_uteis = 0
        n = 1

        while True:
            col_ini  = next((c for c in cols if c.lower() == f"p{n}_ini"),  None)
            col_fim  = next((c for c in cols if c.lower() == f"p{n}_fim"),  None)
            col_dias = next((c for c in cols if c.lower() == f"dias_{n}"), None)

            if not col_ini or not col_fim:
                break

            ini_raw = str(row.get(col_ini, "")).strip()
            fim_raw = str(row.get(col_fim, "")).strip()

            if not ini_raw or ini_raw == "nan":
                break

            ini_fmt = _parse_data(ini_raw, ano)
            fim_fmt = _parse_data(fim_raw, ano) if fim_raw and fim_raw != "nan" else ini_fmt

            if not ini_fmt:
                n += 1
                continue

            dias_uteis = 0
            if col_dias:
                try:
                    dias_uteis = int(float(str(row.get(col_dias, 0))))
                except (ValueError, TypeError):
                    dias_uteis = 0

            dias_corr = _dias_corridos(ini_fmt, fim_fmt, ano)
            total_uteis += dias_uteis

            periodos.append({
                "numero": n,
                "inicio": ini_fmt,
                "fim": fim_fmt,
                "dias_corridos": dias_corr,
                "dias_uteis": dias_uteis,
            })
            n += 1

        return {
            "ano": ano,
            "periodos": periodos,
            "total_dias_uteis": total_uteis,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
