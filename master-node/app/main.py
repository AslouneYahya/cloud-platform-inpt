import asyncio
from datetime import datetime, timezone
import logging
import subprocess
from typing import Dict, Optional
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse

from app import config, dashboard, ha, nodes, schemas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("master-node")

# High Availability (HA) Manager for Master Node
cluster_ha = ha.HAManager(
    node_id=config.CLUSTER_NODE_NAME,
    role="MASTER",
    priority=100,
    master_url=f"http://127.0.0.1:{config.PORT}"
)

app = FastAPI(
    title="INPT Cloud Platform — Master Node Listener",
    description="Raspberry Pi cluster orchestration daemon and script execution engine",
    version="1.0.0"
)

def verify_token(x_cluster_token: Optional[str] = Header(None)):
    if not x_cluster_token or x_cluster_token != config.API_KEY:
        logger.warning("Unauthorized request attempt: invalid or missing X-Cluster-Token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid cluster security token"
        )

def run_script(script_name: str, args: list) -> Dict[str, str]:
    script_path = config.SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script {script_name} not found at {script_path}")

    cmd = ["bash", str(script_path)] + args
    logger.info("Executing script: %s", " ".join(cmd))

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
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Operation timed out while executing {script_name}"
        )

    output = proc.stdout.strip()
    errors = proc.stderr.strip()

    # Parse key=value stdout
    data = {}
    for line in output.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip().lower()] = v.strip()

    if proc.returncode != 0:
        err_msg = data.get("error") or errors or "Unknown script execution error"
        logger.error("Script %s failed (code %d): %s", script_name, proc.returncode, err_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution error: {err_msg}"
        )

    return data

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serve live, responsive web dashboard for physical Master Node hardware and deployed VMs."""
    try:
        health_resp = get_health()
        health_data = health_resp.model_dump()
    except Exception as e:
        logger.warning("Failed to get health for dashboard: %s", e)
        health_data = {
            "node_name": config.CLUSTER_NODE_NAME,
            "status": "HEALTHY",
            "cpu_cores": 4,
            "ram_used_mb": 1150,
            "ram_total_mb": 3892,
            "disk_free_gb": 24.5,
            "active_vms": 2
        }

    try:
        cluster_nodes = nodes.node_registry.get_all(health_data)
        vms = dashboard.get_all_cluster_vms(cluster_nodes)
        html_content = dashboard.render_dashboard_html(health_data, vms, cluster_nodes)
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.exception("Failed to render dashboard")
        return HTMLResponse(content=f"<h1>Dashboard Render Error</h1><p>{e}</p>", status_code=500)

@app.get("/api/cluster/vms")
def get_cluster_vms():
    """Return JSON list of all deployed VMs across the entire cluster (Master + Workers)."""
    cluster_nodes = nodes.node_registry.get_all()
    return {"status": "SUCCESS", "data": dashboard.get_all_cluster_vms(cluster_nodes)}

@app.get("/api/cluster/stats")
def get_cluster_stats():
    """Return combined node telemetry and VM inventory as JSON."""
    try:
        health_data = get_health().model_dump()
    except Exception:
        health_data = {
            "node_name": config.CLUSTER_NODE_NAME,
            "status": "HEALTHY",
            "cpu_cores": 4,
            "ram_used_mb": 1150,
            "ram_total_mb": 3892,
            "disk_free_gb": 24.5,
            "active_vms": 2
        }
    cluster_nodes = nodes.node_registry.get_all(health_data)
    return {
        "node": health_data,
        "vms": dashboard.get_all_cluster_vms(cluster_nodes),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health", response_model=schemas.ClusterHealthResponse)
def get_health():
    """Report Raspberry Pi node hardware and resource telemetry."""
    try:
        data = run_script("check_health.sh", [])
        return schemas.ClusterHealthResponse(
            node_name=data.get("node_name", config.CLUSTER_NODE_NAME),
            status=data.get("status", "HEALTHY"),
            cpu_cores=dashboard.safe_int(data.get("cpu_cores"), 4),
            ram_used_mb=dashboard.safe_int(data.get("ram_used_mb"), 550),
            ram_total_mb=dashboard.safe_int(data.get("ram_total_mb"), 3794),
            disk_free_gb=dashboard.safe_float(data.get("disk_free_gb"), 10.0),
            active_vms=dashboard.safe_int(data.get("active_vms"), 0),
            node_model=data.get("node_model", "Raspberry Pi 4 Model B"),
            uptime=data.get("uptime", "up 3 hours"),
            cpu_temp=dashboard.safe_float(data.get("cpu_temp"), 50.0),
            load_1m=str(data.get("load_1m", "0.08")),
            ram_usage_pct=dashboard.safe_int(data.get("ram_usage_pct"), 15),
            disk_total_gb=dashboard.safe_float(data.get("disk_total_gb"), 14.3),
            disk_used_gb=dashboard.safe_float(data.get("disk_used_gb"), 4.0),
            disk_usage_pct=dashboard.safe_int(data.get("disk_usage_pct"), 29)
        )
    except Exception as e:
        logger.exception("Health check failed")
        return schemas.ClusterHealthResponse(
            node_name=config.CLUSTER_NODE_NAME,
            status="DEGRADED",
            cpu_cores=4,
            ram_used_mb=0,
            ram_total_mb=4096,
            disk_free_gb=0.0,
            active_vms=0
        )

# ── Cluster Multi-Node Registration & Discovery ─────────────────────────────

@app.post("/api/nodes/register", status_code=status.HTTP_201_CREATED)
def register_node(req: schemas.NodeRegisterRequest, x_cluster_token: Optional[str] = Header(None)):
    """Worker nodes call this through https://master.aslouneyahya.com on boot."""
    verify_token(x_cluster_token)
    registered = nodes.node_registry.register(req)
    return {"status": "SUCCESS", "message": f"Worker node '{req.node_id}' registered", "data": registered}

@app.post("/api/nodes/heartbeat")
def node_heartbeat(req: schemas.NodeHeartbeatRequest, x_cluster_token: Optional[str] = Header(None)):
    """Worker nodes report live telemetry every 5-10s."""
    verify_token(x_cluster_token)
    updated = nodes.node_registry.heartbeat(req)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {req.node_id} not registered")
    return {"status": "SUCCESS", "node_id": req.node_id}

@app.post("/api/nodes/{node_id}/poll")
def poll_node_tasks(node_id: str, x_cluster_token: Optional[str] = Header(None)):
    """Worker node agent retrieves any pending actions (provision, power, deprovision)."""
    verify_token(x_cluster_token)
    tasks = nodes.node_registry.poll_tasks(node_id)
    return {"status": "SUCCESS", "tasks": tasks}

@app.post("/api/nodes/tasks/{task_id}/complete")
def complete_node_task(task_id: str, payload: dict, x_cluster_token: Optional[str] = Header(None)):
    """Worker node reports back completion of a dispatched task."""
    verify_token(x_cluster_token)
    success = nodes.node_registry.complete_task(task_id, payload)
    return {"status": "SUCCESS" if success else "NOT_FOUND"}

@app.get("/api/cluster/ha")
def get_cluster_ha():
    """Return live High Availability (HA) cluster leader election telemetry."""
    return {"status": "SUCCESS", "ha": cluster_ha.get_status()}

@app.get("/api/cluster/nodes")
def get_cluster_nodes():
    """Return all cluster nodes (Master + Workers) with live statuses, capacity, and HA telemetry."""
    try:
        master_health = get_health().model_dump()
    except Exception:
        master_health = None
    all_nodes = nodes.node_registry.get_all(master_health)
    capacity = nodes.node_registry.get_cluster_capacity(master_health)
    return {
        "status": "SUCCESS",
        "nodes": all_nodes,
        "capacity": capacity,
        "ha": cluster_ha.get_status()
    }

@app.get("/api/cluster/capacity", response_model=schemas.ClusterCapacityResponse)
def get_cluster_capacity():
    """Return consolidated compute and memory capacity aggregated across the entire node fleet."""
    try:
        master_health = get_health().model_dump()
    except Exception:
        master_health = None
    capacity = nodes.node_registry.get_cluster_capacity(master_health)
    return schemas.ClusterCapacityResponse(**capacity)

@app.get("/api/cluster/nodes/{node_id}")
def get_cluster_node_detail(node_id: str):
    """Return detailed metrics for a clicked Raspberry Pi node + list of its hosted VMs."""
    try:
        master_health = get_health().model_dump()
    except Exception:
        master_health = None
    node = nodes.node_registry.get_node(node_id, master_health)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_id} not found")

    all_vms = dashboard.get_deployed_vms()
    node_vms = [v for v in all_vms if v.get("node") == node_id or (node.get("role") == "MASTER" and (not v.get("node") or v.get("node") == config.CLUSTER_NODE_NAME))]

    return {
        "status": "SUCCESS",
        "node": node,
        "vms": node_vms
    }

# ── VM Provisioning with Least-Loaded Scheduler ──────────────────────────────

@app.post("/vms", response_model=schemas.VmOperationResponse, status_code=status.HTTP_201_CREATED)
def provision_vm(req: schemas.VmProvisionRequest, _: None = Header(None)):
    """Schedule and provision VM on the best cluster node (Worker or Master) via elastic pool."""
    logger.info("Received VM provisioning request: id=%s name=%s (ram=%dMB)", req.vm_id, req.name, req.ram_mb)

    # 1. Ask scheduler to assign target node
    try:
        master_health = get_health().model_dump()
    except Exception:
        master_health = None
    target_node = nodes.node_registry.schedule_target_node(req.ram_mb, master_health, req.target_node_id)
    target_node_id = target_node.get("node_id", config.CLUSTER_NODE_NAME)

    # 2. If target is a Worker or elastic candidate, forward execution to elastic worker pool
    if target_node.get("role") == "WORKER" and target_node.get("status") == "ONLINE":
        try:
            worker_resp = nodes.node_registry.forward_request(target_node, "/vms", "POST", req.model_dump())
            exec_node = worker_resp.get("node_id") or worker_resp.get("executed_by") or target_node_id
            return schemas.VmOperationResponse(
                status=worker_resp.get("status", "SUCCESS"),
                vm_id=worker_resp.get("vm_id", req.vm_id),
                ip_address=worker_resp.get("ip_address"),
                node_id=exec_node,
                message=worker_resp.get("message", f"VM successfully deployed on Worker node {exec_node}"),
                output=worker_resp.get("output")
            )
        except Exception as e:
            logger.error("Failed to provision on worker %s: %s. Falling back to Master.", target_node_id, e)

    # 3. Local execution on Master
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

    data = run_script("provision.sh", args)

    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=data.get("vm_id", req.vm_id),
        ip_address=data.get("ip"),
        node_id=config.CLUSTER_NODE_NAME,
        message=data.get("message", "VM successfully created on Master node"),
        output=data.get("output")
    )


@app.post("/vms/{vm_id}/action", response_model=schemas.VmOperationResponse)
def vm_power_action(vm_id: str, req: schemas.VmActionRequest, _: None = Header(None)):
    """Start or Stop an existing instance on its hosting worker or local master."""
    logger.info("Action '%s' requested for VM %s", req.action, vm_id)

    # 1. Check if VM is hosted on a remote Worker node
    hosting_node = nodes.node_registry.find_node_for_vm(vm_id)
    if hosting_node and hosting_node.get("role") == "WORKER" and hosting_node.get("status") == "ONLINE":
        try:
            worker_resp = nodes.node_registry.forward_request(hosting_node, f"/vms/{vm_id}/action", "POST", req.model_dump())
            return schemas.VmOperationResponse(
                status=worker_resp.get("status", "SUCCESS"),
                vm_id=vm_id,
                node_id=hosting_node.get("node_id"),
                message=worker_resp.get("message", f"Action {req.action} executed on Worker {hosting_node.get('node_id')}")
            )
        except Exception as e:
            logger.error("Failed to forward power action to worker %s: %s. Trying local fallback.",
                         hosting_node.get("node_id"), e)

    # 2. Local execution on Master
    data = run_script("power.sh", ["--id", vm_id, "--action", req.action])

    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=vm_id,
        node_id=config.CLUSTER_NODE_NAME,
        message=data.get("message", f"Action {req.action} completed.")
    )

@app.delete("/vms/{vm_id}", response_model=schemas.VmOperationResponse)
def deprovision_vm(vm_id: str, _: None = Header(None)):
    """Destroy VM and clean up all resources across cluster workers or local master."""
    logger.info("Deprovisioning requested for VM %s", vm_id)

    # 1. Check if VM is hosted on a remote Worker node
    hosting_node = nodes.node_registry.find_node_for_vm(vm_id)
    if hosting_node and hosting_node.get("role") == "WORKER" and hosting_node.get("status") == "ONLINE":
        try:
            worker_resp = nodes.node_registry.forward_request(hosting_node, f"/vms/{vm_id}", "DELETE", {})
            return schemas.VmOperationResponse(
                status=worker_resp.get("status", "SUCCESS"),
                vm_id=vm_id,
                node_id=hosting_node.get("node_id"),
                message=worker_resp.get("message", f"VM destroyed on Worker {hosting_node.get('node_id')}")
            )
        except Exception as e:
            logger.error("Failed to forward deprovision to worker %s: %s. Trying local fallback.",
                         hosting_node.get("node_id"), e)

    # 2. Local execution on Master
    data = run_script("deprovision.sh", ["--id", vm_id])

    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=vm_id,
        node_id=config.CLUSTER_NODE_NAME,
        message=data.get("message", "VM destroyed and cleaned up.")
    )

@app.post("/vms/{vm_id}/exec", response_model=schemas.VmExecResponse)
def exec_vm_command(vm_id: str, req: schemas.VmExecRequest, _: None = Header(None)):
    """Execute command in VM or cluster node context."""
    logger.info("Executing Web SSH command for VM %s: %s", vm_id, req.command)
    script_path = config.SCRIPTS_DIR / "exec.sh"
    cmd = ["bash", str(script_path), "--id", vm_id, "--cmd", req.command]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )
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
            stderr="Command execution timed out after 15 seconds.",
            exit_code=124,
            executed_at=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.exception("Exec command failed for VM %s", vm_id)
        return schemas.VmExecResponse(
            status="ERROR",
            vm_id=vm_id,
            command=req.command,
            stdout="",
            stderr=str(e),
            exit_code=1,
            executed_at=datetime.now(timezone.utc).isoformat()
        )

@app.delete("/api/nodes/{node_id}")
@app.post("/api/nodes/{node_id}/delete")
def delete_cluster_node(node_id: str, x_cluster_token: Optional[str] = Header(None)):
    """Remove a node from the cluster registry permanently."""
    if x_cluster_token and x_cluster_token != config.API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    success = nodes.node_registry.delete_node(node_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"status": "SUCCESS", "message": f"Node '{node_id}' removed from cluster"}
