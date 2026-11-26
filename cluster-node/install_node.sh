#!/usr/bin/env bash
# ==============================================================================
# install_node.sh — Universal Peer Node & Cloudflare Tunnel Installer
# INPT Cloud Platform — Homogeneous, Decentralized Cluster
# Every Raspberry Pi runs this exact script: sets up KVM, API daemon, and Cloudflare Tunnel.
# ==============================================================================
set -eo pipefail

NODE_ID="${1:-$(hostname)}"
AGENT_PORT="${2:-5000}"
CLOUDFLARE_TOKEN="${3:-eyJhIjoiODcwZWRiNzc5M2IyYTc2OGMyZmE2ZGRjYTBlOGYzYmEiLCJ0IjoiNGU2Mzc4NzQtMTRlYi00ZjViLThkMjItNDUyNzMyMTRiZDYyIiwicyI6Ik9EUTBNVGcyTldZdFpXRmlNUzAwTURSbExXRmhOemd0T0RVd01ESXdOalJoTVRaaiJ9}"

echo "=========================================================="
echo "=== [INPT Cloud Platform] Universal Peer Node Installer ==="
echo "Node Identity: ${NODE_ID} (Port: ${AGENT_PORT})"
echo "=========================================================="

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install_node.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$(whoami)}"

# 1. Debian repository fixes for ARM64 Bullseye
echo "[1/6] Configuring package mirrors and tools..."
echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4
sed -i 's|^deb http://security.debian.org|#deb http://security.debian.org|g' /etc/apt/sources.list 2>/dev/null || true
rm -rf /var/lib/apt/lists/*
apt-get update -o Acquire::CompressionTypes::Order::=gz || apt-get update || true

apt-get install -y --no-install-recommends \
    qemu-system-arm \
    qemu-utils \
    bridge-utils \
    cloud-image-utils \
    python3-venv \
    python3-pip \
    curl \
    git \
    socat || true

# 2. Storage Setup
echo "[2/6] Setting up cluster storage directories..."
mkdir -p /var/lib/inpt-cloud/images
mkdir -p /var/lib/inpt-cloud/vms
chmod -R 775 /var/lib/inpt-cloud
chown -R "${REAL_USER}:${REAL_USER}" /var/lib/inpt-cloud 2>/dev/null || true

# 3. Python Virtual Environment
echo "[3/6] Setting up Python virtual environment..."
cd "${SCRIPT_DIR}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip || true
pip install fastapi uvicorn pydantic

# 4. Script permissions
echo "[4/6] Setting executable permissions on scripts..."
chmod +x scripts/*.sh

# 5. Cloudflare Tunnel Replica Setup (Multi-Master High Availability)
echo "[5/6] Setting up Cloudflare Tunnel replica..."
if [ ! -f /usr/local/bin/cloudflared ] && [ ! -f /usr/bin/cloudflared ]; then
    echo "Downloading cloudflared binary (ARM64)..."
    curl -fsSL -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 || true
    chmod +x /usr/local/bin/cloudflared 2>/dev/null || true
fi

CLOUDFLARED_BIN="/usr/local/bin/cloudflared"
if [ ! -f "$CLOUDFLARED_BIN" ]; then
    CLOUDFLARED_BIN="/usr/bin/cloudflared"
fi

if [ -f "$CLOUDFLARED_BIN" ]; then
    cat <<EOF > /etc/systemd/system/cloudflared.service
[Unit]
Description=Cloudflare Tunnel (INPT Cloud Replica)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
TimeoutStartSec=10s
Restart=always
RestartSec=5s
ExecStart=${CLOUDFLARED_BIN} tunnel --no-autoupdate run --token ${CLOUDFLARE_TOKEN}

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable cloudflared.service
    systemctl restart cloudflared.service
    echo "✅ Cloudflare Tunnel replica active!"
fi

# 6. INPT Node Systemd Service
echo "[6/6] Installing and starting inpt-node.service..."
cat <<EOF > /etc/default/inpt-node
NODE_ID=${NODE_ID}
PORT=${AGENT_PORT}
CLUSTER_TOKEN=inpt-cluster-secret-2026
PYTHONUNBUFFERED=1
EOF

cat <<EOF > /etc/systemd/system/inpt-node.service
[Unit]
Description=INPT Cloud Platform — Universal Peer Node Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${AGENT_PORT}
Restart=always
RestartSec=3
EnvironmentFile=/etc/default/inpt-node

[Install]
WantedBy=multi-user.target
EOF

# Stop old master/worker services
systemctl stop inpt-master-node.service 2>/dev/null || true
systemctl stop inpt-worker.service 2>/dev/null || true
systemctl disable inpt-master-node.service 2>/dev/null || true
systemctl disable inpt-worker.service 2>/dev/null || true

systemctl daemon-reload
systemctl enable inpt-node.service
systemctl restart inpt-node.service

echo "=========================================================="
echo "✅ Universal Peer Node '${NODE_ID}' fully configured!"
echo "API & Dashboard: http://localhost:${AGENT_PORT}/dashboard"
echo "Public Domain:   https://master.aslouneyahya.com"
echo "=========================================================="
