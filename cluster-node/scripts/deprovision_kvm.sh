#!/usr/bin/env bash
# ==============================================================================
# deprovision_kvm.sh — Destroy KVM VM and clean up disk overlay
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

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"
PID_FILE="${RUNTIME_DIR}/qemu.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi
fi

# Clean up instance CoW disk and config
rm -rf "$RUNTIME_DIR"

echo "STATUS=SUCCESS"
echo "VM_ID=${VM_ID}"
echo "MESSAGE=VM destroyed and storage deallocated"
