## Bootable image

This release contains the ReBoot Debian Live amd64 ISO, its SHA-256 checksum,
the exact Debian package manifest, and corresponding source packages.

Verify the ISO:

```bash
sha256sum --check live-image-amd64.hybrid.iso.sha256
```

The corresponding Debian package source and live-build configuration source
archives are split into release-asset-sized parts. Reassemble and verify them
with:

```bash
cat live-image-amd64-source.debian.tar.part-* \
  > live-image-amd64-source.debian.tar
cat live-image-amd64-source.live.tar.part-* \
  > live-image-amd64-source.live.tar
sha256sum --check live-image-amd64.sources.sha256
```

ReBoot's own corresponding source is the source archive attached automatically
to this tagged GitHub release. ReBoot is licensed under GPL-3.0-or-later;
bundled components retain their respective licenses.
