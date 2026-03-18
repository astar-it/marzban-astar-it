import json

from app.db import GetDB
from app.db import models as db_models
from app.models.proxy import ProxyTypes
from app.models.user import UserStatus
from config import TUIC_CONGESTION_CONTROL, TUIC_PORT


def get_tuic_users():
    """Get all active TUIC users (uuid, password) from DB."""
    users = {}
    try:
        with GetDB() as db:
            rows = (
                db.query(db_models.Proxy)
                .join(db_models.User)
                .filter(
                    db_models.Proxy.type == ProxyTypes.TUIC,
                    db_models.User.status.in_([UserStatus.active, UserStatus.on_hold]),
                )
                .all()
            )
    except Exception:
        return users
    for proxy in rows:
        settings = proxy.settings or {}
        if not isinstance(settings, dict):
            continue
        uuid_val = settings.get("uuid")
        password = settings.get("password")
        if uuid_val and password:
            users[str(uuid_val)] = str(password)
    return users


def generate_tuic_config(
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> dict:
    users = get_tuic_users()
    config = {
        "server": f"[::]:{TUIC_PORT}",
        "users": users,
        "certificate": cert_path,
        "private_key": key_path,
        "congestion_control": TUIC_CONGESTION_CONTROL,
        "log_level": "warn",
        "auth_timeout": "3s",
        "zero_rtt_handshake": False,
    }
    return config


def write_tuic_config(
    path: str = "/var/lib/marzban/tuic.json",
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> str:
    config = generate_tuic_config(cert_path, key_path)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path
