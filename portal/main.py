"""Portal de Escalas GNR — FastAPI entry point."""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from portal.api import auth, escala, trocas, utilizadores, notificacoes, ferias, calendar
try:
    from portal.api import admin as admin_api
    _admin_ok = True
except ImportError:
    _admin_ok = False

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
if _admin_ok:
    app.include_router(admin_api.router, prefix="/admin/api", tags=["admin"])


@app.on_event("startup")
async def warmup():
    """Pré-carregar dados críticos no arranque para resposta imediata."""
    async def _load():
        try:
            from services.data_loader_factory import get_data_loader
            loader = get_data_loader()
            loader.carregar_usuarios()
            loader.carregar_dias_publicados()
            loader.carregar_trocas()
            logger.info("Warm-up completo (PostgreSQL)" if __import__('os').environ.get('DATABASE_URL') else "Warm-up completo (Sheets)")
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


@app.post("/api/cache/clear")
async def clear_cache(payload: dict):
    """Limpa o cache interno do loader — chamado pelo Streamlit após alterações."""
    import os
    expected = os.environ.get("RAILWAY_NOTIFY_SECRET", "")
    if not expected or payload.get("secret") != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Não autorizado")
    try:
        from portal.api.escala import get_loader
        loader = get_loader()
        loader.limpar_cache()
    except Exception:
        pass
    return {"ok": True}
