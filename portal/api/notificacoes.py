"""Router de notificações push (Web Push / VAPID)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from portal.api.auth import obter_user_atual, obter_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# ── VAPID ────────────────────────────────────────────────────
# Gera uma vez com:  python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.public_key_urlsafe, v.private_key_urlsafe)"
# Guarda como variáveis de ambiente no Railway.
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS  = {"sub": "mailto:admin@gnr-famalicao.pt"}


def _sheet_subscriptions():
    """Devolve a worksheet de subscriptions (cria se não existir)."""
    from core.database import get_sheet
    sh = get_sheet()
    try:
        return sh.worksheet("push_subscriptions")
    except Exception:
        ws = sh.add_worksheet("push_subscriptions", rows=500, cols=3)
        ws.append_row(["u_id", "subscription_json", "updated_at"])
        return ws


def _guardar_subscription(u_id: str, sub_json: str) -> None:
    ws = _sheet_subscriptions()
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):   # linha 1 = cabeçalho
        if str(row[0]).strip() == str(u_id):
            ws.update(f"B{i}", [[sub_json]])
            ws.update(f"C{i}", [[_now()]])
            return
    ws.append_row([u_id, sub_json, _now()])


def _get_subscriptions(u_ids: list[str] | None = None) -> list[dict]:
    """Devolve lista de dicts {u_id, subscription}."""
    try:
        ws = _sheet_subscriptions()
        rows = ws.get_all_values()[1:]   # ignorar cabeçalho
        result = []
        for row in rows:
            if len(row) < 2 or not row[1].strip():
                continue
            uid = str(row[0]).strip()
            if u_ids is not None and uid not in u_ids:
                continue
            try:
                result.append({"u_id": uid, "subscription": json.loads(row[1])})
            except Exception:
                pass
        return result
    except Exception:
        return []


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ── Enviar push (interno, chamado por outros routers) ─────────

def enviar_push(u_ids: list[str], titulo: str, corpo: str, url: str = "/") -> None:
    """Envia notificação push a uma lista de u_ids. Falhas são ignoradas silenciosamente."""
    if not VAPID_PRIVATE or not VAPID_PUBLIC:
        logger.warning("VAPID keys não configuradas — push não enviado")
        return
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush não instalado — push não enviado")
        return

    subs = _get_subscriptions(u_ids)
    payload = json.dumps({"title": titulo, "body": corpo, "url": url})

    for entry in subs:
        try:
            webpush(
                subscription_info=entry["subscription"],
                data=payload,
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims=VAPID_CLAIMS,
            )
        except Exception as e:
            logger.warning(f"Push falhou para {entry['u_id']}: {e}")


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/vapid-public-key")
async def vapid_public_key():
    """Devolve a chave pública VAPID para o frontend."""
    if not VAPID_PUBLIC:
        raise HTTPException(status_code=503, detail="VAPID não configurado")
    return {"public_key": VAPID_PUBLIC}


class SubscriptionPayload(BaseModel):
    subscription: dict[str, Any]


@router.post("/subscribe")
async def subscribe(payload: SubscriptionPayload, current_user: dict = Depends(obter_user_atual)):
    """Guarda subscription do utilizador autenticado."""
    u_id = str(current_user.get("sub"))
    try:
        _guardar_subscription(u_id, json.dumps(payload.subscription))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unsubscribe")
async def unsubscribe(current_user: dict = Depends(obter_user_atual)):
    """Remove subscription do utilizador."""
    u_id = str(current_user.get("sub"))
    try:
        ws = _sheet_subscriptions()
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if str(row[0]).strip() == u_id:
                ws.update(f"B{i}", [[""]])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TestePush(BaseModel):
    u_ids: list[str]
    titulo: str = "🛡️ Teste GNR"
    corpo: str = "Notificação de teste do Portal de Escalas."


@router.post("/teste", dependencies=[Depends(obter_admin)])
async def teste_push(payload: TestePush):
    """Admin envia push de teste para uma lista de utilizadores."""
    enviar_push(payload.u_ids, payload.titulo, payload.corpo)
    return {"ok": True}
