# ReBoot live image

Debian 13 amd64 live development image with an LXQt desktop, hardware tooling,
and manual launchers for the current ReBoot PySide6 application. The build
stages `../app/` into `/opt/reboot/app`; no separate prototype source is kept
inside this directory.

See [`docs/development.md`](docs/development.md)
for architecture, build, VM test, USB flashing, persistence, security, and
status documentation.

Quick build on Debian 13:

```bash
./scripts/build-debian.sh
```

Build through an emulated Debian VM on Apple Silicon macOS:

```bash
./scripts/build-via-qemu-macos.sh
```

Quick VM test after building:

```bash
./scripts/create-test-disk.sh
./scripts/test-qemu.sh
```

The QEMU test script boots the live kernel directly, so the Debian boot menu
does not appear and no Enter key is required.

Use `./scripts/test-qemu.sh --uefi` for an EDK II UEFI boot.

Build outputs:

```text
live-image-amd64.hybrid.iso
live-image-amd64.hybrid.iso.sha256
live-image-amd64-source.debian.tar
live-image-amd64-source.live.tar
live-image-amd64.sources.sha256
```

The local `~/Developer/ReBoot/app` folder is shared live with QEMU at
`/mnt/reboot-app`. Set `REBOOT_APP_DIR` to override that location. Application
changes can be tested without rebuilding the ISO. Tagged GitHub releases build
and publish the bundled image automatically.

ReBoot is licensed under GPL-3.0-or-later. The ISO also includes Debian
packages under their respective licenses and package copyright notices. The
build collects corresponding Debian package source and the live-build
configuration source into separate tarballs. Tagged releases split those
tarballs into numbered parts that can be concatenated and verified using the
source checksum file.
