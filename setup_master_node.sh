#!/usr/bin/env bash
# ==============================================================================
# setup_master_node.sh — One-click Master Node Daemon Setup for Raspberry Pi
# INPT Cloud Platform — FastAPI Daemon + Shell Execution Engine
# ==============================================================================
set -e

TARGET_DIR="$HOME/cloud-platform-inpt"
REPO_URL="https://github.com/AslouneYahya/cloud-platform-inpt.git"

echo "=== [1/4] Cloning / Updating Cloud Platform Repository ==="
if [ -d "$TARGET_DIR" ]; then
    echo "Repository already present, pulling latest version..."
    cd "$TARGET_DIR"
    git pull origin main || true
else
    echo "Cloning repository from GitHub..."
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

cd "$TARGET_DIR/master-node"

echo "=== [2/4] Making scripts executable ==="
chmod +x install.sh
chmod +x scripts/*.sh

echo "=== [3/4] Running Master Node Installer ==="
./install.sh

echo "=== [4/4] Verifying Master Node Health ==="
sleep 3
if curl -fsSL http://localhost:5000/health >/dev/null 2>&1; then
    echo ""
    echo "======================================================================"
    echo "  Master Node Listener is LIVE and HEALTHY on port 5000!              "
    echo "======================================================================"
    curl -s http://localhost:5000/health
    echo ""
else
    echo "Master Node starting... checking systemd status:"
    sudo systemctl status inpt-master-node.service --no-pager
fi

echo ""
echo "======================================================================"
echo "  Installation terminée avec succès !                                 "
echo "  Le Nœud Maître écoute sur le port 5000 et via Cloudflare Tunnel.    "
echo "======================================================================"
