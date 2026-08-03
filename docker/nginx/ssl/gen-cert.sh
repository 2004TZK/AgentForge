#!/bin/sh
# ============================================================
# AgentForge HTTPS 自签证书生成（ssl-init 一次性容器，幂等）
#   证书不存在时自动生成（SAN 覆盖 localhost/127.0.0.1/内网名），
#   已存在则跳过 —— 不破坏「docker compose up -d」一键体验。
# 生产建议：替换为正规 CA 证书（Let's Encrypt 等），目录挂载不变。
# ============================================================
set -e

CERT_DIR=${CERT_DIR:-/certs}
CERT=${CERT_DIR}/agentforge.crt
KEY=${CERT_DIR}/agentforge.key

if [ -f "${CERT}" ] && [ -f "${KEY}" ]; then
  echo "SSL certificate already exists, skip"
  exit 0
fi

echo "Generating self-signed certificate (CN=AgentForge, SAN localhost/127.0.0.1)..."
mkdir -p "${CERT_DIR}"
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout "${KEY}" -out "${CERT}" \
  -subj "/CN=AgentForge" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:0.0.0.0"
echo "Certificate generated: ${CERT}"
