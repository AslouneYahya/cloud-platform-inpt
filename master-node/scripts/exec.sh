#!/usr/bin/env bash
# ==============================================================================
# exec.sh — Execute command in VM or cluster node context
# ==============================================================================
set -o pipefail

VM_ID=""
CMD=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --id) VM_ID="$2"; shift ;;
        --cmd) CMD="$2"; shift ;;
        *) echo "Unknown parameter: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ -z "$CMD" ]; then
    echo "ERROR: --cmd is mandatory" >&2
    exit 1
fi

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"
CONF_FILE="$RUNTIME_DIR/vm.conf"
VM_NAME="inpt-vm"
VM_IP=""

if [ -f "$CONF_FILE" ]; then
    VM_NAME=$(grep '^NAME=' "$CONF_FILE" | cut -d= -f2)
    VM_IP=$(grep '^IP=' "$CONF_FILE" | cut -d= -f2)
fi

# 1. Native LXD container execution if container is running
if command -v lxc &>/dev/null && [ -n "$VM_NAME" ] && lxc list -c n --format csv | grep -q "^${VM_NAME}$"; then
    exec lxc exec "$VM_NAME" -- sh -c "$CMD"
fi

# 2. SSH connection if target IP is alive
if [ -n "$VM_IP" ] && command -v nc &>/dev/null && nc -z -w 1 "$VM_IP" 22 2>/dev/null; then
    exec ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 "root@$VM_IP" "$CMD"
fi

# 3. Native host execution in VM context (for simulated/emulated nodes)
export HOSTNAME="${VM_NAME}"
export USER="root"
export HOME="/root"

eval "$CMD"
