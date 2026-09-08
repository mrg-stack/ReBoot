# ReBoot - Copilot Implementation Brief

## Objective
Build the missing backend for ReBoot so that the desktop app can prepare a Debian boot device workflow safely and predictably.

This brief is intended to be pasted into Copilot as implementation context so it can generate production-leaning backend code that integrates with the existing PySide6 UI flow.

## Product Context
ReBoot is a PySide6 desktop proof-of-concept with a guided flow:
1. Welcome screen
2. Hardware analysis
3. Recommendation and user choice (Mint, Debian, or erase-only)
4. Secure erase confirmation
5. Hardware analysis report generation (analysis only; erasure is not executed)

The current app is mostly UI + placeholders. The backend that performs actual Debian boot-device preparation is not implemented yet.

## Supported Production Platform
The production runtime and hardware-report target is exclusively
**PC-compatible x86-64/amd64 Linux**. Unsupported operating systems and CPU
architectures must fail closed with an explicit error before hardware probing
or installer operations. macOS is permitted only as a development host for
editing and for running an x86-64 Linux guest in QEMU; it is not a supported
ReBoot runtime or hardware-report target.

## Existing Repository Structure (Important)
- app/main.py: Qt entrypoint.
- app/ui/: UI screens and wrappers.
- app/core/: screen logic and transitions.
- app/services/system_info.py: hardware collection.
- app/services/certificate.py: one-page analysis-only PDF rendering.
- app/services/hardware_report.py: factual PC x86-64 Linux hardware evidence collection.
- app/services/installer.py: currently a placeholder.
- app/profiles/: currently minimal profile stubs.

## Current Runtime Wiring (What already works)
- Welcome -> Hardware -> Recommendation -> SecureErase screens are connected.
- Hardware screen calls get_system_info() from services/system_info.py.
- Recommendation screen sets:
  - selected_distro = "mint" | "debian" | "none"
  - install_os = True/False
- Secure erase screen:
  - tracks wipe method "quick" or "secure"
  - requires explicit confirmation checkbox
  - currently performs no destructive action
  - generates/opens a factual hardware analysis PDF that does not claim erasure

## Problem To Solve
Implement a real backend for Debian boot-device preparation that can be called from the current app flow after secure erase confirmation when:
- install_os is True
- selected distro is Debian

The backend must be safe by default, auditable, and modular so future distro support can be added.

## Backend Scope (Debian First)
### In Scope
- Device detection and validation for removable target media.
- Debian ISO acquisition strategy (from provided path or configured URL).
- ISO verification (checksum and optional signature verification).
- Bootable USB writing workflow.
- Progress reporting suitable for UI consumption.
- Structured logging and result payloads.
- Error taxonomy and recoverable failure messages.
- Dry-run mode for development and tests.

### Out of Scope (for this step)
- Full secure erase execution on internal disks (keep existing POC behavior unless explicitly enabled later).
- Multi-distro smart recommendation engine.
- Advanced partition customization beyond what is needed to create a standard Debian boot device.

## Required Architectural Changes
Create or extend backend services while preserving existing UI flow and minimizing UI breakage.

### 1) Installer Service Contract
Replace placeholder app/services/installer.py with a concrete API. Suggested shape:

- dataclasses:
  - InstallRequest
  - InstallProgress
  - InstallResult
- enums:
  - InstallStage (discover_device, fetch_iso, verify_iso, write_usb, validate_usb, complete, failed)
  - InstallStatus (ok, warning, error, cancelled)

Primary function:
- install_debian_boot_device(request: InstallRequest, progress_cb: Callable[[InstallProgress], None] | None = None) -> InstallResult

InstallRequest should include:
- target_device (example: /dev/sdX)
- iso_path (optional, local file)
- iso_url (optional if path absent)
- checksum_sha256 (required unless explicitly bypassed in dev)
- verify_signature (bool)
- dry_run (bool)
- force (bool, for explicit destructive acknowledgement)
- run_context metadata (operator name, profile, timestamp)

InstallResult should include:
- success: bool
- status: InstallStatus
- stage: InstallStage
- message: str
- details: dict
- artifacts: dict (paths for logs, checksum file, verification report)

### 2) Debian Backend Module
Add app/services/debian_backend.py (or similarly named module) containing OS-level operations:
- discover_removable_devices()
- validate_target_device()
- ensure_not_system_disk()
- fetch_iso_if_needed()
- verify_sha256()
- verify_signature_if_enabled()
- write_iso_to_device()
- sync_and_eject()
- validate_written_media()

Keep command-execution isolated in one utility helper so mocking/testing is easy.

### 3) Command Execution Wrapper
Add a safe subprocess wrapper module (for example app/services/command_runner.py):
- explicit argument arrays (no shell=True)
- timeout support
- stdout/stderr capture
- structured exceptions
- command allowlist for dangerous ops

### 4) Integration Point with Existing Flow
Integrate at secure erase continuation path:
- if install_os is False: keep erase-only behavior.
- if install_os is True and selected distro is debian: call installer backend.
- if selected distro is mint: return clear not-implemented message for now, without crash.

Important: Keep UI responsive. Long-running install should run off main thread and emit progress events.

## Debian-Specific Operational Requirements
Assume backend runtime environment is Debian-based and has required CLI tools.

Preferred tooling strategy:
- ISO download: curl or wget
- checksum: sha256sum
- signature verification: gpg (optional but supported)
- block-device info: lsblk, blkid, findmnt
- writing image: dd (or configurable writer tool)
- partition refresh/sync: partprobe + sync

Safety requirements:
- Never write unless target resolves to removable device and explicit force/confirm is present.
- Block writes to device hosting current root filesystem.
- Require unmount of target partitions before writing.
- Use deterministic block size and status output for progress parsing.
- Produce detailed logs including command, exit code, and redacted outputs.

## Dependencies
Current Python dependencies:
- PySide6==6.11.1
- PySide6_Addons==6.11.1
- PySide6_Essentials==6.11.1
- shiboken6==6.11.1
- psutil==6.1.0

Additional Python dependencies (recommended):
- pydantic (optional, for request/result validation)
- tenacity (optional, for retrying downloads)

System dependencies expected on Debian host:
- coreutils (dd, sync, sha256sum)
- util-linux (lsblk, findmnt)
- curl or wget
- gnupg (for signature checks)
- udev/systemd tools as needed for device metadata

## Profiles and Configuration
Current profile files are minimal (name only). Extend profile design so backend can consume:
- distro target (debian)
- install mode (standard, advanced)
- verification strictness
- mirror/iso source preferences
- locale/timezone/keyboard defaults (future installer integration)

Add config loading helper under services for profile-driven install behavior.

## Error Model (Must Implement)
Define explicit exception types and map them to user-safe messages:
- DeviceDiscoveryError
- UnsafeTargetError
- IsoDownloadError
- IsoVerificationError
- SignatureVerificationError
- MediaWriteError
- PostWriteValidationError

Each error should include:
- stage
- technical detail
- suggested user action

## Logging and Auditability
Create per-run log files in a predictable location (for example tempdir/reboot_logs/).
Log schema should include:
- run_id
- timestamp
- operator/profile
- selected device
- selected ISO
- verification outcomes
- all stage transitions
- final result

Return log path in InstallResult.artifacts.

## Testing Requirements
Add tests for backend modules (unit first):
- command wrapper behavior (timeouts, failures)
- target device safety checks
- checksum verification logic
- stage transitions and progress callbacks
- dry-run execution path

Use monkeypatch/mocks for subprocess and filesystem interactions.
No test should require writing real block devices.

## Acceptance Criteria
1. Calling installer with a valid Debian request returns structured progress and final result.
2. Unsafe device selections are blocked with clear errors.
3. ISO verification is mandatory by default.
4. Dry-run performs all validations except destructive write.
5. Errors are surfaced as actionable, user-readable messages.
6. Existing UI flow still launches and runs without regressions.

## Non-Functional Requirements
- Keep code modular and typed.
- Use dataclasses or pydantic models for IO contracts.
- Avoid hardcoded paths except safe defaults.
- No shell injection risks.
- Keep implementation Linux-only for the supported PC x86-64/amd64 production target.

## Suggested Implementation Sequence
1. Implement command runner + error types.
2. Implement Debian backend primitives (device discovery, ISO verify, write).
3. Implement installer service API and progress model.
4. Wire secure-erase continuation to installer call path.
5. Add tests and dry-run fixtures.
6. Document usage in README.

## Notes About Current Codebase Constraints
- app/services/installer.py is currently a no-op placeholder.
- app/services/certificate.py renders an analysis-only report; hardware probing is isolated in
  app/services/hardware_report.py with a Linux x86-64 collector.
- app/services/system_info.py delegates to the normalized Linux x86-64 collector
  and rejects unsupported runtimes.
- app/profiles/*.yaml currently only contain a name field.

## Immediate Deliverables Copilot Should Generate
- Fully implemented app/services/installer.py with structured API.
- New app/services/debian_backend.py.
- New app/services/command_runner.py.
- New app/services/errors.py.
- Tests under a new tests/ tree for installer and backend safety checks.
- Minimal integration update in secure erase/recommendation flow to trigger Debian backend.
- README update section: Debian backend setup + required system packages.

## Important Safety Policy
No destructive operation should happen silently.
Require explicit user intent + safety checks + clear log trail before writing media.

When uncertain about a target device, fail closed.
