#!/usr/bin/env bash
# ==============================================================================
# install_worker.sh — 1-Click Provisioning for Raspberry Pi Worker Nodes
# Sets up KVM virtualization, base image directories, and auto-start daemon
# Usage: ./install_worker.sh [NODE_ID] [AGENT_PORT]
# Example: ./install_worker.sh worker-01 5001
# ==============================================================================
set -e

NODE_ID="${1:-worker-$(hostname)}"
AGENT_PORT="${2:-5001}"

echo "=== [INPT Cloud Platform] Worker Node Installer ==="
echo "Configuring Worker Identity: ${NODE_ID} (Port: ${AGENT_PORT})"

# 1. Update and install virtualization packages
echo "[1/5] Installing KVM, QEMU and virtualization tools..."
echo 'Acquire::ForceIPv4 "true";' | sudo tee /etc/apt/apt.conf.d/99force-ipv4 > /dev/null
sudo rm -rf /var/lib/apt/lists/*
sudo apt-get clean
sudo apt-get update -y
sudo apt-get install -y --fix-missing --no-install-recommends \
    qemu-system-arm \
    qemu-utils \
    cloud-image-utils \
    bridge-utils \
    avahi-daemon \
    python3-pip \
    python3-venv \
    curl \
    git

# 2. Check hardware acceleration (/dev/kvm)
echo "[2/5] Checking hardware virtualization support..."
if [ -c /dev/kvm ]; then
    echo "✅ Hardware KVM (/dev/kvm) detected on this Raspberry Pi!"
    sudo usermod -aG kvm "$USER" || true
else
    echo "⚠️ /dev/kvm not found. Ensure 64-bit kernel is running (arm_64bit=1 in /boot/config.txt)"
fi

# 3. Create persistent directories
echo "[3/5] Setting up persistent storage pools..."
sudo mkdir -p /var/lib/inpt-cloud/images
sudo mkdir -p /var/lib/inpt-cloud/vms
sudo mkdir -p /opt/inpt-cloud/worker-node

# Copy files to /opt/inpt-cloud/worker-node
sudo cp -r . /opt/inpt-cloud/worker-node/
sudo chmod +x /opt/inpt-cloud/worker-node/scripts/*.sh

# 4. Setup Python Virtual Environment
echo "[4/5] Setting up Worker Agent Python environment..."
cd /opt/inpt-cloud/worker-node
sudo python3 -m venv venv
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install fastapi uvicorn pydantic psutil

# 5. Install & Enable systemd service with dynamic Worker Identity
echo "[5/5] Configuring systemd service for ${NODE_ID}..."
SERVICE_NAME="inpt-worker-${NODE_ID}.service"
cat <<EOF | sudo tee /etc/systemd/system/${SERVICE_NAME} > /dev/null
[Unit]
Description=INPT Cloud Platform — Worker Hypervisor Agent (${NODE_ID})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/inpt-cloud/worker-node
Environment="MASTER_URL=https://master.aslouneyahya.com"
Environment="CLUSTER_TOKEN=inpt-cluster-secret-2026"
Environment="NODE_ID=${NODE_ID}"
Environment="AGENT_PORT=${AGENT_PORT}"
ExecStart=/opt/inpt-cloud/worker-node/venv/bin/python3 agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo "=========================================================="
echo "✅ Worker Node '${NODE_ID}' installed and started!"
echo "Service: ${SERVICE_NAME} on port ${AGENT_PORT}"
echo "Worker will automatically register to: https://master.aslouneyahya.com"
echo "Check status anytime with: sudo systemctl status ${SERVICE_NAME}"
echo "=========================================================="
