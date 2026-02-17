ARG PYTHON_VERSION=3.12
# Build version to invalidate cache when code changes
ARG BUILD_VERSION=20260126-v14

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
        XRAY_VERSION=$(curl -s https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/'); \
    fi \
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

COPY ./requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Save the actual site-packages path for the next stage
RUN python -c "import site; print(site.getsitepackages()[0])" > /tmp/site_packages_path

FROM python:$PYTHON_VERSION-slim

WORKDIR /code

# Install runtime dependencies (libpq for PostgreSQL, openssl for certs)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 openssl \
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

# Create certs directory if not exists
mkdir -p "$CERT_DIR"

# Generate self-signed certificate if not exists
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "========================================"
    echo "Generating self-signed TLS certificate..."
    echo "========================================"
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=marzban" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
    echo "Certificate generated. Replace with real cert for production!"
fi

# Reality key management: reuse saved keys or generate new ones
SAVED_PRIVATE_KEY_FILE="$CERT_DIR/reality_private_key.txt"
SAVED_PUBLIC_KEY_FILE="$CERT_DIR/reality_public_key.txt"

if grep -q "YOUR_PRIVATE_KEY_HERE" "$XRAY_CONFIG"; then
    # Check if we have previously saved keys
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

# Remove publicKey from server config (only needed on client side)
sed -i '/"publicKey"/d' "$XRAY_CONFIG" 2>/dev/null || true

# Show Reality public key if available
if [ -f "$SAVED_PUBLIC_KEY_FILE" ]; then
    echo "========================================"
    echo "Reality Public Key for clients:"
    cat "$SAVED_PUBLIC_KEY_FILE"
    echo "========================================"
fi

# Ensure setuptools with pkg_resources is available (needed by apscheduler)
pip install --no-cache-dir 'setuptools==70.3.0' 2>/dev/null || true

# Run migrations and start app
alembic upgrade head
exec python main.py
EOF

RUN chmod +x /code/entrypoint.sh

CMD ["/code/entrypoint.sh"]
