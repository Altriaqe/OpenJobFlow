#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
JOBFLOW_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
QUEUE_DIR="${JOBFLOW_CAPTURE_QUEUE:-${JOBFLOW_DIR}/runtime/manual-capture}"

mkdir -p "$QUEUE_DIR"
cd "$JOBFLOW_DIR"

while true; do
    found_request=false
    for request in "$QUEUE_DIR"/*.request; do
        [[ -e "$request" ]] || continue
        found_request=true
        snapshot_date="$(basename "$request" .request)"
        running="$QUEUE_DIR/${snapshot_date}.running"
        result="$QUEUE_DIR/${snapshot_date}.result"
        mv "$request" "$running" 2>/dev/null || continue

        if JOBFLOW_SNAPSHOT_DATE="$snapshot_date" JOBFLOW_CAPTURE_ONLY=true \
            bash "$JOBFLOW_DIR/ops/daily_update.sh"; then
            printf 'succeeded\n' > "${result}.tmp"
        else
            printf 'failed\n' > "${result}.tmp"
        fi
        mv "${result}.tmp" "$result"
        rm -f "$running"
    done
    [[ "$found_request" == true ]] || sleep 2
done
