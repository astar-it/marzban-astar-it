from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import logger
from app.db import GetDB
from app.db import models as db_models
from app.models.proxy import ProxyTypes
from app.models.user import UserStatus

router = APIRouter(tags=["Hysteria2"])


@router.post("/hysteria2/auth")
async def hysteria2_auth(request: Request):
    """Hysteria2 HTTP auth callback.

    Hysteria2 server sends POST with {"addr": "...", "auth": "password", "tx": 0}
    and expects {"ok": true, "id": "user_id"} or {"ok": false}.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False})

    password = body.get("auth", "")
    if not password:
        return JSONResponse({"ok": False})

    with GetDB() as db:
        proxies = (
            db.query(db_models.Proxy)
            .join(db_models.User)
            .filter(
                db_models.Proxy.type == ProxyTypes.Hysteria2,
                db_models.User.status.in_([UserStatus.active, UserStatus.on_hold]),
            )
            .all()
        )

        for proxy in proxies:
            settings = proxy.settings or {}
            if settings.get("password") == password:
                user = proxy.user
                user_id = f"{user.id}.{user.username}"
                logger.debug(f"Hysteria2 auth OK for {user_id}")
                return JSONResponse({"ok": True, "id": user_id})

    return JSONResponse({"ok": False})
