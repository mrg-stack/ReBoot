# ReBoot

**Turn end-of-life computers into safe, ready-to-use systems.**

ReBoot is an open-source project for creating an easy, broadly compatible
bootable USB device that helps people and institutions prepare computers for
reuse.

The goal is to guide non-technical users through a trustworthy device-reuse
workflow:

```text
Boot ReBoot
    -> analyze the hardware
    -> securely erase its storage
    -> verify the erasure
    -> generate an auditable report
    -> optionally install Linux
    -> return the computer to useful service
```

ReBoot is motivated by two connected problems:

- Organizations need a reliable way to remove personal and institutional data
  before computers leave their control.
- Working computers are often discarded when manufacturer support ends, even
  though the hardware could continue serving students, families, charities,
  and community organizations.

By making secure erasure and Linux deployment approachable, ReBoot aims to
improve data privacy, reduce electronic waste, and extend the useful life of
existing hardware.

## Project Direction

### Phase 1: secure erasure and evidence

The first priority is a guided, verifiable data-sanitization workflow:

- Detect the computer and its storage devices.
- Select an appropriate method for HDD, SSD, or NVMe media.
- Require explicit confirmation before destructive operations.
- Verify that sanitization completed successfully.
- Record device identity, method, timestamps, results, and verification data.
- Produce an auditable PDF report and persistent lifecycle record.

ReBoot is intended to support GDPR accountability, but GDPR does not prescribe
one universal erase command. Production claims must be backed by an appropriate
sanitization method, verification evidence, and organizational procedures.
Recognized guidance such as NIST SP 800-88 will inform the implementation.

### Phase 2: operating-system installation

After verified erasure, ReBoot will offer simple installation of mainstream
Linux distributions, beginning with a familiar option such as Linux Mint.
Hardware-aware recommendations and guided installation should make otherwise
usable computers accessible to people without Linux expertise.

### Phase 3: real-world validation

The complete workflow will be tested across different generations of PCs and
piloted with educational and public-sector users. Reliability, usability,
hardware compatibility, and audit quality must be demonstrated before ReBoot
is presented as a production erasure solution.

## Current Status

ReBoot is an early, non-destructive proof of concept.

Available today:

- Debian-based amd64 live-image build environment
- PySide6 guided user interface
- Linux hardware discovery and evidence modeling
- Hardware-analysis PDF generation
- Deterministic developer simulation for UI work on macOS
- Automated GitHub workflow for tagged ISO releases

Not yet implemented:

- Destructive storage erasure
- Post-erasure verification
- Legally or operationally certified erasure reports
- Automated Linux installation
- Digital signing and complete lifecycle audit logging

**Do not treat the current PDF as proof of data erasure.** The application
explicitly labels it as an analysis-only report.

## Supported Hardware

The initial production target is conventional **x86-64/amd64 PCs running the
ReBoot Linux environment**. Broader compatibility is a project goal, not a
current guarantee.

macOS is supported only as a development and QEMU host. Developer mode uses
fictional AMD64 Linux hardware and never represents Mac hardware as a supported
production device.

## Development

Create the local environment and run the application:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

On macOS, enable **Developer mode — simulate an AMD64 Linux PC** on the welcome
screen. Use QEMU for testing against the supported Linux runtime.

Build the bootable image on Debian amd64:

```bash
make -C boot-environment build
```

Generated ISOs and VM disks are not stored in Git. Pushing a version tag such
as `v0.1.0` starts the GitHub ISO release workflow.

Detailed build, QEMU, persistence, and USB-writing instructions are in
[`boot-environment/README.md`](boot-environment/README.md).

## Repository Layout

```text
app/                 ReBoot interface and application services
boot-environment/    Reproducible Debian Live image configuration
deploy/              Linux kiosk-launch configuration
tests/               Application tests
.github/workflows/   Tagged ISO release automation
```

## License

ReBoot is copyright (C) 2026 **Guillaume Nadon** and is licensed under the
[GNU General Public License v3.0 or later](LICENSE)
(`GPL-3.0-or-later`).

Distributed modified versions must remain open source under the GPL and include
the corresponding source code. See [NOTICE](NOTICE), [AUTHORS.md](AUTHORS.md),
[CONTRIBUTING.md](CONTRIBUTING.md), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
