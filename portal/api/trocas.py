"""Router de trocas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.database import GoogleSheetsClient
from services.data_loader import DataLoader
from portal.api.auth import obter_user_atual, obter_admin

router = APIRouter()


def get_loader() -> DataLoader:
    return DataLoader(sheets_client=GoogleSheetsClient())


@router.get("/minhas")
async def minhas_trocas(current_user: dict = Depends(obter_user_atual)):
    """Devolve trocas do utilizador autenticado."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        if df.empty:
            return {"trocas": []}
        minhas = df[
            (df["id_origem"].astype(str) == str(u_id)) |
            (df["id_destino"].astype(str) == str(u_id))
        ]
        return {"trocas": minhas.fillna("").to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pendentes")
async def trocas_pendentes(current_user: dict = Depends(obter_user_atual)):
    """Devolve trocas pendentes de resposta do utilizador."""
    u_id = current_user.get("sub")
    try:
        loader = get_loader()
        df = loader.carregar_trocas()
        if df.empty:
            return {"trocas": []}
        pendentes = df[
            (df["status"] == "Pendente_Militar") &
            (df["id_destino"].astype(str) == str(u_id))
        ]
        return {"trocas": pendentes.fillna("").to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PedidoTroca(BaseModel):
    tipo: str
    data: str
    id_destino: str
    servico_origem: str
    servico_destino: str
    observacoes: Optional[str] = ""


@router.post("/solicitar")
async def solicitar_troca(pedido: PedidoTroca, current_user: dict = Depends(obter_user_atual)):
    """Cria pedido de troca."""
    u_id = current_user.get("sub")
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("registos_trocas")
        ws.append_row([
            pedido.data, u_id, pedido.servico_origem,
            pedido.id_destino, pedido.servico_destino,
            "Pendente_Militar", pedido.observacoes or ""
        ])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
