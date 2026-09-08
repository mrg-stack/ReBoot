#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This helper is for macOS. Use your Linux imaging tool instead." >&2
    exit 1
fi

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 IMAGE.iso /dev/diskN" >&2
    exit 1
fi

IMAGE=$1
DISK=$2

case "$DISK" in
    /dev/disk[0-9]*) ;;
    *)
        echo "Use a whole macOS disk identifier such as /dev/disk4." >&2
        exit 1
        ;;
esac

if [ ! -f "$IMAGE" ]; then
    echo "ISO not found: $IMAGE" >&2
    exit 1
fi

diskutil info "$DISK"
printf '\nThis will overwrite all existing data on %s.\n' "$DISK"
printf 'Type the exact disk identifier to continue: '
read -r CONFIRM

if [ "$CONFIRM" != "$DISK" ]; then
    echo "Confirmation did not match; nothing was written." >&2
    exit 1
fi

RAW_DISK=/dev/r${DISK#/dev/}
diskutil unmountDisk "$DISK"
sudo dd if="$IMAGE" of="$RAW_DISK" bs=4m
sync
diskutil eject "$DISK"
echo "ReBoot image written successfully."
