#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This helper is for macOS." >&2
    exit 1
fi

for command in curl hdiutil qemu-img qemu-system-x86_64 scp ssh ssh-keygen tar; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Missing required command: $command" >&2
        exit 1
    fi
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REBOOT_DIR=$(CDPATH= cd -- "$PROJECT_DIR/.." && pwd)
BUILD_DIR=${REBOOT_BUILD_DIR:-"$HOME/.cache/reboot-builder"}
BASE_IMAGE="$BUILD_DIR/debian-13-genericcloud-amd64.qcow2"
OVERLAY="$BUILD_DIR/reboot-builder.qcow2"
SEED_DIR="$BUILD_DIR/seed"
SEED_ISO="$BUILD_DIR/seed.iso"
SSH_KEY="$BUILD_DIR/id_ed25519"
QEMU_LOG="$BUILD_DIR/qemu.log"
QEMU_PID_FILE="$BUILD_DIR/qemu.pid"
SSH_PORT=${REBOOT_BUILD_SSH_PORT:-2222}
IMAGE_URL="https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2"
CHECKSUM_URL="https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS"
QEMU_PID=
CLOCK_SYNC_PID=

mkdir -p "$BUILD_DIR"

cleanup() {
    if [ -n "$CLOCK_SYNC_PID" ] && kill -0 "$CLOCK_SYNC_PID" 2>/dev/null; then
        kill "$CLOCK_SYNC_PID"
        wait "$CLOCK_SYNC_PID" 2>/dev/null || true
    fi
    if [ -n "$QEMU_PID" ] && kill -0 "$QEMU_PID" 2>/dev/null; then
        kill "$QEMU_PID"
        wait "$QEMU_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

if [ ! -f "$BASE_IMAGE" ]; then
    echo "Downloading Debian 13 amd64 cloud image..."
    curl -fL --progress-bar "$IMAGE_URL" -o "$BASE_IMAGE.download"
    curl -fsSL "$CHECKSUM_URL" -o "$BUILD_DIR/SHA512SUMS"
    EXPECTED=$(grep -E '[ *]debian-13-genericcloud-amd64.qcow2$' \
        "$BUILD_DIR/SHA512SUMS" | awk '{print $1}')
    ACTUAL=$(shasum -a 512 "$BASE_IMAGE.download" | awk '{print $1}')
    if [ -z "$EXPECTED" ] || [ "$ACTUAL" != "$EXPECTED" ]; then
        echo "Debian cloud image checksum verification failed." >&2
        exit 1
    fi
    mv "$BASE_IMAGE.download" "$BASE_IMAGE"
    echo "Debian cloud image checksum verified."
fi

if [ ! -f "$SSH_KEY" ]; then
    ssh-keygen -q -t ed25519 -N "" -f "$SSH_KEY"
fi

if [ ! -f "$OVERLAY" ]; then
    qemu-img create \
        -f qcow2 \
        -F qcow2 \
        -b "$BASE_IMAGE" \
        "$OVERLAY" \
        40G
fi

rm -rf "$SEED_DIR"
mkdir -p "$SEED_DIR"
PUBLIC_KEY=$(cat "$SSH_KEY.pub")

cat > "$SEED_DIR/meta-data" <<EOF
instance-id: reboot-builder-1
local-hostname: reboot-builder
EOF

cat > "$SEED_DIR/user-data" <<EOF
#cloud-config
users:
  - name: builder
    gecos: ReBoot image builder
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $PUBLIC_KEY
package_update: true
packages:
  - live-build
  - rsync
ssh_pwauth: false
disable_root: true
EOF

rm -f "$SEED_ISO"
hdiutil makehybrid \
    -iso \
    -joliet \
    -default-volume-name cidata \
    -o "$SEED_ISO" \
    "$SEED_DIR" >/dev/null

echo "Starting disposable amd64 Debian build VM..."
qemu-system-x86_64 \
    -name "ReBoot ISO Builder" \
    -machine q35,accel=tcg \
    -cpu max \
    -smp 4 \
    -m 6144 \
    -drive "file=$OVERLAY,if=virtio,format=qcow2" \
    -drive "file=$SEED_ISO,media=cdrom,format=raw,readonly=on" \
    -nic "user,model=virtio-net-pci,hostfwd=tcp::$SSH_PORT-:22" \
    -rtc base=utc,clock=host,driftfix=slew \
    -display none \
    -serial file:"$QEMU_LOG" \
    -monitor none \
    -pidfile "$QEMU_PID_FILE" \
    -daemonize

QEMU_PID=$(cat "$QEMU_PID_FILE")
if [ -z "$QEMU_PID" ] || ! kill -0 "$QEMU_PID" 2>/dev/null; then
    echo "Could not determine QEMU process ID. See $QEMU_LOG" >&2
    exit 1
fi

SSH_OPTIONS="-i $SSH_KEY -p $SSH_PORT -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5"
SCP_OPTIONS="-i $SSH_KEY -P $SSH_PORT -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5"

echo "Waiting for cloud-init and SSH..."
attempt=0
until ssh $SSH_OPTIONS builder@127.0.0.1 \
    'test -f /var/lib/cloud/instance/boot-finished && command -v lb >/dev/null'
do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 120 ]; then
        echo "Builder VM did not become ready. See $QEMU_LOG" >&2
        exit 1
    fi
    sleep 5
done

sync_guest_clock() {
    while kill -0 "$QEMU_PID" 2>/dev/null; do
        HOST_EPOCH=$(date -u +%s)
        ssh $SSH_OPTIONS builder@127.0.0.1 \
            "sudo date -u -s '@$HOST_EPOCH'" >/dev/null 2>&1 || true
        sleep 60
    done
}

sync_guest_clock &
CLOCK_SYNC_PID=$!

echo "Copying ReBoot image source into the VM..."
ssh $SSH_OPTIONS builder@127.0.0.1 \
    'set -eu
     sudo rm -rf /home/builder/reboot-cache
     if [ -d /home/builder/reboot/boot-environment/cache ]; then
         sudo mv /home/builder/reboot/boot-environment/cache /home/builder/reboot-cache
     fi
     sudo rm -rf /home/builder/reboot
     mkdir -p /home/builder/reboot'
tar \
    --exclude='.DS_Store' \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='live-image-*' \
    --exclude='reboot-test-disk.qcow2' \
    -czf - \
    -C "$REBOOT_DIR" \
    boot-environment \
    app \
    LICENSE \
    NOTICE \
    AUTHORS.md \
    THIRD_PARTY_NOTICES.md \
    | ssh $SSH_OPTIONS builder@127.0.0.1 \
        'tar -xzf - -C /home/builder/reboot
         if [ -d /home/builder/reboot-cache ]; then
             sudo mv /home/builder/reboot-cache /home/builder/reboot/boot-environment/cache
         fi'

echo "Building ReBoot hybrid ISO inside Debian..."
ssh $SSH_OPTIONS builder@127.0.0.1 \
    'cd /home/builder/reboot/boot-environment && ./scripts/build-debian.sh'

kill "$CLOCK_SYNC_PID"
wait "$CLOCK_SYNC_PID" 2>/dev/null || true
CLOCK_SYNC_PID=

echo "Copying ISO and checksum back to the project..."
scp $SCP_OPTIONS \
    builder@127.0.0.1:/home/builder/reboot/boot-environment/live-image-amd64.hybrid.iso \
    "$PROJECT_DIR/"
scp $SCP_OPTIONS \
    builder@127.0.0.1:/home/builder/reboot/boot-environment/live-image-amd64.hybrid.iso.sha256 \
    "$PROJECT_DIR/"

ssh $SSH_OPTIONS builder@127.0.0.1 'sudo poweroff' || true
sleep 3

echo "Built: $PROJECT_DIR/live-image-amd64.hybrid.iso"
echo "VM log: $QEMU_LOG"
