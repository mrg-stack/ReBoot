# ReBoot

ReBoot is a PySide6 desktop proof-of-concept that guides a user through:

1. Welcome/start screen
2. Hardware analysis
3. Distro recommendation and experience choice
4. Secure erase confirmation step (POC, non-destructive)

The current implementation focuses on a clean architecture and incremental product flow.

## Features

- Guided multi-screen setup flow
- Cross-platform hardware detection strategy:
	- macOS: `platform` + `psutil` + `sysctl`
	- Linux: `inxi -Fxz` parsing fallback
- Detailed CPU presentation (model, architecture, cores/threads, speed)
- Recommendation screen with user-selectable experience level:
	- Easy to use (Linux Mint)
	- Advanced setup (Debian)
- Secure erase UX step with explicit confirmation gating:
	- Quick erase option
	- Secure erase option (recommended for GDPR-style compliance)
	- Continue disabled until user confirms permanent data deletion

## GDPR-Style Erasure Guidance (POC)

- If the user wants GDPR-style compliance, they should select `Secure erase`.
- GDPR expectations are that personal data is rendered irrecoverable using proper sanitization methods.
- Potential penalties can reach up to EUR 20 million or 4% of annual global turnover (whichever is greater).
- The erasure process should be documented for accountability. A certificate of data erasure is a practical way to support this.
- In this POC build, no destructive wipe command is executed yet; this section defines UX and policy intent only.

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
python -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python app/main.py
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
- POC certificate flow generates a local PDF proof and opens it with the default viewer (USB export is planned)
- Linux parsing is intentionally simple and should be hardened over time

## Next Steps

- Connect selected distro/profile to next-step workflow
- Add unit tests for `services/system_info.py`
- Add installer integration in `services/installer.py`
