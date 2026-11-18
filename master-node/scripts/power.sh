#!/usr/bin/env bash
# ==============================================================================
# power.sh — Manage Power State of KVM VM on Raspberry Pi
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
    echo "ERROR=VM runtime configuration not found for ${VM_ID}."
    exit 1
fi

case "$ACTION" in
    stop)
        # Terminate running QEMU hardware VM process
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE" 2>/dev/null || true)
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                kill -15 "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null || true
            fi
            rm -f "$PID_FILE"
        fi
        sed -i 's/^STATUS=.*/STATUS=STOPPED/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "STATE=STOPPED"
        echo "MESSAGE=VM ${VM_ID} stopped successfully."
        ;;
    start)
        # Re-launch QEMU VM if stopped
        DISK_IMG="${RUNTIME_DIR}/disk.qcow2"
        CPU=$(grep '^CPU=' "$CONF_FILE" | cut -d= -f2 || echo 1)
        RAM=$(grep '^RAM_MB=' "$CONF_FILE" | cut -d= -f2 || echo 512)
        KVM_FLAG="-enable-kvm -cpu host"
        [ ! -c /dev/kvm ] && KVM_FLAG="-cpu cortex-a72"

        QEMU_BIN="qemu-system-aarch64"
        ! command -v "$QEMU_BIN" &>/dev/null && QEMU_BIN="qemu-system-arm"

        if command -v "$QEMU_BIN" &>/dev/null && [ -f "$DISK_IMG" ]; then
            $QEMU_BIN \
                -M virt \
                $KVM_FLAG \
                -m "${RAM}M" \
                -smp "$CPU" \
                -drive file="$DISK_IMG",if=virtio,format=qcow2 \
                -display none \
                -daemonize \
                -pidfile "$PID_FILE" 2>/dev/null || true
        fi

        sed -i 's/^STATUS=.*/STATUS=RUNNING/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "STATE=RUNNING"
        echo "MESSAGE=VM ${VM_ID} started successfully."
        ;;
    restart)
        "$0" --id "$VM_ID" --action stop || true
        sleep 1
        "$0" --id "$VM_ID" --action start
        ;;
    *)
        echo "STATUS=FAILED"
        echo "ERROR=Unknown action: $ACTION"
        exit 1
        ;;
esac
