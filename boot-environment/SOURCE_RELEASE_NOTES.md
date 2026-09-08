## Corresponding source

These files accompany the ReBoot bootable ISO release with the same version.
They are provided for GPL compliance and are **not needed to flash or run the
ReBoot USB image**.

The Debian package source and live-build configuration source archives are
split into release-asset-sized parts. Reassemble and verify them with:

```bash
cat live-image-amd64-source.debian.tar.part-* \
  > live-image-amd64-source.debian.tar
cat live-image-amd64-source.live.tar.part-* \
  > live-image-amd64-source.live.tar
sha256sum --check live-image-amd64.sources.sha256
```

ReBoot's own source is available from the corresponding version tag in the
main repository. ReBoot is licensed under GPL-3.0-or-later; bundled components
retain their respective licenses.
