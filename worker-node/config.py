import os
from pathlib import Path
import socket

# Master Node Cloudflare Tunnel endpoint — NO hardcoded IPs!
MASTER_URL = os.getenv("MASTER_URL", "https://master.aslouneyahya.com").rstrip("/")
CLUSTER_TOKEN = os.getenv("CLUSTER_TOKEN", "inpt-cluster-secret-2026")

# Dynamic Node Identity
HOSTNAME = socket.gethostname()
NODE_ID = os.getenv("NODE_ID", f"worker-{HOSTNAME}")
AGENT_PORT = int(os.getenv("AGENT_PORT", "5001"))

# Storage paths on Worker Pi
BASE_DIR = Path("/var/lib/inpt-cloud")
IMAGES_DIR = BASE_DIR / "images"
VMS_DIR = BASE_DIR / "vms"
SCRIPTS_DIR = Path(__file__).parent / "scripts"

# Official Cloud Image URLs (ARM64 / aarch64)
IMAGE_URLS = {
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/aarch64/alpine-virt-3.19.1-aarch64.iso",
    "debian": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-arm64.qcow2",
    "ubuntu": "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64.img"
}
