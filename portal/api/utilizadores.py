"""Router de utilizadores."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())


@router.get("/")
async def listar_utilizadores(current_user: dict = Depends(obter_admin)):
    """Lista todos os utilizadores (admin only)."""
    try:
        loader = get_loader()
        df = loader.carregar_usuarios()
        if df.empty:
            return {"utilizadores": []}
        # Não expor PIN
        cols = [c for c in df.columns if "pin" not in c.lower() and "hash" not in c.lower()]
        return {"utilizadores": df[cols].fillna("").to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/efetivo")
async def efetivo(current_user: dict = Depends(obter_user_atual)):
    """Lista militares (id, nome, posto) para selects."""
    try:
        loader = get_loader()
        df = loader.carregar_usuarios()
        if df.empty:
            return {"militares": []}
        cols = ["id", "nome", "posto"]
        cols_existentes = [c for c in cols if c in df.columns]
        return {"militares": df[cols_existentes].fillna("").to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
