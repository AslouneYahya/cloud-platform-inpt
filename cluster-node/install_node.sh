#!/usr/bin/env bash
# ==============================================================================
# install_node.sh — Universal Peer Node Installer (INPT Cloud Platform)
# Every Raspberry Pi in the cluster runs this exact script.
# No Master/Worker distinction: creates a homogeneous, decentralized Peer.
# ==============================================================================
set -eo pipefail

NODE_ID="${1:-$(hostname)}"
AGENT_PORT="${2:-5000}"

echo "=== [INPT Cloud Platform] Universal Peer Node Installer ==="
echo "Node Identity: ${NODE_ID} (Port: ${AGENT_PORT})"

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install_node.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$(whoami)}"

# 1. Debian repository fixes for ARM64 Bullseye
echo "[1/5] Configuring system package mirrors and tools..."
echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4
sed -i 's|^deb http://security.debian.org|#deb http://security.debian.org|g' /etc/apt/sources.list 2>/dev/null || true
rm -rf /var/lib/apt/lists/*
apt-get update -o Acquire::CompressionTypes::Order::=gz || apt-get update

apt-get install -y --no-install-recommends \
    qemu-system-arm \
    qemu-utils \
    bridge-utils \
    cloud-image-utils \
    python3-venv \
    python3-pip \
    curl \
    git \
    socat

# 2. Storage Setup
echo "[2/5] Creating cluster storage directories..."
mkdir -p /var/lib/inpt-cloud/images
mkdir -p /var/lib/inpt-cloud/vms
chmod -R 775 /var/lib/inpt-cloud
chown -R "${REAL_USER}:${REAL_USER}" /var/lib/inpt-cloud 2>/dev/null || true

# 3. Python Virtual Environment
echo "[3/5] Setting up Python virtual environment..."
cd "${SCRIPT_DIR}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn pydantic

# 4. Permissions for KVM execution scripts
echo "[4/5] Setting executable permissions on scripts..."
chmod +x scripts/*.sh

# 5. Environment & Systemd Service
echo "[5/5] Installing and starting inpt-node.service..."
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

# Stop old master/worker services if present
systemctl stop inpt-master-node.service 2>/dev/null || true
systemctl stop inpt-worker.service 2>/dev/null || true
systemctl disable inpt-master-node.service 2>/dev/null || true
systemctl disable inpt-worker.service 2>/dev/null || true

systemctl daemon-reload
systemctl enable inpt-node.service
systemctl restart inpt-node.service

echo "=========================================================="
echo "✅ Universal Peer Node '${NODE_ID}' successfully installed!"
echo "Status: Active on port ${AGENT_PORT}"
echo "API & Dashboard: http://localhost:${AGENT_PORT}/dashboard"
echo "=========================================================="
