"""
INPT Cloud Platform — Unified Cluster Node (Peer Daemon)
Every Raspberry Pi in the cluster runs this exact same daemon.
Each node is a fully capable Peer: local KVM hypervisor + API orchestrator + telemetry streaming.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import time
from typing import Dict, List, Optional
import urllib.request
import urllib.error

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from app import config, dashboard, image_manager, mesh, schemas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Peer-Node] %(message)s")
logger = logging.getLogger("cluster-node")

peer_mesh = mesh.PeerMesh(node_id=config.NODE_ID)

app = FastAPI(
    title="INPT Cloud Platform — Peer Node",
    description="Decentralized peer daemon providing KVM virtualization, orchestration API, and mesh telemetry",
    version="2.0.0"
)

def verify_token(x_cluster_token: Optional[str] = Header(None)):
    if not x_cluster_token or x_cluster_token != config.CLUSTER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid cluster security token"
        )

def run_script(script_name: str, args: list) -> Dict[str, str]:
    script_path = config.SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script {script_name} not found at {script_path}")

    cmd = ["bash", str(script_path)] + args
    logger.info("Executing local script: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        logger.error("Script execution timed out: %s", script_name)
        return {"status": "FAILED", "error": f"Script {script_name} timed out after 60s"}

    data = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip().lower()] = v.strip()

    if proc.returncode != 0 and "status" not in data:
        data["status"] = "FAILED"
        data["error"] = proc.stderr.strip() or f"Script exited with code {proc.returncode}"
    elif "status" not in data:
        data["status"] = "SUCCESS"

    data["output"] = proc.stdout.strip()
    return data

# ── Health & Dashboard Endpoints ─────────────────────────────────────────────

@app.get("/health", response_model=schemas.ClusterHealthResponse)
def get_health():
    """Report Raspberry Pi hardware and resource telemetry."""
    try:
        data = run_script("check_health.sh", [])
        return schemas.ClusterHealthResponse(
            node_name=data.get("node_name", config.NODE_ID),
            status=data.get("status", "HEALTHY"),
            cpu_cores=dashboard.safe_int(data.get("cpu_cores"), 4),
            ram_used_mb=dashboard.safe_int(data.get("ram_used_mb"), 550),
            ram_total_mb=dashboard.safe_int(data.get("ram_total_mb"), 3892),
            disk_free_gb=dashboard.safe_float(data.get("disk_free_gb"), 10.0),
            active_vms=dashboard.safe_int(data.get("active_vms"), 0),
            node_model=data.get("node_model", "Raspberry Pi 4 Model B"),
            uptime=data.get("uptime", "up"),
            cpu_temp=dashboard.safe_float(data.get("cpu_temp"), 50.0),
            load_1m=str(data.get("load_1m", "0.08")),
            ram_usage_pct=dashboard.safe_int(data.get("ram_usage_pct"), 15),
            disk_total_gb=dashboard.safe_float(data.get("disk_total_gb"), 29.0),
            disk_used_gb=dashboard.safe_float(data.get("disk_used_gb"), 4.0),
            disk_usage_pct=dashboard.safe_int(data.get("disk_usage_pct"), 20)
        )
    except Exception as e:
        logger.exception("Health check failed: %s", e)
        return schemas.ClusterHealthResponse(
            node_name=config.NODE_ID,
            status="DEGRADED",
            cpu_cores=4,
            ram_used_mb=1000,
            ram_total_mb=4096,
            disk_free_gb=10.0,
            active_vms=0
        )

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/", response_class=HTMLResponse)
def get_dashboard():
    """Render unified web dashboard showing all cluster peers and hosted VMs."""
    try:
        health_data = get_health().model_dump()
    except Exception:
        health_data = {"node_name": config.NODE_ID, "status": "HEALTHY"}
    all_peers = peer_mesh.get_all(health_data)
    all_vms = dashboard.get_all_cluster_vms(all_peers)
    return dashboard.render_dashboard_html(health_data, all_vms, all_peers)

@app.get("/api/cluster/nodes")
def get_cluster_nodes():
    """Return all peer nodes with live telemetry and fleet capacity."""
    try:
        health_data = get_health().model_dump()
    except Exception:
        health_data = None
    all_nodes = peer_mesh.get_all(health_data)
    capacity = peer_mesh.get_cluster_capacity(health_data)
    return {"status": "SUCCESS", "nodes": all_nodes, "capacity": capacity}

@app.get("/api/cluster/capacity", response_model=schemas.ClusterCapacityResponse)
def get_cluster_capacity():
    """Return consolidated compute and RAM capacity across all cluster peers."""
    try:
        health_data = get_health().model_dump()
    except Exception:
        health_data = None
    capacity = peer_mesh.get_cluster_capacity(health_data)
    return schemas.ClusterCapacityResponse(**capacity)

@app.get("/api/cluster/vms")
def get_cluster_vms():
    all_peers = peer_mesh.get_all()
    return {"status": "SUCCESS", "data": dashboard.get_all_cluster_vms(all_peers)}

# ── VM Lifecycle Operations (Local or Dispatched to Best Peer) ────────────────

@app.post("/vms", response_model=schemas.VmOperationResponse, status_code=status.HTTP_201_CREATED)
def provision_vm(req: schemas.VmProvisionRequest, _: None = Header(None)):
    """Provision VM on optimal peer (locally or forwarded to peer)."""
    logger.info("Received provisioning request: id=%s name=%s (ram=%dMB)", req.vm_id, req.name, req.ram_mb)

    try:
        local_health = get_health().model_dump()
    except Exception:
        local_health = None

    is_local, target_node = peer_mesh.schedule_best_node(req.ram_mb, local_health, req.target_node_id)
    target_node_id = target_node.get("node_id", config.NODE_ID)

    if not is_local:
        # Forward to best peer
        try:
            resp = peer_mesh.forward_request(target_node_id, "/vms", "POST", req.model_dump())
            return schemas.VmOperationResponse(
                status=resp.get("status", "SUCCESS"),
                vm_id=resp.get("vm_id", req.vm_id),
                ip_address=resp.get("ip_address"),
                node_id=resp.get("node_id", target_node_id),
                message=resp.get("message", f"VM deployed on peer {target_node_id}"),
                output=resp.get("output")
            )
        except Exception as e:
            logger.error("Failed to forward to peer %s: %s. Falling back to local.", target_node_id, e)

    # Local KVM execution
    ports_str = ",".join(str(p) for p in req.open_ports)
    args = [
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

    data = run_script("provision_kvm.sh", args)
    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=data.get("vm_id", req.vm_id),
        ip_address=data.get("ip", "10.244.10.20"),
        node_id=config.NODE_ID,
        message=data.get("message", f"VM created with native KVM isolation on {config.NODE_ID}"),
        output=data.get("output")
    )

@app.post("/vms/{vm_id}/action", response_model=schemas.VmOperationResponse)
def vm_power_action(vm_id: str, req: schemas.VmActionRequest, _: None = Header(None)):
    """Power start/stop VM on whichever peer node hosts it."""
    is_local, hosting_node = peer_mesh.find_node_for_vm(vm_id)

    if not is_local and hosting_node:
        try:
            resp = peer_mesh.forward_request(hosting_node, f"/vms/{vm_id}/action", "POST", req.model_dump())
            return schemas.VmOperationResponse(
                status=resp.get("status", "SUCCESS"),
                vm_id=vm_id,
                node_id=hosting_node,
                message=resp.get("message", f"Action {req.action} executed on peer {hosting_node}")
            )
        except Exception as e:
            logger.error("Failed to forward action to peer %s: %s", hosting_node, e)

    data = run_script("power_kvm.sh", ["--id", vm_id, "--action", req.action])
    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=vm_id,
        node_id=config.NODE_ID,
        message=data.get("message", f"Action {req.action} completed on {config.NODE_ID}.")
    )

@app.delete("/vms/{vm_id}", response_model=schemas.VmOperationResponse)
def deprovision_vm(vm_id: str, _: None = Header(None)):
    """Destroy VM on whichever peer node hosts it."""
    is_local, hosting_node = peer_mesh.find_node_for_vm(vm_id)

    if not is_local and hosting_node:
        try:
            resp = peer_mesh.forward_request(hosting_node, f"/vms/{vm_id}", "DELETE", {})
            return schemas.VmOperationResponse(
                status=resp.get("status", "SUCCESS"),
                vm_id=vm_id,
                node_id=hosting_node,
                message=resp.get("message", f"VM destroyed on peer {hosting_node}")
            )
        except Exception as e:
            logger.error("Failed to forward delete to peer %s: %s", hosting_node, e)

    data = run_script("deprovision_kvm.sh", ["--id", vm_id])
    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=vm_id,
        node_id=config.NODE_ID,
        message=data.get("message", "VM destroyed and cleaned up.")
    )

@app.post("/vms/{vm_id}/exec", response_model=schemas.VmExecResponse)
def exec_vm_command(vm_id: str, req: schemas.VmExecRequest, _: None = Header(None)):
    script_path = config.SCRIPTS_DIR / "exec.sh"
    cmd = ["bash", str(script_path), "--id", vm_id, "--cmd", req.command]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        return schemas.VmExecResponse(
            status="SUCCESS" if proc.returncode == 0 else "ERROR",
            vm_id=vm_id,
            command=req.command,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            executed_at=datetime.now(timezone.utc).isoformat()
        )
    except subprocess.TimeoutExpired:
        return schemas.VmExecResponse(
            status="TIMEOUT",
            vm_id=vm_id,
            command=req.command,
            stdout="",
            stderr="Execution timed out after 15s.",
            exit_code=124,
            executed_at=datetime.now(timezone.utc).isoformat()
        )

# ── Peer Mesh Protocol Endpoints ─────────────────────────────────────────────

@app.post("/api/nodes/register", status_code=status.HTTP_201_CREATED)
def register_peer(req: schemas.NodeRegisterRequest, x_cluster_token: Optional[str] = Header(None)):
    verify_token(x_cluster_token)
    registered = peer_mesh.register_peer(req)
    return {"status": "SUCCESS", "data": registered}

@app.post("/api/nodes/heartbeat")
def peer_heartbeat(req: schemas.NodeHeartbeatRequest, x_cluster_token: Optional[str] = Header(None)):
    verify_token(x_cluster_token)
    updated = peer_mesh.heartbeat_peer(req)
    return {"status": "SUCCESS", "node_id": req.node_id}

@app.post("/api/nodes/{node_id}/poll")
def poll_peer_tasks(node_id: str, x_cluster_token: Optional[str] = Header(None)):
    verify_token(x_cluster_token)
    tasks = peer_mesh.poll_tasks(node_id)
    return {"status": "SUCCESS", "tasks": tasks}

@app.post("/api/nodes/tasks/{task_id}/complete")
def complete_peer_task(task_id: str, payload: dict, x_cluster_token: Optional[str] = Header(None)):
    verify_token(x_cluster_token)
    success = peer_mesh.complete_task(task_id, payload)
    return {"status": "SUCCESS" if success else "NOT_FOUND"}

# ── Background Peer Mesh Synchronization & Heartbeat Broadcast ─────────────

def call_cluster_domain(path: str, payload: dict) -> bool:
    """Send authenticated request to the cluster ingress domain."""
    url = f"{config.TUNNEL_DOMAIN}{path}"
    headers = {
        "Content-Type": "application/json",
        "X-Cluster-Token": config.CLUSTER_TOKEN,
        "User-Agent": "inpt-node/2.0"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.debug("call_cluster_domain to %s failed: %s", url, e)
        return False

def register_self_with_cluster():
    """Announce this peer node to the cluster mesh on boot."""
    try:
        health_resp = get_health()
        payload = {
            "node_id": config.NODE_ID,
            "hostname": config.HOSTNAME,
            "lan_ip": "127.0.0.1",
            "agent_port": config.PORT,
            "cpu_cores": health_resp.cpu_cores,
            "ram_total_mb": health_resp.ram_total_mb,
            "disk_total_gb": health_resp.disk_total_gb or 29.0,
            "disk_free_gb": health_resp.disk_free_gb,
            "node_model": health_resp.node_model or "Raspberry Pi 4 Model B"
        }
        call_cluster_domain("/api/nodes/register", payload)
        logger.info("Announced node '%s' to cluster ingress domain", config.NODE_ID)
    except Exception as e:
        logger.warning("Failed to auto-register node with cluster: %s", e)

async def peer_heartbeat_broadcast_loop():
    """Stream live hardware and VM metrics to the cluster mesh every 5s."""
    await asyncio.sleep(2)
    while True:
        try:
            health_resp = get_health()
            local_vms = dashboard.get_deployed_vms()
            active_vms = sum(1 for v in local_vms if v.get("status") == "RUNNING")
            payload = {
                "node_id": config.NODE_ID,
                "status": "ONLINE",
                "cpu_usage_pct": float(health_resp.load_1m or "0.1") * 25.0,
                "cpu_temp": health_resp.cpu_temp,
                "load_1m": health_resp.load_1m,
                "ram_used_mb": health_resp.ram_used_mb,
                "ram_total_mb": health_resp.ram_total_mb,
                "disk_free_gb": health_resp.disk_free_gb,
                "active_vms": active_vms,
                "hosted_vms": local_vms
            }
            # 1. Update local peer registry directly
            req = schemas.NodeHeartbeatRequest(**payload)
            peer_mesh.heartbeat_peer(req)

            # 2. Broadcast to cluster domain (ensures all peers receive it via tunnel)
            call_cluster_domain("/api/nodes/heartbeat", payload)
        except Exception as e:
            logger.debug("Heartbeat broadcast error: %s", e)
        await asyncio.sleep(5)

def process_dispatched_task(task: dict) -> dict:
    path = task.get("path", "")
    method = task.get("method", "POST")
    payload = task.get("payload", {})
    if path == "/vms" and method == "POST":
        req = schemas.VmProvisionRequest(**payload)
        res = provision_vm(req)
        return res.model_dump()
    elif "/action" in path and method == "POST":
        parts = path.split("/")
        vm_id = parts[2] if len(parts) > 2 else payload.get("vm_id", "")
        req = schemas.VmActionRequest(**payload)
        res = vm_power_action(vm_id, req)
        return res.model_dump()
    elif method == "DELETE":
        parts = path.split("/")
        vm_id = parts[2] if len(parts) > 2 else payload.get("vm_id", "")
        res = deprovision_vm(vm_id)
        return res.model_dump()
    return {"status": "ERROR", "message": f"Unknown action {method} {path}"}

async def task_execution_loop():
    """Poll the cluster task queue for operations dispatched to this peer."""
    while True:
        try:
            # 1. Local mesh poll
            tasks = peer_mesh.poll_tasks(config.NODE_ID)

            # 2. Remote domain poll (if peer is polling through domain tunnel)
            if not tasks:
                poll_url = f"{config.TUNNEL_DOMAIN}/api/nodes/{config.NODE_ID}/poll"
                headers = {
                    "Content-Type": "application/json",
                    "X-Cluster-Token": config.CLUSTER_TOKEN,
                    "User-Agent": "inpt-node/2.0"
                }
                req = urllib.request.Request(poll_url, data=b"{}", headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            tasks = data.get("tasks", [])
                except Exception:
                    pass

            for task in tasks:
                task_id = task.get("task_id")
                result = await asyncio.get_event_loop().run_in_executor(None, process_dispatched_task, task)
                peer_mesh.complete_task(task_id, result)
                # Report completion back to cluster domain
                comp_url = f"{config.TUNNEL_DOMAIN}/api/nodes/tasks/{task_id}/complete"
                comp_data = json.dumps(result).encode("utf-8")
                comp_req = urllib.request.Request(comp_url, data=comp_data, headers={"Content-Type": "application/json", "X-Cluster-Token": config.CLUSTER_TOKEN}, method="POST")
                try:
                    with urllib.request.urlopen(comp_req, timeout=4):
                        pass
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Task execution loop error: %s", e)
        await asyncio.sleep(1.5)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting INPT Cloud Platform Peer Node '%s' on port %d...", config.NODE_ID, config.PORT)
    # 1. Ensure Golden Images are downloaded and verified
    asyncio.get_event_loop().run_in_executor(None, image_manager.ensure_base_images)
    # 2. Initial self-registration to cluster mesh
    asyncio.get_event_loop().run_in_executor(None, register_self_with_cluster)
    # 3. Start periodic heartbeat broadcast loop
    asyncio.create_task(peer_heartbeat_broadcast_loop())
    # 4. Start task execution loop
    asyncio.create_task(task_execution_loop())

if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
