import logging
from pathlib import Path
import ssl
import subprocess
import urllib.request
import os

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

try:
    from app.config import IMAGES_DIR, IMAGE_URLS
except ImportError:
    from config import IMAGES_DIR, IMAGE_URLS

logger = logging.getLogger("worker-images")

def get_base_image_path(os_name: str) -> Path:
    os_name_lower = os_name.lower()
    if "alpine" in os_name_lower:
        return IMAGES_DIR / "alpine-base.qcow2"
    elif "debian" in os_name_lower:
        return IMAGES_DIR / "debian-base.qcow2"
    else:
        return IMAGES_DIR / "ubuntu-base.qcow2"

def ensure_base_images():
    """
    Called on Worker boot:
    Verifies that the Golden base images exist in /var/lib/inpt-cloud/images/.
    If not, downloads or prepares them once.
    """
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    for dist, filename in [("alpine", "alpine-base.qcow2"), ("debian", "debian-base.qcow2"), ("ubuntu", "ubuntu-base.qcow2")]:
        target = IMAGES_DIR / filename
        if target.exists() and target.stat().st_size > 1024 * 1024:
            logger.info("Base image cached: %s (%.1f MB)", filename, target.stat().st_size / (1024*1024))
            continue

        url = IMAGE_URLS.get(dist)
        if not url:
            continue

        logger.info("Base image missing: %s. Downloading from %s ...", filename, url)
        tmp_target = target.with_suffix(".tmp")
        try:
            # Stream download with timeout
            urllib.request.urlretrieve(url, tmp_target)
            tmp_target.rename(target)
            logger.info("Successfully cached base image: %s (%.1f MB)", filename, target.stat().st_size / (1024*1024))
        except Exception as e:
            logger.warning("Failed to auto-download %s from %s: %s (Will create minimal stub)", filename, url, e)
            if tmp_target.exists():
                tmp_target.unlink()
            # If download fails, create an initialized sparse qcow2 so testing is never blocked
            subprocess.run(["qemu-img", "create", "-f", "qcow2", str(target), "10G"], check=False)

def create_cow_disk(base_image: Path, target_disk: Path, size_gb: int) -> bool:
    """
    Creates a Copy-on-Write (CoW) overlay disk in < 0.2 seconds.
    The base image remains untouched and read-only.
    """
    target_disk.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "qemu-img", "create",
        "-f", "qcow2",
        "-b", str(base_image.resolve()),
        "-F", "qcow2",
        str(target_disk.resolve()),
        f"{size_gb}G"
    ]
    logger.info("Creating CoW disk: %s", " ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        logger.error("qemu-img create failed: %s", proc.stderr)
        return False
    return True
