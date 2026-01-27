ARG PYTHON_VERSION=3.12
# Build version to invalidate cache when code changes
ARG BUILD_VERSION=20260127-v2

FROM python:$PYTHON_VERSION-slim AS build

ENV PYTHONUNBUFFERED=1
ENV BUILD_VERSION=$BUILD_VERSION

WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip gcc python3-dev libpq-dev \
    && curl -L https://github.com/Gozargah/Marzban-scripts/raw/master/install_latest_xray.sh | bash \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/
RUN python3 -m pip install --upgrade pip setuptools \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

FROM python:$PYTHON_VERSION-slim

ENV PYTHON_LIB_PATH=/usr/local/lib/python${PYTHON_VERSION%.*}/site-packages
WORKDIR /code

RUN rm -rf $PYTHON_LIB_PATH/*

COPY --from=build $PYTHON_LIB_PATH $PYTHON_LIB_PATH
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build /usr/local/share/xray /usr/local/share/xray

COPY --from=build /usr/local/bin/xray /usr/local/bin/xray

COPY . /code

# Generate Reality keys and update xray_config.json if placeholder exists
RUN if grep -q "YOUR_PRIVATE_KEY_HERE" /code/xray_config.json; then \
        KEYS=$(/usr/local/bin/xray x25519) && \
        PRIVATE_KEY=$(echo "$KEYS" | awk '/Private key:/ {print $3}') && \
        PUBLIC_KEY=$(echo "$KEYS" | awk '/Public key:/ {print $3}') && \
        sed -i "s/YOUR_PRIVATE_KEY_HERE/$PRIVATE_KEY/g" /code/xray_config.json && \
        sed -i "s/YOUR_PUBLIC_KEY_HERE/$PUBLIC_KEY/g" /code/xray_config.json && \
        echo "======================================" && \
        echo "Reality keys generated automatically!" && \
        echo "Private key: $PRIVATE_KEY" && \
        echo "Public key: $PUBLIC_KEY" && \
        echo "======================================" && \
        echo "$PUBLIC_KEY" > /code/reality_public_key.txt; \
    fi

# Create marzban-cli symlink (skip completion install as it requires full app initialization)
RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli

# Install openssl for certificate generation
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*

# Startup script that generates certs if needed and runs the app
COPY <<'EOF' /code/entrypoint.sh
#!/bin/bash
set -e

CERT_DIR="/var/lib/marzban/certs"
CERT_FILE="$CERT_DIR/fullchain.pem"
KEY_FILE="$CERT_DIR/key.pem"

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

# Show Reality public key if available
if [ -f "/code/reality_public_key.txt" ]; then
    echo "========================================"
    echo "Reality Public Key for clients:"
    cat /code/reality_public_key.txt
    echo "========================================"
fi

# Run migrations and start app
alembic upgrade head
exec python main.py
EOF

RUN chmod +x /code/entrypoint.sh

CMD ["/code/entrypoint.sh"]
