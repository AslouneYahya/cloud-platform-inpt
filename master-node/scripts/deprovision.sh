#!/usr/bin/env bash
# ==============================================================================
# deprovision.sh — Destroy a VM and release allocated resources on Raspberry Pi
# ==============================================================================
set -eo pipefail

VM_ID=""
VM_NAME=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --id) VM_ID="$2"; shift ;;
        --name) VM_NAME="$2"; shift ;;
        *) echo "Unknown parameter: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ -z "$VM_ID" ]; then
    echo "ERROR: --id is required." >&2
    exit 1
fi

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"

# Teardown LXD container if it exists
if command -v lxc &>/dev/null && [ -n "$VM_NAME" ]; then
    lxc stop "$VM_NAME" --force 2>/dev/null || true
    lxc delete "$VM_NAME" 2>/dev/null || true
fi

# Clean up runtime directory
if [ -d "$RUNTIME_DIR" ]; then
    rm -rf "$RUNTIME_DIR"
fi

echo "STATUS=SUCCESS"
echo "VM_ID=${VM_ID}"
echo "MESSAGE=VM ${VM_ID} resources released."
