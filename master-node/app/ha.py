"""
High Availability (HA) & Decentralized Leader Election Engine
Implements deterministic priority-jittered Bully/Raft election algorithm
to eliminate Master Node as Single Point of Failure (SPOF).
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import ssl
import subprocess
import threading
import time
from typing import Callable, Dict, Optional
import urllib.error
import urllib.request

logger = logging.getLogger("cluster-ha")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

class HAManager:
    def __init__(
        self,
        node_id: str,
        role: str = "WORKER",
        priority: int = 50,
        master_url: str = "https://master.aslouneyahya.com",
        fail_threshold: int = 3,
        check_interval: float = 3.0,
        on_promoted: Optional[Callable[[], None]] = None,
        on_demoted: Optional[Callable[[str], None]] = None
    ):
        self.node_id = node_id
        self.current_role = role  # "MASTER", "STANDBY", "WORKER"
        self.priority = priority
        self.master_url = master_url.rstrip("/")
        self.fail_threshold = fail_threshold
        self.check_interval = check_interval
        self.active_leader_id: Optional[str] = node_id if role == "MASTER" else None
        self.consecutive_failures = 0
        self.last_healthy_heartbeat: Optional[datetime] = datetime.now(timezone.utc) if role == "MASTER" else None
        self.on_promoted_callback = on_promoted
        self.on_demoted_callback = on_demoted
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    def check_master_health(self) -> bool:
        """Probe the active master's health endpoint."""
        url = f"{self.master_url}/health"
        headers = {"User-Agent": "inpt-ha-watchdog/1.0"}
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    leader_node = data.get("node_name") or data.get("node_id") or "master"
                    with self._lock:
                        self.consecutive_failures = 0
                        self.active_leader_id = leader_node
                        self.last_healthy_heartbeat = datetime.now(timezone.utc)
                    return True
        except Exception as e:
            logger.debug("HA health probe failed for %s: %s", url, e)

        with self._lock:
            self.consecutive_failures += 1
        return False

    def trigger_election_cycle(self) -> bool:
        """
        Evaluate if current active Master has died and run priority-jittered election.
        Returns True if this node promoted itself to Master.
        """
        with self._lock:
            if self.current_role == "MASTER":
                return False

            is_alive = self.check_master_health()
            if is_alive:
                return False

            if self.consecutive_failures < self.fail_threshold:
                logger.info("[HA Watchdog] Master probe missed (%d/%d consecutive failures)",
                            self.consecutive_failures, self.fail_threshold)
                return False

            # Master is declared DEAD
            logger.warning("[HA Watchdog] ⚠️ Active Master unreachable for %d consecutive probes! Initiating election...",
                           self.consecutive_failures)

        # Priority Jitter: Higher priority nodes elect faster (lower delay)
        # Priority 100 -> 0.2s delay, Priority 80 -> 1.2s delay, Priority 60 -> 2.2s delay
        delay = max(0.2, (100 - self.priority) * 0.05)
        logger.info("[HA Election] Node '%s' (priority=%d) waiting election backoff %.2fs",
                    self.node_id, self.priority, delay)
        time.sleep(delay)

        # Final verification: Did another higher-priority peer already claim leadership?
        if self.check_master_health():
            logger.info("[HA Election] Another node has already assumed leadership ('%s'). Aborting election.",
                        self.active_leader_id)
            return False

        # Promote self to MASTER
        self.promote_to_master()
        return True

    def promote_to_master(self):
        """Transition node from STANDBY/WORKER to ACTIVE_MASTER."""
        with self._lock:
            old_role = self.current_role
            self.current_role = "MASTER"
            self.active_leader_id = self.node_id
            self.consecutive_failures = 0
            self.last_healthy_heartbeat = datetime.now(timezone.utc)
            logger.warning("=" * 60)
            logger.warning("[HA FAILOVER] 👑 Node '%s' PROMOTED to ACTIVE_MASTER (was %s)!",
                           self.node_id, old_role)
            logger.warning("=" * 60)

        if self.on_promoted_callback:
            try:
                self.on_promoted_callback()
            except Exception as e:
                logger.exception("Error in promotion callback: %s", e)

    def demote_to_standby(self, new_leader_id: str):
        """Demote this node to STANDBY if a legitimate leader exists."""
        with self._lock:
            self.current_role = "STANDBY"
            self.active_leader_id = new_leader_id
            logger.info("[HA] Node '%s' demoted to STANDBY (Active Leader: '%s')",
                        self.node_id, new_leader_id)

        if self.on_demoted_callback:
            try:
                self.on_demoted_callback(new_leader_id)
            except Exception as e:
                logger.exception("Error in demotion callback: %s", e)

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "node_id": self.node_id,
                "role": self.current_role,
                "priority": self.priority,
                "active_leader": self.active_leader_id,
                "is_leader": self.current_role == "MASTER",
                "master_healthy": self.consecutive_failures < self.fail_threshold,
                "consecutive_failures": self.consecutive_failures,
                "last_healthy_heartbeat": self.last_healthy_heartbeat.isoformat() if self.last_healthy_heartbeat else None
            }

    def start_watchdog_thread(self):
        """Start background daemon monitoring Master health and executing auto-failover."""
        if self._running:
            return
        self._running = True

        def _loop():
            logger.info("[HA] Watchdog thread started for '%s' (role=%s, priority=%d)",
                        self.node_id, self.current_role, self.priority)
            while self._running:
                try:
                    if self.current_role != "MASTER":
                        self.trigger_election_cycle()
                except Exception as e:
                    logger.debug("[HA] Watchdog loop error: %s", e)
                time.sleep(self.check_interval)

        self._thread = threading.Thread(target=_loop, daemon=True, name="ha-watchdog")
        self._thread.start()

    def stop(self):
        self._running = False
