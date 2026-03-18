#!/usr/bin/env python3
"""Extract a domain's TLS certificate from Traefik's acme.json.

Coolify uses Traefik as reverse proxy and stores all Let's Encrypt
certificates in a single acme.json file. This script extracts
the cert+key for a specific domain into PEM files that Hysteria2,
TUIC, Juicity, and Xray can use directly.

Usage:
    python extract_traefik_cert.py <domain> <acme_json_path> <cert_out> <key_out>
"""
import base64
import json
import sys
import os


def extract(domain: str, acme_path: str, cert_out: str, key_out: str) -> bool:
    with open(acme_path, "r") as f:
        data = json.load(f)

    # Traefik acme.json has resolvers at the top level
    # Each resolver has "Certificates" list
    for resolver_name, resolver in data.items():
        if not isinstance(resolver, dict):
            continue
        certs = resolver.get("Certificates") or []
        for entry in certs:
            entry_domain = entry.get("domain", {})
            main = entry_domain.get("main", "")
            sans = entry_domain.get("sans") or []

            if domain == main or domain in sans or f"*.{domain.split('.', 1)[-1]}" in [main] + sans:
                cert_b64 = entry.get("certificate", "")
                key_b64 = entry.get("key", "")

                if not cert_b64 or not key_b64:
                    continue

                cert_pem = base64.b64decode(cert_b64).decode("utf-8")
                key_pem = base64.b64decode(key_b64).decode("utf-8")

                os.makedirs(os.path.dirname(cert_out), exist_ok=True)
                with open(cert_out, "w") as f:
                    f.write(cert_pem)
                with open(key_out, "w") as f:
                    f.write(key_pem)
                os.chmod(key_out, 0o600)

                print(f"Certificate for {domain} extracted from resolver '{resolver_name}'")
                return True

    print(f"No certificate found for {domain} in {acme_path}")
    return False


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <domain> <acme.json> <cert_out> <key_out>")
        sys.exit(1)
    ok = extract(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    sys.exit(0 if ok else 1)
