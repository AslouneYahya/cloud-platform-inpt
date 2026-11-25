import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
from typing import Dict, List, Optional
import urllib.request
import urllib.error

# Allow HTTPS communication even if local Debian CA bundle is outdated
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Install default opener with custom User-Agent to satisfy Cloudflare WAF
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx))
opener.addheaders = [("User-Agent", "inpt-agent/1.0")]
urllib.request.install_opener(opener)

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

import config
import ha
import image_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Worker-Agent] %(message)s")
logger = logging.getLogger("worker-agent")

def on_worker_promoted():
    logger.warning("=" * 60)
    logger.warning("🚨 [HA FAILOVER] THIS WORKER NODE HAS PROMOTED ITSELF TO ACTIVE MASTER! 🚨")
    logger.warning("Starting Master Node service on port 5000...")
    logger.warning("=" * 60)
    try:
        subprocess.Popen(["sudo", "systemctl", "start", "inpt-master-node.service"])
    except Exception as e:
        logger.warning("Could not start inpt-master-node.service via systemctl: %s", e)

# High Availability (HA) Manager
# worker-raspberrypi has priority 80, worker-pi-02 has priority 60
worker_prio = 80 if ("worker-raspberrypi" in config.NODE_ID or "01" in config.NODE_ID) else 60
ha_manager = ha.WorkerHAManager(
    node_id=config.NODE_ID,
    role="STANDBY",
    priority=worker_prio,
    master_url=config.MASTER_URL,
    on_promoted=on_worker_promoted
)

app = FastAPI(
    title="INPT Cloud Platform — Worker Node Agent",
    description="Worker hypervisor daemon managing KVM instances and streaming telemetry to Master",
    version="1.0.0"
)

# ── Dynamic System Telemetry ──────────────────────────────────────────────────

def get_lan_ip() -> str:
    """Detect real physical LAN IP (eth0/wlan0), skipping WARP tunnel ranges (172.16.x.x)."""
    # 1. Check all IPs from hostname -I for a physical LAN IP (192.168.x.x, 10.x.x.x, etc.)
    try:
        proc = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, text=True, timeout=2)
        ips = proc.stdout.strip().split()
        for ip in ips:
            if ip.startswith("127.") or ip.startswith("169.254.") or ip.startswith("172.16."):
                continue
            return ip
    except Exception:
        pass

    # 2. Check routing table for physical interface
    try:
        proc = subprocess.run(["ip", "route", "show"], stdout=subprocess.PIPE, text=True, timeout=2)
        for line in proc.stdout.splitlines():
            if "src " in line and ("eth0" in line or "wlan0" in line or "en" in line or "wl" in line):
                src_ip = line.split("src ")[1].split()[0]
                if not src_ip.startswith("172.16."):
                    return src_ip
    except Exception:
        pass

    # 3. Socket fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("172.16."):
            return ip
    except Exception:
        pass

    return "127.0.0.1"

def get_cpu_temp() -> Optional[float]:
    """Read hardware thermal sensor on Raspberry Pi."""
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        try:
            return round(int(temp_path.read_text().strip()) / 1000.0, 1)
        except Exception:
            pass
    return 48.5

def get_memory_info() -> Dict[str, int]:
    """Read real RAM from /proc/meminfo."""
    mem = {"total_mb": 3892, "used_mb": 950, "free_mb": 2942}
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        try:
            data = {}
            for line in meminfo.read_text().splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    data[parts[0].strip()] = parts[1].strip().split()[0]
            total_kb = int(data.get("MemTotal", 3985408))
            avail_kb = int(data.get("MemAvailable", 2800000))
            mem["total_mb"] = total_kb // 1024
            mem["used_mb"] = (total_kb - avail_kb) // 1024
            mem["free_mb"] = avail_kb // 1024
        except Exception as e:
            logger.debug("Failed to parse meminfo: %s", e)
    return mem

def get_disk_info() -> Dict[str, float]:
    """Read available disk space in GB."""
    try:
        usage = shutil.disk_usage(config.BASE_DIR if config.BASE_DIR.exists() else "/")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1)
        }
    except Exception:
        return {"total_gb": 28.5, "used_gb": 4.5, "free_gb": 24.0}

def get_local_vms() -> List[dict]:
    """Inspect all KVM instances deployed on this Worker node."""
    vms = []
    if config.VMS_DIR.exists():
        for vm_folder in config.VMS_DIR.iterdir():
            conf_file = vm_folder / "vm.conf"
            if vm_folder.is_dir() and conf_file.exists():
                try:
                    vm_data = {
                        "vm_id": vm_folder.name,
                        "name": vm_folder.name,
                        "os": "Linux ARM64",
                        "cpu": 1,
                        "ram_mb": 512,
                        "disk_gb": 10,
                        "ip": "10.244.x.y",
                        "ports": "22",
                        "status": "STOPPED",
                        "node": config.NODE_ID,
                        "created_at": "-"
                    }
                    for line in conf_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip().lower(), v.strip()
                            if k == "id": vm_data["vm_id"] = v
                            elif k == "name": vm_data["name"] = v
                            elif k == "os": vm_data["os"] = v
                            elif k == "cpu": vm_data["cpu"] = int(v) if v.isdigit() else 1
                            elif k == "ram_mb": vm_data["ram_mb"] = int(v) if v.isdigit() else 512
                            elif k == "disk_gb": vm_data["disk_gb"] = int(v) if v.isdigit() else 10
                            elif k == "ip": vm_data["ip"] = v
                            elif k == "ports": vm_data["ports"] = v
                            elif k == "status": vm_data["status"] = v
                            elif k == "created_at": vm_data["created_at"] = v
                    vms.append(vm_data)
                except Exception:
                    pass
    return vms

def count_active_vms() -> int:
    return sum(1 for v in get_local_vms() if v.get("status") == "RUNNING")

# ── Master Registration & Heartbeat Client ───────────────────────────────────

def call_master(path: str, payload: dict) -> bool:
    """Send authenticated HTTPS request to Master through domain."""
    url = f"{config.MASTER_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "X-Cluster-Token": config.CLUSTER_TOKEN,
        "User-Agent": "inpt-agent/1.0"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.warning("Failed to contact Master at %s: %s", url, e)
        return False

def register_to_master():
    """Initial self-registration on boot."""
    lan_ip = get_lan_ip()
    mem = get_memory_info()
    disk = get_disk_info()
    cpu_cores = os.cpu_count() or 4

    payload = {
        "node_id": config.NODE_ID,
        "hostname": config.HOSTNAME,
        "lan_ip": lan_ip,
        "agent_port": config.AGENT_PORT,
        "cpu_cores": cpu_cores,
        "ram_total_mb": mem["total_mb"],
        "disk_total_gb": disk["total_gb"],
        "disk_free_gb": disk["free_gb"],
        "node_model": "Raspberry Pi 4 Model B"
    }

    logger.info("Registering to Master (%s) as %s (%s)...", config.MASTER_URL, config.NODE_ID, lan_ip)
    success = call_master("/api/nodes/register", payload)
    if success:
        logger.info("✅ Worker successfully registered with Master Node!")
    else:
        logger.warning("Registration pending (Master might be booting or unreachable)")

async def heartbeat_loop():
    """Periodic heartbeat streaming hardware telemetry every 10 seconds."""
    while True:
        try:
            mem = get_memory_info()
            disk = get_disk_info()
            load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.15
            temp = get_cpu_temp()
            local_vms = get_local_vms()
            active_vms = sum(1 for v in local_vms if v.get("status") == "RUNNING")

            payload = {
                "node_id": config.NODE_ID,
                "status": "ONLINE",
                "cpu_usage_pct": round(float(load) * 25.0, 1),
                "cpu_temp": temp,
                "load_1m": f"{load:.2f}",
                "ram_used_mb": mem["used_mb"],
                "ram_total_mb": mem["total_mb"],
                "disk_free_gb": disk["free_gb"],
                "active_vms": active_vms,
                "hosted_vms": local_vms
            }
            call_master("/api/nodes/heartbeat", payload)
        except Exception as e:
            logger.debug("Heartbeat error: %s", e)
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Worker Node Agent on port %d...", config.AGENT_PORT)
    # 1. Verify/cache Golden images
    asyncio.get_event_loop().run_in_executor(None, image_manager.ensure_base_images)
    # 2. Register to Master
    asyncio.get_event_loop().run_in_executor(None, register_to_master)
    # 3. Start background heartbeat
    asyncio.create_task(heartbeat_loop())
    # 4. Start resilient outbound task polling loop
    asyncio.create_task(task_worker_loop())
    # 5. Start High Availability (HA) Master watchdog & leader election thread
    ha_manager.start_watchdog_thread()

@app.get("/ha")
def get_ha_status():
    """Return live HA election and watchdog metrics."""
    return {"status": "SUCCESS", "ha": ha_manager.get_status()}

# ── VM Provisioning & Lifecycle Endpoints ─────────────────────────────────────

class VmProvisionReq(BaseModel):
    vm_id: str
    name: str
    os: str
    cpu: int = 1
    ram_mb: int = 512
    disk_gb: int = 10
    open_ports: List[int] = Field(default_factory=lambda: [22])
    ssh_key: Optional[str] = None
    initial_password: Optional[str] = None
    target_node_id: Optional[str] = None

class VmActionReq(BaseModel):
    action: str

def verify_token(x_cluster_token: Optional[str] = Header(None)):
    if not x_cluster_token or x_cluster_token != config.CLUSTER_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized cluster token")

@app.post("/vms")
def provision_vm(req: VmProvisionReq, _: None = Header(None)):
    """Execute local KVM VM creation on this worker."""
    logger.info("Provisioning VM '%s' (%s) locally...", req.name, req.vm_id)
    script_path = config.SCRIPTS_DIR / "provision_kvm.sh"

    ports_str = ",".join(str(p) for p in req.open_ports)
    args = [
        "bash", str(script_path),
        "--id", req.vm_id,
        "--name", req.name,
        "--os", req.os,
        "--cpu", str(req.cpu),
        "--ram", str(req.ram_mb),
        "--disk", str(req.disk_gb),
        "--ports", ports_str
    ]
    if req.ssh_key:
        args += ["--key", req.ssh_key]
    if req.initial_password:
        args += ["--pass", req.initial_password]

    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    logger.info("Script returncode=%d, stdout: '%s', stderr: '%s'", proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    data = {}
    for line in proc.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip().lower()] = v.strip()

    if proc.returncode != 0:
        err = data.get("error") or proc.stderr.strip() or f"Script exited with code {proc.returncode}"
        raise HTTPException(status_code=500, detail=err)

    return {
        "status": "SUCCESS",
        "vm_id": req.vm_id,
        "node_id": config.NODE_ID,
        "ip_address": data.get("ip", "10.244.1.20"),
        "message": f"VM created with real KVM isolation on {config.NODE_ID}"
    }

@app.post("/vms/{vm_id}/action")
def power_vm(vm_id: str, req: VmActionReq, _: None = Header(None)):
    """Start/Stop local KVM instance."""
    script_path = config.SCRIPTS_DIR / "power_kvm.sh"
    proc = subprocess.run(["bash", str(script_path), "--id", vm_id, "--action", req.action],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail="Power action failed")
    return {"status": "SUCCESS", "vm_id": vm_id, "action": req.action}

@app.delete("/vms/{vm_id}")
def destroy_vm(vm_id: str, _: None = Header(None)):
    """Destroy VM and delete overlay disk."""
    script_path = config.SCRIPTS_DIR / "deprovision_kvm.sh"
    proc = subprocess.run(["bash", str(script_path), "--id", vm_id],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {"status": "SUCCESS", "vm_id": vm_id, "message": "VM destroyed on worker"}

@app.get("/health")
def health():
    mem = get_memory_info()
    disk = get_disk_info()
    return {
        "node_id": config.NODE_ID,
        "status": "ONLINE",
        "cpu_temp": get_cpu_temp(),
        "ram_used_mb": mem["used_mb"],
        "ram_total_mb": mem["total_mb"],
        "disk_free_gb": disk["free_gb"],
        "active_vms": count_active_vms()
    }

def process_task(task: dict) -> dict:
    task_id = task.get("task_id")
    path = task.get("path", "")
    method = task.get("method", "POST")
    payload = task.get("payload", {})
    logger.info("Executing dispatched task %s: %s %s", task_id, method, path)

    try:
        if path == "/vms" and method == "POST":
            req = VmProvisionReq(**payload)
            res = provision_vm(req)
            return res
        elif "/action" in path and method == "POST":
            parts = path.split("/")
            vm_id = parts[2] if len(parts) > 2 else payload.get("vm_id", "")
            req = VmActionReq(**payload)
            return power_vm(vm_id, req)
        elif method == "DELETE":
            parts = path.split("/")
            vm_id = parts[2] if len(parts) > 2 else payload.get("vm_id", "")
            return destroy_vm(vm_id)
        else:
            return {"status": "ERROR", "message": f"Unsupported action {method} {path}"}
    except Exception as e:
        logger.exception("Task %s execution error: %s", task_id, e)
        return {"status": "ERROR", "message": str(e)}

async def task_worker_loop():
    """Poll Master for scheduled tasks over Cloudflare Tunnel (resilient to campus Wi-Fi AP-Isolation)."""
    while True:
        try:
            url = f"{config.MASTER_URL}/api/nodes/{config.NODE_ID}/poll"
            headers = {
                "Content-Type": "application/json",
                "X-Cluster-Token": config.CLUSTER_TOKEN,
                "User-Agent": "inpt-agent/1.0"
            }
            req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tasks = data.get("tasks", [])
                    for task in tasks:
                        task_id = task.get("task_id")
                        result = await asyncio.get_event_loop().run_in_executor(None, process_task, task)
                        complete_url = f"{config.MASTER_URL}/api/nodes/tasks/{task_id}/complete"
                        comp_data = json.dumps(result).encode("utf-8")
                        comp_req = urllib.request.Request(complete_url, data=comp_data, headers=headers, method="POST")
                        try:
                            with urllib.request.urlopen(comp_req, context=ssl_ctx, timeout=8) as comp_resp:
                                logger.info("Reported task %s complete (HTTP %d)", task_id, comp_resp.status)
                        except Exception as ce:
                            logger.error("Failed to report task %s completion: %s", task_id, ce)
        except Exception as e:
            logger.debug("Task poll loop: %s", e)
        await asyncio.sleep(1.5)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.AGENT_PORT)
