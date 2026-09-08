#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
APP_DIR=${REBOOT_APP_DIR:-"$HOME/Developer/ReBoot/app"}
BOOT_CACHE="$PROJECT_DIR/.qemu-direct-boot"
MODE=bios

if [ "${1:-}" = "--uefi" ]; then
    MODE=uefi
    shift
fi

IMAGE=${1:-"$PROJECT_DIR/live-image-amd64.hybrid.iso"}

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
    echo "qemu-system-x86_64 is required." >&2
    exit 1
fi

if [ ! -f "$IMAGE" ]; then
    echo "ISO not found: $IMAGE" >&2
    exit 1
fi

if [ ! -r "$APP_DIR/main.py" ]; then
    echo "ReBoot application not found: $APP_DIR/main.py" >&2
    echo "Set REBOOT_APP_DIR to override the local application path." >&2
    exit 1
fi

if ! command -v bsdtar >/dev/null 2>&1; then
    echo "bsdtar is required for direct QEMU boot." >&2
    exit 1
fi

IMAGE_DIGEST=$(shasum -a 256 "$IMAGE" | awk '{print $1}')
CACHED_DIGEST=
if [ -f "$BOOT_CACHE/image.sha256" ]; then
    CACHED_DIGEST=$(cat "$BOOT_CACHE/image.sha256")
fi

if [ "$IMAGE_DIGEST" != "$CACHED_DIGEST" ]; then
    mkdir -p "$BOOT_CACHE"
    KERNEL_ENTRY=$(bsdtar -tf "$IMAGE" | grep '^live/vmlinuz-' | head -1)
    INITRD_ENTRY=$(bsdtar -tf "$IMAGE" | grep '^live/initrd\.img-' | head -1)
    if [ -z "$KERNEL_ENTRY" ] || [ -z "$INITRD_ENTRY" ]; then
        echo "Could not locate the live kernel and initramfs in $IMAGE" >&2
        exit 1
    fi
    bsdtar -xOf "$IMAGE" "$KERNEL_ENTRY" > "$BOOT_CACHE/vmlinuz"
    bsdtar -xOf "$IMAGE" "$INITRD_ENTRY" > "$BOOT_CACHE/initrd.img"
    printf '%s\n' "$IMAGE_DIGEST" > "$BOOT_CACHE/image.sha256"
fi

ACCEL=tcg
CPU=max
if [ "$(uname -s)" = "Linux" ] && [ -r /dev/kvm ]; then
    ACCEL=kvm
    CPU=host
fi

if [ "$MODE" = "uefi" ]; then
    if [ -f /opt/homebrew/share/qemu/edk2-x86_64-code.fd ]; then
        UEFI_CODE=/opt/homebrew/share/qemu/edk2-x86_64-code.fd
        UEFI_VARS_TEMPLATE=/opt/homebrew/share/qemu/edk2-i386-vars.fd
    elif [ -f /usr/share/OVMF/OVMF_CODE.fd ]; then
        UEFI_CODE=/usr/share/OVMF/OVMF_CODE.fd
        UEFI_VARS_TEMPLATE=/usr/share/OVMF/OVMF_VARS.fd
    else
        echo "No supported x86_64 UEFI firmware was found." >&2
        exit 1
    fi

    UEFI_VARS="$PROJECT_DIR/.qemu-uefi-vars.fd"
    if [ ! -f "$UEFI_VARS" ]; then
        cp "$UEFI_VARS_TEMPLATE" "$UEFI_VARS"
    fi

    exec qemu-system-x86_64 \
        -name "ReBoot Live UEFI" \
        -machine "q35,accel=$ACCEL" \
        -cpu "$CPU" \
        -smp 2 \
        -m 4096 \
        -drive "if=pflash,format=raw,readonly=on,file=$UEFI_CODE" \
        -drive "if=pflash,format=raw,file=$UEFI_VARS" \
        -kernel "$BOOT_CACHE/vmlinuz" \
        -initrd "$BOOT_CACHE/initrd.img" \
        -append "boot=live components persistence username=reboot hostname=reboot locales=en_DK.UTF-8 keyboard-layouts=dk quiet splash" \
        -cdrom "$IMAGE" \
        -drive "file=$PROJECT_DIR/reboot-test-disk.qcow2,if=virtio,format=qcow2" \
        -device virtio-vga,xres=1024,yres=640 \
        -virtfs "local,path=$APP_DIR,mount_tag=reboot_app,security_model=none,id=reboot_app" \
        -display default \
        -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
        -snapshot
fi

exec qemu-system-x86_64 \
    -name "ReBoot Live" \
    -machine "q35,accel=$ACCEL" \
    -cpu "$CPU" \
    -smp 2 \
    -m 4096 \
    -kernel "$BOOT_CACHE/vmlinuz" \
    -initrd "$BOOT_CACHE/initrd.img" \
    -append "boot=live components persistence username=reboot hostname=reboot locales=en_DK.UTF-8 keyboard-layouts=dk quiet splash" \
    -cdrom "$IMAGE" \
    -drive "file=$PROJECT_DIR/reboot-test-disk.qcow2,if=virtio,format=qcow2" \
    -device virtio-vga,xres=1024,yres=640 \
    -virtfs "local,path=$APP_DIR,mount_tag=reboot_app,security_model=none,id=reboot_app" \
    -display default \
    -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
    -snapshot
