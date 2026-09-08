#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DISK="$PROJECT_DIR/reboot-test-disk.qcow2"

if ! command -v qemu-img >/dev/null 2>&1; then
    echo "qemu-img is required." >&2
    exit 1
fi

if [ -e "$DISK" ]; then
    echo "Refusing to overwrite existing test disk: $DISK" >&2
    exit 1
fi

qemu-img create -f qcow2 "$DISK" 32G
echo "Created disposable VM disk: $DISK"
