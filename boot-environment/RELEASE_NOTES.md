## Pre-alpha bootable image

Download `live-image-amd64.hybrid.iso` and flash it directly to a USB drive
with Rufus, balenaEtcher, or another raw-image writer. The checksum is optional
and can be used to verify the download:

```bash
sha256sum --check live-image-amd64.hybrid.iso.sha256
```

This is an early testing image for PC-compatible x86-64/amd64 hardware. It
boots the ReBoot environment and runs hardware analysis, but it does **not**
erase data or install Linux.

GPL package manifests and corresponding Debian source are published separately
for developers and redistributors: [source-compliance release](@SOURCE_RELEASE_URL@).
