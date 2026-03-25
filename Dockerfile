ARG PYTHON_VERSION=3.12
# Build version to invalidate cache when code changes
ARG BUILD_VERSION=20260126-v17

FROM python:$PYTHON_VERSION-slim AS build

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip gcc python3-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Xray from official XTLS repository
ARG XRAY_VERSION=latest
RUN set -ex \
    && if [ "$XRAY_VERSION" = "latest" ]; then \
        XRAY_VERSION=$(curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep -m1 '"tag_name"' | cut -d'"' -f4); \
    fi \
    && echo "Xray version: ${XRAY_VERSION}" \
    && test -n "$XRAY_VERSION" && echo "$XRAY_VERSION" | grep -qE '^v[0-9]' || { echo "ERROR: Failed to detect Xray version (got: $XRAY_VERSION)"; exit 1; } \
    && ARCH=$(uname -m) \
    && case "$ARCH" in \
        x86_64) XRAY_ARCH="64" ;; \
        aarch64) XRAY_ARCH="arm64-v8a" ;; \
        armv7l) XRAY_ARCH="arm32-v7a" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac \
    && curl -L -o /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-${XRAY_ARCH}.zip" \
    && unzip /tmp/xray.zip -d /tmp/xray \
    && mv /tmp/xray/xray /usr/local/bin/xray \
    && chmod +x /usr/local/bin/xray \
    && mkdir -p /usr/local/share/xray \
    && mv /tmp/xray/*.dat /usr/local/share/xray/ \
    && rm -rf /tmp/xray /tmp/xray.zip \
    && echo "Xray ${XRAY_VERSION} installed"

# Install Hysteria2
ARG HYSTERIA_VERSION=latest
RUN set -ex \
    && if [ "$HYSTERIA_VERSION" = "latest" ]; then \
        HYSTERIA_VERSION=$(curl -sL https://api.github.com/repos/apernet/hysteria/releases/latest | grep -m1 '"tag_name"' | cut -d'"' -f4); \
    fi \
    && ARCH=$(uname -m) \
    && case "$ARCH" in \
        x86_64) HY_ARCH="amd64" ;; \
        aarch64) HY_ARCH="arm64" ;; \
        armv7l) HY_ARCH="armv7" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac \
    && curl -L -o /usr/local/bin/hysteria "https://github.com/apernet/hysteria/releases/download/${HYSTERIA_VERSION}/hysteria-linux-${HY_ARCH}" \
    && chmod +x /usr/local/bin/hysteria \
    && echo "Hysteria2 ${HYSTERIA_VERSION} installed"

# Install TUIC server
ARG TUIC_VERSION=latest
RUN set -ex \
    && if [ "$TUIC_VERSION" = "latest" ]; then \
        TUIC_VERSION=$(curl -sL https://api.github.com/repos/Itsusinn/tuic/releases/latest | grep -m1 '"tag_name"' | cut -d'"' -f4); \
    fi \
    && ARCH=$(uname -m) \
    && case "$ARCH" in \
        x86_64) TUIC_ARCH="x86_64" ;; \
        aarch64) TUIC_ARCH="aarch64" ;; \
        armv7l) TUIC_ARCH="armv7" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac \
    && curl -L -o /usr/local/bin/tuic-server "https://github.com/Itsusinn/tuic/releases/download/${TUIC_VERSION}/tuic-server-${TUIC_ARCH}-linux" \
    && chmod +x /usr/local/bin/tuic-server \
    && echo "TUIC ${TUIC_VERSION} installed"

# Install Juicity server
ARG JUICITY_VERSION=latest
RUN set -ex \
    && if [ "$JUICITY_VERSION" = "latest" ]; then \
        JUICITY_VERSION=$(curl -sL https://api.github.com/repos/juicity/juicity/releases/latest | grep -m1 '"tag_name"' | cut -d'"' -f4); \
    fi \
    && ARCH=$(uname -m) \
    && case "$ARCH" in \
        x86_64) JUICITY_ARCH="x86_64" ;; \
        aarch64) JUICITY_ARCH="arm64" ;; \
        armv7l) JUICITY_ARCH="armv7" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac \
    && curl -L -o /tmp/juicity.zip "https://github.com/juicity/juicity/releases/download/${JUICITY_VERSION}/juicity-linux-${JUICITY_ARCH}.zip" \
    && unzip -j /tmp/juicity.zip juicity-server -d /usr/local/bin \
    && chmod +x /usr/local/bin/juicity-server \
    && rm /tmp/juicity.zip \
    && echo "Juicity ${JUICITY_VERSION} installed"

COPY ./requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Save the actual site-packages path for the next stage
RUN python -c "import site; print(site.getsitepackages()[0])" > /tmp/site_packages_path

FROM python:$PYTHON_VERSION-slim

WORKDIR /code

# Install runtime dependencies (libpq for PostgreSQL, openssl for certs, certbot for Let's Encrypt)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 openssl certbot cron \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages using the correct path
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /usr/local/share/xray /usr/local/share/xray
COPY --from=build /usr/local/bin/xray /usr/local/bin/xray

# Force cache invalidation for code changes
ARG BUILD_VERSION
RUN echo "Build: ${BUILD_VERSION}"

COPY . /code

# Expose ports: Uvicorn(8000), Xray(various), Hysteria2(4443/udp), TUIC(18443/udp), Juicity(23182/udp)
EXPOSE 8000 62050 62051 4443/udp 4443/tcp 18443/udp 18443/tcp 23182/udp 23182/tcp

# Create marzban-cli symlink
RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli

# Startup script that generates certs and Reality keys if needed
COPY <<'EOF' /code/entrypoint.sh
#!/bin/bash
set -e

CERT_DIR="/var/lib/marzban/certs"
CERT_FILE="$CERT_DIR/fullchain.pem"
KEY_FILE="$CERT_DIR/privkey.pem"
XRAY_CONFIG="/code/xray_config.json"

mkdir -p "$CERT_DIR"

# ──────────────────────────────────────────────────
# TLS Certificate management
# Priority: Coolify/Traefik acme.json > certbot > existing valid cert > self-signed
# ──────────────────────────────────────────────────
ACME_JSON="${TRAEFIK_ACME_JSON:-/etc/traefik/acme.json}"

cert_is_valid() {
    [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ] && \
    openssl x509 -in "$CERT_FILE" -noout -checkend 86400 2>/dev/null
}

try_acme_extract() {
    local domain="$1"
    if [ -z "$domain" ] || [ ! -f "$ACME_JSON" ]; then
        return 1
    fi
    echo "========================================"
    echo "Extracting certificate for $domain from Coolify/Traefik..."
    echo "========================================"
    python /code/scripts/extract_traefik_cert.py \
        "$domain" "$ACME_JSON" "$CERT_FILE" "$KEY_FILE" 2>&1
    return $?
}

try_certbot() {
    local domain="$1"
    local email="$2"
    local le_live="/etc/letsencrypt/live/$domain"
    [ -z "$domain" ] && return 1
    command -v certbot >/dev/null 2>&1 || return 1

    local email_arg="--register-unsafely-without-email"
    [ -n "$email" ] && email_arg="--email $email"

    echo "========================================"
    echo "Obtaining Let's Encrypt certificate for $domain ..."
    echo "========================================"
    certbot certonly --standalone --preferred-challenges http \
        --http-01-port "${SSL_HTTP_PORT:-80}" \
        --non-interactive --agree-tos $email_arg \
        -d "$domain" --cert-name "$domain" --keep-until-expiring \
        2>&1 && LE_OK=1 || LE_OK=0

    if [ "$LE_OK" = "1" ] && [ -f "$le_live/fullchain.pem" ]; then
        cp "$le_live/fullchain.pem" "$CERT_FILE"
        cp "$le_live/privkey.pem" "$KEY_FILE"
        echo "Let's Encrypt certificate installed!"
        echo "0 3 * * * certbot renew --quiet --http-01-port ${SSL_HTTP_PORT:-80} --deploy-hook \"cp '$le_live/fullchain.pem' '$CERT_FILE' && cp '$le_live/privkey.pem' '$KEY_FILE'\"" \
            > /etc/cron.d/certbot-renew
        chmod 0644 /etc/cron.d/certbot-renew
        cron
        return 0
    fi
    echo "WARNING: certbot failed."
    return 1
}

generate_self_signed() {
    echo "========================================"
    echo "Generating self-signed TLS certificate..."
    echo "========================================"
    local san="DNS:localhost,IP:127.0.0.1"
    [ -n "$SSL_CERT_DOMAIN" ] && san="DNS:$SSL_CERT_DOMAIN,$san"
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
        -sha256 -days 3650 -nodes \
        -keyout "$KEY_FILE" -out "$CERT_FILE" \
        -subj "/CN=${SSL_CERT_DOMAIN:-marzban}" \
        -addext "subjectAltName=$san"
    echo "Self-signed cert generated. Set SSL_CERT_DOMAIN + mount acme.json for real cert."
}

# Decide cert strategy
GOT_CERT=0
if [ -n "$SSL_CERT_DOMAIN" ]; then
    # 1) Try Coolify/Traefik acme.json (best for Coolify deployments)
    try_acme_extract "$SSL_CERT_DOMAIN" && GOT_CERT=1

    # 2) Fallback to certbot standalone
    if [ "$GOT_CERT" = "0" ]; then
        try_certbot "$SSL_CERT_DOMAIN" "${SSL_CERT_EMAIL:-}" && GOT_CERT=1
    fi

    # 3) Fallback to self-signed
    if [ "$GOT_CERT" = "0" ] && ! cert_is_valid; then
        generate_self_signed
    fi
else
    if ! cert_is_valid; then
        generate_self_signed
    else
        echo "Existing valid certificate found."
    fi
fi

# ──────────────────────────────────────────────────
# Reality key management
# ──────────────────────────────────────────────────
SAVED_PRIVATE_KEY_FILE="$CERT_DIR/reality_private_key.txt"
SAVED_PUBLIC_KEY_FILE="$CERT_DIR/reality_public_key.txt"

if grep -q "YOUR_PRIVATE_KEY_HERE" "$XRAY_CONFIG"; then
    if [ -f "$SAVED_PRIVATE_KEY_FILE" ] && [ -f "$SAVED_PUBLIC_KEY_FILE" ]; then
        echo "========================================"
        echo "Restoring saved Reality keys..."
        PRIVATE_KEY=$(cat "$SAVED_PRIVATE_KEY_FILE")
        PUBLIC_KEY=$(cat "$SAVED_PUBLIC_KEY_FILE")
        sed -i "s/YOUR_PRIVATE_KEY_HERE/$PRIVATE_KEY/g" "$XRAY_CONFIG"
        echo "Reality keys restored from previous run!"
        echo "Public key (for clients): $PUBLIC_KEY"
        echo "========================================"
    else
        echo "========================================"
        echo "Generating new Reality keys..."
        echo "========================================"
        KEYS=$(xray x25519 2>&1) || true
        PRIVATE_KEY=$(echo "$KEYS" | grep -i "private" | awk -F': ' '{print $2}' | tr -d '[:space:]')
        PUBLIC_KEY=$(echo "$KEYS" | sed -n '2p' | awk -F': ' '{print $2}' | tr -d '[:space:]')

        if [ -n "$PRIVATE_KEY" ] && [ -n "$PUBLIC_KEY" ]; then
            sed -i "s/YOUR_PRIVATE_KEY_HERE/$PRIVATE_KEY/g" "$XRAY_CONFIG"
            echo "$PRIVATE_KEY" > "$SAVED_PRIVATE_KEY_FILE"
            echo "$PUBLIC_KEY" > "$SAVED_PUBLIC_KEY_FILE"
            echo "Reality keys generated and saved!"
            echo "Private key: $PRIVATE_KEY"
            echo "Public key (for clients): $PUBLIC_KEY"
            echo ""
            echo "=========================================="
            echo "SAVE THIS PUBLIC KEY for client configuration!"
            echo "=========================================="
        else
            echo "ERROR: Failed to generate Reality keys!"
        fi
        echo "========================================"
    fi
fi

sed -i '/"publicKey"/d' "$XRAY_CONFIG" 2>/dev/null || true

if [ -f "$SAVED_PUBLIC_KEY_FILE" ]; then
    echo "========================================"
    echo "Reality Public Key for clients:"
    cat "$SAVED_PUBLIC_KEY_FILE"
    echo "========================================"
fi

# ──────────────────────────────────────────────────
# Finalize and start
# ──────────────────────────────────────────────────
pip install --no-cache-dir 'setuptools==70.3.0' 2>/dev/null || true

if [ "${HYSTERIA2_ENABLED:-true}" = "true" ] && command -v hysteria >/dev/null 2>&1; then
    echo "Generating Hysteria2 config..."
    python /code/scripts/generate_hysteria2_config.py 2>&1 || echo "WARNING: Failed to generate Hysteria2 config"
fi

alembic upgrade head
exec python main.py
EOF

RUN chmod +x /code/entrypoint.sh

CMD ["/code/entrypoint.sh"]
