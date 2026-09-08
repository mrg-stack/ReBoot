# ReBoot

ReBoot is a PySide6 desktop proof-of-concept that guides a user through:

1. Welcome/start screen
2. Hardware analysis
3. Distro recommendation and experience choice
4. Secure erase preference confirmation and hardware analysis report (non-destructive)

The current implementation focuses on a clean architecture and incremental product flow.

## Supported Production Platform

ReBoot supports **PC-compatible x86-64/amd64 Linux only** as a production
runtime and hardware-report target. Other operating systems and CPU
architectures are rejected explicitly before hardware probing. macOS may be
used as a development host for editing the project and running an x86-64 Linux
guest in QEMU, but it is not a supported ReBoot runtime or report target.

For UI development on macOS or another unsupported host, start the app normally
and enable the unchecked **Developer mode — simulate an AMD64 Linux PC** control
on the welcome screen before choosing any route. This mode uses one deterministic,
fictional Linux x86-64 fixture and never probes the host's hardware. The warning
remains visible through hardware analysis, recommendation, and secure-erase
screens, including the direct erase-only route.

Developer simulation is not a production bypass: leaving the control unchecked
retains fail-closed Linux/amd64 validation, including rejection of Darwin and
ARM. Simulation performs no erasure, analyzes no real hardware, and produces a
clearly bannered `reboot_development_simulation_...pdf` that is not valid
hardware or erasure evidence.

## Features

- Guided multi-screen setup flow
- Normalized PC x86-64 Linux hardware detection from kernel interfaces and
  standard command-line tools
- Detailed CPU presentation (model, architecture, cores/threads, speed)
- Recommendation screen with user-selectable experience level:
	- Easy to use (Linux Mint)
	- Advanced setup (Debian)
- Secure erase UX step with explicit confirmation gating:
	- Quick erase option
	- Secure erase option (recommended for GDPR-style compliance)
	- Continue disabled until user confirms permanent data deletion
- One-page `Data Erasure Report` PDF with analysis-only semantics:
	- Records the requested method but clearly states it was not executed
	- Uses factual disk and hardware evidence without simulated results
	- Generates a report ID and local timestamped artifact under `artifacts/`

## GDPR-Style Erasure Guidance (POC)

- If the user wants GDPR-style compliance, they should select `Secure erase`.
- GDPR expectations are that personal data is rendered irrecoverable using proper sanitization methods.
- Potential penalties can reach up to EUR 20 million or 4% of annual global turnover (whichever is greater).
- A completed erasure process should be documented for accountability, but a
  certificate must only claim success when backed by execution and verification evidence.
- In this build, no destructive wipe command is executed. The generated PDF is a
  hardware analysis report, not proof that data was erased.

### Planned Method Model (HDD vs SSD)

- HDD path: use a verified single-pass overwrite of the full disk.
- Rationale: modern guidance (NIST 800-88 context) considers single-pass overwrite sufficient for current HDD density when verification is performed.
- SSD/NVMe path: do not rely on host-level overwrite for compliance assurance.
- Rationale: wear leveling and over-provisioned regions can leave data outside host-visible write paths.
- SSD/NVMe secure path: use firmware-level operations such as ATA Secure Erase or NVMe Sanitize (Block Erase or Crypto Erase).
- For self-encrypting drives, cryptographic erase should be supported by deleting the media encryption key.
- Accountability path: store wipe metadata and generate certificate-ready evidence for regulated environments.

### Tooling Notes for Future Integration

- HDD overwrite tooling candidates: DBAN, ShredOS, or equivalent controlled workflows.
- SSD/NVMe tooling candidates: nvme-cli, hdparm, and vendor-approved firmware erase tooling.
- ReBoot currently exposes only UX and policy decisions for these paths; command execution is intentionally disabled in the POC.

## Hardware Analysis Report

The report collector keeps OS probing separate from PDF rendering and always
distinguishes a successful empty probe (`Not detected`) from a failed or
unsupported probe (`Unavailable`). Functional checks that are not performed are
shown as `Not tested`.

- Linux uses DMI, network, power, TPM, DRM display, camera, input, firmware,
  Secure Boot, Thunderbolt/USB4, audio, and optical-drive evidence from
  `/sys`, `/dev`, and `/proc`, plus `lsblk --json --bytes`, `lspci`, `lsusb`,
  and `xrandr` fallback data when available.
- Disk model, serial, capacity, transport, sector count, and health are printed
  only when the operating system reports them. Machine serials are never
  substituted for disk serials.
- HPA, DCO, remapped-sector, SMART, and similar values remain `Not reported` or
  `Unavailable` unless a real probe supplies evidence.
- Missing tools or kernel data remain truthfully distinguished as
  `Unavailable`, `Not detected`, or `Not tested`.

Digital signing and destructive erasure execution are intentionally deferred.

## Project Structure

```text
ReBoot/
├── app/
│   ├── main.py
│   ├── ui/
│   │   ├── welcome.py
│   │   ├── hardware.py
│   │   └── summary.py
│   ├── core/
│   │   ├── hardware.py
│   │   ├── recommendation.py
│   │   └── secure_erase.py
│   ├── services/
│   │   ├── certificate.py
│   │   ├── hardware_report.py
│   │   ├── system_info.py
│   │   └── installer.py
│   └── profiles/
│       ├── developer.yaml
│       ├── student.yaml
│       └── casual.yaml
├── assets/
├── requirements.txt
└── README.md
```

## Architecture Notes

- `app/ui`: user-facing screens and simple flow transitions
- `app/core`: domain logic used by UI (analysis + recommendations)
- `app/services`: system interaction layer (hardware collection, installer hooks)

`app/ui/hardware.py` intentionally re-exports `HardwareScreen` from `app/core/hardware.py` so existing imports in the UI flow remain stable while logic lives in `core`.

## Getting Started

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

On a PC-compatible x86-64/amd64 Linux host:

```bash
python app/main.py
```

On macOS, use the welcome-screen developer simulation only for UI/report
development. Use QEMU to exercise the supported production Linux target.

### Window mode override

ReBoot now supports three runtime window modes:

- `fullscreen` (default on Linux, intended for Debian kiosk boot)
- `maximized`
- `windowed` (fixed-size development window)

You can override mode at runtime:

```bash
REBOOT_WINDOW_MODE=windowed python app/main.py
```

## Runtime Flow

1. `WelcomeScreen` is shown from `app/main.py`
2. User opens hardware analysis
3. Hardware info is collected via `services/system_info.py`
4. Results are displayed with a manual Continue button
5. Recommendation screen allows experience refinement (Mint vs Debian)
6. Secure erase step captures wipe mode and explicit user consent

## Current Limitations

- Recommendation logic is still POC-level
- Secure erase action is a placeholder (no destructive disk command is executed)
- The local PDF is an analysis-only report and is not an erasure certificate or proof of sanitization
- Some low-level disk facts require privileged Linux tooling and are truthfully shown as unavailable or not reported
- Non-Linux and non-x86-64/amd64 systems are intentionally unsupported

## Next Steps

- Connect selected distro/profile to next-step workflow
- Expand unit tests for `services/system_info.py`
- Add installer integration in `services/installer.py`

## Debian Boot Kiosk Setup

If the goal is to start ReBoot fullscreen automatically at boot on Debian,
use the deployment files under `deploy/`.

### Prerequisites

- A desktop session that auto-logs into your kiosk user.
- Python virtual environment already created at `.venv/`.
- Dependencies installed with `pip install -r requirements.txt`.

### Install kiosk startup (user-level)

From the project root:

```bash
bash deploy/install_kiosk_user.sh
```

This installs:

- `~/.config/systemd/user/reboot-kiosk.service`
- `~/.config/autostart/reboot-kiosk.desktop`

and enables/restarts the user service when `systemctl --user` is available.

### Manual control

```bash
systemctl --user status reboot-kiosk.service
systemctl --user restart reboot-kiosk.service
systemctl --user stop reboot-kiosk.service
```

### Files involved

- `deploy/reboot-kiosk-launch.sh`: launcher script used by service/autostart
- `deploy/reboot-kiosk.service`: systemd user service template
- `deploy/reboot-kiosk.desktop`: XDG autostart template
- `deploy/install_kiosk_user.sh`: installs templates with absolute project path
