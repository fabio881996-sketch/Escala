"""Portal de Escalas GNR — FastAPI entry point."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from portal.api import auth, escala, trocas, utilizadores

app = FastAPI(title="Portal de Escalas GNR", version="2.0.0")

# Servir ficheiros estáticos (CSS, JS, ícones)
app.mount("/static", StaticFiles(directory="portal/static"), name="static")

# Registar routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(escala.router, prefix="/api/escala", tags=["escala"])
app.include_router(trocas.router, prefix="/api/trocas", tags=["trocas"])
app.include_router(utilizadores.router, prefix="/api/utilizadores", tags=["utilizadores"])

# Servir o frontend
@app.get("/")
async def root():
    return FileResponse("portal/templates/index.html")

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    return FileResponse("portal/templates/index.html")
