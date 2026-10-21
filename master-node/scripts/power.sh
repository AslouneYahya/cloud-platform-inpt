#!/usr/bin/env bash
# ==============================================================================
# power.sh — Start or Stop an existing VM on the node
# ==============================================================================
set -eo pipefail

VM_ID=""
ACTION=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --id) VM_ID="$2"; shift ;;
        --action) ACTION="$2"; shift ;;
        *) echo "Unknown parameter: $1" >&2; exit 1 ;;
    esac
    shift
done

RUNTIME_DIR="/var/lib/inpt-cloud/vms/${VM_ID}"
CONF_FILE="$RUNTIME_DIR/vm.conf"

if [ ! -f "$CONF_FILE" ]; then
    echo "STATUS=FAILED"
    echo "ERROR=VM config not found for ${VM_ID}"
    exit 1
fi

case "$ACTION" in
    start)
        sed -i 's/^STATUS=.*/STATUS=RUNNING/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "STATE=RUNNING"
        echo "MESSAGE=VM ${VM_ID} powered on."
        ;;
    stop)
        sed -i 's/^STATUS=.*/STATUS=STOPPED/' "$CONF_FILE"
        echo "STATUS=SUCCESS"
        echo "STATE=STOPPED"
        echo "MESSAGE=VM ${VM_ID} powered off."
        ;;
    *)
        echo "STATUS=FAILED"
        echo "ERROR=Invalid action: ${ACTION}"
        exit 1
        ;;
esac
