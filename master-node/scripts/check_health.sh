#!/usr/bin/env bash
# ==============================================================================
# check_health.sh — Report hardware statistics of the Raspberry Pi node
# ==============================================================================
set -eo pipefail

CPU_CORES=$(nproc)
MEM_INFO=$(free -m | awk '/^Mem:/{print $3","$2}')
RAM_USED=$(echo "$MEM_INFO" | cut -d, -f1)
RAM_TOTAL=$(echo "$MEM_INFO" | cut -d, -f2)

DISK_FREE=$(df -BG / | awk 'NR==2{print $4}' | tr -d 'G')
ACTIVE_VMS=$(find /var/lib/inpt-cloud/vms -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l || echo "0")

echo "NODE_NAME=$(hostname)"
echo "STATUS=HEALTHY"
echo "CPU_CORES=${CPU_CORES}"
echo "RAM_USED_MB=${RAM_USED}"
echo "RAM_TOTAL_MB=${RAM_TOTAL}"
echo "DISK_FREE_GB=${DISK_FREE}"
echo "ACTIVE_VMS=${ACTIVE_VMS}"
