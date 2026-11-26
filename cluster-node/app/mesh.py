"""
Peer-to-Peer Mesh & Cluster Synchronization Engine
Every Raspberry Pi is an equal Peer capable of API coordination,
distributed scheduling, and local KVM virtualization.
"""

from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import ssl
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import uuid

from app import config, schemas

logger = logging.getLogger("cluster-mesh")
PEERS_FILE = Path("/var/lib/inpt-cloud/cluster_peers.json")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def safe_int(val, default: int = 0) -> int:
    try:
        if isinstance(val, str):
            val = val.replace(",", ".").strip()
        return int(float(val))
    except (ValueError, TypeError):
        return default

def safe_float(val, default: float = 0.0) -> float:
    try:
        if isinstance(val, str):
            val = val.replace(",", ".").strip()
        return float(val)
    except (ValueError, TypeError):
        return default

class PeerMesh:
    def __init__(self, node_id: Optional[str] = None):
        self.node_id = node_id or config.NODE_ID
        self.peers: Dict[str, dict] = {}
        self.pending_tasks: Dict[str, List[dict]] = {}
        self.shared_tasks: List[dict] = []
        self.claimed_tasks: Dict[str, dict] = {}
        self.task_results: Dict[str, dict] = {}
        self.task_events: Dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._load_from_disk()

    def _load_from_disk(self):
        if PEERS_FILE.exists():
            try:
                data = json.loads(PEERS_FILE.read_text(encoding="utf-8"))
                for nid, ndata in data.items():
                    if nid != self.node_id:
                        ndata["status"] = "OFFLINE"
                        self.peers[nid] = ndata
                logger.info("Loaded %d peer nodes from %s", len(self.peers), PEERS_FILE)
            except Exception as e:
                logger.warning("Failed to load peer registry: %s", e)

    def _save_to_disk(self):
        try:
            PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            PEERS_FILE.write_text(json.dumps(self.peers, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save peer registry: %s", e)

    def register_peer(self, req: schemas.NodeRegisterRequest) -> dict:
        now_str = datetime.now(timezone.utc).isoformat()
        peer_data = {
            "node_id": req.node_id,
            "role": "PEER",
            "hostname": req.hostname,
            "lan_ip": req.lan_ip,
            "agent_port": req.agent_port,
            "status": "ONLINE",
            "node_model": req.node_model or "Raspberry Pi 4 Model B",
            "cpu_cores": req.cpu_cores,
            "cpu_usage_pct": 0.0,
            "cpu_temp": None,
            "load_1m": "0.00",
            "ram_used_mb": 0,
            "ram_total_mb": req.ram_total_mb,
            "ram_usage_pct": 0,
            "disk_free_gb": req.disk_free_gb,
            "disk_total_gb": req.disk_total_gb,
            "active_vms": 0,
            "hosted_vms": [],
            "uptime": "just joined",
            "last_heartbeat": now_str
        }
        with self._lock:
            self.peers[req.node_id] = peer_data
            self._save_to_disk()
        logger.info("Peer node '%s' registered into mesh (%s)", req.node_id, req.lan_ip)
        return peer_data

    def heartbeat_peer(self, req: schemas.NodeHeartbeatRequest) -> Optional[dict]:
        with self._lock:
            peer = self.peers.get(req.node_id)
            if not peer:
                # Auto-enroll newly discovered peer
                peer = {
                    "node_id": req.node_id,
                    "role": "PEER",
                    "hostname": req.node_id,
                    "lan_ip": "127.0.0.1",
                    "agent_port": 5000,
                    "node_model": "Raspberry Pi 4 Model B",
                    "cpu_cores": 4,
                    "disk_total_gb": 29.0
                }
                self.peers[req.node_id] = peer

            ram_pct = int((req.ram_used_mb / req.ram_total_mb) * 100) if req.ram_total_mb > 0 else 0
            peer.update({
                "status": req.status,
                "cpu_usage_pct": req.cpu_usage_pct or 0.0,
                "cpu_temp": req.cpu_temp,
                "load_1m": req.load_1m or peer.get("load_1m", "0.00"),
                "ram_used_mb": req.ram_used_mb,
                "ram_total_mb": req.ram_total_mb,
                "ram_usage_pct": ram_pct,
                "disk_free_gb": req.disk_free_gb,
                "active_vms": req.active_vms,
                "hosted_vms": req.hosted_vms or [],
                "last_heartbeat": datetime.now(timezone.utc).isoformat()
            })
            return peer

    def merge_peers(self, remote_peers: Dict[str, dict]):
        """Gossip Synchronization: merge peer registry received from other cluster replicas."""
        with self._lock:
            changed = False
            for nid, rpeer in remote_peers.items():
                if nid == self.node_id or not isinstance(rpeer, dict):
                    continue
                local_peer = self.peers.get(nid)
                if not local_peer:
                    self.peers[nid] = rpeer
                    changed = True
                else:
                    r_hb = str(rpeer.get("last_heartbeat", ""))
                    l_hb = str(local_peer.get("last_heartbeat", ""))
                    if r_hb > l_hb:
                        local_peer.update(rpeer)
                        changed = True
            if changed:
                self._save_to_disk()

    def get_all(self, local_health: Optional[dict] = None) -> List[dict]:
        """Return all nodes in the mesh (local node + all discovered peers)."""
        now = datetime.now(timezone.utc)
        result = []

        # 1. Local Node entry
        if local_health:
            ram_used = local_health.get("ram_used_mb", 1000)
            ram_total = local_health.get("ram_total_mb", 3892)
            ram_pct = int((ram_used / ram_total) * 100) if ram_total > 0 else 0
            local_entry = {
                "node_id": self.node_id,
                "role": "PEER",
                "hostname": os.uname().nodename if hasattr(os, "uname") else self.node_id,
                "lan_ip": "127.0.0.1",
                "agent_port": config.PORT,
                "status": "ONLINE",
                "node_model": local_health.get("node_model", "Raspberry Pi 4 Model B"),
                "cpu_cores": safe_int(local_health.get("cpu_cores", 4), 4),
                "cpu_usage_pct": float(local_health.get("load_1m", "0.10")) * 25.0,
                "cpu_temp": local_health.get("cpu_temp", 48.0),
                "load_1m": str(local_health.get("load_1m", "0.08")),
                "ram_used_mb": ram_used,
                "ram_total_mb": ram_total,
                "ram_usage_pct": ram_pct,
                "disk_free_gb": local_health.get("disk_free_gb", 15.0),
                "disk_total_gb": local_health.get("disk_total_gb", 29.0),
                "active_vms": safe_int(local_health.get("active_vms", 0), 0),
                "uptime": local_health.get("uptime", "up"),
                "last_heartbeat": now.isoformat()
            }
            result.append(local_entry)

        # 2. Add Remote Peers
        with self._lock:
            for pid, peer in list(self.peers.items()):
                if pid == self.node_id:
                    continue
                last_hb_str = peer.get("last_heartbeat")
                is_online = False
                if last_hb_str:
                    try:
                        last_hb = datetime.fromisoformat(last_hb_str)
                        is_online = (now - last_hb).total_seconds() < 45
                    except Exception:
                        pass
                peer["status"] = "ONLINE" if is_online else "OFFLINE"
                result.append(peer)

        result.sort(key=lambda n: n.get("node_id", ""))
        return result

    def get_cluster_capacity(self, local_health: Optional[dict] = None) -> dict:
        all_nodes = self.get_all(local_health)
        total_cores = 0
        total_ram_mb = 0
        used_ram_mb = 0
        total_disk_gb = 0.0
        free_disk_gb = 0.0
        total_vms = 0
        online_nodes = 0

        for node in all_nodes:
            is_online = node.get("status") == "ONLINE"
            if is_online:
                online_nodes += 1
            total_cores += safe_int(node.get("cpu_cores", 4), 4)
            total_ram_mb += safe_int(node.get("ram_total_mb", 0), 0)
            used_ram_mb += safe_int(node.get("ram_used_mb", 0), 0)
            total_disk_gb += safe_float(node.get("disk_total_gb", 0.0), 0.0)
            free_disk_gb += safe_float(node.get("disk_free_gb", 0.0), 0.0)
            total_vms += safe_int(node.get("active_vms", 0), 0)

        free_ram_mb = max(0, total_ram_mb - used_ram_mb)
        ram_usage_pct = int((used_ram_mb / total_ram_mb) * 100) if total_ram_mb > 0 else 0
        used_disk_gb = max(0.0, total_disk_gb - free_disk_gb)
        disk_usage_pct = int((used_disk_gb / total_disk_gb) * 100) if total_disk_gb > 0 else 0

        return {
            "total_nodes": len(all_nodes),
            "online_nodes": online_nodes,
            "worker_nodes": max(0, len(all_nodes) - 1),
            "total_cpu_cores": total_cores,
            "total_ram_mb": total_ram_mb,
            "used_ram_mb": used_ram_mb,
            "free_ram_mb": free_ram_mb,
            "ram_usage_pct": ram_usage_pct,
            "total_disk_gb": round(total_disk_gb, 1),
            "used_disk_gb": round(used_disk_gb, 1),
            "free_disk_gb": round(free_disk_gb, 1),
            "disk_usage_pct": disk_usage_pct,
            "total_active_vms": total_vms
        }

    def schedule_best_node(self, ram_mb: int, local_health: Optional[dict] = None, target_node_id: Optional[str] = None) -> Tuple[bool, dict]:
        """
        Decentralized scheduler:
        Determines the optimal peer node to host the VM.
        Returns: (is_local: bool, node_dict: dict)
        """
        all_nodes = self.get_all(local_health)

        # 1. Target node requested
        if target_node_id:
            for n in all_nodes:
                if n["node_id"] == target_node_id or target_node_id.lower() in n["node_id"].lower():
                    if n.get("status") == "ONLINE":
                        is_local = (n["node_id"] == self.node_id)
                        return is_local, n

        # 2. Find all online candidates with enough free RAM
        candidates = []
        for n in all_nodes:
            if n.get("status") != "ONLINE":
                continue
            free_ram = n.get("ram_total_mb", 3800) - n.get("ram_used_mb", 0)
            if free_ram >= ram_mb:
                candidates.append(n)

        if not candidates:
            # Fallback to local node
            local_node = next((n for n in all_nodes if n["node_id"] == self.node_id), {"node_id": self.node_id})
            return True, local_node

        # Sort by lowest ram_usage_pct
        candidates.sort(key=lambda n: n.get("ram_usage_pct", 100))
        chosen = candidates[0]
        is_local = (chosen["node_id"] == self.node_id)
        logger.info("Scheduler selected node '%s' (is_local=%s, ram_used=%dMB)",
                    chosen["node_id"], is_local, chosen.get("ram_used_mb", 0))
        return is_local, chosen

    def find_node_for_vm(self, vm_id: str) -> Tuple[bool, Optional[str]]:
        """
        Locates whether a VM is hosted locally or on a remote peer.
        Returns: (is_local: bool, node_id: Optional[str])
        """
        # 1. Local disk inspection
        local_path = config.VMS_DIR / vm_id
        if local_path.exists() and (local_path / "vm.conf").exists():
            return True, self.node_id

        # 2. Inspect peer heartbeats
        with self._lock:
            for pid, peer in self.peers.items():
                for v in peer.get("hosted_vms", []):
                    if v.get("vm_id") == vm_id or v.get("name") == vm_id:
                        return False, pid

        return True, self.node_id

    # ── Task Queue & Watchdog for Peer Operations ─────────────────────────────

    def _recover_stalled_tasks(self):
        now = time.time()
        for task_id, claim in list(self.claimed_tasks.items()):
            if now - claim.get("claimed_at", 0) > 18.0:
                logger.warning("Watchdog: Peer '%s' stalled on task %s. Reclaiming to shared pool.",
                               claim.get("claimed_by"), task_id)
                task = claim.get("task")
                self.claimed_tasks.pop(task_id, None)
                if task:
                    self.shared_tasks.insert(0, task)

    def poll_tasks(self, node_id: str) -> List[dict]:
        with self._lock:
            self._recover_stalled_tasks()
            tasks = self.pending_tasks.pop(node_id, [])
            if tasks:
                return tasks
            if not self.shared_tasks:
                return []

            task = self.shared_tasks.pop(0)
            task_id = task["task_id"]
            self.claimed_tasks[task_id] = {
                "task": task,
                "claimed_by": node_id,
                "claimed_at": time.time()
            }
            return [task]

    def complete_task(self, task_id: str, result: dict) -> bool:
        with self._lock:
            claim = self.claimed_tasks.pop(task_id, None)
            if claim:
                result["executed_by"] = claim.get("claimed_by")
            self.task_results[task_id] = result
            evt = self.task_events.get(task_id)
            if evt:
                evt.set()
            return True if (claim is not None or evt is not None) else False

    def forward_request(self, target_node_id: str, path: str, method: str = "POST",
                        payload: Optional[dict] = None, timeout: float = 25.0) -> dict:
        task_id = str(uuid.uuid4())
        evt = threading.Event()
        task = {
            "task_id": task_id,
            "path": path,
            "method": method,
            "payload": payload or {}
        }

        with self._lock:
            self.task_events[task_id] = evt
            if target_node_id and target_node_id in self.peers and self.peers[target_node_id].get("status") == "ONLINE":
                self.pending_tasks.setdefault(target_node_id, []).append(task)
            else:
                self.shared_tasks.append(task)

        start = time.time()
        while not evt.is_set() and (time.time() - start) < timeout:
            evt.wait(timeout=1.0)
            with self._lock:
                self._recover_stalled_tasks()

        with self._lock:
            self.task_events.pop(task_id, None)
            self.claimed_tasks.pop(task_id, None)

        if evt.is_set():
            return self.task_results.pop(task_id, {})
        raise TimeoutError(f"Operation on peer {target_node_id} timed out after {timeout}s")
