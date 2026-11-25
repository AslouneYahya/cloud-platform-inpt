import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import threading
import time
from typing import Dict, List, Optional
import urllib.request
import urllib.error
import uuid

from app import config, schemas

logger = logging.getLogger("cluster-nodes")

REGISTRY_FILE = Path("/var/lib/inpt-cloud/cluster_nodes.json")

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

class NodeRegistry:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.pending_tasks: Dict[str, List[dict]] = {}
        self.shared_tasks: List[dict] = []
        self.claimed_tasks: Dict[str, dict] = {}
        self.task_results: Dict[str, dict] = {}
        self.task_events: Dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._load_from_disk()

    def _load_from_disk(self):
        if REGISTRY_FILE.exists():
            try:
                data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
                pruned = False
                for node_id, node_data in data.items():
                    if "test" in str(node_id).lower() or "test" in str(node_data.get("hostname", "")).lower():
                        pruned = True
                        continue
                    # Keep persistent config, but mark status until heartbeat
                    node_data["status"] = "OFFLINE"
                    self.nodes[node_id] = node_data
                if pruned:
                    self._save_to_disk()
                logger.info("Loaded %d cluster nodes from %s", len(self.nodes), REGISTRY_FILE)
            except Exception as e:
                logger.warning("Failed to load node registry from %s: %s", REGISTRY_FILE, e)

    def delete_node(self, node_id: str) -> bool:
        """Remove a node from the cluster registry permanently."""
        to_del = [k for k in self.nodes if k == node_id or k.lower() == node_id.lower()]
        if to_del:
            for k in to_del:
                del self.nodes[k]
            self._save_to_disk()
            logger.info("Node '%s' permanently removed from registry", node_id)
            return True
        return False

    def _save_to_disk(self):
        try:
            REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            REGISTRY_FILE.write_text(json.dumps(self.nodes, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist node registry: %s", e)

    def register(self, req: schemas.NodeRegisterRequest) -> dict:
        now_str = datetime.now(timezone.utc).isoformat()
        node_data = {
            "node_id": req.node_id,
            "role": "WORKER",
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
            "uptime": "just registered",
            "last_heartbeat": now_str
        }
        self.nodes[req.node_id] = node_data
        self._save_to_disk()
        logger.info("Node '%s' (%s - %s) successfully registered", req.node_id, req.hostname, req.lan_ip)
        return node_data

    def heartbeat(self, req: schemas.NodeHeartbeatRequest) -> Optional[dict]:
        node = self.nodes.get(req.node_id)
        if not node:
            logger.warning("Heartbeat received from unknown node: %s", req.node_id)
            return None

        ram_pct = int((req.ram_used_mb / req.ram_total_mb) * 100) if req.ram_total_mb > 0 else 0

        node.update({
            "status": req.status,
            "cpu_usage_pct": req.cpu_usage_pct or 0.0,
            "cpu_temp": req.cpu_temp,
            "load_1m": req.load_1m or node.get("load_1m", "0.00"),
            "ram_used_mb": req.ram_used_mb,
            "ram_total_mb": req.ram_total_mb,
            "ram_usage_pct": ram_pct,
            "disk_free_gb": req.disk_free_gb,
            "active_vms": req.active_vms,
            "hosted_vms": req.hosted_vms or [],
            "last_heartbeat": datetime.now(timezone.utc).isoformat()
        })
        return node

    def get_all(self, master_health: Optional[dict] = None) -> List[dict]:
        now = datetime.now(timezone.utc)
        result = []

        # 1. Always inject Master Node as first node
        if master_health:
            ram_used = master_health.get("ram_used_mb", 1000)
            ram_total = master_health.get("ram_total_mb", 3800)
            ram_pct = int((ram_used / ram_total) * 100) if ram_total > 0 else 0
            master_entry = {
                "node_id": config.CLUSTER_NODE_NAME,
                "role": "MASTER",
                "hostname": os.uname().nodename if hasattr(os, "uname") else "inpt-master",
                "lan_ip": "127.0.0.1",
                "agent_port": 5000,
                "status": "ONLINE",
                "node_model": master_health.get("node_model", "Raspberry Pi 4 Model B"),
                "cpu_cores": master_health.get("cpu_cores", 4),
                "cpu_usage_pct": float(master_health.get("load_1m", "0.10")) * 25.0,
                "cpu_temp": master_health.get("cpu_temp", 45.0),
                "load_1m": str(master_health.get("load_1m", "0.08")),
                "ram_used_mb": ram_used,
                "ram_total_mb": ram_total,
                "ram_usage_pct": master_health.get("ram_usage_pct", ram_pct),
                "disk_free_gb": master_health.get("disk_free_gb", 15.0),
                "disk_total_gb": master_health.get("disk_total_gb", 29.0),
                "active_vms": master_health.get("active_vms", 0),
                "uptime": master_health.get("uptime", "up"),
                "last_heartbeat": now.isoformat()
            }
            result.append(master_entry)

        # 2. Add Worker Nodes (evaluating if any is timed out / OFFLINE)
        pruned = False
        for node_id, node in list(self.nodes.items()):
            if "test" in str(node_id).lower() or "test" in str(node.get("hostname", "")).lower():
                self.nodes.pop(node_id, None)
                pruned = True
                continue

            last_hb_str = node.get("last_heartbeat")
            is_online = False
            if last_hb_str:
                try:
                    last_hb = datetime.fromisoformat(last_hb_str)
                    if now - last_hb < timedelta(seconds=30):
                        is_online = True
                except Exception:
                    pass

            node["status"] = "ONLINE" if is_online else "OFFLINE"
            result.append(node)

        if pruned:
            self._save_to_disk()

        # Sort: Master first, then workers alphabetically by node_id
        result.sort(key=lambda n: (0 if n.get("role") == "MASTER" else 1, n.get("node_id", "")))
        return result

    def get_cluster_capacity(self, master_health: Optional[dict] = None) -> dict:
        """
        Aggregate total computing capacity and utilization across all cluster nodes (Master + N Workers).
        Provides unified fleet metrics for scale-out monitoring (Cores, RAM pool, Disk, Active nodes).
        """
        all_nodes = self.get_all(master_health)
        total_cores = 0
        total_ram_mb = 0
        used_ram_mb = 0
        total_disk_gb = 0.0
        free_disk_gb = 0.0
        total_vms = 0
        online_nodes = 0
        worker_nodes = 0

        for node in all_nodes:
            is_online = node.get("status") == "ONLINE"
            if is_online:
                online_nodes += 1
            if node.get("role") == "WORKER":
                worker_nodes += 1

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
            "worker_nodes": worker_nodes,
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

    def get_node(self, node_id: str, master_health: Optional[dict] = None) -> Optional[dict]:
        all_nodes = self.get_all(master_health)
        for n in all_nodes:
            if n["node_id"] == node_id:
                return n
        return None

    def schedule_target_node(self, ram_mb: int, master_health: Optional[dict] = None, target_node_id: Optional[str] = None) -> dict:
        """
        Least-Loaded Scheduler:
        Picks the active node with enough free RAM that has the lowest RAM utilization percentage.
        Prefers Worker nodes over Master node so Master stays dedicated to orchestration.
        If target_node_id is specified, routes directly to that node if it is online.
        """
        all_nodes = self.get_all(master_health)

        if target_node_id:
            for n in all_nodes:
                if n["node_id"] == target_node_id or target_node_id.lower() in n["node_id"].lower():
                    if n.get("status") == "ONLINE":
                        logger.info("Explicit target node requested: '%s'", n["node_id"])
                        return n

        online_candidates = []

        for node in all_nodes:
            if node["status"] != "ONLINE":
                continue
            free_ram = node["ram_total_mb"] - node["ram_used_mb"]
            if free_ram >= ram_mb:
                online_candidates.append(node)

        if not online_candidates:
            # Fallback to Master
            logger.warning("No online node has %dMB free RAM. Defaulting to Master.", ram_mb)
            return all_nodes[0] if all_nodes else {"node_id": config.CLUSTER_NODE_NAME, "role": "MASTER"}

        # Sort: workers first, then lowest ram_usage_pct
        online_candidates.sort(key=lambda n: (0 if n["role"] == "WORKER" else 1, n.get("ram_usage_pct", 100)))
        chosen = online_candidates[0]
        logger.info("Scheduler assigned VM to node '%s' (role=%s, ram_used=%dMB/%dMB)",
                    chosen["node_id"], chosen["role"], chosen["ram_used_mb"], chosen["ram_total_mb"])
        return chosen

    def _recover_stalled_tasks(self):
        """
        Watchdog & Auto-failover:
        1. Revokes tasks claimed by a worker that failed to complete within 18s or went offline,
           and pushes them back to shared_tasks for healthy workers.
        2. Detects pending tasks assigned to offline nodes and transfers them to the elastic shared pool.
        """
        now = time.time()
        now_dt = datetime.now(timezone.utc)

        # 1. Check claimed tasks for timeout or dead claiming worker
        for task_id, claim in list(self.claimed_tasks.items()):
            claimed_by = claim.get("claimed_by")
            claimed_at = claim.get("claimed_at", 0)
            worker = self.nodes.get(claimed_by, {})
            last_hb_str = worker.get("last_heartbeat")
            is_worker_alive = True
            if last_hb_str:
                try:
                    is_worker_alive = (now_dt - datetime.fromisoformat(last_hb_str)).total_seconds() < 25
                except Exception:
                    pass

            if (now - claimed_at > 18.0) or not is_worker_alive:
                logger.warning("Watchdog: Worker '%s' stalled on task %s (alive=%s). Reclaiming task.",
                               claimed_by, task_id, is_worker_alive)
                task = claim.get("task")
                self.claimed_tasks.pop(task_id, None)
                if task:
                    self.shared_tasks.insert(0, task)

        # 2. Check pending tasks queued for nodes that went OFFLINE
        for node_id, tasks in list(self.pending_tasks.items()):
            node = self.nodes.get(node_id, {})
            last_hb_str = node.get("last_heartbeat")
            is_alive = False
            if last_hb_str:
                try:
                    is_alive = (now_dt - datetime.fromisoformat(last_hb_str)).total_seconds() < 25
                except Exception:
                    pass
            if not is_alive and tasks:
                logger.warning("Watchdog: Node '%s' is OFFLINE. Moving %d pending tasks to shared pool.",
                               node_id, len(tasks))
                self.shared_tasks.extend(tasks)
                self.pending_tasks[node_id] = []

    def poll_tasks(self, node_id: str) -> List[dict]:
        """
        Elastic Task Polling:
        1. Worker checks its dedicated task queue.
        2. If empty, worker checks the shared elastic pool for unassigned tasks it can handle.
        """
        with self._lock:
            self._recover_stalled_tasks()

            # 1. Dedicated node tasks
            tasks = self.pending_tasks.pop(node_id, [])
            if not tasks:
                for k in list(self.pending_tasks.keys()):
                    if k.lower() == node_id.lower() or node_id.lower() in k.lower():
                        tasks = self.pending_tasks.pop(k, [])
                        break

            if tasks:
                return tasks

            # 2. Elastic shared pool tasks
            if not self.shared_tasks:
                return []

            node = self.nodes.get(node_id, {})
            free_ram = node.get("ram_total_mb", 3800) - node.get("ram_used_mb", 0)

            # Find first task that fits node capacity
            for idx, task in enumerate(self.shared_tasks):
                payload = task.get("payload", {})
                req_ram = safe_int(payload.get("ram_mb", 256), 256)
                if free_ram >= req_ram or task.get("method") in ("DELETE", "POST") and "/action" in task.get("path", ""):
                    claimed_task = self.shared_tasks.pop(idx)
                    task_id = claimed_task["task_id"]
                    self.claimed_tasks[task_id] = {
                        "task": claimed_task,
                        "claimed_by": node_id,
                        "claimed_at": time.time(),
                        "req_ram": req_ram
                    }
                    logger.info("Worker '%s' claimed elastic task %s (%s %s)",
                                node_id, task_id, claimed_task.get("method"), claimed_task.get("path"))
                    return [claimed_task]

            return []

    def complete_task(self, task_id: str, result: dict) -> bool:
        """Worker reports task execution output back to Master."""
        with self._lock:
            claim = self.claimed_tasks.pop(task_id, None)
            if claim:
                result["executed_by"] = claim.get("claimed_by")
            self.task_results[task_id] = result
            evt = self.task_events.get(task_id)
            if evt:
                evt.set()
            return True if (claim is not None or evt is not None) else False

    def find_node_for_vm(self, vm_id: str) -> Optional[dict]:
        """
        Locates which cluster node hosts the specified VM instance.
        Inspects worker telemetry (hosted_vms) and local Master storage.
        """
        now = datetime.now(timezone.utc)
        # 1. Search worker nodes
        for node_id, node in self.nodes.items():
            last_hb = node.get("last_heartbeat")
            is_online = False
            if last_hb:
                try:
                    is_online = (now - datetime.fromisoformat(last_hb)).total_seconds() < 30
                except Exception:
                    pass

            for v in node.get("hosted_vms", []):
                if v.get("vm_id") == vm_id or v.get("name") == vm_id:
                    node_copy = dict(node)
                    node_copy["status"] = "ONLINE" if is_online else "OFFLINE"
                    return node_copy

        # 2. Check local master storage
        master_vm_path = Path("/var/lib/inpt-cloud/vms") / vm_id
        if master_vm_path.exists():
            return {
                "node_id": config.CLUSTER_NODE_NAME,
                "role": "MASTER",
                "status": "ONLINE"
            }

        return None

    def forward_request(self, node: Optional[dict], path: str, method: str = "POST",
                        payload: Optional[dict] = None, timeout: float = 25.0) -> dict:
        """
        Dispatches operations to a specific Worker Node or the Elastic Shared Pool.
        Monitored by active watchdog with automatic failover and completion event notification.
        """
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
            target_id = node.get("node_id") if node else None
            # If target node is specified and online, put in its queue
            if target_id and node.get("status") == "ONLINE" and node.get("role") == "WORKER":
                self.pending_tasks.setdefault(target_id, []).append(task)
                logger.info("Queued targeted task %s (%s %s) for Worker '%s'", task_id, method, path, target_id)
            else:
                # Add to decentralized elastic shared pool
                self.shared_tasks.append(task)
                logger.info("Queued elastic task %s (%s %s) in shared pool (target was %s)",
                            task_id, method, path, target_id or "NONE")

        # Wait with active watchdog loop
        start_time = time.time()
        while not evt.is_set() and (time.time() - start_time) < timeout:
            evt.wait(timeout=1.0)
            with self._lock:
                self._recover_stalled_tasks()

        with self._lock:
            self.task_events.pop(task_id, None)
            self.claimed_tasks.pop(task_id, None)
            # Remove from queues if still unexecuted
            if task in self.shared_tasks:
                self.shared_tasks.remove(task)
            for q in self.pending_tasks.values():
                if task in q:
                    q.remove(task)

        if evt.is_set():
            res = self.task_results.pop(task_id, {})
            exec_node = res.get("executed_by") or (node.get("node_id") if node else "worker")
            logger.info("Task %s successfully completed by '%s'", task_id, exec_node)
            return res
        else:
            target_name = node.get("node_id") if node else "elastic-pool"
            logger.warning("Task %s timed out after %.1fs on target '%s'", task_id, timeout, target_name)
            raise TimeoutError(f"Task {task_id} timed out after {timeout}s on {target_name}")

node_registry = NodeRegistry()
