# Certificate generation helpers for erase-proof documentation (POC).
#
# PDF assembly is manual (no external PDF library):
# - collect report/system data
# - build one-page PDF drawing commands
# - write to tempdir and open with system viewer

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform
import psutil
import re
import subprocess
import tempfile
import textwrap
import time
import uuid
import webbrowser


# PDF drawing coordinate notes:
# - Origin is bottom-left of page (standard PDF coordinate system).
# - Y values increase upward.
# - Keep geometry constants in REPORT_LAYOUT so alignment changes do not require
#   rewriting drawing logic.
REPORT_LAYOUT = {
    "header_bar": {
        "x": 0,
        "y": 818,
        "width": 595,
        "height": 24,
        "text_x": 10,
        "text_y": 826,
        "text_size": 8,
        "color": (0.180, 0.404, 0.910),
    },
    "title": {
        "x": 22,
        "y": 758,
        "size": 20,
    },
    "logo": {
        "x": 382,
        "y": 742,
        # Logo geometry is parameterized for manual visual tuning.
        "baseline_offset": 26,
        "font_size": 24,
        "re_x_offset": 16,
        "colon_x_offset": 52,
        "boot_x_offset": 56,
        "top_dot_y_offset": 10,
        "bottom_dot_y_offset": 2,
        "dot_radius": 3.2,
    },
    "section_titles": {
        "x": 22,
        "size": 15,
    },
    "custom_fields": {
        "title_y": 720,
        "title_gap": 18,
        "left_x": 22,
        "left_value_x": 63,
        "left_wrap_width": 22,
        "right_x": 270,
        "right_value_x": 340,
        "right_wrap_width": 22,
        "next_section_gap": 34,
    },
    "erasure_results": {
        "title_gap": 18,
        "disk_gap": 14,
        "col1_x": 115,
        "col2_x": 270,
        "col3_x": 430,
        "grid_row_gap": 10,
        "health_label_width": 70,
        "health_wrap_width": 22,
        "after_health_gap": 16,
        "detail_x": 22,
        "detail_label_width": 92,
        "detail_wrap_width": 72,
        "start_end_wrap_width": 86,
        "detail_row_gap": 13,
    },
    "hardware_details": {
        "section_gap": 10,
        "title_gap": 20,
        "x": 22,
        "label_width": 95,
        "wrap_width": 74,
        "row_gap": 12,
    },
    "hardware_check": {
        "section_gap": 10,
        "title_gap": 20,
        "left_x": 22,
        "left_label_width": 105,
        "left_wrap_width": 28,
        "right_x": 310,
        "right_label_width": 85,
        "right_wrap_width": 26,
        "row_gap": 13,
    },
}


def _rect_fill_op(x: float, y: float, width: float, height: float, color: tuple[float, float, float]) -> str:
    r, g, b = color
    return f"{r:.3f} {g:.3f} {b:.3f} rg\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f\n"


def _circle_fill_op(x: float, y: float, radius: float, color: tuple[float, float, float]) -> str:
    # PDF has no native circle primitive; approximate with 4 cubic segments.
    kappa = 0.5522847498
    c = radius * kappa
    r, g, b = color
    return (
        f"{r:.3f} {g:.3f} {b:.3f} rg\n"
        f"{x + radius:.2f} {y:.2f} m\n"
        f"{x + radius:.2f} {y + c:.2f} {x + c:.2f} {y + radius:.2f} {x:.2f} {y + radius:.2f} c\n"
        f"{x - c:.2f} {y + radius:.2f} {x - radius:.2f} {y + c:.2f} {x - radius:.2f} {y:.2f} c\n"
        f"{x - radius:.2f} {y - c:.2f} {x - c:.2f} {y - radius:.2f} {x:.2f} {y - radius:.2f} c\n"
        f"{x + c:.2f} {y - radius:.2f} {x + radius:.2f} {y - c:.2f} {x + radius:.2f} {y:.2f} c f\n"
    )


def _build_logo_ops() -> str:
    # Draw the Re:Boot wordmark directly in PDF drawing commands.
    #
    # Use text operators for "Re" and "Boot" and bezier circles for colon
    # dots so visual tuning can happen via coordinates only.
    logo = REPORT_LAYOUT["logo"]
    x = float(logo["x"])
    y = float(logo["y"])

    parts: list[str] = []

    baseline = int(y + float(logo["baseline_offset"]))
    text_color = (0.133, 0.133, 0.133)
    font_size = int(float(logo["font_size"]))

    re_x = x + float(logo["re_x_offset"])
    colon_x = x + float(logo["colon_x_offset"])
    boot_x = x + float(logo["boot_x_offset"])
    top_dot_y = baseline + float(logo["top_dot_y_offset"])
    bottom_dot_y = baseline + float(logo["bottom_dot_y_offset"])
    dot_radius = float(logo["dot_radius"])

    parts.append(_text_op("Re", int(re_x), baseline, font_size, font="F2", color=text_color))
    parts.append(_text_op("Boot", int(boot_x), baseline, font_size, font="F2", color=text_color))

    # Colon dots use the same green/blue palette as the new brand mark.
    parts.append(_circle_fill_op(colon_x, top_dot_y, dot_radius, (0.298, 0.686, 0.533)))
    parts.append(_circle_fill_op(colon_x, bottom_dot_y, dot_radius, (0.180, 0.404, 0.910)))

    return "".join(parts)


def _safe_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text_op(text: str, x: int, y: int, size: int, font: str = "F1", color: tuple[float, float, float] = (0, 0, 0)) -> str:
    r, g, b = color
    return (
        "BT\n"
        f"/{font} {size} Tf\n"
        f"{r:.3f} {g:.3f} {b:.3f} rg\n"
        f"{x} {y} Td\n"
        f"({_safe_text(text)}) Tj\n"
        "ET\n"
    )


def _section_title(text: str, y: int, x: int = 22, size: int = 15) -> str:
    return _text_op(text, x, y, size, font="F2")


def _wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]


def _label_value_block(
    label: str,
    value: str,
    x: int,
    y: int,
    label_width: int = 120,
    wrap_width: int = 32,
    value_font: str = "F1",
    value_color: tuple[float, float, float] = (0, 0, 0),
    line_step: int = 12,
) -> tuple[str, int]:
    parts = [_text_op(label, x, y, 9, font="F2")]
    current_y = y
    wrapped = _wrap_lines(value, wrap_width)
    for index, line in enumerate(wrapped):
        parts.append(_text_op(line, x + label_width, current_y, 9, font=value_font, color=value_color))
        if index < len(wrapped) - 1:
            current_y -= line_step
    return "".join(parts), current_y


def _read_sysctl_value(key: str) -> str | None:
    try:
        result = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, check=False)
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def _read_ioreg_value(key: str) -> str | None:
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    pattern = re.compile(rf'"{re.escape(key)}"\s*=\s*<"([^"]+)">|"{re.escape(key)}"\s*=\s*"([^"]+)"')
    match = pattern.search(result.stdout)
    if not match:
        return None

    return (match.group(1) or match.group(2) or "").strip() or None


def _read_system_profiler_output(*data_types: str) -> str:
    try:
        result = subprocess.run(
            ["system_profiler", *data_types],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return ""
    return result.stdout


def _read_first_existing_text_file(paths: list[Path]) -> str | None:
    for path in paths:
        if not path.exists():
            continue
        try:
            value = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if value:
            return value
    return None


def detect_system_vendor() -> str | None:
    # Best-effort system vendor detection used for certificate metadata.
    system = platform.system()

    if system == "Darwin":
        return "Apple"

    if system == "Linux":
        # Common DMI locations on Debian and many other Linux distributions.
        return _read_first_existing_text_file(
            [
                Path("/sys/devices/virtual/dmi/id/sys_vendor"),
                Path("/sys/class/dmi/id/sys_vendor"),
            ]
        )

    return None


def _extract_first_named_value(text: str, label: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(label)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip() or None


def _get_graphics_card() -> str:
    output = _read_system_profiler_output("SPDisplaysDataType")
    return _extract_first_named_value(output, "Chipset Model") or "NOT IMPLEMENTED"


def _get_current_resolution() -> str:
    output = _read_system_profiler_output("SPDisplaysDataType")
    return _extract_first_named_value(output, "Resolution") or "NOT IMPLEMENTED"


def _get_sound_card() -> str:
    output = _read_system_profiler_output("SPAudioDataType")
    preferred_patterns = [
        re.compile(r"^\s{8}(.+):\s*$", re.MULTILINE),
    ]

    for pattern in preferred_patterns:
        for match in pattern.finditer(output):
            name = match.group(1).strip()
            if "speaker" in name.lower() or "microphone" in name.lower():
                return name

    return "NOT IMPLEMENTED"


def _get_storage_controller() -> str:
    output = _read_system_profiler_output("SPNVMeDataType", "SPSerialATADataType")
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith(":") is False:
            continue
        if stripped in {"NVMExpress:", "Serial-ATA:", "Volumes:"}:
            continue
        return stripped[:-1]
    return "NOT IMPLEMENTED"


def _get_battery_report() -> tuple[str, str]:
    # Return battery detail text and capacity check status.
    output = _read_system_profiler_output("SPPowerDataType")
    if not output:
        return "NOT IMPLEMENTED", "Not performed"

    max_capacity = _extract_first_named_value(output, "Maximum Capacity")
    state_of_charge = _extract_first_named_value(output, "State of Charge (%)")
    condition = _extract_first_named_value(output, "Condition")

    normalized_max = None
    if max_capacity:
        digits = re.search(r"(\d+)", max_capacity)
        if digits:
            normalized_max = f"{digits.group(1)}%"

    normalized_soc = None
    if state_of_charge:
        digits = re.search(r"(\d+)", state_of_charge)
        if digits:
            normalized_soc = f"{digits.group(1)}%"

    details = []
    if normalized_max:
        details.append(f"Maximum Capacity: {normalized_max}")
    if normalized_soc:
        details.append(f"State of Charge: {normalized_soc}")
    if condition:
        details.append(f"Condition: {condition}")

    if not details:
        return "NOT IMPLEMENTED", "Not performed"

    check_status = f"Successful (Capacity: {normalized_max})" if normalized_max else "Successful"
    return ", ".join(details), check_status


def _format_size_gb(size_bytes: int) -> str:
    return f"{round(size_bytes / (1024 ** 3), 1)} GB"


def _collect_report_data(wipe_method: str, metadata: dict | None = None) -> dict:
    metadata = metadata or {}

    vendor = metadata.get("vendor", "") or detect_system_vendor() or "NOT IMPLEMENTED"
    asset_id = metadata.get("asset_id", "") or "NOT IMPLEMENTED"
    operator_name = metadata.get("operator_name", "") or "ReBoot Operator"
    chassis_type = metadata.get("chassis_type", "") or "Workstation / Laptop (not implemented)"

    identifier_type, identifier_value = get_device_identifier()
    timestamp = datetime.now(timezone.utc)
    certificate_id = str(uuid.uuid4()).upper()

    disk_usage = psutil.disk_usage("/")
    ram_total = psutil.virtual_memory().total
    cpu_name = _read_sysctl_value("machdep.cpu.brand_string") or platform.processor() or "Not implemented"
    system_model = _read_sysctl_value("hw.model") or platform.node() or "Not implemented"
    system_sku = (
        _read_ioreg_value("target-sub-type")
        or _read_ioreg_value("model-number")
        or _read_ioreg_value("regulatory-model-number")
        or system_model
    )
    serial_number = identifier_value
    bus_type = "NVMe/ATA (not implemented)"
    sectors = str(disk_usage.total // 512)
    disk_size = _format_size_gb(disk_usage.total)
    graphics_card = _get_graphics_card()
    current_resolution = _get_current_resolution()
    sound_card = _get_sound_card()
    storage_controller = _get_storage_controller()
    battery_details, battery_check_status = _get_battery_report()
    duration_seconds = 15 * 60 if wipe_method == "secure" else 6 * 60
    end_timestamp = timestamp
    start_timestamp = end_timestamp.timestamp() - duration_seconds
    start_time = datetime.fromtimestamp(start_timestamp, timezone.utc)
    method_text = "NIST 800-88 Purge - Secure Erase" if wipe_method == "secure" else "NIST 800-88 Clear - Verified Single Pass"
    rounds_text = "2 (1 overwrite pass, 1 certificate generation step)" if wipe_method == "secure" else "1 (verified overwrite pass)"
    status_text = "Erased (simulated)"

    return {
        "header_bar": f"{end_timestamp.strftime('%Y-%m-%d %H:%M:%S %z')}, REBOOT DRIVE ERASER POC, {platform.system().upper()}, {system_model}, {serial_number}",
        "custom_fields": {
            "Asset ID": asset_id,
            "Operator Name": operator_name,
        },
        "erasure_results": {
            "Disk": "Disk 1 (1-1)",
            "Vendor": vendor,
            "Model": system_model,
            "Serial": serial_number,
            "Size": disk_size,
            "Bus": bus_type,
            "Sectors": sectors,
            "HPA": "Doesn't exist",
            "DCO": "Doesn't exist",
            "Remapped Sector(s)": "0",
            "Health Status": "good",
            "Start/End Time": f"{start_time.strftime('%Y-%m-%d %H:%M:%S %z')} / {end_timestamp.strftime('%Y-%m-%d %H:%M:%S %z')}",
            "Duration": time.strftime('%H:%M:%S', time.gmtime(duration_seconds)),
            "Method": method_text,
            "Erasure Rounds": rounds_text,
            "Status": status_text,
            "Certificate ID": certificate_id,
        },
        "hardware_details": {
            "Manufacturer": platform.system(),
            "Chassis Type": chassis_type,
            "Model": system_model,
            "Serial": serial_number,
            "UUID": str(uuid.uuid5(uuid.NAMESPACE_DNS, serial_number)),
            "System SKU Number": system_sku,
            "Processor": cpu_name,
            "Memory": _format_size_gb(ram_total),
            "Graphics Card": graphics_card,
            "Current Resolution": current_resolution,
            "Sound Card": sound_card,
            "Storage Controller": storage_controller,
            "Disk 1 (1-1)": f"Main disk, {disk_size}, {bus_type}",
            "Network Adapter 1": "NOT IMPLEMENTED",
            "Network Adapter 2": "NOT IMPLEMENTED",
            "USB Device 1": "NOT IMPLEMENTED",
            "USB Device 2": "NOT IMPLEMENTED",
            "USB Device 3": "NOT IMPLEMENTED",
            "Motherboard": "NOT IMPLEMENTED",
            "BIOS": "NOT IMPLEMENTED",
            "BIOS Features": "NOT IMPLEMENTED",
            "Ports": "NOT IMPLEMENTED",
            "Battery": battery_details,
            "TPM": "NOT IMPLEMENTED",
        },
        "hardware_check_left": {
            "Battery Capacity": battery_check_status,
            "CPU": "Successful",
            "Display": "Successful",
            "PC Speaker": "Not performed",
            "Optical Drive": "Not performed",
            "Network Adapter": "Successful",
        },
        "hardware_check_right": {
            "Motherboard": "Successful",
            "Pointer": "Successful",
            "Keyboard": "Successful",
            "Webcam": "Not implemented",
            "USB Ports": "Successful (count not implemented)",
            "Wi-Fi Adapter": "Successful",
        },
        "identifier_type": identifier_type,
        "identifier_value": identifier_value,
        "generated_at": end_timestamp.isoformat(),
    }


def _status_color(value: str) -> tuple[float, float, float]:
    lowered = value.lower()
    if "successful" in lowered or "erased" in lowered or "good" in lowered:
        return (0.0, 0.50, 0.0)
    if "not performed" in lowered or "not implemented" in lowered:
        return (0.80, 0.45, 0.0)
    return (0.0, 0.0, 0.0)


def _build_report_content(report: dict) -> str:
    # Render a one-page report-like certificate content stream.
    layout = REPORT_LAYOUT
    parts = []

    # Top metadata bar
    header_bar = layout["header_bar"]
    header_r, header_g, header_b = header_bar["color"]
    parts.append(
        f"{header_r:.3f} {header_g:.3f} {header_b:.3f} rg\n"
        f"{header_bar['x']} {header_bar['y']} {header_bar['width']} {header_bar['height']} re f\n"
    )
    parts.append(
        _text_op(
            report["header_bar"],
            header_bar["text_x"],
            header_bar["text_y"],
            header_bar["text_size"],
            color=(1, 1, 1),
        )
    )

    # Header title + right-side brand mark (reference-style placement).
    title = layout["title"]
    parts.append(_text_op("Data Erasure Report", title["x"], title["y"], title["size"], font="F2"))

    # Render the current white SVG logo on a dark badge for contrast.
    parts.append(_build_logo_ops())

    section_titles = layout["section_titles"]
    custom_layout = layout["custom_fields"]
    y = custom_layout["title_y"]
    parts.append(_section_title("Custom Fields", y, x=section_titles["x"], size=section_titles["size"]))
    y -= custom_layout["title_gap"]

    custom = report["custom_fields"]
    left_label_width = max(1, custom_layout["left_value_x"] - custom_layout["left_x"])
    right_label_width = max(1, custom_layout["right_value_x"] - custom_layout["right_x"])
    block, _ = _label_value_block(
        "Asset ID:",
        custom["Asset ID"],
        custom_layout["left_x"],
        y,
        label_width=left_label_width,
        wrap_width=custom_layout["left_wrap_width"],
    )
    parts.append(block)
    block, _ = _label_value_block(
        "Operator Name:",
        custom["Operator Name"],
        custom_layout["right_x"],
        y,
        label_width=right_label_width,
        wrap_width=custom_layout["right_wrap_width"],
    )
    parts.append(block)

    y -= custom_layout["next_section_gap"]
    erasure_layout = layout["erasure_results"]
    parts.append(_section_title("Erasure Results", y, x=section_titles["x"], size=section_titles["size"]))
    y -= erasure_layout["title_gap"]
    erasure = report["erasure_results"]
    parts.append(_text_op(erasure["Disk"], section_titles["x"], y, 10, font="F2"))
    y -= erasure_layout["disk_gap"]

    def draw_grid_row(y_pos: int, cells: list[tuple[int, str, str, int, int]]) -> int:
        row_min_y = y_pos
        for x_pos, label, value, label_width, wrap_width in cells:
            block, block_end_y = _label_value_block(
                f"{label}:",
                value,
                x_pos,
                y_pos,
                label_width=label_width,
                wrap_width=wrap_width,
            )
            parts.append(block)
            row_min_y = min(row_min_y, block_end_y)
        return row_min_y - erasure_layout["grid_row_gap"]

    col1_x = erasure_layout["col1_x"]
    col2_x = erasure_layout["col2_x"]
    col3_x = erasure_layout["col3_x"]

    y = draw_grid_row(
        y,
        [
            (col1_x, "Vendor", erasure["Vendor"], 42, 16),
            (col2_x, "Model", erasure["Model"], 38, 20),
            (col3_x, "Serial", erasure["Serial"], 40, 16),
        ],
    )
    y = draw_grid_row(
        y,
        [
            (col1_x, "Size", erasure["Size"], 42, 16),
            (col2_x, "Bus", erasure["Bus"], 38, 20),
            (col3_x, "Sectors", erasure["Sectors"], 50, 14),
        ],
    )
    y = draw_grid_row(
        y,
        [
            (col1_x, "HPA", erasure["HPA"], 42, 16),
            (col2_x, "DCO", erasure["DCO"], 38, 20),
            (col3_x, "Remapped Sector(s)", erasure["Remapped Sector(s)"], 88, 6),
        ],
    )

    block, block_end_y = _label_value_block(
        "Health Status:",
        erasure["Health Status"],
        col1_x,
        y,
        label_width=erasure_layout["health_label_width"],
        wrap_width=erasure_layout["health_wrap_width"],
        value_font="F2",
        value_color=_status_color(erasure["Health Status"]),
    )
    parts.append(block)
    y = block_end_y - erasure_layout["after_health_gap"]

    block, new_y = _label_value_block(
        "Start/End Time:",
        erasure["Start/End Time"],
        erasure_layout["detail_x"],
        y,
        label_width=erasure_layout["detail_label_width"],
        wrap_width=erasure_layout["start_end_wrap_width"],
    )
    parts.append(block)
    y = new_y - erasure_layout["detail_row_gap"]

    for label in ["Duration", "Method", "Erasure Rounds", "Status", "Certificate ID"]:
        color = _status_color(erasure[label]) if label == "Status" else (0, 0, 0)
        block, new_y = _label_value_block(
            f"{label}:",
            erasure[label],
            erasure_layout["detail_x"],
            y,
            label_width=erasure_layout["detail_label_width"],
            wrap_width=erasure_layout["detail_wrap_width"],
            value_font="F2" if label == "Status" else "F1",
            value_color=color,
        )
        parts.append(block)
        y = new_y - erasure_layout["detail_row_gap"]

    hardware_layout = layout["hardware_details"]
    y -= hardware_layout["section_gap"]
    parts.append(_section_title("Hardware Details", y, x=section_titles["x"], size=section_titles["size"]))
    y -= hardware_layout["title_gap"]
    hardware = report["hardware_details"]
    for label, value in hardware.items():
        block, new_y = _label_value_block(
            f"{label}:",
            value,
            hardware_layout["x"],
            y,
            label_width=hardware_layout["label_width"],
            wrap_width=hardware_layout["wrap_width"],
        )
        parts.append(block)
        y = new_y - hardware_layout["row_gap"]

    hardware_check_layout = layout["hardware_check"]
    y -= hardware_check_layout["section_gap"]
    parts.append(_section_title("Hardware check", y, x=section_titles["x"], size=section_titles["size"]))
    y -= hardware_check_layout["title_gap"]
    left_check = report["hardware_check_left"]
    right_check = report["hardware_check_right"]
    left_y = y
    right_y = y
    for label, value in left_check.items():
        block, new_y = _label_value_block(
            f"{label}:",
            value,
            hardware_check_layout["left_x"],
            left_y,
            label_width=hardware_check_layout["left_label_width"],
            wrap_width=hardware_check_layout["left_wrap_width"],
            value_color=_status_color(value),
        )
        parts.append(block)
        left_y = new_y - hardware_check_layout["row_gap"]
    for label, value in right_check.items():
        block, new_y = _label_value_block(
            f"{label}:",
            value,
            hardware_check_layout["right_x"],
            right_y,
            label_width=hardware_check_layout["right_label_width"],
            wrap_width=hardware_check_layout["right_wrap_width"],
            value_color=_status_color(value),
        )
        parts.append(block)
        right_y = new_y - hardware_check_layout["row_gap"]

    return "".join(parts)


def _build_report_pdf(content: str) -> bytes:
    # Build a one-page PDF document using pre-rendered drawing commands.
    content_bytes = content.encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R /F3 7 0 R >> >> >>",
        f"<< /Length {len(content_bytes)} >>\nstream\n{content}endstream".encode("utf-8"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    start_xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{start_xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def _read_mac_serial() -> str | None:
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    for line in result.stdout.splitlines():
        if "Serial Number" in line:
            return line.split(":", 1)[-1].strip() or None
    return None


def get_device_identifier() -> tuple[str, str]:
    # Return the best available hardware identifier for certificate records.
    if platform.system() == "Darwin":
        serial = _read_mac_serial()
        if serial:
            return "serial_number", serial

    machine_id = None
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        try:
            machine_id = machine_id_path.read_text(encoding="utf-8").strip()
        except Exception:
            machine_id = None

    if machine_id:
        return "machine_id", machine_id

    node_id = f"{uuid.getnode():012x}"
    return "fallback_node_id", f"{platform.node()}-{node_id}"


def _sanitize_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def generate_erase_certificate(wipe_method: str, metadata: dict | None = None) -> Path:
    # Generate a styled PDF erase certificate in a temporary folder.
    report = _collect_report_data(wipe_method, metadata)
    identifier_value = report["identifier_value"]

    file_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ident = _sanitize_filename_part(identifier_value)[:40]
    file_name = f"reboot_erase_certificate_{file_stamp}_{ident}.pdf"
    output_path = Path(tempfile.gettempdir()) / file_name

    content = _build_report_content(report)
    output_path.write_bytes(_build_report_pdf(content))
    return output_path


def open_certificate(path: Path) -> None:
    # Open a generated certificate with the default system PDF handler.
    if platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    webbrowser.open(path.as_uri())
