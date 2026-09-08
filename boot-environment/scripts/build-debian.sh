#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REBOOT_DIR=$(CDPATH= cd -- "$PROJECT_DIR/.." && pwd)
STAGED_APP="$PROJECT_DIR/config/includes.chroot/opt/reboot/app"
STAGED_DOCS="$PROJECT_DIR/config/includes.chroot/usr/share/doc/reboot"
IMAGE=live-image-amd64.hybrid.iso
PACKAGE_MANIFEST=live-image-amd64.packages
DEBIAN_SOURCE=live-image-amd64-source.debian.tar
LIVE_SOURCE=live-image-amd64-source.live.tar
SOURCE_CHECKSUM=live-image-amd64.sources.sha256

run_as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

normalize_artifact() {
    target=$1
    shift

    if [ -f "$target" ]; then
        return
    fi

    for candidate in "$@"; do
        if [ -f "$candidate" ]; then
            mv "$candidate" "$target"
            return
        fi
    done

    echo "Build completed without expected artifact: $target" >&2
    exit 1
}

if [ "$(uname -s)" != "Linux" ]; then
    echo "This build requires Debian Linux with live-build installed." >&2
    exit 1
fi

if ! command -v lb >/dev/null 2>&1; then
    echo "Missing live-build. Install it with: sudo apt install live-build" >&2
    exit 1
fi

if [ "$(dpkg --print-architecture)" != "amd64" ]; then
    echo "ReBoot must be built in an amd64 Debian environment." >&2
    exit 1
fi

cd "$PROJECT_DIR"

if [ "${1:-}" = "--clean" ]; then
    run_as_root lb clean --purge
elif [ "$#" -gt 0 ]; then
    echo "Usage: $0 [--clean]" >&2
    exit 1
fi

if [ ! -f "$REBOOT_DIR/app/main.py" ]; then
    echo "ReBoot application source not found: $REBOOT_DIR/app/main.py" >&2
    exit 1
fi

rm -rf "$STAGED_APP"
mkdir -p "$STAGED_APP" "$STAGED_DOCS"
tar \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    -cf - \
    -C "$REBOOT_DIR/app" \
    . \
    | tar -xf - -C "$STAGED_APP"

for document in LICENSE NOTICE AUTHORS.md THIRD_PARTY_NOTICES.md; do
    if [ ! -f "$REBOOT_DIR/$document" ]; then
        echo "Required licensing document not found: $REBOOT_DIR/$document" >&2
        exit 1
    fi
    install -m 0644 "$REBOOT_DIR/$document" "$STAGED_DOCS/$document"
done

run_as_root rm -f \
    "$IMAGE" \
    "$IMAGE.sha256" \
    "$PACKAGE_MANIFEST" \
    "$DEBIAN_SOURCE" \
    "$LIVE_SOURCE" \
    "$SOURCE_CHECKSUM" \
    binary.hybrid.iso \
    binary.packages \
    live-image-source.debian.tar \
    live-image-source.live.tar \
    source.debian.tar \
    source.debian-live.tar
run_as_root lb config
run_as_root lb build

normalize_artifact "$IMAGE" binary.hybrid.iso
normalize_artifact "$PACKAGE_MANIFEST" binary.packages
normalize_artifact "$DEBIAN_SOURCE" live-image-source.debian.tar source.debian.tar
normalize_artifact "$LIVE_SOURCE" live-image-source.live.tar source.debian-live.tar

sha256sum "$IMAGE" > "$IMAGE.sha256"
sha256sum "$DEBIAN_SOURCE" "$LIVE_SOURCE" > "$SOURCE_CHECKSUM"
echo "Built: $PROJECT_DIR/$IMAGE"
echo "Checksum: $PROJECT_DIR/$IMAGE.sha256"
echo "Package manifest: $PROJECT_DIR/$PACKAGE_MANIFEST"
echo "Debian package source: $PROJECT_DIR/$DEBIAN_SOURCE"
echo "Live configuration source: $PROJECT_DIR/$LIVE_SOURCE"
echo "Source checksums: $PROJECT_DIR/$SOURCE_CHECKSUM"
