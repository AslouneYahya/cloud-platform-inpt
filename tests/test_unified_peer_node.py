#!/usr/bin/env python3
"""
Unit and Integration Tests for Unified Peer-to-Peer Cluster Node (cluster-node)
Tests:
- PeerMesh initialization: Every Pi is an equal Peer
- Dynamic peer registration and heartbeat aggregation
- Fleet capacity calculation across homogeneous peers
- Decentralized Least-Loaded scheduling (local vs peer forwarding)
- VM location discovery (local disk vs peer telemetry)
- Distributed task queue & watchdog failover
"""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "cluster-node"))

from app import config, mesh, schemas

class TestUnifiedPeerNode(unittest.TestCase):
    def setUp(self):
        self.peer_mesh = mesh.PeerMesh(node_id="pi-node-alpha")
        self.peer_mesh.peers.clear()
        self.peer_mesh.pending_tasks.clear()
        self.peer_mesh.shared_tasks.clear()
        self.peer_mesh.claimed_tasks.clear()
        self.peer_mesh.task_results.clear()
        self.peer_mesh.task_events.clear()

    def test_peer_registration_and_list(self):
        """Peers register dynamically and are listed as equal cluster members."""
        reg_req = schemas.NodeRegisterRequest(
            node_id="pi-node-beta",
            hostname="pi-node-beta",
            lan_ip="192.168.1.102",
            agent_port=5000,
            cpu_cores=4,
            ram_total_mb=4000,
            disk_total_gb=30.0,
            disk_free_gb=25.0
        )
        self.peer_mesh.register_peer(reg_req)

        local_health = {
            "node_name": "pi-node-alpha",
            "cpu_cores": 4,
            "ram_used_mb": 1000,
            "ram_total_mb": 4000,
            "disk_free_gb": 20.0,
            "disk_total_gb": 30.0,
            "active_vms": 1
        }

        all_nodes = self.peer_mesh.get_all(local_health)
        self.assertEqual(len(all_nodes), 2)
        # Both are PEERs!
        self.assertEqual(all_nodes[0]["role"], "PEER")
        self.assertEqual(all_nodes[1]["role"], "PEER")

    def test_peer_capacity_aggregation(self):
        """Capacity aggregates across all equal peer nodes."""
        reg_req = schemas.NodeRegisterRequest(
            node_id="pi-node-beta",
            hostname="pi-node-beta",
            lan_ip="192.168.1.102",
            agent_port=5000,
            cpu_cores=4,
            ram_total_mb=4000,
            disk_total_gb=30.0,
            disk_free_gb=20.0
        )
        self.peer_mesh.register_peer(reg_req)

        hb = schemas.NodeHeartbeatRequest(
            node_id="pi-node-beta",
            status="ONLINE",
            cpu_usage_pct=20.0,
            ram_used_mb=1500,
            ram_total_mb=4000,
            disk_free_gb=20.0,
            active_vms=2
        )
        self.peer_mesh.heartbeat_peer(hb)

        local_health = {
            "node_name": "pi-node-alpha",
            "cpu_cores": 4,
            "ram_used_mb": 1000,
            "ram_total_mb": 4000,
            "disk_free_gb": 20.0,
            "disk_total_gb": 30.0,
            "active_vms": 1
        }

        cap = self.peer_mesh.get_cluster_capacity(local_health)
        self.assertEqual(cap["total_nodes"], 2)
        self.assertEqual(cap["online_nodes"], 2)
        self.assertEqual(cap["total_cpu_cores"], 8)
        self.assertEqual(cap["total_ram_mb"], 8000)
        self.assertEqual(cap["used_ram_mb"], 2500)
        self.assertEqual(cap["free_ram_mb"], 5500)
        self.assertEqual(cap["total_active_vms"], 3)

    def test_decentralized_scheduling_prefers_best_peer(self):
        """Scheduler picks the peer with lowest memory load."""
        reg_req = schemas.NodeRegisterRequest(
            node_id="pi-node-beta",
            hostname="pi-node-beta",
            lan_ip="192.168.1.102",
            agent_port=5000,
            cpu_cores=4,
            ram_total_mb=4000
        )
        self.peer_mesh.register_peer(reg_req)

        # Peer Beta is almost idle (500MB used / 4000MB -> 12% RAM)
        hb = schemas.NodeHeartbeatRequest(
            node_id="pi-node-beta",
            status="ONLINE",
            ram_used_mb=500,
            ram_total_mb=4000,
            disk_free_gb=25.0
        )
        self.peer_mesh.heartbeat_peer(hb)

        # Local Node Alpha is busy (3000MB used / 4000MB -> 75% RAM)
        local_health = {
            "node_name": "pi-node-alpha",
            "ram_used_mb": 3000,
            "ram_total_mb": 4000,
            "disk_free_gb": 10.0,
            "cpu_cores": 4
        }

        is_local, target = self.peer_mesh.schedule_best_node(ram_mb=512, local_health=local_health)
        # Beta should be chosen because it is least loaded!
        self.assertFalse(is_local)
        self.assertEqual(target["node_id"], "pi-node-beta")

    def test_find_node_for_vm_peer(self):
        """Correctly identifies which peer hosts a VM from mesh heartbeats."""
        reg_req = schemas.NodeRegisterRequest(
            node_id="pi-node-gamma",
            hostname="pi-node-gamma",
            lan_ip="192.168.1.103",
            agent_port=5000,
            cpu_cores=4,
            ram_total_mb=4000
        )
        self.peer_mesh.register_peer(reg_req)

        hb = schemas.NodeHeartbeatRequest(
            node_id="pi-node-gamma",
            status="ONLINE",
            ram_used_mb=1000,
            ram_total_mb=4000,
            disk_free_gb=20.0,
            active_vms=1,
            hosted_vms=[{"vm_id": "vm-cloud-99", "name": "database"}]
        )
        self.peer_mesh.heartbeat_peer(hb)

        is_local, node_id = self.peer_mesh.find_node_for_vm("vm-cloud-99")
        self.assertFalse(is_local)
        self.assertEqual(node_id, "pi-node-gamma")

    def test_gossip_merge_peers(self):
        """Gossip protocol merges remote peer table and updates fresher timestamps."""
        from datetime import datetime, timezone, timedelta
        now_str = datetime.now(timezone.utc).isoformat()
        remote_data = {
            "pi-node-delta": {
                "node_id": "pi-node-delta",
                "role": "PEER",
                "status": "ONLINE",
                "last_heartbeat": now_str,
                "ram_used_mb": 500,
                "ram_total_mb": 4000
            }
        }
        self.peer_mesh.merge_peers(remote_data)
        self.assertIn("pi-node-delta", self.peer_mesh.peers)
        self.assertEqual(self.peer_mesh.peers["pi-node-delta"]["ram_used_mb"], 500)

    def test_reap_stale_dead_nodes(self):
        """Nodes inactive for > 180 seconds are automatically garbage collected."""
        from datetime import datetime, timezone, timedelta
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        self.peer_mesh.peers["dead-node-99"] = {
            "node_id": "dead-node-99",
            "role": "PEER",
            "last_heartbeat": old_time
        }
        self.assertIn("dead-node-99", self.peer_mesh.peers)
        self.peer_mesh.purge_stale_peers()
        self.assertNotIn("dead-node-99", self.peer_mesh.peers)

if __name__ == "__main__":
    unittest.main()
