#!/usr/bin/env python3
"""
Unit and Integration Tests for US5.1: Multi-Workers Scale-Out (N > 1)
Tests:
- Dynamic registration of multiple workers (worker-01, worker-02, worker-03)
- Real-time aggregation of fleet compute capacity (vCPUs, RAM pool, Disk, Active nodes)
- Least-loaded scheduling across multiple worker nodes
- API endpoint verification
"""

import sys
from pathlib import Path
import unittest

# Add master-node directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "master-node"))

from app import config, nodes, schemas

class TestMultiWorkerScaleOut(unittest.TestCase):
    def setUp(self):
        # Fresh registry instance for testing
        self.registry = nodes.NodeRegistry()
        self.registry.nodes.clear()
        self.registry.pending_tasks.clear()

    def test_multi_worker_registration_and_sorting(self):
        # Register 3 workers
        for i in [3, 1, 2]:
            req = schemas.NodeRegisterRequest(
                node_id=f"worker-rpi-{i:02d}",
                hostname=f"pi-worker-{i}",
                lan_ip=f"192.168.59.{100 + i}",
                agent_port=5000 + i,
                cpu_cores=4,
                ram_total_mb=3892,
                disk_total_gb=29.0,
                disk_free_gb=20.0
            )
            self.registry.register(req)

        master_health = {
            "node_name": "master-rpi-01",
            "cpu_cores": 4,
            "ram_used_mb": 1100,
            "ram_total_mb": 3892,
            "disk_free_gb": 15.0,
            "disk_total_gb": 29.0,
            "active_vms": 0
        }

        all_nodes = self.registry.get_all(master_health)
        self.assertEqual(len(all_nodes), 4) # 1 Master + 3 Workers
        self.assertEqual(all_nodes[0]["role"], "MASTER")
        self.assertEqual(all_nodes[1]["node_id"], "worker-rpi-01")
        self.assertEqual(all_nodes[2]["node_id"], "worker-rpi-02")
        self.assertEqual(all_nodes[3]["node_id"], "worker-rpi-03")

    def test_fleet_capacity_aggregation(self):
        # Register 2 workers with heartbeats
        w1_req = schemas.NodeRegisterRequest(
            node_id="worker-01",
            hostname="worker-01",
            lan_ip="192.168.1.101",
            agent_port=5001,
            cpu_cores=4,
            ram_total_mb=4000,
            disk_total_gb=30.0,
            disk_free_gb=25.0
        )
        self.registry.register(w1_req)
        self.registry.heartbeat(schemas.NodeHeartbeatRequest(
            node_id="worker-01",
            ram_used_mb=1000,
            ram_total_mb=4000,
            disk_free_gb=25.0,
            active_vms=1
        ))

        w2_req = schemas.NodeRegisterRequest(
            node_id="worker-02",
            hostname="worker-02",
            lan_ip="192.168.1.102",
            agent_port=5002,
            cpu_cores=4,
            ram_total_mb=4000,
            disk_total_gb=30.0,
            disk_free_gb=20.0
        )
        self.registry.register(w2_req)
        self.registry.heartbeat(schemas.NodeHeartbeatRequest(
            node_id="worker-02",
            ram_used_mb=2000,
            ram_total_mb=4000,
            disk_free_gb=20.0,
            active_vms=2
        ))

        master_health = {
            "node_name": "inpt-master",
            "cpu_cores": 4,
            "ram_used_mb": 1000,
            "ram_total_mb": 4000,
            "disk_total_gb": 30.0,
            "disk_free_gb": 20.0,
            "active_vms": 0
        }

        cap = self.registry.get_cluster_capacity(master_health)
        self.assertEqual(cap["total_nodes"], 3)
        self.assertEqual(cap["online_nodes"], 3)
        self.assertEqual(cap["worker_nodes"], 2)
        self.assertEqual(cap["total_cpu_cores"], 12) # 4 + 4 + 4
        self.assertEqual(cap["total_ram_mb"], 12000) # 4000 + 4000 + 4000
        self.assertEqual(cap["used_ram_mb"], 4000) # 1000 + 1000 + 2000
        self.assertEqual(cap["free_ram_mb"], 8000)
        self.assertEqual(cap["total_disk_gb"], 90.0)
        self.assertEqual(cap["total_active_vms"], 3) # 0 + 1 + 2

    def test_least_loaded_scheduler_across_multiple_workers(self):
        # Worker 1 has 1000MB used (25%)
        self.registry.register(schemas.NodeRegisterRequest(
            node_id="worker-01", hostname="w1", lan_ip="192.168.1.101",
            agent_port=5001, cpu_cores=4, ram_total_mb=4000
        ))
        self.registry.heartbeat(schemas.NodeHeartbeatRequest(
            node_id="worker-01", ram_used_mb=1000, ram_total_mb=4000, disk_free_gb=20.0
        ))

        # Worker 2 has 3000MB used (75%)
        self.registry.register(schemas.NodeRegisterRequest(
            node_id="worker-02", hostname="w2", lan_ip="192.168.1.102",
            agent_port=5002, cpu_cores=4, ram_total_mb=4000
        ))
        self.registry.heartbeat(schemas.NodeHeartbeatRequest(
            node_id="worker-02", ram_used_mb=3000, ram_total_mb=4000, disk_free_gb=10.0
        ))

        # Scheduler should pick Worker 1 (lowest ram_usage_pct)
        target = self.registry.schedule_target_node(ram_mb=512)
        self.assertEqual(target["node_id"], "worker-01")

        # Explicit target selection for Worker 2
        explicit_target = self.registry.schedule_target_node(ram_mb=512, target_node_id="worker-02")
        self.assertEqual(explicit_target["node_id"], "worker-02")


if __name__ == "__main__":
    unittest.main()
