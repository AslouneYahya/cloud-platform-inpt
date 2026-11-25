#!/usr/bin/env python3
"""
Unit and Integration Tests for US5.2: Decentralized Worker Pool & Auto-Failover
Tests:
- Elastic Task Claiming: Unassigned task in shared pool claimed by first eligible worker
- Resource Aware Claiming: Task only claimed by worker with sufficient free RAM
- Watchdog & Auto-Failover: Stalled claimed task revoked and returned to shared pool
- Dead Node Rescue: Pending tasks on offline node automatically moved to shared pool
- VM Location Discovery: Correctly finds worker node hosting a VM and routes actions
"""

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "master-node"))

from app import config, nodes, schemas

class TestDecentralizedPool(unittest.TestCase):
    def setUp(self):
        self.registry = nodes.NodeRegistry()
        self.registry.nodes.clear()
        self.registry.pending_tasks.clear()
        self.registry.shared_tasks.clear()
        self.registry.claimed_tasks.clear()
        self.registry.task_results.clear()
        self.registry.task_events.clear()

        # Register two healthy workers
        for wid, ip, port in [("worker-01", "192.168.1.101", 5001), ("worker-02", "192.168.1.102", 5002)]:
            req = schemas.NodeRegisterRequest(
                node_id=wid,
                hostname=wid,
                lan_ip=ip,
                agent_port=port,
                cpu_cores=4,
                ram_total_mb=4000,
                disk_total_gb=30.0,
                disk_free_gb=20.0
            )
            self.registry.register(req)
            # Send initial healthy heartbeat
            hb = schemas.NodeHeartbeatRequest(
                node_id=wid,
                status="ONLINE",
                cpu_usage_pct=15.0,
                ram_used_mb=1000,
                ram_total_mb=4000,
                disk_free_gb=20.0,
                active_vms=0
            )
            self.registry.heartbeat(hb)

    def test_elastic_task_claim(self):
        """Verify unassigned task in shared pool is claimed by worker-01."""
        task = {
            "task_id": "task-elastic-1",
            "path": "/vms",
            "method": "POST",
            "payload": {"vm_id": "vm-test-1", "ram_mb": 512}
        }
        self.registry.shared_tasks.append(task)

        # Worker 01 polls
        polled = self.registry.poll_tasks("worker-01")
        self.assertEqual(len(polled), 1)
        self.assertEqual(polled[0]["task_id"], "task-elastic-1")

        # Shared queue should now be empty, and task tracked in claimed_tasks
        self.assertEqual(len(self.registry.shared_tasks), 0)
        self.assertIn("task-elastic-1", self.registry.claimed_tasks)
        self.assertEqual(self.registry.claimed_tasks["task-elastic-1"]["claimed_by"], "worker-01")

        # Worker 01 reports completion
        success = self.registry.complete_task("task-elastic-1", {"status": "SUCCESS", "ip": "10.244.1.50"})
        self.assertTrue(success)
        self.assertNotIn("task-elastic-1", self.registry.claimed_tasks)
        self.assertEqual(self.registry.task_results["task-elastic-1"]["executed_by"], "worker-01")

    def test_resource_aware_claiming(self):
        """Worker with insufficient RAM does not claim a high-memory task."""
        # Set worker-01 RAM to almost full (3800/4000 used -> 200MB free)
        self.registry.nodes["worker-01"]["ram_used_mb"] = 3800
        # Worker-02 has 1000/4000 used -> 3000MB free
        self.registry.nodes["worker-02"]["ram_used_mb"] = 1000

        task = {
            "task_id": "heavy-task",
            "path": "/vms",
            "method": "POST",
            "payload": {"vm_id": "vm-heavy", "ram_mb": 1024} # Needs 1024MB
        }
        self.registry.shared_tasks.append(task)

        # Worker 01 polls: should NOT be able to claim
        polled_w1 = self.registry.poll_tasks("worker-01")
        self.assertEqual(len(polled_w1), 0)
        self.assertIn(task, self.registry.shared_tasks)

        # Worker 02 polls: should claim it!
        polled_w2 = self.registry.poll_tasks("worker-02")
        self.assertEqual(len(polled_w2), 1)
        self.assertEqual(polled_w2[0]["task_id"], "heavy-task")
        self.assertEqual(self.registry.claimed_tasks["heavy-task"]["claimed_by"], "worker-02")

    def test_watchdog_auto_failover_on_stalled_worker(self):
        """If claiming worker stalls (>18s), watchdog revokes claim and worker-02 can claim it."""
        task = {
            "task_id": "stalled-task",
            "path": "/vms",
            "method": "POST",
            "payload": {"vm_id": "vm-failover", "ram_mb": 512}
        }
        # Simulate worker-01 claimed task 20 seconds ago
        self.registry.claimed_tasks["stalled-task"] = {
            "task": task,
            "claimed_by": "worker-01",
            "claimed_at": time.time() - 20.0,
            "req_ram": 512
        }

        # Worker-02 polls: triggers watchdog recovery
        polled_w2 = self.registry.poll_tasks("worker-02")
        self.assertEqual(len(polled_w2), 1)
        self.assertEqual(polled_w2[0]["task_id"], "stalled-task")
        self.assertEqual(self.registry.claimed_tasks["stalled-task"]["claimed_by"], "worker-02")

    def test_dead_node_task_rescue(self):
        """Tasks queued for a node that dies (no heartbeat >25s) are rescued to shared pool."""
        # Mark worker-01 as offline (heartbeat was 40 seconds ago)
        old_hb = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
        self.registry.nodes["worker-01"]["last_heartbeat"] = old_hb

        # Assign task directly to worker-01
        task = {
            "task_id": "rescued-task",
            "path": "/vms",
            "method": "POST",
            "payload": {"vm_id": "vm-rescued", "ram_mb": 512}
        }
        self.registry.pending_tasks["worker-01"] = [task]

        # Worker-02 polls: watchdog should rescue worker-01's task to shared pool, and worker-02 claims it
        polled_w2 = self.registry.poll_tasks("worker-02")
        self.assertEqual(len(polled_w2), 1)
        self.assertEqual(polled_w2[0]["task_id"], "rescued-task")
        self.assertEqual(self.registry.claimed_tasks["rescued-task"]["claimed_by"], "worker-02")

    def test_find_node_for_vm(self):
        """Correctly identifies which worker hosts a VM based on heartbeat telemetry."""
        # Worker-02 hosts a VM
        hb = schemas.NodeHeartbeatRequest(
            node_id="worker-02",
            status="ONLINE",
            cpu_usage_pct=10.0,
            ram_used_mb=1200,
            ram_total_mb=4000,
            disk_free_gb=18.0,
            active_vms=1,
            hosted_vms=[{"vm_id": "vm-alpha-77", "name": "web-server", "status": "RUNNING"}]
        )
        self.registry.heartbeat(hb)

        # Lookup
        found_node = self.registry.find_node_for_vm("vm-alpha-77")
        self.assertIsNotNone(found_node)
        self.assertEqual(found_node["node_id"], "worker-02")
        self.assertEqual(found_node["status"], "ONLINE")

        # Non-existent VM returns None
        self.assertIsNone(self.registry.find_node_for_vm("non-existent-vm"))

if __name__ == "__main__":
    unittest.main()
