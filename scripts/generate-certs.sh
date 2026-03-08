#!/usr/bin/env bash
# MetivitaEval Certificate Generation Script
#
# Generates:
# 1. CA certificate (self-signed)
# 2. Server certificate (signed by CA)
# 3. Client certificate (signed by CA) - for mTLS
# 4. JWT signing keys (RSA)
#
# Usage:
#   ./scripts/generate-certs.sh [--production]
#
# Options:
#   --production    Generate production-ready certs (longer validity, stronger keys)

set -euo pipefail

# Configuration
CERTS_DIR="${CERTS_DIR:-certs}"
PRODUCTION="${1:-}"

# Certificate settings
if [[ "$PRODUCTION" == "--production" ]]; then
    CA_DAYS=3650          # 10 years
    CERT_DAYS=365         # 1 year
    KEY_SIZE=4096
    echo "Generating PRODUCTION certificates..."
else
    CA_DAYS=365           # 1 year
    CERT_DAYS=30          # 30 days
    KEY_SIZE=2048
    echo "Generating DEVELOPMENT certificates..."
fi

# Organization details
COUNTRY="US"
STATE="New York"
LOCALITY="New York"
ORG="Metivta"
ORG_UNIT="Engineering"
CA_CN="Metivta Root CA"
SERVER_CN="metivta-eval"
CLIENT_CN="metivta-client"

# Create certs directory
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# ============================================================================
# 1. GENERATE CA CERTIFICATE
# ============================================================================
echo ""
echo "=== Generating CA Certificate ==="

# CA private key
openssl genrsa -out ca.key $KEY_SIZE

# CA certificate
openssl req -x509 -new -nodes \
    -key ca.key \
    -sha256 \
    -days $CA_DAYS \
    -out ca.crt \
    -subj "/C=$COUNTRY/ST=$STATE/L=$LOCALITY/O=$ORG/OU=$ORG_UNIT/CN=$CA_CN"

echo "CA certificate generated: ca.crt"

# ============================================================================
# 2. GENERATE SERVER CERTIFICATE
# ============================================================================
echo ""
echo "=== Generating Server Certificate ==="

# Server private key
openssl genrsa -out server.key $KEY_SIZE

# Server CSR config
cat > server.cnf << EOF
[req]
default_bits = $KEY_SIZE
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORG
OU = $ORG_UNIT
CN = $SERVER_CN

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = gateway
DNS.3 = fastapi
DNS.4 = flask
DNS.5 = *.metivta.ai
DNS.6 = *.metivta.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Server CSR
openssl req -new -key server.key -out server.csr -config server.cnf

# Sign server certificate
openssl x509 -req \
    -in server.csr \
    -CA ca.crt \
    -CAkey ca.key \
    -CAcreateserial \
    -out server.crt \
    -days $CERT_DAYS \
    -sha256 \
    -extfile server.cnf \
    -extensions req_ext

echo "Server certificate generated: server.crt"

# ============================================================================
# 3. GENERATE CLIENT CERTIFICATE (for mTLS)
# ============================================================================
echo ""
echo "=== Generating Client Certificate ==="

# Client private key
openssl genrsa -out client.key $KEY_SIZE

# Client CSR config
cat > client.cnf << EOF
[req]
default_bits = $KEY_SIZE
prompt = no
default_md = sha256
distinguished_name = dn

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORG
OU = $ORG_UNIT
CN = $CLIENT_CN
EOF

# Client CSR
openssl req -new -key client.key -out client.csr -config client.cnf

# Sign client certificate
openssl x509 -req \
    -in client.csr \
    -CA ca.crt \
    -CAkey ca.key \
    -CAcreateserial \
    -out client.crt \
    -days $CERT_DAYS \
    -sha256

echo "Client certificate generated: client.crt"

# ============================================================================
# 4. GENERATE JWT SIGNING KEYS
# ============================================================================
echo ""
echo "=== Generating JWT Signing Keys ==="

# RSA private key for JWT signing
openssl genrsa -out jwt_private.pem $KEY_SIZE

# RSA public key for JWT verification
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem

echo "JWT keys generated: jwt_private.pem, jwt_public.pem"

# ============================================================================
# 5. CLEANUP & PERMISSIONS
# ============================================================================
echo ""
echo "=== Cleanup ==="

# Remove CSR and config files
rm -f *.csr *.cnf *.srl

# Set strict permissions on private keys
chmod 600 *.key *.pem 2>/dev/null || true
chmod 644 *.crt 2>/dev/null || true

# ============================================================================
# 6. VERIFICATION
# ============================================================================
echo ""
echo "=== Verification ==="

# Verify CA certificate
echo "CA Certificate:"
openssl x509 -in ca.crt -noout -subject -issuer -dates | head -4

# Verify server certificate
echo ""
echo "Server Certificate:"
openssl x509 -in server.crt -noout -subject -issuer -dates | head -4

# Verify certificate chain
echo ""
echo "Verifying certificate chain..."
openssl verify -CAfile ca.crt server.crt
openssl verify -CAfile ca.crt client.crt

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo "=========================================="
echo "Certificate generation complete!"
echo "=========================================="
echo ""
echo "Files created in $CERTS_DIR/:"
echo "  CA:     ca.crt, ca.key"
echo "  Server: server.crt, server.key"
echo "  Client: client.crt, client.key"
echo "  JWT:    jwt_private.pem, jwt_public.pem"
echo ""
echo "Usage in config.toml:"
echo '  [security.mtls]'
echo '  enabled = true'
echo "  ca_cert_path = \"$CERTS_DIR/ca.crt\""
echo "  server_cert_path = \"$CERTS_DIR/server.crt\""
echo "  server_key_path = \"$CERTS_DIR/server.key\""
echo ""
echo '  [security.jwt]'
echo "  public_key_path = \"$CERTS_DIR/jwt_public.pem\""
echo "  private_key_path = \"$CERTS_DIR/jwt_private.pem\""
echo ""
if [[ "$PRODUCTION" != "--production" ]]; then
    echo "WARNING: These are DEVELOPMENT certificates."
    echo "For production, run: $0 --production"
fi
