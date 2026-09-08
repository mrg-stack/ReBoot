from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import platform
import re
import subprocess
from typing import Any, Callable


SUPPORTED_MACHINES = {"x86_64", "amd64"}


class UnsupportedPlatformError(RuntimeError):
    """Raised when hardware collection is requested outside the production target."""


class EvidenceState(str, Enum):
    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    NOT_TESTED = "not_tested"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Evidence:
    state: EvidenceState
    value: str = ""
    detail: str = ""

    def display(self) -> str:
        if self.state == EvidenceState.DETECTED:
            return self.value
        if self.state == EvidenceState.NOT_DETECTED:
            return "Not detected"
        if self.state == EvidenceState.NOT_TESTED:
            return "Not tested"
        if self.detail:
            return f"Unavailable ({self.detail})"
        return "Unavailable"

    def check_status(self, detected_value: str | None = None) -> str:
        if self.state == EvidenceState.DETECTED:
            value = detected_value or self.value
            return f"Detected ({value})" if value else "Detected"
        return self.display()


@dataclass(frozen=True)
class DiskInfo:
    name: str
    model: str
    serial: str
    capacity_bytes: int | None
    transport: str
    logical_sector_size: int | None
    vendor: str
    health: str
    revision: str = ""
    removable: str = ""

    @property
    def sector_count(self) -> str:
        if self.capacity_bytes is None or not self.logical_sector_size:
            return "Not reported"
        return str(self.capacity_bytes // self.logical_sector_size)

    @property
    def capacity(self) -> str:
        if self.capacity_bytes is None:
            return "Not reported"
        return format_bytes(self.capacity_bytes)


@dataclass
class HardwareSnapshot:
    os_name: str
    architecture: str = ""
    fields: dict[str, Evidence] = field(default_factory=dict)
    disks: list[DiskInfo] = field(default_factory=list)
    disk_probe: Evidence = field(default_factory=lambda: unavailable("not probed"))
    simulated: bool = False

    def field(self, name: str) -> Evidence:
        return self.fields.get(name, unavailable("not collected"))

    def first_disk(self) -> DiskInfo | None:
        return self.disks[0] if self.disks else None


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    @property
    def successful(self) -> bool:
        return self.returncode == 0 and not self.error


CommandRunner = Callable[[list[str]], CommandResult]


def detected(value: Any) -> Evidence:
    text = _clean(value)
    return Evidence(EvidenceState.DETECTED, text) if text else not_detected()


def not_detected() -> Evidence:
    return Evidence(EvidenceState.NOT_DETECTED)


def not_tested() -> Evidence:
    return Evidence(EvidenceState.NOT_TESTED)


def unavailable(detail: str = "") -> Evidence:
    return Evidence(EvidenceState.UNAVAILABLE, detail=_clean(detail))


def format_bytes(value: int) -> str:
    if value >= 1000**3:
        return f"{value / (1000**3):.1f} GB"
    if value >= 1000**2:
        return f"{value / (1000**2):.1f} MB"
    return f"{value} bytes"


def run_command(args: list[str]) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        return CommandResult(tuple(args), None, error="tool missing")
    except PermissionError:
        return CommandResult(tuple(args), None, error="permission denied")
    except subprocess.TimeoutExpired:
        return CommandResult(tuple(args), None, error="timed out")
    except OSError as error:
        return CommandResult(tuple(args), None, error=error.strerror or "operating system error")
    return CommandResult(tuple(args), result.returncode, result.stdout, result.stderr)


def normalize_machine(machine: str) -> str:
    normalized = _clean(machine).lower()
    if normalized not in SUPPORTED_MACHINES:
        raise UnsupportedPlatformError(
            "ReBoot hardware reporting supports PC-compatible x86-64 "
            f"(x86_64/amd64) Linux only; detected architecture {machine or 'unknown'}"
        )
    return "x86_64"


def collect_hardware_snapshot(
    os_name: str | None = None,
    runner: CommandRunner = run_command,
    root: Path = Path("/"),
    machine: str | None = None,
) -> HardwareSnapshot:
    current_os = os_name or platform.system()
    if current_os != "Linux":
        raise UnsupportedPlatformError(
            "ReBoot hardware reporting supports Linux only; "
            f"detected operating system {current_os or 'unknown'}"
        )
    architecture = normalize_machine(machine or platform.machine())
    return _collect_linux(runner, root, architecture)


def create_development_snapshot() -> HardwareSnapshot:
    """Return deterministic fictional hardware without probing the host."""
    fields = {
        "manufacturer": detected("ReBoot Development Fixture"),
        "chassis_type": detected("Simulated Desktop"),
        "model": detected("Simulated AMD64 PC"),
        "machine_name": detected("Simulated AMD64 PC"),
        "serial": detected("SIMULATED-SYSTEM-SERIAL"),
        "uuid": detected("SIMULATED-SYSTEM-UUID"),
        "sku": detected("SIMULATED-PC-SKU"),
        "processor": detected("Simulated x86-64 Processor"),
        "cpu_cores": detected("4 simulated physical cores"),
        "cpu_threads": detected("8 simulated logical threads"),
        "cpu_speed": detected("3.20 GHz (simulated)"),
        "memory": detected("16.0 GB (simulated)"),
        "motherboard": detected("ReBoot Simulated Mainboard"),
        "bios": detected("ReBoot Simulated UEFI Firmware 1.0"),
        "bios_features": detected("Simulated UEFI boot; Simulated Secure Boot enabled"),
        "security_module": detected("Simulated TPM 2.0"),
        "graphics": detected("ReBoot Simulated Graphics Adapter"),
        "displays": detected("Simulated Display: 1920x1080"),
        "audio": detected("ReBoot Simulated HD Audio"),
        "audio_input": detected("Simulated Microphone"),
        "audio_output": detected("Simulated Speakers"),
        "cameras": detected("Simulated Webcam"),
        "battery": detected("Simulated Battery, capacity: 90%, status: Not tested"),
        "thunderbolt": detected("Simulated USB4 Host Interface"),
        "networks": detected(
            "Simulated Ethernet [simeth0, up]; Simulated Wi-Fi [simwifi0, down]"
        ),
        "wifi": detected("Simulated Wi-Fi [simwifi0, down]"),
        "usb_devices": detected(
            "Simulated USB Keyboard; Simulated USB Mouse; Simulated USB Storage"
        ),
        "ports": detected("Simulated USB controller; Simulated USB4 controller"),
        "storage_controller": detected("Simulated NVMe Controller"),
        "keyboard": detected("Simulated USB Keyboard"),
        "pointer": detected("Simulated USB Mouse"),
        "optical_drive": detected("Simulated DVD-RW Drive"),
    }
    disk = DiskInfo(
        name="/dev/simulated-nvme0n1",
        model="Simulated NVMe SSD",
        serial="SIMULATED-DISK-SERIAL",
        capacity_bytes=512_000_000_000,
        transport="NVMe (simulated)",
        logical_sector_size=512,
        vendor="ReBoot Development Fixture",
        health="Simulated healthy status (not tested)",
        revision="SIM-1.0",
        removable="removable: No (simulated)",
    )
    return HardwareSnapshot(
        os_name="Linux",
        architecture="x86_64",
        simulated=True,
        fields=fields,
        disks=[disk],
        disk_probe=detected("1 simulated disk"),
    )


def _collect_linux(
    runner: CommandRunner,
    root: Path,
    architecture: str,
) -> HardwareSnapshot:
    dmi, dmi_error = _read_linux_dmi(root)

    def dmi_evidence(key: str) -> Evidence:
        value = dmi.get(key, "")
        return detected(value) if value else unavailable(dmi_error or "not reported by DMI sysfs")

    processor, cpu_cores, cpu_threads, cpu_speed = _linux_cpu(root)
    memory = _linux_memory(root)

    lsblk = runner(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--output",
            "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,TRAN,VENDOR,LOG-SEC,ROTA,STATE,REV,RM",
        ]
    )
    disks: list[DiskInfo] = []
    optical_drive: Evidence
    if lsblk.successful:
        try:
            payload = json.loads(lsblk.stdout)
        except json.JSONDecodeError:
            disk_probe = unavailable("invalid lsblk JSON")
            optical_drive = unavailable("invalid lsblk JSON")
        else:
            devices = list(_walk_block_devices(payload.get("blockdevices", [])))
            disks = [_linux_disk(item) for item in devices if item.get("type") == "disk"]
            optical_names = [
                _join_nonempty(
                    [
                        _clean(item.get("path") or item.get("name")),
                        _clean(item.get("vendor")),
                        _clean(item.get("model")),
                    ]
                )
                for item in devices
                if item.get("type") == "rom"
            ]
            disk_probe = detected(f"{len(disks)} disk(s)") if disks else not_detected()
            optical_drive = _evidence_from_values(optical_names)
    else:
        detail = lsblk.error or _command_failure_detail(lsblk)
        disk_probe = unavailable(detail)
        optical_drive = _linux_optical_sysfs(root)
        if optical_drive.state == EvidenceState.UNAVAILABLE:
            optical_drive = unavailable(detail)

    lspci = runner(["lspci"])
    pci_lines: list[str] = []
    if lspci.successful:
        pci_lines = [line.strip() for line in lspci.stdout.splitlines() if line.strip()]
        graphics = _matching_lines(
            pci_lines,
            ("vga compatible controller", "3d controller", "display controller"),
        )
        pci_audio = _matching_values(
            pci_lines,
            ("audio device", "multimedia audio controller"),
        )
        storage = _matching_lines(
            pci_lines,
            ("sata controller", "non-volatile memory controller", "raid bus controller"),
        )
        port_values = _matching_values(pci_lines, ("usb controller", "thunderbolt", "usb4"))
        ports = _evidence_from_values(port_values)
    else:
        detail = lspci.error or _command_failure_detail(lspci)
        graphics = unavailable(detail)
        pci_audio = []
        storage = unavailable(detail)
        ports = unavailable(detail)

    lsusb = runner(["lsusb"])
    if lsusb.successful:
        usb_names = []
        for line in lsusb.stdout.splitlines():
            match = re.match(r"Bus \d+ Device \d+: ID [0-9a-fA-F:]+\s*(.*)", line.strip())
            usb_names.append(_clean(match.group(1) if match else line))
        usb = _evidence_from_values([name for name in usb_names if name])
    else:
        usb = unavailable(lsusb.error or _command_failure_detail(lsusb))

    networks, wifi = _linux_networks(root)
    battery = _linux_battery(root)
    security = _linux_tpm(root)
    cameras = _linux_cameras(root)
    keyboard, pointer = _linux_input_devices(root)
    display = _linux_displays(root, runner)
    audio, audio_input, audio_output = _linux_audio(root, pci_audio, lspci)
    thunderbolt = _linux_thunderbolt(root, pci_lines, lspci)
    ports = _combine_evidence(
        [ports, thunderbolt],
        "USB/Thunderbolt controller evidence unavailable",
    )
    firmware_mode, secure_boot = _linux_firmware(root)

    bios = _join_nonempty(
        [
            _prefixed("Vendor", dmi.get("bios_vendor", "")),
            _prefixed("Version", dmi.get("bios_version", "")),
            _prefixed("Date", dmi.get("bios_date", "")),
            firmware_mode.value if firmware_mode.state == EvidenceState.DETECTED else "",
        ]
    )
    board = _join_nonempty(
        [
            dmi.get("board_vendor", ""),
            dmi.get("board_name", ""),
            dmi.get("board_version", ""),
        ]
    )
    bios_features = _combine_evidence(
        [firmware_mode, secure_boot],
        "firmware and Secure Boot evidence unavailable",
    )

    fields = {
        "manufacturer": dmi_evidence("sys_vendor"),
        "chassis_type": _linux_chassis_evidence(dmi.get("chassis_type", ""), dmi_error),
        "model": dmi_evidence("product_name"),
        "machine_name": dmi_evidence("product_name"),
        "serial": dmi_evidence("product_serial"),
        "uuid": dmi_evidence("product_uuid"),
        "sku": dmi_evidence("product_sku"),
        "processor": processor,
        "cpu_cores": cpu_cores,
        "cpu_threads": cpu_threads,
        "cpu_speed": cpu_speed,
        "memory": memory,
        "motherboard": detected(board) if board else unavailable(dmi_error or "not reported by DMI sysfs"),
        "bios": detected(bios) if bios else unavailable(dmi_error or "firmware details not reported"),
        "bios_features": bios_features,
        "security_module": security,
        "graphics": graphics,
        "displays": display,
        "audio": audio,
        "audio_input": audio_input,
        "audio_output": audio_output,
        "cameras": cameras,
        "battery": battery,
        "thunderbolt": thunderbolt,
        "networks": networks,
        "wifi": wifi,
        "usb_devices": usb,
        "ports": ports,
        "storage_controller": storage,
        "keyboard": keyboard,
        "pointer": pointer,
        "optical_drive": optical_drive,
    }
    return HardwareSnapshot(
        os_name="Linux",
        architecture=architecture,
        fields=fields,
        disks=disks,
        disk_probe=disk_probe,
    )


def _linux_disk(item: dict[str, Any]) -> DiskInfo:
    return DiskInfo(
        name=_clean(item.get("path") or item.get("name")) or "Disk",
        model=_clean(item.get("model")) or "Not reported",
        serial=_clean(item.get("serial")) or "Not reported",
        capacity_bytes=_to_int(item.get("size")),
        transport=_clean(item.get("tran")) or "Not reported",
        logical_sector_size=_to_int(item.get("log-sec")),
        vendor=_clean(item.get("vendor")) or "Not reported",
        health="Not reported",
        revision=_clean(item.get("rev")),
        removable=_prefixed("removable", item.get("rm")),
    )


def _walk_block_devices(value: Any):
    if not isinstance(value, list):
        return
    for item in value:
        if not isinstance(item, dict):
            continue
        yield item
        yield from _walk_block_devices(item.get("children", []))


def _linux_networks(root: Path) -> tuple[Evidence, Evidence]:
    directory = root / "sys/class/net"
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        return unavailable("sysfs network data missing"), unavailable("sysfs network data missing")
    except PermissionError:
        return unavailable("permission denied"), unavailable("permission denied")
    except OSError as error:
        detail = error.strerror or "sysfs read failed"
        return unavailable(detail), unavailable(detail)

    values = []
    wifi_values = []
    for entry in entries:
        name = entry.name
        if _is_virtual_network_name(name) or not (entry / "device").exists():
            continue
        state = _read_text(entry / "operstate") or "state unknown"
        kind = "Wi-Fi" if (entry / "wireless").exists() else "network"
        value = f"{kind} [{name}, {state}]"
        values.append(value)
        if kind == "Wi-Fi":
            wifi_values.append(value)
    return _evidence_from_values(values), _evidence_from_values(wifi_values)


def _is_virtual_network_name(name: str) -> bool:
    return bool(
        re.match(
            r"^(?:lo|docker\d*|br(?:-.+|\d+)|virbr\d*|veth.+|dummy\d*|"
            r"tun\d*|tunl\d*|tap\d*|utun\d*|tailscale\d*|wg\d*|"
            r"bond\d*|team\d*|ifb\d*|macvlan\d*|vxlan\d*|"
            r"gre\d*|gretap\d*|sit\d*|ip6tnl\d*)$",
            name,
        )
    )


def _linux_battery(root: Path) -> Evidence:
    directory = root / "sys/class/power_supply"
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        return unavailable("power_supply sysfs missing")
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "power_supply read failed")

    batteries = []
    for entry in entries:
        if (_read_text(entry / "type") or "").lower() != "battery":
            continue
        capacity = _read_text(entry / "capacity")
        health = _read_text(entry / "health")
        status = _read_text(entry / "status")
        cycles = _read_text(entry / "cycle_count")
        batteries.append(
            _join_nonempty(
                [
                    entry.name,
                    _prefixed("capacity", _percentage(capacity)),
                    _prefixed("health", health),
                    _prefixed("status", status),
                    _prefixed("cycles", cycles),
                ]
            )
        )
    return _evidence_from_values(batteries)


def _linux_tpm(root: Path) -> Evidence:
    directory = root / "sys/class/tpm"
    try:
        entries = sorted(entry for entry in directory.iterdir() if entry.name.startswith("tpm"))
    except FileNotFoundError:
        return not_detected()
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "TPM sysfs read failed")

    values = []
    for entry in entries:
        description = _read_text(entry / "device/description")
        version = _read_text(entry / "tpm_version_major")
        values.append(
            _join_nonempty(
                [
                    entry.name,
                    description or "",
                    _prefixed("version", version),
                ]
            )
        )
    return _evidence_from_values(values)


def _linux_cameras(root: Path) -> Evidence:
    directory = root / "dev"
    try:
        devices = sorted(path.name for path in directory.iterdir() if re.fullmatch(r"video\d+", path.name))
    except FileNotFoundError:
        return unavailable("device directory missing")
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "camera device read failed")

    values = []
    for device in devices:
        name = _read_text(root / "sys/class/video4linux" / device / "name")
        values.append(_join_nonempty([device, name or ""]))
    return _evidence_from_values(values)


def _linux_input_devices(root: Path) -> tuple[Evidence, Evidence]:
    path = root / "proc/bus/input/devices"
    text, detail = _read_text_with_error(path)
    if text is None:
        return unavailable(detail), unavailable(detail)
    names = re.findall(r'^N:\s+Name="([^"]+)"', text, flags=re.MULTILINE)
    keyboard = [name for name in names if "keyboard" in name.lower()]
    pointer = [
        name
        for name in names
        if any(term in name.lower() for term in ("mouse", "touchpad", "trackpad", "trackpoint"))
    ]
    return _evidence_from_values(keyboard), _evidence_from_values(pointer)


def _linux_displays(root: Path, runner: CommandRunner) -> Evidence:
    directory = root / "sys/class/drm"
    try:
        connectors = sorted(directory.iterdir())
    except FileNotFoundError:
        return _linux_xrandr(runner)
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "DRM sysfs read failed")

    values = []
    for connector in connectors:
        if _read_text(connector / "status") != "connected":
            continue
        modes = _read_text(connector / "modes")
        resolution = modes.splitlines()[0].strip() if modes else "resolution unavailable"
        values.append(f"{connector.name}: {resolution}")
    return _evidence_from_values(values)


def _linux_xrandr(runner: CommandRunner) -> Evidence:
    result = runner(["xrandr", "--current"])
    if not result.successful:
        return unavailable(result.error or _command_failure_detail(result))
    values = []
    pattern = re.compile(r"^(\S+)\s+connected(?:\s+primary)?(?:\s+(\d+x\d+)\+\d+\+\d+)?")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            values.append(_join_nonempty([match.group(1), match.group(2) or "resolution unavailable"]))
    return _evidence_from_values(values)


def _linux_audio(
    root: Path,
    pci_audio: list[str],
    lspci: CommandResult,
) -> tuple[Evidence, Evidence, Evidence]:
    cards_text, cards_error = _read_text_with_error(root / "proc/asound/cards")
    pcm_text, pcm_error = _read_text_with_error(root / "proc/asound/pcm")

    card_names = []
    if cards_text:
        card_names = [
            _clean(match.group(1))
            for match in re.finditer(r"^\s*\d+\s+\[[^\]]+\]:\s*(.+)$", cards_text, re.MULTILINE)
        ]
    audio_values = _deduplicate(pci_audio + card_names)
    if audio_values:
        audio = _evidence_from_values(audio_values)
    elif cards_text is not None or lspci.successful:
        audio = not_detected()
    else:
        audio = unavailable(cards_error or lspci.error or _command_failure_detail(lspci))

    inputs: list[str] = []
    outputs: list[str] = []
    if pcm_text is not None:
        for line in pcm_text.splitlines():
            name = _clean(line.split(":", 1)[-1])
            if "capture" in line.lower():
                inputs.append(name)
            if "playback" in line.lower():
                outputs.append(name)
        return audio, _evidence_from_values(inputs), _evidence_from_values(outputs)
    return audio, unavailable(pcm_error), unavailable(pcm_error)


def _linux_thunderbolt(
    root: Path,
    pci_lines: list[str],
    lspci: CommandResult,
) -> Evidence:
    directory = root / "sys/bus/thunderbolt/devices"
    sysfs_values: list[str] = []
    sysfs_available = True
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        sysfs_available = False
        entries = []
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "Thunderbolt sysfs read failed")

    for entry in entries:
        name = _read_text(entry / "device_name") or _read_text(entry / "name") or entry.name
        vendor = _read_text(entry / "vendor_name")
        sysfs_values.append(_join_nonempty([name, vendor or ""]))

    pci_values = _matching_values(pci_lines, ("thunderbolt", "usb4"))
    values = _deduplicate(sysfs_values + pci_values)
    if values:
        return _evidence_from_values(values)
    if sysfs_available or lspci.successful:
        return not_detected()
    return unavailable(lspci.error or _command_failure_detail(lspci))


def _linux_optical_sysfs(root: Path) -> Evidence:
    directory = root / "sys/class/block"
    try:
        names = sorted(entry.name for entry in directory.iterdir() if re.fullmatch(r"sr\d+", entry.name))
    except FileNotFoundError:
        return unavailable("block-device sysfs missing")
    except PermissionError:
        return unavailable("permission denied")
    except OSError as error:
        return unavailable(error.strerror or "block-device sysfs read failed")
    return _evidence_from_values(names)


def _linux_firmware(root: Path) -> tuple[Evidence, Evidence]:
    firmware = root / "sys/firmware"
    if not firmware.exists():
        return unavailable("firmware sysfs missing"), unavailable("firmware sysfs missing")

    efi = firmware / "efi"
    if not efi.exists():
        return detected("Legacy BIOS boot"), not_detected()

    mode = detected("UEFI boot")
    variables = efi / "efivars"
    try:
        secure_boot_paths = sorted(variables.glob("SecureBoot-*"))
    except OSError as error:
        return mode, unavailable(error.strerror or "EFI variable read failed")
    if not variables.exists():
        return mode, unavailable("EFI variable data missing")
    if not secure_boot_paths:
        return mode, unavailable("SecureBoot EFI variable not readable")

    try:
        payload = secure_boot_paths[0].read_bytes()
    except PermissionError:
        return mode, unavailable("permission denied")
    except OSError as error:
        return mode, unavailable(error.strerror or "SecureBoot EFI variable read failed")
    if len(payload) < 5:
        return mode, unavailable("invalid SecureBoot EFI variable")
    if payload[4] == 1:
        return mode, detected("Secure Boot enabled")
    if payload[4] == 0:
        return mode, detected("Secure Boot disabled")
    return mode, unavailable("unrecognized SecureBoot EFI value")


def _read_linux_dmi(root: Path) -> tuple[dict[str, str], str]:
    directory = root / "sys/class/dmi/id"
    keys = (
        "sys_vendor",
        "product_name",
        "product_serial",
        "product_uuid",
        "product_sku",
        "chassis_type",
        "board_vendor",
        "board_name",
        "board_version",
        "bios_vendor",
        "bios_version",
        "bios_date",
    )
    try:
        available_names = {entry.name for entry in directory.iterdir()}
    except FileNotFoundError:
        return {}, "DMI sysfs missing"
    except PermissionError:
        return {}, "permission denied"
    except OSError as error:
        return {}, error.strerror or "DMI sysfs read failed"

    values = {key: _read_text(directory / key) or "" for key in keys if key in available_names}
    return values, ""


def _linux_chassis_evidence(value: str, dmi_error: str) -> Evidence:
    cleaned = _clean(value)
    if not cleaned:
        return unavailable(dmi_error or "not reported by DMI sysfs")
    chassis_names = {
        "3": "Desktop",
        "4": "Low Profile Desktop",
        "6": "Mini Tower",
        "7": "Tower",
        "8": "Portable",
        "9": "Laptop",
        "10": "Notebook",
        "13": "All in One",
        "23": "Rack Mount Chassis",
        "30": "Tablet",
        "35": "Mini PC",
    }
    name = chassis_names.get(cleaned)
    return detected(f"{name} (DMI {cleaned})" if name else f"DMI type {cleaned}")


def _linux_cpu(root: Path) -> tuple[Evidence, Evidence, Evidence, Evidence]:
    text, detail = _read_text_with_error(root / "proc/cpuinfo")
    if text is None:
        missing = unavailable(detail)
        return missing, missing, missing, missing

    model_match = re.search(r"^model name\s*:\s*(.+)$", text, flags=re.MULTILINE)
    processor = detected(model_match.group(1)) if model_match else unavailable("processor model not reported")

    logical = len(re.findall(r"^processor\s*:", text, flags=re.MULTILINE))
    core_pairs = set()
    for cpu_record in re.split(r"\n\s*\n", text):
        physical_match = re.search(r"^physical id\s*:\s*(\d+)$", cpu_record, re.MULTILINE)
        core_match = re.search(r"^core id\s*:\s*(\d+)$", cpu_record, re.MULTILINE)
        if physical_match and core_match:
            core_pairs.add((physical_match.group(1), core_match.group(1)))
    if logical:
        threads = detected(f"{logical} logical thread{'s' if logical != 1 else ''}")
        if core_pairs:
            physical = len(core_pairs)
            cores = detected(f"{physical} physical core{'s' if physical != 1 else ''}")
        else:
            cores = unavailable("physical core topology not reported")
    else:
        cores = unavailable("CPU topology not reported")
        threads = unavailable("logical thread count not reported")

    frequency_match = re.search(r"^cpu MHz\s*:\s*([\d.]+)$", text, flags=re.MULTILINE)
    if frequency_match:
        speed = detected(f"{float(frequency_match.group(1)) / 1000:.2f} GHz")
    else:
        speed = unavailable("CPU frequency not reported")
    return processor, cores, threads, speed


def _linux_memory(root: Path) -> Evidence:
    text, detail = _read_text_with_error(root / "proc/meminfo")
    if text is None:
        return unavailable(detail)
    match = re.search(r"^MemTotal:\s*(\d+)\s+kB$", text, flags=re.MULTILINE)
    if not match:
        return unavailable("MemTotal not reported")
    return detected(format_bytes(int(match.group(1)) * 1024))


def _combine_evidence(evidence: list[Evidence], unavailable_detail: str) -> Evidence:
    values = [item.value for item in evidence if item.state == EvidenceState.DETECTED]
    if values:
        return detected("; ".join(values))
    details = [item.detail for item in evidence if item.detail]
    if any(item.state == EvidenceState.UNAVAILABLE for item in evidence):
        return unavailable("; ".join(_deduplicate(details)) or unavailable_detail)
    if any(item.state == EvidenceState.NOT_TESTED for item in evidence):
        return not_tested()
    return not_detected()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return ""
    return " ".join(str(value).strip().split())


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    cleaned = re.sub(r"[^\d]", "", _clean(value))
    return int(cleaned) if cleaned else None


def _join_nonempty(values: list[str]) -> str:
    return ", ".join(value for value in values if _clean(value))


def _prefixed(label: str, value: Any) -> str:
    cleaned = _clean(value)
    return f"{label}: {cleaned}" if cleaned else ""


def _percentage(value: Any) -> str:
    cleaned = _clean(value)
    if not cleaned:
        return ""
    return cleaned if "%" in cleaned else f"{cleaned}%"


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _summarize(values: list[str], limit: int = 3) -> str:
    unique = _deduplicate(values)
    if len(unique) <= limit:
        return "; ".join(unique)
    return f"{'; '.join(unique[:limit])}; +{len(unique) - limit} more"


def _evidence_from_values(values: list[str]) -> Evidence:
    summary = _summarize(values)
    return detected(summary) if summary else not_detected()


def _matching_values(lines: list[str], terms: tuple[str, ...]) -> list[str]:
    return [line for line in lines if any(term in line.lower() for term in terms)]


def _matching_lines(lines: list[str], terms: tuple[str, ...]) -> Evidence:
    return _evidence_from_values(_matching_values(lines, terms))


def _command_failure_detail(result: CommandResult) -> str:
    stderr = _clean(result.stderr)
    if result.returncode is None:
        return result.error or "command unavailable"
    if stderr:
        return f"command failed: {stderr[:80]}"
    return f"command failed with exit {result.returncode}"


def _read_text_with_error(path: Path) -> tuple[str | None, str]:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None, f"{path.name} data missing"
    except PermissionError:
        return None, "permission denied"
    except UnicodeError:
        return None, f"{path.name} data is not valid text"
    except OSError as error:
        return None, error.strerror or f"{path.name} read failed"
    return (value or None), "" if value else f"{path.name} data empty"


def _read_text(path: Path) -> str | None:
    value, _ = _read_text_with_error(path)
    return value
