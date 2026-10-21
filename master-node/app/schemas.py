from typing import List, Optional
from pydantic import BaseModel, Field

class VmProvisionRequest(BaseModel):
    vm_id: str = Field(..., description="Unique UUIDv7 of the VM")
    name: str = Field(..., min_length=3, max_length=50)
    os: str = Field(..., description="Requested OS template")
    cpu: int = Field(..., ge=1, le=4)
    ram_mb: int = Field(..., ge=512, le=4096)
    disk_gb: int = Field(..., ge=10, le=100)
    ssh_key: Optional[str] = None
    initial_password: Optional[str] = None
    open_ports: List[int] = Field(default_factory=lambda: [22])

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
