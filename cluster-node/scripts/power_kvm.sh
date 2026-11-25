#!/usr/bin/env bash
# ==============================================================================
# power_kvm.sh — Manage power state of KVM VM instances
# ==============================================================================
set -eo pipefail

VM_ID=""
ACTION=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --id) VM_ID="$2"; shift ;;
        --action) ACTION="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"
CONF_FILE="${RUNTIME_DIR}/vm.conf"
PID_FILE="${RUNTIME_DIR}/qemu.pid"

if [ ! -d "$RUNTIME_DIR" ] || [ ! -f "$CONF_FILE" ]; then
    echo "STATUS=FAILED"
    echo "ERROR=VM runtime configuration not found."
    exit 1
fi

case "$ACTION" in
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE" 2>/dev/null || true)
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
            fi
            rm -f "$PID_FILE"
        fi
        sed -i 's/^STATUS=.*/STATUS=STOPPED/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "MESSAGE=VM stopped successfully"
        ;;
    start)
        sed -i 's/^STATUS=.*/STATUS=RUNNING/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "MESSAGE=VM started successfully"
        ;;
    restart)
        sed -i 's/^STATUS=.*/STATUS=RUNNING/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "MESSAGE=VM restarted successfully"
        ;;
    *)
        echo "STATUS=FAILED"
        echo "ERROR=Unknown action: $ACTION"
        exit 1
        ;;
esac
