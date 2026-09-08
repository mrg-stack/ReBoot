# Third-Party Notices

ReBoot depends on and, in its bootable ISO form, redistributes third-party
free and open-source software. Each component remains governed by its own
license; the ReBoot GPL license does not replace those terms.

## Python application dependencies

| Component | License family | Project |
|---|---|---|
| Python | Python Software Foundation License | <https://www.python.org/> |
| Qt for Python / PySide6 / Shiboken6 | LGPLv3/GPLv3 or commercial terms | <https://doc.qt.io/qtforpython-6/> |
| psutil | BSD 3-Clause | <https://github.com/giampaolo/psutil> |

The development dependency versions are pinned in `requirements.txt`.

## Debian Live image

The ISO is assembled from Debian 13 packages listed in
`boot-environment/config/package-lists/reboot.list.chroot`. Those packages
have individual copyright and license terms. Debian installs the authoritative
package notices in:

```text
/usr/share/doc/<package>/copyright
```

Corresponding source packages are available from Debian repositories:
<https://www.debian.org/distrib/packages>

Each tagged ISO release also includes its exact package manifest, source
checksum, and numbered parts of the corresponding Debian package and
live-configuration source archives. Concatenate each archive's parts in
filename order and verify the reconstructed tarballs using the supplied
checksum.

This file is a convenient summary, not a substitute for the complete notices
shipped by each package. Release maintainers must review dependency and
firmware licensing when the package list changes.
