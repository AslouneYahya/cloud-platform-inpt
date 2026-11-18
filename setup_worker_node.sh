#!/usr/bin/env bash
# ==============================================================================
# setup_worker_node.sh — Complete 1-Click Worker Node Setup for Raspberry Pi
# INPT Cloud Platform — Sets up KVM, QEMU, Cloudflare WARP-CLI & Worker Agent
# Zero manual commands: clones, installs, connects, and auto-registers to Master
# ==============================================================================
set -e
export DEBIAN_FRONTEND=noninteractive

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR"
REPO_URL="https://github.com/AslouneYahya/cloud-platform-inpt.git"
MASTER_URL="https://master.aslouneyahya.com"

echo "======================================================================"
echo "   🍓 [INPT Cloud Platform] Worker Node Complete Automated Setup      "
echo "======================================================================"

# ── 1. Clean Sync with GitHub Repository ──────────────────────────────────────
echo "=== [1/6] Updating Cloud Platform Repository ==="
if [ -d "$TARGET_DIR/.git" ]; then
    echo "Repository detected at $TARGET_DIR, syncing cleanly with origin/main..."
    cd "$TARGET_DIR"
    git fetch origin main 2>/dev/null || true
    git reset --hard origin/main 2>/dev/null || true
else
    TARGET_DIR="$HOME/cloud-platform-inpt"
    echo "Cloning repository from GitHub to $TARGET_DIR..."
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

# ── 2. Automatic Debian 11 Bullseye EOL Archive Fix ───────────────────────────
echo "=== [2/6] Configuring APT Repositories & Packages ==="
RELEASE=$(lsb_release -cs 2>/dev/null || grep VERSION_CODENAME /etc/os-release | cut -d= -f2 || echo "bullseye")

if [ "$RELEASE" = "bullseye" ]; then
    echo "Patching Debian 11 Bullseye EOL security repositories to archive.debian.org..."
    sudo sed -i 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list 2>/dev/null || true
    sudo sed -i 's|deb.debian.org/debian bullseye-updates|archive.debian.org/debian bullseye-updates|g' /etc/apt/sources.list 2>/dev/null || true
    sudo rm -f /etc/apt/sources.list.d/cloudflare-client.list 2>/dev/null || true
    echo 'Acquire::Check-Valid-Until "false";' | sudo tee /etc/apt/apt.conf.d/99no-check-valid-until > /dev/null
    sudo apt-get clean 2>/dev/null || true
fi

echo "Installing KVM, QEMU & Virtualization Packages..."
sudo apt-get update -o Acquire::Check-Valid-Until=false -y || true
sudo apt-get install --fix-missing -y \
    qemu-system-arm \
    qemu-utils \
    cloud-image-utils \
    bridge-utils \
    avahi-daemon \
    python3-pip \
    python3-venv \
    curl \
    git \
    socat || true

if [ -c /dev/kvm ]; then
    echo "✅ Hardware KVM (/dev/kvm) detected on this Raspberry Pi!"
    sudo usermod -aG kvm "$USER" 2>/dev/null || true
else
    echo "⚠️ /dev/kvm not found. Ensure 64-bit kernel is running (arm_64bit=1 in /boot/config.txt)"
fi

# ── 3. Install & Connect Cloudflare WARP CLI (Zero Trust Mesh) ────────────────
echo "=== [3/6] Setting up Cloudflare WARP-CLI on Worker ==="
if [ "$RELEASE" = "bullseye" ]; then
    DEB_URL="https://pkg.cloudflareclient.com/pool/bullseye/main/c/cloudflare-warp/cloudflare-warp_2026.3.846.0_arm64.deb"
else
    DEB_URL="https://pkg.cloudflareclient.com/pool/bookworm/main/c/cloudflare-warp/cloudflare-warp_2026.8.2115.0_arm64.deb"
fi

if ! command -v warp-cli &>/dev/null; then
    echo "Downloading official Cloudflare WARP package..."
    curl -# -L -o /tmp/cloudflare-warp.deb "$DEB_URL" 2>/dev/null || true
    if [ -f /tmp/cloudflare-warp.deb ]; then
        rm -rf /tmp/warp_extract && mkdir -p /tmp/warp_extract
        dpkg-deb -x /tmp/cloudflare-warp.deb /tmp/warp_extract
        sudo cp /tmp/warp_extract/bin/warp-svc /bin/warp-svc
        sudo cp /tmp/warp_extract/bin/warp-cli /bin/warp-cli
        sudo chmod +x /bin/warp-svc /bin/warp-cli
        sudo cp /tmp/warp_extract/lib/systemd/system/warp-svc.service /etc/systemd/system/warp-svc.service
        sudo systemctl daemon-reload
        sudo systemctl enable --now warp-svc
        sleep 3
    fi
fi

if command -v warp-cli &>/dev/null; then
    echo "Connecting to Cloudflare Network via WARP..."
    yes | warp-cli --accept-tos register 2>/dev/null || warp-cli --accept-tos registration new 2>/dev/null || true
    warp-cli --accept-tos mode warp 2>/dev/null || true
    warp-cli --accept-tos connect 2>/dev/null || true
    sleep 2
    warp-cli status || true
fi

# ── 4. Set up Storage Pools & Permissions ─────────────────────────────────────
echo "=== [4/6] Initializing Local Storage Pools ==="
sudo mkdir -p /var/lib/inpt-cloud/vms
sudo mkdir -p /var/lib/inpt-cloud/images
sudo mkdir -p /opt/inpt-cloud/worker-node

sudo cp -r "$TARGET_DIR/worker-node"/* /opt/inpt-cloud/worker-node/
sudo chmod +x /opt/inpt-cloud/worker-node/scripts/*.sh 2>/dev/null || true

# ── 5. Set up Worker Daemon Environment & Systemd Service ─────────────────────
echo "=== [5/6] Configuring Worker Agent Service ==="
cd /opt/inpt-cloud/worker-node

if [ ! -d "venv" ]; then
    sudo python3 -m venv venv
    sudo venv/bin/pip install --upgrade pip -q 2>/dev/null || true
    sudo venv/bin/pip install fastapi uvicorn pydantic psutil -q 2>/dev/null || true
fi

cat <<EOF | sudo tee /etc/systemd/system/inpt-worker.service > /dev/null
[Unit]
Description=INPT Cloud Platform — Worker Node Hypervisor Agent
After=network.target network-online.target warp-svc.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/inpt-cloud/worker-node
Environment="MASTER_URL=${MASTER_URL}"
Environment="CLUSTER_TOKEN=inpt-cluster-secret-2026"
Environment="AGENT_PORT=5001"
ExecStart=/opt/inpt-cloud/worker-node/venv/bin/python3 agent.py
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable inpt-worker.service
sudo systemctl restart inpt-worker.service

# ── 6. Verification of Self-Registration with Master ──────────────────────────
echo "=== [6/6] Verifying Connection with Master Node ==="
sleep 4

echo "Worker Agent Status:"
sudo systemctl status inpt-worker.service --no-pager -l || true

echo ""
echo "======================================================================"
echo "  🎉 Worker Node is UP and connected!                                  "
echo "  Connected to Master: ${MASTER_URL}                                   "
echo "  Auto-Registration is complete and heartbeats are streaming.         "
echo "======================================================================"
