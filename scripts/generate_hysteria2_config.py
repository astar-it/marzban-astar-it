#!/usr/bin/env python3
"""Standalone script to generate Hysteria2 config. No app imports - safe for entrypoint."""
import json
import os

def main():
    port = int(os.environ.get("HYSTERIA2_PORT", "4443"))
    uvicorn_port = int(os.environ.get("UVICORN_PORT", "3000"))
    obfs = os.environ.get("HYSTERIA2_OBFS_PASSWORD", "")
    masq = os.environ.get("HYSTERIA2_MASQUERADE_URL", "https://www.bing.com")
    up_mbps = int(os.environ.get("HYSTERIA2_UP_MBPS", "100"))
    down_mbps = int(os.environ.get("HYSTERIA2_DOWN_MBPS", "100"))
    cert = "/var/lib/marzban/certs/fullchain.pem"
    key = "/var/lib/marzban/certs/privkey.pem"
    out_path = "/var/lib/marzban/hysteria2.json"

    config = {
        "listen": f":{port}",
        "tls": {"cert": cert, "key": key},
        "auth": {
            "type": "http",
            "http": {
                "url": f"http://127.0.0.1:{uvicorn_port}/hysteria2/auth",
                "insecure": True,
            },
        },
        "bandwidth": {"up": f"{up_mbps} mbps", "down": f"{down_mbps} mbps"},
        "masquerade": {
            "type": "proxy",
            "proxy": {"url": masq, "rewriteHost": True},
        },
    }
    if obfs:
        config["obfs"] = {"type": "salamander", "salamander": {"password": obfs}}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Hysteria2 config written to {out_path}")


if __name__ == "__main__":
    main()
