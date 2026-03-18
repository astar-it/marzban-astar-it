import json

from app.db import GetDB
from app.db import models as db_models
from app.models.proxy import ProxyTypes
from app.models.user import UserStatus
from config import JUICITY_CONGESTION_CONTROL, JUICITY_PORT


def get_juicity_users():
    """Get all active Juicity users (uuid, password) from DB."""
    users = {}
    try:
        with GetDB() as db:
            rows = (
                db.query(db_models.Proxy)
                .join(db_models.User)
                .filter(
                    db_models.Proxy.type == ProxyTypes.Juicity,
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


def generate_juicity_config(
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> dict:
    users = get_juicity_users()
    config = {
        "listen": f":{JUICITY_PORT}",
        "users": users,
        "certificate": cert_path,
        "private_key": key_path,
        "congestion_control": JUICITY_CONGESTION_CONTROL,
        "log_level": "info",
        "disable_outbound_udp443": True,
    }
    return config


def write_juicity_config(
    path: str = "/var/lib/marzban/juicity.json",
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> str:
    config = generate_juicity_config(cert_path, key_path)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path
