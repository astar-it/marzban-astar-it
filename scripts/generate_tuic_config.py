#!/usr/bin/env python3
"""Generate TUIC config. Run from project root: python scripts/generate_tuic_config.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app.tuic.config import write_tuic_config

    out_path = os.environ.get("TUIC_CONFIG_PATH", "/var/lib/marzban/tuic.json")
    cert = os.environ.get("TLS_CERT_PATH", "/var/lib/marzban/certs/fullchain.pem")
    key = os.environ.get("TLS_KEY_PATH", "/var/lib/marzban/certs/privkey.pem")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_tuic_config(out_path, cert, key)
    print(f"TUIC config written to {out_path}")


if __name__ == "__main__":
    main()
