from typing import List, Optional
from pydantic import BaseModel, Field

class VmProvisionRequest(BaseModel):
    vm_id: str = Field(..., description="Unique UUIDv7 of the VM")
    name: str = Field(..., min_length=3, max_length=50)
    os: str = Field(..., description="Requested OS template")
    cpu: int = Field(..., ge=1, le=4)
    ram_mb: int = Field(..., ge=128, le=4096)
    disk_gb: int = Field(..., ge=1, le=100)
    ssh_key: Optional[str] = None
    initial_password: Optional[str] = None
    open_ports: List[int] = Field(default_factory=lambda: [22])
    target_node_id: Optional[str] = None

class VmActionRequest(BaseModel):
    action: str = Field(..., description="'start', 'stop', or 'restart'")

class VmOperationResponse(BaseModel):
    status: str
    vm_id: str
    ip_address: Optional[str] = None
    node_id: Optional[str] = None
    message: str
    output: Optional[str] = None

class ClusterHealthResponse(BaseModel):
    node_name: str
    status: str
    cpu_cores: int
    ram_used_mb: int
    ram_total_mb: int
    disk_free_gb: float
    active_vms: int
    node_model: Optional[str] = "Raspberry Pi 4 Model B"
    uptime: Optional[str] = None
    cpu_temp: Optional[float] = None
    load_1m: Optional[str] = None
    ram_usage_pct: Optional[int] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_usage_pct: Optional[int] = None

class VmExecRequest(BaseModel):
    command: str = Field(..., max_length=1000)

class VmExecResponse(BaseModel):
    status: str
    vm_id: str
    command: str
    stdout: str
    stderr: Optional[str] = ""
    exit_code: int
    executed_at: str

class NodeRegisterRequest(BaseModel):
    node_id: str = Field(..., description="Unique node identifier, e.g. worker-pi-01")
    hostname: str
    lan_ip: str
    agent_port: int = 5001
    cpu_cores: int = 4
    ram_total_mb: int
    disk_total_gb: Optional[float] = 0.0
    disk_free_gb: Optional[float] = 0.0
    node_model: Optional[str] = "Raspberry Pi 4 Model B"

class NodeHeartbeatRequest(BaseModel):
    node_id: str
    status: str = "ONLINE"
    cpu_usage_pct: Optional[float] = 0.0
    cpu_temp: Optional[float] = None
    load_1m: Optional[str] = None
    ram_used_mb: int
    ram_total_mb: int
    disk_free_gb: float
    active_vms: int = 0
    hosted_vms: Optional[List[dict]] = Field(default_factory=list)

class NodeInfo(BaseModel):
    node_id: str
    role: str = "WORKER"  # "MASTER" or "WORKER"
    hostname: str
    lan_ip: str
    agent_port: int
    status: str  # "ONLINE", "OFFLINE", "DEGRADED"
    node_model: str = "Raspberry Pi 4 Model B"
    cpu_cores: int
    cpu_usage_pct: float = 0.0
    cpu_temp: Optional[float] = None
    load_1m: Optional[str] = None
    ram_used_mb: int
    ram_total_mb: int
    ram_usage_pct: int = 0
    disk_free_gb: float
    disk_total_gb: Optional[float] = None
    active_vms: int = 0
    uptime: Optional[str] = None
    last_heartbeat: str

class ClusterCapacityResponse(BaseModel):
    total_nodes: int
    online_nodes: int
    worker_nodes: int
    total_cpu_cores: int
    total_ram_mb: int
    used_ram_mb: int
    free_ram_mb: int
    ram_usage_pct: int
    total_disk_gb: float
    used_disk_gb: float
    free_disk_gb: float
    disk_usage_pct: int
    total_active_vms: int


