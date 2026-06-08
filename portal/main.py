"""Portal de Escalas GNR — FastAPI entry point."""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from portal.api import auth, escala, trocas, utilizadores, notificacoes, ferias, calendar
from portal.api import admin as admin_api

logger = logging.getLogger(__name__)

app = FastAPI(title="Portal de Escalas GNR", version="2.0.0")

# Servir ficheiros estáticos
app.mount("/static", StaticFiles(directory="portal/static"), name="static")

# Servir admin React
from fastapi.staticfiles import StaticFiles as _SF
import os as _os
if _os.path.isdir("portal/static/admin"):
    app.mount("/admin/assets", _SF(directory="portal/static/admin/assets"), name="admin-assets")

# Registar routers
app.include_router(auth.router,           prefix="/api/auth",          tags=["auth"])
app.include_router(escala.router,         prefix="/api/escala",        tags=["escala"])
app.include_router(trocas.router,         prefix="/api/trocas",        tags=["trocas"])
app.include_router(utilizadores.router,   prefix="/api/utilizadores",  tags=["utilizadores"])
app.include_router(ferias.router,         prefix="/api/ferias",        tags=["ferias"])
app.include_router(calendar.router,       prefix="/api/calendar",      tags=["calendar"])
app.include_router(notificacoes.router,   prefix="/api/notificacoes",  tags=["notificacoes"])
app.include_router(admin_api.router,      prefix="/admin/api",         tags=["admin"])


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


# Servir o frontend
@app.get("/")
@app.head("/")
async def root():
    return FileResponse("portal/templates/index.html")

@app.get("/sw.js")
async def sw():
    return FileResponse("portal/static/sw.js", media_type="application/javascript")

@app.get("/admin")
@app.get("/admin/{full_path:path}")
async def admin_spa(full_path: str = ""):
    import os
    admin_index = "portal/static/admin/index.html"
    if os.path.isfile(admin_index):
        return FileResponse(admin_index)
    return FileResponse("portal/templates/index.html")

@app.get("/{full_path:path}")
@app.head("/{full_path:path}")
async def catch_all(full_path: str):
    return FileResponse("portal/templates/index.html")
