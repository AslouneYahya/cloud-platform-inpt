import os
from pathlib import Path
import socket

# Dynamic Node Identity (Every Pi is a Peer)
HOSTNAME = socket.gethostname()
NODE_ID = os.getenv("NODE_ID", HOSTNAME)
CLUSTER_NODE_NAME = NODE_ID
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")
CLUSTER_TOKEN = os.getenv("CLUSTER_TOKEN", "inpt-cluster-secret-2026")

# Base Storage Paths on Pi
BASE_DIR = Path("/var/lib/inpt-cloud")
VMS_DIR = BASE_DIR / "vms"
IMAGES_DIR = BASE_DIR / "images"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# Official Cloud Image URLs (ARM64 / aarch64)
IMAGE_URLS = {
    "alpine": "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/aarch64/alpine-virt-3.19.1-aarch64.iso",
    "debian": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-arm64.qcow2",
    "ubuntu": "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64.img"
}

# Cluster Peer Mesh Configuration
# List of known peers or discovery URL
CLUSTER_PEERS = [p.strip() for p in os.getenv("CLUSTER_PEERS", "").split(",") if p.strip()]
TUNNEL_DOMAIN = os.getenv("TUNNEL_DOMAIN", "https://master.aslouneyahya.com").rstrip("/")
