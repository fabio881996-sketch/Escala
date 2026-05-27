"""Portal de Escalas GNR — FastAPI entry point."""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from portal.api import auth, escala, trocas, utilizadores, notificacoes, ferias

logger = logging.getLogger(__name__)

app = FastAPI(title="Portal de Escalas GNR", version="2.0.0")

# Servir ficheiros estáticos
app.mount("/static", StaticFiles(directory="portal/static"), name="static")

# Registar routers
app.include_router(auth.router,           prefix="/api/auth",          tags=["auth"])
app.include_router(escala.router,         prefix="/api/escala",        tags=["escala"])
app.include_router(trocas.router,         prefix="/api/trocas",        tags=["trocas"])
app.include_router(utilizadores.router,   prefix="/api/utilizadores",  tags=["utilizadores"])
app.include_router(ferias.router,         prefix="/api/ferias",        tags=["ferias"])
app.include_router(notificacoes.router,   prefix="/api/notificacoes",  tags=["notificacoes"])


@app.on_event("startup")
async def warmup():
    """Pré-carregar dados críticos no arranque para resposta imediata."""
    async def _load():
        try:
            from core.database import GoogleSheetsClient
            from services.data_loader import DataLoader
            loader = DataLoader(sheets_client=GoogleSheetsClient())
            loader.carregar_usuarios()
            loader.carregar_dias_publicados()
            loader.carregar_trocas()
            logger.info("Warm-up completo")
        except Exception as e:
            logger.warning(f"Warm-up falhou (ignorado): {e}")
    asyncio.create_task(_load())


# Servir sw.js na raiz (necessário para o scope correcto do Service Worker)
@app.get("/sw.js")
async def sw():
    return FileResponse("portal/static/sw.js", media_type="application/javascript")

# Servir o frontend
@app.get("/")
@app.head("/")
async def root():
    return FileResponse("portal/templates/index.html")

@app.get("/{full_path:path}")
@app.head("/{full_path:path}")
async def catch_all(full_path: str):
    return FileResponse("portal/templates/index.html")
