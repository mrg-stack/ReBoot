# Contributing to ReBoot

Contributions are welcome through GitHub issues and pull requests.

By submitting a contribution, you certify that you have the right to submit
it and agree that it is licensed under the
[GNU General Public License v3.0 or later](LICENSE), the same license as
ReBoot. Retain existing copyright and license notices when modifying files.

Do not submit secrets, private hardware identifiers, proprietary code, or
third-party material that cannot be redistributed under compatible terms.

Before opening a pull request:

```bash
.venv/bin/python -m compileall -q app tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

ISO-related changes should also be built on Debian amd64:

```bash
make -C boot-environment build
```
