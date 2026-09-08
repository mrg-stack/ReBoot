#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Persistence must be configured from Linux." >&2
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: sudo $0 /dev/sdXN" >&2
    exit 1
fi

PARTITION=$1

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this helper with sudo." >&2
    exit 1
fi

if [ ! -b "$PARTITION" ]; then
    echo "Not a block device: $PARTITION" >&2
    exit 1
fi

TYPE=$(lsblk -dnro TYPE "$PARTITION")
if [ "$TYPE" != "part" ]; then
    echo "Refusing a whole disk; provide an existing partition." >&2
    exit 1
fi

lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS "$PARTITION"
printf '\nThis will format %s and erase its existing contents.\n' "$PARTITION"
printf 'Type the exact partition path to continue: '
read -r CONFIRM

if [ "$CONFIRM" != "$PARTITION" ]; then
    echo "Confirmation did not match; nothing was changed." >&2
    exit 1
fi

if findmnt -rn -S "$PARTITION" >/dev/null 2>&1; then
    echo "Partition is mounted; unmount it before continuing." >&2
    exit 1
fi

mkfs.ext4 -F -L persistence "$PARTITION"
MOUNT_DIR=$(mktemp -d)
mount "$PARTITION" "$MOUNT_DIR"
printf '%s\n' "/var/lib/reboot" > "$MOUNT_DIR/persistence.conf"
sync
umount "$MOUNT_DIR"
rmdir "$MOUNT_DIR"
echo "ReBoot persistence configured on $PARTITION."
