import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", BASE_DIR / "scripts"))

API_KEY = os.getenv("CLUSTER_API_KEY", "inpt-cluster-secret-2026")
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")

# Maximum allocations supported by this hardware node
MAX_RAM_MB = int(os.getenv("MAX_RAM_MB", "4096"))
MAX_CPU_CORES = int(os.getenv("MAX_CPU_CORES", "4"))
CLUSTER_NODE_NAME = os.getenv("NODE_NAME", "master-rpi-01")
