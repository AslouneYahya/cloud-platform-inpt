#!/usr/bin/env bash
# ==============================================================================
# setup_cloudflare_tunnel.sh — Official Cloudflare WARP (Headless) + Tunnel
# INPT Cloud Platform — Zero apt dependencies (Bypasses debian repo timeouts)
# ==============================================================================
set -e

TOKEN="${1:-eyJhIjoiODcwZWRiNzc5M2IyYTc2OGMyZmE2ZGRjYTBlOGYzYmEiLCJ0IjoiNGU2Mzc4NzQtMTRlYi00ZjViLThkMjItNDUyNzMyMTRiZDYyIiwicyI6Ik9EUTBNVGcyTldZdFpXRmlNUzAwTURSbExXRmhOemd0T0RVd01ESXdOalJoTVRaaiJ9}"

echo "=== [1/5] Detecting Architecture ==="
ARCH=$(uname -m)
echo "System architecture detected: $ARCH"

# Stop existing services cleanly
sudo systemctl stop cloudflared 2>/dev/null || true
sudo systemctl stop warp-svc 2>/dev/null || true

echo "=== [2/5] Downloading & Extracting Cloudflare WARP ==="
if [ ! -f /tmp/cloudflare-warp.deb ]; then
    echo "Downloading official Cloudflare WARP ARM64 package..."
    curl -# -L -o /tmp/cloudflare-warp.deb https://pkg.cloudflareclient.com/pool/bookworm/main/c/cloudflare-warp/cloudflare-warp_2026.8.2115.0_arm64.deb
fi

echo "Extracting official binaries..."
rm -rf /tmp/warp_extract && mkdir -p /tmp/warp_extract
dpkg-deb -x /tmp/cloudflare-warp.deb /tmp/warp_extract

# Binaries in package are located at /bin/warp-svc and /bin/warp-cli
sudo cp /tmp/warp_extract/bin/warp-svc /bin/warp-svc
sudo cp /tmp/warp_extract/bin/warp-cli /bin/warp-cli
sudo chmod +x /bin/warp-svc /bin/warp-cli

# Copy official systemd service
sudo cp /tmp/warp_extract/lib/systemd/system/warp-svc.service /etc/systemd/system/warp-svc.service

echo "Starting official Cloudflare WARP service..."
sudo systemctl daemon-reload
sudo systemctl enable --now warp-svc
sleep 4

echo "=== [3/5] Activating & Connecting Cloudflare WARP ==="
warp-cli --accept-tos registration new 2>/dev/null || warp-cli register 2>/dev/null || true
warp-cli --accept-tos mode warp 2>/dev/null || warp-cli set-mode warp 2>/dev/null || true
echo "Connecting to Cloudflare WARP network..."
warp-cli --accept-tos connect 2>/dev/null || warp-cli connect 2>/dev/null || true
sleep 4
warp-cli status || true

echo "=== [4/5] Installing & Starting Cloudflare Tunnel ==="
sudo rm -f /etc/systemd/system/cloudflared.service 2>/dev/null || true

if [ ! -f /usr/local/bin/cloudflared ]; then
    echo "Downloading cloudflared..."
    sudo curl -# -L -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64
    sudo chmod +x /usr/local/bin/cloudflared
fi

cat << EOF | sudo tee /etc/systemd/system/cloudflared.service > /dev/null
[Unit]
Description=Cloudflare Tunnel
After=network.target network-online.target warp-svc.service
Wants=network-online.target warp-svc.service

[Service]
Type=simple
TimeoutStartSec=10s
Restart=always
RestartSec=5s
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --protocol http2 run --token $TOKEN

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared

echo "=== [5/5] Verification & Live Logs ==="
sleep 4
echo "Tunnel Status:"
sudo systemctl status cloudflared --no-pager
echo ""
echo "Tunnel Connection Logs:"
sudo journalctl -u cloudflared -n 15 --no-pager

echo ""
echo "======================================================================"
echo "  Cloudflare WARP + Tunnel sont ACTIFS !                              "
echo "  Vérifiez le dashboard Cloudflare : le statut doit être HEALTHY !   "
echo "======================================================================"
