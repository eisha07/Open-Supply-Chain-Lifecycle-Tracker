#!/usr/bin/env bash
# Generate self-signed TLS certificate for local development.
# In production, replace with Let's Encrypt or your CA-signed certs.
set -euo pipefail

CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
    echo "Certificates already exist at $CERT_DIR — skipping generation."
    exit 0
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/C=US/ST=Berlin/L=Berlin/O=OSLT-Dev/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"
echo "Self-signed certificate generated at $CERT_DIR"
echo "  - server.crt (certificate)"
echo "  - server.key (private key)"
