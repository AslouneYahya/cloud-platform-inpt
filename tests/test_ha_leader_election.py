#!/usr/bin/env python3
"""
Unit and Integration Tests for High Availability (HA) Multi-Master Leader Election
Tests:
- Master Node HA initialization and status reporting
- Worker Standby HA heartbeat probing
- Failure detection: consecutive probe failure counter and trigger conditions
- Priority-jittered Bully Election: higher-priority standby promotes first
- Split-Brain prevention: second standby detects new leader and aborts promotion
- Self-promotion callback execution
"""

import sys
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "master-node"))
sys.path.insert(0, str(Path(__file__).parent.parent / "worker-node"))

import app.ha as master_ha
import ha as worker_ha

class TestHALeaderElection(unittest.TestCase):
    def test_master_ha_initialization(self):
        """Master node initializes as ACTIVE_MASTER with priority 100."""
        mgr = master_ha.HAManager(
            node_id="master-rpi-01",
            role="MASTER",
            priority=100,
            master_url="http://127.0.0.1:5000"
        )
        status = mgr.get_status()
        self.assertEqual(status["role"], "MASTER")
        self.assertTrue(status["is_leader"])
        self.assertEqual(status["priority"], 100)
        self.assertEqual(status["active_leader"], "master-rpi-01")
        self.assertTrue(status["master_healthy"])

    def test_worker_standby_probing_healthy_master(self):
        """Worker Standby probes healthy Master and resets failure count."""
        worker = worker_ha.WorkerHAManager(
            node_id="worker-raspberrypi",
            role="STANDBY",
            priority=80,
            master_url="https://master.aslouneyahya.com"
        )

        # Mock successful HTTP probe
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b'{"status": "HEALTHY", "node_name": "master-rpi-01"}'
            mock_url.return_value.__enter__.return_value = mock_resp

            alive = worker.check_master_health()
            self.assertTrue(alive)
            self.assertEqual(worker.consecutive_failures, 0)
            self.assertEqual(worker.active_leader_id, "master-rpi-01")

    def test_failure_detection_counter(self):
        """Failed probes increment consecutive_failures until threshold."""
        worker = worker_ha.WorkerHAManager(
            node_id="worker-raspberrypi",
            role="STANDBY",
            priority=80,
            fail_threshold=3
        )

        with patch("urllib.request.urlopen", side_effect=Exception("Connection Refused")):
            self.assertFalse(worker.check_master_health())
            self.assertEqual(worker.consecutive_failures, 1)

            self.assertFalse(worker.check_master_health())
            self.assertEqual(worker.consecutive_failures, 2)

            self.assertFalse(worker.check_master_health())
            self.assertEqual(worker.consecutive_failures, 3)

            # Master is now deemed dead
            status = worker.get_status()
            self.assertFalse(status["master_healthy"])

    def test_priority_jittered_auto_promotion(self):
        """Worker promotes to ACTIVE_MASTER when threshold reached and no peer took over."""
        promoted_called = []
        def on_promoted():
            promoted_called.append(True)

        worker1 = worker_ha.WorkerHAManager(
            node_id="worker-raspberrypi",
            role="STANDBY",
            priority=80,
            fail_threshold=3,
            on_promoted=on_promoted
        )
        worker1.consecutive_failures = 3

        with patch.object(worker1, "check_master_health", return_value=False):
            with patch("time.sleep"):  # Mock backoff sleep for instant test
                promoted = worker1.trigger_election_cycle()
                self.assertTrue(promoted)
                self.assertEqual(worker1.current_role, "MASTER")
                self.assertEqual(worker1.active_leader_id, "worker-raspberrypi")
                self.assertEqual(len(promoted_called), 1)

    def test_split_brain_prevention_second_worker_aborts(self):
        """Lower priority worker-02 aborts promotion because worker-01 claimed leadership."""
        worker2 = worker_ha.WorkerHAManager(
            node_id="worker-pi-02",
            role="STANDBY",
            priority=60,
            fail_threshold=3
        )
        worker2.consecutive_failures = 3

        # First check in election_cycle returns False (old master down),
        # but final check after jitter delay returns True (worker-01 already promoted!)
        probe_results = [False, True]
        def mock_probe():
            return probe_results.pop(0)

        with patch.object(worker2, "check_master_health", side_effect=mock_probe):
            with patch("time.sleep"):
                promoted = worker2.trigger_election_cycle()
                self.assertFalse(promoted)
                self.assertEqual(worker2.current_role, "STANDBY")

if __name__ == "__main__":
    unittest.main()
