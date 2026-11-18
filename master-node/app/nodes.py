import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import urllib.request
import urllib.error

from app import config, schemas

logger = logging.getLogger("cluster-nodes")

REGISTRY_FILE = Path("/var/lib/inpt-cloud/cluster_nodes.json")

class NodeRegistry:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
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

        return result

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

    def forward_request(self, node: dict, path: str, method: str = "POST", payload: Optional[dict] = None) -> dict:
        """
        Forwards VM operations to the Worker Node Agent over the local cluster LAN.
        Tries physical LAN IP first, then mDNS hostname fallback.
        """
        lan_ip = node.get("lan_ip")
        hostname = node.get("hostname")
        port = node.get("agent_port", 5001)

        targets = []
        if lan_ip and not lan_ip.startswith("172.16.") and lan_ip != "127.0.0.1":
            targets.append(lan_ip)
        if hostname:
            targets.append(f"{hostname}.local")
            targets.append(hostname)
        if lan_ip and lan_ip not in targets:
            targets.append(lan_ip)

        headers = {
            "Content-Type": "application/json",
            "X-Cluster-Token": config.API_KEY,
            "User-Agent": "inpt-master/1.0"
        }
        data = json.dumps(payload).encode("utf-8") if payload else None

        last_err = None
        for host in targets:
            url = f"http://{host}:{port}{path}"
            logger.info("Forwarding %s to Worker '%s' at %s", method, node["node_id"], url)
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_body = resp.read().decode("utf-8")
                    return json.loads(resp_body) if resp_body else {"status": "SUCCESS"}
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8")
                logger.error("Worker %s HTTP %d error: %s", node["node_id"], e.code, err_text)
                raise RuntimeError(f"Worker node error ({e.code}): {err_text}")
            except Exception as e:
                last_err = e
                logger.warning("Failed route to Worker %s at %s: %s (trying next target)", node["node_id"], url, e)

        raise RuntimeError(f"Failed to communicate with worker {node['node_id']}: {last_err}")

node_registry = NodeRegistry()
