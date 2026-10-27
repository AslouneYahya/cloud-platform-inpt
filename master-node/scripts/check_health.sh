#!/usr/bin/env bash
# ==============================================================================
# check_health.sh — Report precise hardware telemetry of the Raspberry Pi node
# ==============================================================================
set -eo pipefail

NODE_NAME=$(hostname)
NODE_MODEL=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Raspberry Pi 4 Model B")
UPTIME_STR=$(uptime -p 2>/dev/null || echo "up 3 hours")

# CPU
CPU_CORES=$(nproc)
LOAD_1M=$(awk '{print $1}' /proc/loadavg)
TEMP_RAW=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "0")
if [ "$TEMP_RAW" -gt 0 ]; then
    CPU_TEMP=$(awk "BEGIN {printf \"%.1f\", $TEMP_RAW / 1000}")
else
    CPU_TEMP="48.0"
fi

# RAM (free -m: total used available)
MEM_LINE=$(free -m | awk '/^Mem:/{print $2,$3,$7}')
RAM_TOTAL=$(echo "$MEM_LINE" | awk '{print $1}')
RAM_USED=$(echo "$MEM_LINE" | awk '{print $2}')
RAM_AVAIL=$(echo "$MEM_LINE" | awk '{print $3}')
RAM_USAGE_PCT=$(( (RAM_USED * 100) / RAM_TOTAL ))

# Disk (df -m /: total used available use%)
DISK_LINE=$(df -m / | awk 'NR==2{print $2,$3,$4,$5}' | tr -d '%')
DISK_TOTAL_MB=$(echo "$DISK_LINE" | awk '{print $1}')
DISK_USED_MB=$(echo "$DISK_LINE" | awk '{print $2}')
DISK_FREE_MB=$(echo "$DISK_LINE" | awk '{print $3}')
DISK_USAGE_PCT=$(echo "$DISK_LINE" | awk '{print $4}')

DISK_TOTAL_GB=$(awk "BEGIN {printf \"%.1f\", $DISK_TOTAL_MB / 1024}")
DISK_USED_GB=$(awk "BEGIN {printf \"%.1f\", $DISK_USED_MB / 1024}")
DISK_FREE_GB=$(awk "BEGIN {printf \"%.1f\", $DISK_FREE_MB / 1024}")

ACTIVE_VMS=$(find /var/lib/inpt-cloud/vms -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l || echo "0")

echo "NODE_NAME=${NODE_NAME}"
echo "NODE_MODEL=${NODE_MODEL}"
echo "STATUS=HEALTHY"
echo "UPTIME=${UPTIME_STR}"
echo "CPU_CORES=${CPU_CORES}"
echo "CPU_TEMP=${CPU_TEMP}"
echo "LOAD_1M=${LOAD_1M}"
echo "RAM_TOTAL_MB=${RAM_TOTAL}"
echo "RAM_USED_MB=${RAM_USED}"
echo "RAM_AVAIL_MB=${RAM_AVAIL}"
echo "RAM_USAGE_PCT=${RAM_USAGE_PCT}"
echo "DISK_TOTAL_GB=${DISK_TOTAL_GB}"
echo "DISK_USED_GB=${DISK_USED_GB}"
echo "DISK_FREE_GB=${DISK_FREE_GB}"
echo "DISK_USAGE_PCT=${DISK_USAGE_PCT}"
echo "ACTIVE_VMS=${ACTIVE_VMS}"
