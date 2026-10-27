import asyncio
from datetime import datetime, timezone
import logging
import subprocess
from typing import Dict, Optional
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app import config, schemas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("master-node")

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

@app.get("/health", response_model=schemas.ClusterHealthResponse)
def get_health():
    """Report Raspberry Pi node hardware and resource telemetry."""
    try:
        data = run_script("check_health.sh", [])
        return schemas.ClusterHealthResponse(
            node_name=data.get("node_name", config.CLUSTER_NODE_NAME),
            status=data.get("status", "HEALTHY"),
            cpu_cores=int(data.get("cpu_cores", 4)),
            ram_used_mb=int(data.get("ram_used_mb", 0)),
            ram_total_mb=int(data.get("ram_total_mb", 4096)),
            disk_free_gb=float(data.get("disk_free_gb", 10.0)),
            active_vms=int(data.get("active_vms", 0))
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

@app.post("/vms", response_model=schemas.VmOperationResponse, status_code=status.HTTP_201_CREATED)
def provision_vm(req: schemas.VmProvisionRequest, _: None = Header(None)):
    """Translate Web API request into provisioning script on Raspberry Pi."""
    logger.info("Received VM provisioning request: id=%s name=%s", req.vm_id, req.name)

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
        node_id=data.get("node", config.CLUSTER_NODE_NAME),
        message=data.get("message", "VM successfully created on Raspberry Pi node"),
        output=data.get("output")
    )

@app.post("/vms/{vm_id}/action", response_model=schemas.VmOperationResponse)
def vm_power_action(vm_id: str, req: schemas.VmActionRequest, _: None = Header(None)):
    """Start or Stop an existing instance."""
    logger.info("Action '%s' requested for VM %s", req.action, vm_id)
    data = run_script("power.sh", ["--id", vm_id, "--action", req.action])

    return schemas.VmOperationResponse(
        status=data.get("status", "SUCCESS"),
        vm_id=vm_id,
        node_id=config.CLUSTER_NODE_NAME,
        message=data.get("message", f"Action {req.action} completed.")
    )

@app.delete("/vms/{vm_id}", response_model=schemas.VmOperationResponse)
def deprovision_vm(vm_id: str, _: None = Header(None)):
    """Destroy VM and clean up all resources."""
    logger.info("Deprovisioning requested for VM %s", vm_id)
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
