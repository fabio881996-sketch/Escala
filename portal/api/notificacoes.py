"""Router de notificações push — FCM V1 (APK) + Web Push (PWA)."""
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

# ── VAPID (Web Push / PWA) ────────────────────────────────────
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS  = {"sub": "mailto:admin@gnr-famalicao.pt"}

# ── Firebase Admin (FCM V1 / APK) ────────────────────────────
_firebase_app = None

def _get_firebase():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
    if not raw:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            info = json.loads(raw) if isinstance(raw, str) else raw
            cred = credentials.Certificate(info)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            _firebase_app = firebase_admin.get_app()
        return _firebase_app
    except Exception as e:
        logger.warning(f"Firebase init falhou: {e}")
        return None


# ── Sheet helpers ────────────────────────────────────────────

def _sheet_subscriptions():
    from core.database import get_sheet
    sh = get_sheet()
    try:
        return sh.worksheet("push_subscriptions")
    except Exception:
        ws = sh.add_worksheet("push_subscriptions", rows=500, cols=4)
        ws.append_row(["u_id", "subscription_json", "fcm_token", "updated_at"])
        return ws

def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _guardar_subscription(u_id: str, sub_json: str = "", fcm_token: str = "") -> None:
    ws = _sheet_subscriptions()
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if str(row[0]).strip() == str(u_id):
            if sub_json:
                ws.update(f"B{i}", [[sub_json]])
            if fcm_token:
                ws.update(f"C{i}", [[fcm_token]])
            ws.update(f"D{i}", [[_now()]])
            return
    ws.append_row([u_id, sub_json, fcm_token, _now()])

def _get_subscriptions(u_ids: list[str] | None = None):
    try:
        ws = _sheet_subscriptions()
        rows = ws.get_all_values()[1:]
        result = []
        for row in rows:
            if len(row) < 1 or not row[0].strip():
                continue
            uid = str(row[0]).strip()
            if u_ids is not None and uid not in u_ids:
                continue
            sub_json = row[1].strip() if len(row) > 1 else ""
            fcm_token = row[2].strip() if len(row) > 2 else ""
            result.append({
                "u_id": uid,
                "subscription": json.loads(sub_json) if sub_json else None,
                "fcm_token": fcm_token,
            })
        return result
    except Exception:
        return []


# ── Enviar push (FCM + Web Push) ──────────────────────────────

def enviar_push(u_ids: list[str], titulo: str, corpo: str, url: str = "/", tag: str = "gnr-notif") -> None:
    """Envia notificação para todos os dispositivos de cada u_id.
    APK → FCM V1 | PWA → Web Push
    """
    subs = _get_subscriptions(u_ids)
    if not subs:
        return

    # ── FCM (APK Android) ──
    firebase = _get_firebase()
    if firebase:
        try:
            from firebase_admin import messaging
            fcm_tokens = [s["fcm_token"] for s in subs if s.get("fcm_token")]
            if fcm_tokens:
                notification = messaging.Notification(title=titulo, body=corpo)
                android_config = messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        title=titulo,
                        body=corpo,
                        click_action="FLUTTER_NOTIFICATION_CLICK",
                        tag=tag,
                    )
                )
                if len(fcm_tokens) == 1:
                    msg = messaging.Message(
                        notification=notification,
                        android=android_config,
                        data={"url": url, "tag": tag},
                        token=fcm_tokens[0],
                    )
                    messaging.send(msg)
                else:
                    msg = messaging.MulticastMessage(
                        notification=notification,
                        android=android_config,
                        data={"url": url, "tag": tag},
                        tokens=fcm_tokens,
                    )
                    messaging.send_each_for_multicast(msg)
        except Exception as e:
            logger.warning(f"FCM falhou: {e}")

    # ── Web Push (PWA) ──
    if not VAPID_PRIVATE or not VAPID_PUBLIC:
        return
    try:
        from pywebpush import webpush
    except ImportError:
        return

    payload = json.dumps({"title": titulo, "body": corpo, "url": url, "tag": tag})
    for entry in subs:
        if not entry.get("subscription"):
            continue
        try:
            webpush(
                subscription_info=entry["subscription"],
                data=payload,
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims=VAPID_CLAIMS,
            )
        except Exception as e:
            logger.warning(f"Web Push falhou para {entry['u_id']}: {e}")


# ── Endpoints ────────────────────────────────────────────────

@router.get("/vapid-public-key")
async def vapid_public_key():
    if not VAPID_PUBLIC:
        raise HTTPException(status_code=503, detail="VAPID não configurado")
    return {"public_key": VAPID_PUBLIC}


class SubscriptionPayload(BaseModel):
    subscription: dict[str, Any] | None = None
    fcm_token: str | None = None


@router.post("/subscribe")
async def subscribe(payload: SubscriptionPayload, current_user: dict = Depends(obter_user_atual)):
    u_id = str(current_user.get("sub"))
    try:
        sub_json = json.dumps(payload.subscription) if payload.subscription else ""
        fcm_token = payload.fcm_token or ""
        _guardar_subscription(u_id, sub_json, fcm_token)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unsubscribe")
async def unsubscribe(current_user: dict = Depends(obter_user_atual)):
    u_id = str(current_user.get("sub"))
    try:
        ws = _sheet_subscriptions()
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if str(row[0]).strip() == u_id:
                ws.update(f"B{i}:C{i}", [["", ""]])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PublicarEscalaPayload(BaseModel):
    aba: str
    secret: str


@router.post("/publicar-escala")
async def publicar_escala_notif(payload: PublicarEscalaPayload):
    """Chamado pelo Streamlit após publicar escala — envia push a todos."""
    import os
    expected = os.environ.get("RAILWAY_NOTIFY_SECRET", "")
    if not expected or payload.secret != expected:
        raise HTTPException(status_code=403, detail="Não autorizado")
    try:
        from core.database import GoogleSheetsClient
        from services.data_loader import DataLoader
        loader = DataLoader(sheets_client=GoogleSheetsClient())
        df_util = loader.carregar_usuarios()
        todos_ids = df_util["id"].astype(str).str.strip().tolist()
        data_fmt = payload.aba.replace("-", "/")
        enviar_push(
            u_ids=todos_ids,
            titulo="📅 Nova escala publicada",
            corpo=f"A escala de {data_fmt} foi publicada.",
            url="/escala-geral",
            tag="escala-publicada",
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TestePush(BaseModel):
    u_ids: list[str]
    titulo: str = "🛡️ Teste GNR"
    corpo: str = "Notificação de teste do Portal de Escalas."


@router.post("/teste", dependencies=[Depends(obter_admin)])
async def teste_push(payload: TestePush):
    enviar_push(payload.u_ids, payload.titulo, payload.corpo)
    return {"ok": True}
