"""
High Availability (HA) & Decentralized Leader Election Engine for Worker Nodes
Allows any Worker Node (e.g. worker-raspberrypi, worker-pi-02) to automatically
detect Master failure and promote itself to ACTIVE_MASTER seamlessly.
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

logger = logging.getLogger("worker-ha")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

class WorkerHAManager:
    def __init__(
        self,
        node_id: str,
        role: str = "STANDBY",
        priority: int = 80,
        master_url: str = "https://master.aslouneyahya.com",
        fail_threshold: int = 3,
        check_interval: float = 3.0,
        on_promoted: Optional[Callable[[], None]] = None,
        on_demoted: Optional[Callable[[str], None]] = None
    ):
        self.node_id = node_id
        self.current_role = role  # "STANDBY", "WORKER", "MASTER"
        self.priority = priority
        self.master_url = master_url.rstrip("/")
        self.fail_threshold = fail_threshold
        self.check_interval = check_interval
        self.active_leader_id: Optional[str] = None
        self.consecutive_failures = 0
        self.last_healthy_heartbeat: Optional[datetime] = None
        self.on_promoted_callback = on_promoted
        self.on_demoted_callback = on_demoted
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    def check_master_health(self) -> bool:
        url = f"{self.master_url}/health"
        headers = {"User-Agent": "inpt-worker-ha/1.0"}
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
            logger.debug("Master probe failed at %s: %s", url, e)

        with self._lock:
            self.consecutive_failures += 1
        return False

    def trigger_election_cycle(self) -> bool:
        with self._lock:
            if self.current_role == "MASTER":
                return False

            is_alive = self.check_master_health()
            if is_alive:
                return False

            if self.consecutive_failures < self.fail_threshold:
                return False

            logger.warning("[Worker HA] 🚨 Master unreachable (%d/%d consecutive failures). Initiating election!",
                           self.consecutive_failures, self.fail_threshold)

        # Deterministic Priority Backoff
        delay = max(0.2, (100 - self.priority) * 0.05)
        logger.info("[Worker HA] Backoff delay: %.2fs (priority=%d)", delay, self.priority)
        time.sleep(delay)

        # Final check if higher-priority peer already promoted
        if self.check_master_health():
            logger.info("[Worker HA] Another peer claimed Master ('%s'). Aborting election.", self.active_leader_id)
            return False

        # Self-promotion!
        self.promote_to_master()
        return True

    def promote_to_master(self):
        with self._lock:
            old_role = self.current_role
            self.current_role = "MASTER"
            self.active_leader_id = self.node_id
            self.consecutive_failures = 0
            self.last_healthy_heartbeat = datetime.now(timezone.utc)
            logger.warning("=" * 60)
            logger.warning("[HA PROMOTION] 👑 Worker '%s' is now the ACTIVE_MASTER!", self.node_id)
            logger.warning("=" * 60)

        if self.on_promoted_callback:
            try:
                self.on_promoted_callback()
            except Exception as e:
                logger.exception("Error in Worker HA promotion callback: %s", e)

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
        if self._running:
            return
        self._running = True

        def _loop():
            logger.info("[Worker HA] Watchdog active for '%s' (priority=%d)", self.node_id, self.priority)
            while self._running:
                try:
                    if self.current_role != "MASTER":
                        self.trigger_election_cycle()
                except Exception as e:
                    logger.debug("[Worker HA] Watchdog loop error: %s", e)
                time.sleep(self.check_interval)

        self._thread = threading.Thread(target=_loop, daemon=True, name="worker-ha-watchdog")
        self._thread.start()

    def stop(self):
        self._running = False
