#!/usr/bin/env bash
# ==============================================================================
# install_worker.sh — 1-Click Provisioning for Raspberry Pi Worker Nodes
# Sets up KVM virtualization, base image directories, and auto-start daemon
# ==============================================================================
set -e

echo "=== [INPT Cloud Platform] Worker Node Installer ==="

# 1. Update and install virtualization packages
echo "[1/5] Installing KVM, QEMU and virtualization tools..."
sudo apt-get update -y
sudo apt-get install -y \
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

# 5. Install & Enable systemd service
echo "[5/5] Configuring inpt-worker systemd service..."
sudo cp /opt/inpt-cloud/worker-node/inpt-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable inpt-worker.service
sudo systemctl restart inpt-worker.service

echo "=========================================================="
echo "✅ Worker Node installed and started!"
echo "Worker will automatically register to: https://master.aslouneyahya.com"
echo "Check status anytime with: sudo systemctl status inpt-worker"
echo "=========================================================="
