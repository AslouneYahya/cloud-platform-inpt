#!/usr/bin/env bash
# ==============================================================================
# install.sh — Setup INPT Master Node Listener daemon on Raspberry Pi
# ==============================================================================
set -e

echo "=== [1/5] Installing system dependencies (Python3, venv, curl) ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv curl

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

echo "=== [2/5] Creating Python virtual environment ==="
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "=== [3/5] Setting script permissions and runtime storage ==="
chmod +x scripts/*.sh
sudo mkdir -p /var/lib/inpt-cloud/vms
sudo chown -R "$USER:$USER" /var/lib/inpt-cloud

echo "=== [4/5] Installing systemd daemon service ==="
SERVICE_FILE="/etc/systemd/system/inpt-master-node.service"

sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=INPT Cloud Platform — Master Node Listener
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PORT=5000
Environment=HOST=0.0.0.0
Environment=CLUSTER_API_KEY=inpt-cluster-secret-2026
ExecStart=$INSTALL_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

echo "=== [5/5] Reloading and starting service ==="
sudo systemctl daemon-reload
sudo systemctl enable inpt-master-node.service
sudo systemctl restart inpt-master-node.service

echo ""
echo "================================================================="
echo "  INPT Master Node Listener successfully installed and running!  "
echo "  Address: http://$(hostname -I | awk '{print $1}'):5000"
echo "  Health Check: curl http://localhost:5000/health"
echo "================================================================="
