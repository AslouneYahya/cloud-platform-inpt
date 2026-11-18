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

# If both are already installed, ensure active and skip re-download
if command -v warp-cli &>/dev/null && [ -f /usr/local/bin/cloudflared ]; then
    echo "Cloudflare WARP and Tunnel are already installed! Ensuring services are active..."
    sudo systemctl enable --now warp-svc 2>/dev/null || true
    sudo systemctl enable --now cloudflared 2>/dev/null || true
    exit 0
fi

# Stop existing services cleanly
sudo systemctl stop cloudflared 2>/dev/null || true
sudo systemctl stop warp-svc 2>/dev/null || true

echo "=== [2/5] Downloading & Extracting Cloudflare WARP ==="
RELEASE=$(lsb_release -cs 2>/dev/null || grep VERSION_CODENAME /etc/os-release | cut -d= -f2 || echo "bullseye")
echo "Debian release detected: $RELEASE"

if [ "$RELEASE" = "bullseye" ]; then
    DEB_URL="https://pkg.cloudflareclient.com/pool/bullseye/main/c/cloudflare-warp/cloudflare-warp_2026.3.846.0_arm64.deb"
else
    DEB_URL="https://pkg.cloudflareclient.com/pool/bookworm/main/c/cloudflare-warp/cloudflare-warp_2026.8.2115.0_arm64.deb"
fi

# Do NOT re-download if file is already present on disk (preserves mobile data)
if [ -s /tmp/cloudflare-warp.deb ] && [ $(stat -c%s /tmp/cloudflare-warp.deb 2>/dev/null || stat -f%z /tmp/cloudflare-warp.deb 2>/dev/null || echo 0) -gt 10000000 ]; then
    echo "Package already downloaded on disk (/tmp/cloudflare-warp.deb). Zero data consumed!"
else
    echo "Downloading official Cloudflare WARP package for $RELEASE..."
    curl -# -L -o /tmp/cloudflare-warp.deb "$DEB_URL"
fi

echo "Extracting official binaries..."
rm -rf /tmp/warp_extract && mkdir -p /tmp/warp_extract
dpkg-deb -x /tmp/cloudflare-warp.deb /tmp/warp_extract

# Try native dpkg install first
sudo dpkg -i --force-depends /tmp/cloudflare-warp.deb 2>/dev/null || true

# Guarantee binaries are in both /usr/bin and /bin (where systemd expects them)
sudo cp -f /tmp/warp_extract/usr/bin/warp-svc /usr/bin/warp-svc 2>/dev/null || sudo cp -f /tmp/warp_extract/bin/warp-svc /usr/bin/warp-svc 2>/dev/null || true
sudo cp -f /tmp/warp_extract/usr/bin/warp-cli /usr/bin/warp-cli 2>/dev/null || sudo cp -f /tmp/warp_extract/bin/warp-cli /usr/bin/warp-cli 2>/dev/null || true
sudo cp -f /usr/bin/warp-svc /bin/warp-svc 2>/dev/null || true
sudo cp -f /usr/bin/warp-cli /bin/warp-cli 2>/dev/null || true
sudo chmod +x /usr/bin/warp-svc /usr/bin/warp-cli /bin/warp-svc /bin/warp-cli 2>/dev/null || true

# Ensure required state directories exist
sudo mkdir -p /var/lib/cloudflare-warp /etc/cloudflare-warp /run/cloudflare-warp 2>/dev/null || true

# Copy official systemd service
sudo cp -f /tmp/warp_extract/lib/systemd/system/warp-svc.service /etc/systemd/system/warp-svc.service 2>/dev/null || true

echo "Starting official Cloudflare WARP service..."
sudo systemctl daemon-reload
sudo systemctl enable --now warp-svc
sudo systemctl restart warp-svc

# Wait for daemon socket initialization
echo "Waiting for Cloudflare WARP daemon to be ready..."
for i in {1..10}; do
    if systemctl is-active --quiet warp-svc; then
        sleep 2
        break
    fi
    sleep 1
done

echo "=== [3/5] Activating & Connecting Cloudflare WARP ==="
# Accept privacy policy automatically for both new and legacy warp-cli
yes | warp-cli --accept-tos registration new 2>/dev/null || \
yes | warp-cli --accept-tos register 2>/dev/null || \
warp-cli register 2>/dev/null || true

warp-cli --accept-tos mode warp 2>/dev/null || warp-cli set-mode warp 2>/dev/null || true
echo "Connecting to Cloudflare WARP network..."
warp-cli --accept-tos connect 2>/dev/null || warp-cli connect 2>/dev/null || true
sleep 3
warp-cli status 2>/dev/null || true
sudo chmod 666 /run/cloudflare-warp/warp_service 2>/dev/null || true

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
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token $TOKEN

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
