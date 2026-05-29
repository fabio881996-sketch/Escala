"""Router de integração Google Calendar."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel

from portal.api.auth import obter_user_atual

router = APIRouter()

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI         = "https://portal-escalas-gnr-production.up.railway.app/api/calendar/callback"
SCOPES               = "https://www.googleapis.com/auth/calendar.events"


def _auth_url(state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def _exchange_code(code: str) -> dict:
    import httpx
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "code":          code,
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    })
    r.raise_for_status()
    return r.json()


def _criar_evento(access_token: str, evento: dict) -> dict:
    import httpx
    r = httpx.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json=evento,
    )
    r.raise_for_status()
    return r.json()


# ── Sheet helpers para guardar tokens ────────────────────────

def _guardar_token(u_id: str, token_data: dict) -> None:
    try:
        from core.database import get_sheet
        sh = get_sheet()
        try:
            ws = sh.worksheet("google_tokens")
        except Exception:
            ws = sh.add_worksheet("google_tokens", rows=200, cols=3)
            ws.append_row(["u_id", "token_json", "updated_at"])
        rows = ws.get_all_values()
        token_json = json.dumps(token_data)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for i, row in enumerate(rows[1:], start=2):
            if str(row[0]).strip() == str(u_id):
                ws.update(f"B{i}", [[token_json]])
                ws.update(f"C{i}", [[now]])
                return
        ws.append_row([u_id, token_json, now])
    except Exception as e:
        pass


def _get_token(u_id: str) -> dict | None:
    try:
        from core.database import get_sheet
        sh = get_sheet()
        ws = sh.worksheet("google_tokens")
        rows = ws.get_all_values()[1:]
        for row in rows:
            if str(row[0]).strip() == str(u_id):
                return json.loads(row[1])
    except Exception:
        pass
    return None


def _refresh_token(token_data: dict) -> dict:
    import httpx
    r = httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": token_data.get("refresh_token"),
        "grant_type":    "refresh_token",
    })
    r.raise_for_status()
    new_data = {**token_data, **r.json()}
    return new_data


def _get_valid_token(u_id: str) -> str | None:
    """Devolve access_token válido, fazendo refresh se necessário."""
    token_data = _get_token(u_id)
    if not token_data:
        return None
    import time
    expires_at = token_data.get("expires_at", 0)
    if time.time() > expires_at - 60:
        try:
            token_data = _refresh_token(token_data)
            import time as t
            token_data["expires_at"] = t.time() + token_data.get("expires_in", 3600)
            _guardar_token(u_id, token_data)
        except Exception:
            return None
    return token_data.get("access_token")


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/auth")
async def google_auth(
    tipo: str = Query("escala", description="escala | folgas | ferias"),
    current_user: dict = Depends(obter_user_atual)
):
    """Inicia o fluxo OAuth Google Calendar."""
    u_id = str(current_user.get("sub"))
    # state = u_id:tipo para recuperar depois do callback
    state = f"{u_id}:{tipo}"
    return {"auth_url": _auth_url(state)}


@router.get("/callback")
async def google_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """Callback OAuth — recebe o code e guarda o token."""
    if error or not code:
        return HTMLResponse("""
            <html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#1A2B4A;color:white">
                <h2>❌ Autorização cancelada</h2>
                <p>Podes fechar esta janela.</p>
                <script>setTimeout(() => window.close(), 2000)</script>
            </body></html>
        """)

    u_id, tipo = (state or ":").split(":", 1)

    try:
        import time
        token_data = _exchange_code(code)
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        _guardar_token(u_id, token_data)
    except Exception as e:
        return HTMLResponse(f"""
            <html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#1A2B4A;color:white">
                <h2>❌ Erro</h2><p>{e}</p>
                <script>setTimeout(() => window.close(), 3000)</script>
            </body></html>
        """)

    # Redirecionar de volta ao portal — o JS detecta o gcal_pending no sessionStorage
    return RedirectResponse(url="https://portal-escalas-gnr-production.up.railway.app/")


@router.get("/status")
async def google_status(current_user: dict = Depends(obter_user_atual)):
    """Verifica se o utilizador tem token Google válido."""
    u_id = str(current_user.get("sub"))
    token = _get_valid_token(u_id)
    return {"connected": token is not None}


class EventosPayload(BaseModel):
    eventos: list[dict[str, Any]]


@router.post("/sync")
async def sync_eventos(payload: EventosPayload, current_user: dict = Depends(obter_user_atual)):
    """Cria eventos no Google Calendar do utilizador."""
    u_id = str(current_user.get("sub"))
    access_token = _get_valid_token(u_id)
    if not access_token:
        raise HTTPException(status_code=401, detail="Google Calendar não autorizado")

    criados = 0
    erros = 0
    for evento in payload.eventos:
        try:
            _criar_evento(access_token, evento)
            criados += 1
        except Exception:
            erros += 1

    return {"ok": True, "criados": criados, "erros": erros}
