#!/usr/bin/env python3
"""
INPT Cloud Platform — Multi-Worker Fleet Simulator (Scale-Out N > 1)
Enrolls and manages N concurrent worker agents against the Master Node.
Simulates heartbeats, hardware telemetry, task queue polling, and capacity aggregation.
"""

import argparse
import json
import logging
import random
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("MultiWorkerSimulator")

class SimulatedWorker:
    def __init__(self, node_id: str, master_url: str, cluster_token: str, index: int):
        self.node_id = node_id
        self.master_url = master_url.rstrip("/")
        self.cluster_token = cluster_token
        self.index = index
        self.lan_ip = f"192.168.59.{100 + index}"
        self.hostname = f"pi-worker-{index:02d}"
        self.cpu_cores = 4
        self.ram_total_mb = 3892
        self.ram_used_mb = 600 + (index * 120)
        self.disk_total_gb = 29.5
        self.disk_free_gb = 24.0 - (index * 1.5)
        self.active_vms = 0
        self.hosted_vms = []
        self.running = False
        self.log = logging.getLogger(self.node_id)

    def _request(self, path: str, payload: dict) -> dict:
        url = f"{self.master_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Cluster-Token": self.cluster_token,
                "User-Agent": "inpt-agent/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def register(self):
        self.log.info("Registering to master %s as %s (%s)", self.master_url, self.node_id, self.lan_ip)
        payload = {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "lan_ip": self.lan_ip,
            "agent_port": 5000 + self.index,
            "cpu_cores": self.cpu_cores,
            "ram_total_mb": self.ram_total_mb,
            "disk_total_gb": self.disk_total_gb,
            "disk_free_gb": self.disk_free_gb,
            "node_model": "Raspberry Pi 4 Model B (Simulated)"
        }
        res = self._request("/api/nodes/register", payload)
        self.log.info("Registration successful: %s", res.get("message"))

    def send_heartbeat(self):
        cpu_usage = round(random.uniform(3.0, 15.0), 1)
        cpu_temp = round(45.0 + random.uniform(0.5, 8.0) + (self.index * 1.2), 1)
        load_1m = f"{round(random.uniform(0.04, 0.25), 2):.2f}"
        jitter = random.randint(-20, 20)
        self.ram_used_mb = min(self.ram_total_mb - 200, max(450, self.ram_used_mb + jitter))

        payload = {
            "node_id": self.node_id,
            "status": "ONLINE",
            "cpu_usage_pct": cpu_usage,
            "cpu_temp": cpu_temp,
            "load_1m": load_1m,
            "ram_used_mb": self.ram_used_mb,
            "ram_total_mb": self.ram_total_mb,
            "disk_free_gb": self.disk_free_gb,
            "active_vms": self.active_vms,
            "hosted_vms": self.hosted_vms
        }
        self._request("/api/nodes/heartbeat", payload)

    def poll_tasks(self):
        url = f"{self.master_url}/api/nodes/{self.node_id}/poll"
        req = urllib.request.Request(
            url,
            headers={
                "X-Cluster-Token": self.cluster_token,
                "User-Agent": "inpt-agent/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tasks = data.get("tasks", [])
                for task in tasks:
                    self._handle_task(task)
        except Exception as e:
            self.log.debug("Poll error: %s", e)

    def _handle_task(self, task: dict):
        task_id = task.get("task_id")
        action = task.get("action") or task.get("payload", {}).get("action", "provision")
        self.log.info("Received task %s (action=%s)", task_id, action)
        time.sleep(1.0) # simulate work
        res_payload = {
            "status": "SUCCESS",
            "message": f"Task executed on simulated worker {self.node_id}",
            "ip": f"10.244.{self.index}.{random.randint(20, 240)}"
        }
        self._request(f"/api/nodes/tasks/{task_id}/complete", res_payload)
        self.log.info("Task %s completed and reported back", task_id)

    def run_loop(self):
        self.running = True
        try:
            self.register()
        except Exception as e:
            self.log.error("Initial registration failed: %s", e)

        last_hb = 0.0
        while self.running:
            now = time.time()
            if now - last_hb >= 4.0:
                try:
                    self.send_heartbeat()
                    last_hb = now
                except Exception as e:
                    self.log.warning("Heartbeat failed: %s", e)
            try:
                self.poll_tasks()
            except Exception:
                pass
            time.sleep(1.5)

    def stop(self):
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Simulate N concurrent Raspberry Pi Workers for INPT Cloud Platform")
    parser.add_argument("--workers", "-n", type=int, default=3, help="Number of concurrent worker nodes to spawn (default: 3)")
    parser.add_argument("--master-url", type=str, default="http://localhost:5000", help="Master Node base URL")
    parser.add_argument("--token", type=str, default="inpt-cluster-secret-2026", help="Cluster security token")
    parser.add_argument("--prefix", type=str, default="worker-rpi", help="Node ID prefix")
    parser.add_argument("--duration", type=int, default=0, help="Run duration in seconds (0 = run indefinitely)")
    args = parser.parse_args()

    logger.info("==================================================================")
    logger.info("Starting Multi-Worker Fleet Simulation (%d Workers -> %s)", args.workers, args.master_url)
    logger.info("==================================================================")

    workers = []
    threads = []
    for i in range(1, args.workers + 1):
        node_id = f"{args.prefix}-{i:02d}"
        w = SimulatedWorker(node_id, args.master_url, args.token, i)
        workers.append(w)
        t = threading.Thread(target=w.run_loop, daemon=True)
        threads.append(t)
        t.start()
        time.sleep(0.3)

    logger.info("All %d simulated workers are active and reporting heartbeats.", args.workers)

    # Poll capacity to demonstrate aggregation
    try:
        start_time = time.time()
        while True:
            time.sleep(5.0)
            try:
                cap_req = urllib.request.Request(f"{args.master_url}/api/cluster/capacity")
                with urllib.request.urlopen(cap_req, timeout=3) as resp:
                    cap = json.loads(resp.read().decode("utf-8"))
                    logger.info(">>> Fleet Capacity: %d Cores | %d MB RAM (%d%% used) | %d Active Nodes (%d workers)",
                                cap.get("total_cpu_cores"), cap.get("total_ram_mb"), cap.get("ram_usage_pct"),
                                cap.get("online_nodes"), cap.get("worker_nodes"))
            except Exception as e:
                logger.debug("Capacity check error: %s", e)

            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                logger.info("Duration reached (%d seconds). Stopping simulation.", args.duration)
                break
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down workers.")
    finally:
        for w in workers:
            w.stop()
        logger.info("Multi-Worker simulation stopped.")

if __name__ == "__main__":
    main()
