import json

from config import (
    HYSTERIA2_DOWN_MBPS,
    HYSTERIA2_MASQUERADE_URL,
    HYSTERIA2_OBFS_PASSWORD,
    HYSTERIA2_PORT,
    HYSTERIA2_UP_MBPS,
    UVICORN_PORT,
)


def generate_hysteria2_config(
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> dict:
    config = {
        "listen": f":{HYSTERIA2_PORT}",
        "tls": {
            "cert": cert_path,
            "key": key_path,
        },
        "auth": {
            "type": "http",
            "http": {
                "url": f"http://127.0.0.1:{UVICORN_PORT}/hysteria2/auth",
                "insecure": True,
            },
        },
        "bandwidth": {
            "up": f"{HYSTERIA2_UP_MBPS} mbps",
            "down": f"{HYSTERIA2_DOWN_MBPS} mbps",
        },
        "masquerade": {
            "type": "proxy",
            "proxy": {
                "url": HYSTERIA2_MASQUERADE_URL,
                "rewriteHost": True,
            },
        },
    }

    if HYSTERIA2_OBFS_PASSWORD:
        config["obfs"] = {
            "type": "salamander",
            "salamander": {
                "password": HYSTERIA2_OBFS_PASSWORD,
            },
        }

    return config


def write_hysteria2_config(
    path: str = "/var/lib/marzban/hysteria2.json",
    cert_path: str = "/var/lib/marzban/certs/fullchain.pem",
    key_path: str = "/var/lib/marzban/certs/privkey.pem",
) -> str:
    config = generate_hysteria2_config(cert_path, key_path)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path
