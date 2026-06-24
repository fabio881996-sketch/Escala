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
VAPID_CLAIMS  = {"sub": "https://portal-escalas-gnr-production.up.railway.app"}

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


# ── Subscription helpers ─────────────────────────────────────

def _get_loader():
    from services.data_loader_factory import get_data_loader
    return get_data_loader()

def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _guardar_subscription(u_id: str, sub_json: str = "", fcm_token: str = "") -> None:
    try:
        loader = _get_loader()
        import json as _json
        _endpoint = sub_json
        _p256dh = ""
        _auth = ""
        try:
            _sub_dict = _json.loads(sub_json) if sub_json else {}
            _endpoint = _sub_dict.get("endpoint", sub_json)
            _keys = _sub_dict.get("keys", {})
            _p256dh = _keys.get("p256dh", "")
            _auth = _keys.get("auth", "")
        except Exception:
            pass
        loader.guardar_push_subscription(u_id, _endpoint, _p256dh, _auth, "web")
    except Exception as e:
        logger.warning(f"Erro ao guardar subscription: {e}")

def _get_subscriptions(u_ids: list[str] | None = None):
    try:
        loader = _get_loader()
        df_subs = loader.carregar_push_subscriptions()
        result = []
        for _, row in df_subs.iterrows():
            uid = str(row.get("militar_id","")).strip()
            if not uid: continue
            if u_ids is not None and uid not in u_ids: continue
            sub_json = str(row.get("endpoint","")).strip()
            # Reconstruir subscription JSON a partir dos campos
            endpoint = str(row.get("endpoint","")).strip()
            p256dh = str(row.get("p256dh","")).strip()
            auth = str(row.get("auth","")).strip()
            if endpoint:
                import json
                sub_json = json.dumps({"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}})
            fcm_token = ""
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
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


@router.delete("/unsubscribe")
async def unsubscribe(current_user: dict = Depends(obter_user_atual)):
    u_id = str(current_user.get("sub"))
    try:
        loader = _get_loader()
        df_subs = loader.carregar_push_subscriptions(u_id)
        for _, row in df_subs.iterrows():
            endpoint = str(row.get("endpoint","")).strip()
            if endpoint:
                loader.remover_push_subscription(endpoint)
        return {"ok": True}
    except Exception as e:
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


class PublicarEscalaPayload(BaseModel):
    aba: str
    secret: str
    u_ids: list[str] | None = None
    titulo: str | None = None
    corpo: str | None = None


@router.post("/publicar-escala")
async def publicar_escala_notif(payload: PublicarEscalaPayload):
    """Chamado pelo Streamlit após publicar escala ou editar — envia push."""
    import os
    expected = os.environ.get("RAILWAY_NOTIFY_SECRET", "")
    if not expected or payload.secret != expected:
        raise HTTPException(status_code=403, detail="Não autorizado")
    try:
        from services.data_loader_factory import get_data_loader
        loader = get_data_loader()
        data_fmt = payload.aba.replace("-", "/")
        # Se u_ids especificado, notificar só esses; caso contrário todos
        if payload.u_ids:
            u_ids = payload.u_ids
        else:
            df_util = loader.carregar_usuarios()
            u_ids = df_util["id"].astype(str).str.strip().tolist()
        enviar_push(
            u_ids=u_ids,
            titulo=payload.titulo or "📅 Nova escala publicada",
            corpo=payload.corpo or f"A escala de {data_fmt} foi publicada.",
            url="/escala-geral",
            tag="escala-publicada",
        )
        return {"ok": True}
    except Exception as e:
        logger.error("Erro interno: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


class TestePush(BaseModel):
    u_ids: list[str]
    titulo: str = "🛡️ Teste GNR"
    corpo: str = "Notificação de teste do Portal de Escalas."


@router.post("/teste", dependencies=[Depends(obter_admin)])
async def teste_push(payload: TestePush):
    enviar_push(payload.u_ids, payload.titulo, payload.corpo)
    return {"ok": True}
