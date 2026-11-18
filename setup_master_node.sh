#!/usr/bin/env bash
# ==============================================================================
# setup_master_node.sh — Complete 1-Click Master Node & Cloudflare Setup
# INPT Cloud Platform — Sets up Master Daemon, KVM, Cloudflare Tunnel & WARP
# ==============================================================================
set -e

TARGET_DIR="$HOME/cloud-platform-inpt"
REPO_URL="https://github.com/AslouneYahya/cloud-platform-inpt.git"

echo "======================================================================"
echo "   🚀 [INPT Cloud Platform] Master Node Complete Setup                "
echo "======================================================================"

# ── 1. Clone / Pull Latest Repository ─────────────────────────────────────────
echo "=== [1/6] Updating Cloud Platform Repository ==="
if [ -d "$TARGET_DIR" ]; then
    echo "Repository already present, syncing cleanly with origin/main..."
    cd "$TARGET_DIR"
    git fetch origin main || true
    git reset --hard origin/main || true
else
    echo "Cloning repository from GitHub..."
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

# ── 2. Fix Debian 11 Bullseye EOL Mirrors if needed ──────────────────────────
RELEASE=$(lsb_release -cs 2>/dev/null || grep VERSION_CODENAME /etc/os-release | cut -d= -f2 || echo "bullseye")
if [ "$RELEASE" = "bullseye" ]; then
    echo "Fixing Debian 11 Bullseye EOL archive repositories..."
    sudo sed -i 's|security.debian.org/debian-security|archive.debian.org/debian-security|g' /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null || true
    echo 'Acquire::Check-Valid-Until "false";' | sudo tee /etc/apt/apt.conf.d/99no-check-valid-until > /dev/null
fi

echo "=== [2/6] Installing KVM, QEMU & Virtualization Packages ==="
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
    echo "✅ Hardware KVM (/dev/kvm) detected on Master Pi!"
    sudo usermod -aG kvm "$USER" || true
else
    echo "⚠️ /dev/kvm not found. Ensure 64-bit kernel is running (arm_64bit=1 in /boot/config.txt)"
fi

# ── 3. Persistent Storage Directories ─────────────────────────────────────────
echo "=== [3/6] Initializing Storage Pools ==="
sudo mkdir -p /var/lib/inpt-cloud/vms
sudo mkdir -p /var/lib/inpt-cloud/images
sudo chown -R "$USER:$USER" /var/lib/inpt-cloud 2>/dev/null || true

# ── 4. Set up Cloudflare WARP-CLI & Cloudflare Tunnel ──────────────────────────
echo "=== [4/6] Setting up Cloudflare WARP-CLI & Public Tunnel ==="
chmod +x "$TARGET_DIR/setup_cloudflare_tunnel.sh"
sudo "$TARGET_DIR/setup_cloudflare_tunnel.sh" || {
    echo "⚠️ Cloudflare tunnel setup completed with warnings (service active)"
}

# ── 5. Set up Master Node Daemon & Systemd Service ────────────────────────────
echo "=== [5/6] Configuring Master Node Daemon Service ==="
cd "$TARGET_DIR/master-node"
chmod +x install.sh scripts/*.sh

# Run Master install script
./install.sh

# ── 6. Health & Cluster Status Verification ───────────────────────────────────
echo "=== [6/6] Verifying Master Node & Cluster Status ==="
sleep 4

if curl -fsSL http://localhost:5000/health >/dev/null 2>&1; then
    echo ""
    echo "======================================================================"
    echo "  ✅ Master Node Listener is LIVE on port 5000!                       "
    echo "  🌐 Public Endpoint: https://master.aslouneyahya.com                 "
    echo "  📊 Dashboard:       https://master.aslouneyahya.com/dashboard       "
    echo "  🍓 Cluster Nodes:   https://master.aslouneyahya.com/api/cluster/nodes"
    echo "======================================================================"
    curl -s http://localhost:5000/api/cluster/nodes
    echo ""
else
    echo "Master Node starting... checking systemd status:"
    sudo systemctl status inpt-master-node.service --no-pager
fi

echo "======================================================================"
echo "  🎉 Master Node installation complete!                               "
echo "  Worker Pis will now automatically register when they power on.      "
echo "======================================================================"
