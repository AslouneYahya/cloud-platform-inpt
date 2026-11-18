#!/usr/bin/env bash
# ==============================================================================
# deprovision.sh — Destroy a VM and release allocated resources on Raspberry Pi
# ==============================================================================
set -eo pipefail

VM_ID=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --id) VM_ID="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

if [ -z "$VM_ID" ]; then
    echo "ERROR=--id is required."
    exit 1
fi

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"
PID_FILE="${RUNTIME_DIR}/qemu.pid"

# Terminate active QEMU process if running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi
fi

# Clean up runtime directory & CoW overlay disk
if [ -d "$RUNTIME_DIR" ]; then
    rm -rf "$RUNTIME_DIR"
fi

echo "STATUS=SUCCESS"
echo "VM_ID=${VM_ID}"
echo "MESSAGE=VM ${VM_ID} destroyed and storage deallocated."
