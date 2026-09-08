from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import platform
import re
import subprocess
import uuid

from services.hardware_report import (
    Evidence,
    EvidenceState,
    HardwareSnapshot,
    collect_hardware_snapshot,
)


PAGE_WIDTH = 595
PAGE_HEIGHT = 842
SAFE_LEFT_MARGIN = 10
SAFE_RIGHT_MARGIN = 10
SAFE_BOTTOM_MARGIN = 36

# Helvetica's AFM ascent/descent values let differently sized title text share
# a visual center instead of merely sharing an arbitrary PDF baseline.
HELVETICA_ASCENT = 0.718
HELVETICA_DESCENT = -0.207

_ASCII_START = 32
_HELVETICA_WIDTHS = {
    "F1": (
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
        556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
        1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
        333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
        556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    ),
    "F2": (
        278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
        556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
        975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
        333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
        611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
    ),
}

REPORT_LAYOUT = {
    "header_bar": {
        "x": 0,
        "y": 818,
        "width": PAGE_WIDTH,
        "height": 24,
        "text_x": 10,
        "center_y": 830,
        "text_size": 8,
        "color": (0.180, 0.404, 0.910),
    },
    "brand_row": {
        "center_y": 773,
        "title_x": 22,
        "title_size": 20,
        "logo_x": 420,
        "logo_size": 24,
        "logo_re_offset": 0,
        "logo_colon_offset": 36,
        "logo_boot_offset": 42,
        "colon_gap": 4.2,
        "dot_radius": 3.0,
    },
    "sections": {
        "custom_title_y": 733,
        "custom_row_y": 713,
        "analysis_title_y": 681,
        "analysis_disk_y": 661,
        "hardware_title_y": 475,
        "checks_title_y": 270,
    },
    "analysis": {
        "grid_x": (22, 212, 402),
        "grid_right_x": (202, 392, 573),
        "grid_y": (642, 621, 600),
        "grid_label_width": 58,
        "detail_x": 22,
        "detail_right_x": 573,
        "detail_label_width": 96,
        "detail_y": (576, 558, 540, 522, 504, 486),
    },
    "hardware": {
        "left_x": 22,
        "right_x": 305,
        "column_right_x": (285, 573),
        "label_width": (94, 116),
        "start_y": 454,
        "row_gap": 14,
    },
    "checks": {
        "left_x": 22,
        "right_x": 305,
        "column_right_x": (285, 573),
        "label_width": 105,
        "start_y": 249,
        "row_gap": 25,
    },
}


def _baseline_for_visual_center(center_y: float, font_size: float) -> float:
    visual_offset = (HELVETICA_ASCENT + HELVETICA_DESCENT) * font_size / 2
    return center_y - visual_offset


def _visual_center_for_baseline(baseline: float, font_size: float) -> float:
    visual_offset = (HELVETICA_ASCENT + HELVETICA_DESCENT) * font_size / 2
    return baseline + visual_offset


def header_alignment_geometry() -> dict[str, float]:
    row = REPORT_LAYOUT["brand_row"]
    title_baseline = _baseline_for_visual_center(row["center_y"], row["title_size"])
    logo_baseline = _baseline_for_visual_center(row["center_y"], row["logo_size"])
    return {
        "row_center": float(row["center_y"]),
        "title_baseline": title_baseline,
        "title_visual_center": _visual_center_for_baseline(title_baseline, row["title_size"]),
        "logo_baseline": logo_baseline,
        "logo_visual_center": _visual_center_for_baseline(logo_baseline, row["logo_size"]),
    }


def _rect_fill_op(
    x: float,
    y: float,
    width: float,
    height: float,
    color: tuple[float, float, float],
) -> str:
    red, green, blue = color
    return (
        f"{red:.3f} {green:.3f} {blue:.3f} rg\n"
        f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f\n"
    )


def _circle_fill_op(
    x: float,
    y: float,
    radius: float,
    color: tuple[float, float, float],
) -> str:
    kappa = 0.5522847498
    control = radius * kappa
    red, green, blue = color
    return (
        f"{red:.3f} {green:.3f} {blue:.3f} rg\n"
        f"{x + radius:.2f} {y:.2f} m\n"
        f"{x + radius:.2f} {y + control:.2f} {x + control:.2f} {y + radius:.2f} {x:.2f} {y + radius:.2f} c\n"
        f"{x - control:.2f} {y + radius:.2f} {x - radius:.2f} {y + control:.2f} {x - radius:.2f} {y:.2f} c\n"
        f"{x - radius:.2f} {y - control:.2f} {x - control:.2f} {y - radius:.2f} {x:.2f} {y - radius:.2f} c\n"
        f"{x + control:.2f} {y - radius:.2f} {x + radius:.2f} {y - control:.2f} {x + radius:.2f} {y:.2f} c f\n"
    )


def _pdf_safe_text(value: str) -> str:
    latin_text = value.encode("latin-1", errors="replace").decode("latin-1")
    return latin_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _latin1_text(value: str) -> str:
    return str(value).encode("latin-1", errors="replace").decode("latin-1")


def _text_width(text: str, size: float, font: str = "F1") -> float:
    widths = _HELVETICA_WIDTHS[font]
    total = 0
    for character in _latin1_text(text):
        codepoint = ord(character)
        if _ASCII_START <= codepoint < _ASCII_START + len(widths):
            total += widths[codepoint - _ASCII_START]
        else:
            total += 1015
    return total * size / 1000


def _text_op(
    text: str,
    x: float,
    y: float,
    size: float,
    font: str = "F1",
    color: tuple[float, float, float] = (0, 0, 0),
) -> str:
    red, green, blue = color
    return (
        "BT\n"
        f"/{font} {size:.1f} Tf\n"
        f"{red:.3f} {green:.3f} {blue:.3f} rg\n"
        f"{x:.2f} {y:.2f} Td\n"
        f"({_pdf_safe_text(text)}) Tj\n"
        "ET\n"
    )


def _section_title(text: str, y: float) -> str:
    return _text_op(text, 22, y, 14, font="F2")


def _build_logo_ops() -> str:
    row = REPORT_LAYOUT["brand_row"]
    size = float(row["logo_size"])
    baseline = _baseline_for_visual_center(float(row["center_y"]), size)
    x = float(row["logo_x"])
    center_y = float(row["center_y"])
    colon_x = x + float(row["logo_colon_offset"])
    color = (0.133, 0.133, 0.133)
    return "".join(
        [
            _text_op("Re", x + row["logo_re_offset"], baseline, size, font="F2", color=color),
            _text_op("Boot", x + row["logo_boot_offset"], baseline, size, font="F2", color=color),
            _circle_fill_op(
                colon_x,
                center_y + row["colon_gap"],
                row["dot_radius"],
                (0.298, 0.686, 0.533),
            ),
            _circle_fill_op(
                colon_x,
                center_y - row["colon_gap"],
                row["dot_radius"],
                (0.180, 0.404, 0.910),
            ),
        ]
    )


def _fit_line(
    text: str,
    max_width: float,
    size: float,
    font: str = "F1",
    force_ellipsis: bool = False,
) -> str:
    normalized = " ".join(str(text).split())
    if not force_ellipsis and _text_width(normalized, size, font) <= max_width:
        return normalized
    suffix = "..."
    suffix_width = _text_width(suffix, size, font)
    if suffix_width > max_width:
        return ""
    low = 0
    high = len(normalized)
    while low < high:
        midpoint = (low + high + 1) // 2
        candidate = normalized[:midpoint].rstrip() + suffix
        if _text_width(candidate, size, font) <= max_width:
            low = midpoint
        else:
            high = midpoint - 1
    return normalized[:low].rstrip() + suffix


def _split_to_width(text: str, max_width: float, size: float, font: str) -> list[str]:
    if not text:
        return [""]
    pieces = []
    remaining = text
    while remaining:
        low = 1
        high = len(remaining)
        while low < high:
            midpoint = (low + high + 1) // 2
            if _text_width(remaining[:midpoint], size, font) <= max_width:
                low = midpoint
            else:
                high = midpoint - 1
        split_at = low
        if split_at < len(remaining):
            whitespace = remaining.rfind(" ", 0, split_at + 1)
            if whitespace > 0:
                split_at = whitespace
        piece = remaining[:split_at].strip()
        if not piece:
            piece = remaining[0]
            split_at = 1
        pieces.append(piece)
        remaining = remaining[split_at:].strip()
    return pieces


def _wrap_lines(
    text: str,
    max_width: float,
    size: float,
    font: str = "F1",
    max_lines: int = 2,
) -> list[str]:
    normalized = " ".join(str(text).split())
    lines = _split_to_width(normalized, max_width, size, font)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    kept[-1] = _fit_line(kept[-1], max_width, size, font, force_ellipsis=True)
    return kept


def _single_line(text: str, max_width: float, size: float, font: str = "F1") -> str:
    return _fit_line(text, max_width, size, font)


def _label_value_block(
    label: str,
    value: str,
    x: float,
    y: float,
    label_width: float,
    value_width: float,
    value_font: str = "F1",
    value_color: tuple[float, float, float] = (0, 0, 0),
    max_lines: int = 2,
    line_step: float = 10,
) -> tuple[str, float]:
    size = 8.5
    parts = [_text_op(_single_line(label, label_width, size, "F2"), x, y, size, font="F2")]
    final_y = y
    for index, line in enumerate(
        _wrap_lines(value, value_width, size, value_font, max_lines=max_lines)
    ):
        line_y = y - index * line_step
        parts.append(
            _text_op(
                line,
                x + label_width,
                line_y,
                size,
                font=value_font,
                color=value_color,
            )
        )
        final_y = line_y
    return "".join(parts), final_y


def _display(evidence: Evidence) -> str:
    return evidence.display()


def _split_evidence_slots(evidence: Evidence, count: int) -> list[str]:
    if evidence.state != EvidenceState.DETECTED:
        return [evidence.display()] * count
    values = [part.strip() for part in evidence.value.split(";") if part.strip()]
    values = values[:count]
    while len(values) < count:
        values.append("Not detected")
    return values


def _requested_method(wipe_method: str) -> str:
    if wipe_method == "secure":
        return "Secure erase (requested, not executed)"
    if wipe_method == "quick":
        return "Quick erase (requested, not executed)"
    cleaned = " ".join(wipe_method.split()) or "Unspecified method"
    return f"{cleaned} (requested, not executed)"


def _check_from_evidence(
    evidence: Evidence,
    detected_label: str | None = None,
    functional_note: bool = False,
) -> str:
    if evidence.state != EvidenceState.DETECTED:
        return evidence.display()
    label = detected_label or evidence.value
    if functional_note:
        label = f"function not tested; {label}"
    return f"Detected ({label})"


def build_report_data(
    wipe_method: str,
    metadata: dict | None = None,
    snapshot: HardwareSnapshot | None = None,
    generated_at: datetime | None = None,
    report_id: str | None = None,
) -> dict:
    metadata = metadata or {}
    hardware = snapshot or collect_hardware_snapshot()
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    identifier = report_id or str(uuid.uuid4()).upper()
    disk = hardware.first_disk()

    if disk:
        disk_name = f"Disk 1 ({disk.name})"
        disk_vendor = disk.vendor
        disk_model = disk.model
        disk_serial = disk.serial
        disk_size = disk.capacity
        disk_bus = disk.transport
        disk_sectors = disk.sector_count
        disk_health = disk.health
        disk_summary = _join_values([disk.model, disk.capacity, disk.transport])
    else:
        disk_name = f"Disk 1 ({hardware.disk_probe.display()})"
        disk_vendor = hardware.disk_probe.display()
        disk_model = hardware.disk_probe.display()
        disk_serial = hardware.disk_probe.display()
        disk_size = hardware.disk_probe.display()
        disk_bus = hardware.disk_probe.display()
        disk_sectors = hardware.disk_probe.display()
        disk_health = hardware.disk_probe.display()
        disk_summary = hardware.disk_probe.display()

    network_slots = _split_evidence_slots(hardware.field("networks"), 2)
    usb_slots = _split_evidence_slots(hardware.field("usb_devices"), 3)
    chassis = " ".join(str(metadata.get("chassis_type", "")).split())
    if not chassis:
        chassis = _display(hardware.field("chassis_type"))

    generated_text = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    model_for_header = _display(hardware.field("model"))
    report = {
        "header_bar": f"{generated_text}, REBOOT HARDWARE ANALYSIS, {hardware.os_name.upper()}, {model_for_header}",
        "custom_fields": {
            "Asset ID": " ".join(str(metadata.get("asset_id", "")).split()) or "Not provided",
            "Operator Name": " ".join(str(metadata.get("operator_name", "")).split()) or "Not provided",
        },
        "analysis_results": {
            "Disk": disk_name,
            "Vendor": disk_vendor,
            "Model": disk_model,
            "Serial": disk_serial,
            "Size": disk_size,
            "Bus": disk_bus,
            "Sectors": disk_sectors,
            "HPA": "Not reported",
            "DCO": "Not reported",
            "Remapped Sector(s)": "Not reported",
            "Health Status": disk_health,
            "Generated / End": f"{generated_text} / Not applicable",
            "Duration": "Not applicable",
            "Method": _requested_method(wipe_method),
            "Erasure Rounds": "0",
            "Status": "Analysis only - erasure not performed",
            "Report ID": identifier,
        },
        "hardware_details": {
            "Manufacturer": _display(hardware.field("manufacturer")),
            "Chassis Type": chassis,
            "Model": _display(hardware.field("model")),
            "Serial": _display(hardware.field("serial")),
            "UUID": _display(hardware.field("uuid")),
            "System SKU": _display(hardware.field("sku")),
            "Processor": _display(hardware.field("processor")),
            "CPU Topology": (
                f"{_display(hardware.field('cpu_threads'))}; "
                f"{_display(hardware.field('cpu_cores'))}"
            ),
            "Memory": _display(hardware.field("memory")),
            "Graphics Card": _display(hardware.field("graphics")),
            "Current Resolution": _display(hardware.field("displays")),
            "Sound Devices": _display(hardware.field("audio")),
            "Storage Controller": _display(hardware.field("storage_controller")),
            "Disk 1": disk_summary,
            "Network Adapter 1": network_slots[0],
            "Network Adapter 2": network_slots[1],
            "USB Device 1": usb_slots[0],
            "USB Device 2": usb_slots[1],
            "USB Device 3": usb_slots[2],
            "Motherboard": _display(hardware.field("motherboard")),
            "BIOS / Firmware": _display(hardware.field("bios")),
            "Security Features": _display(hardware.field("bios_features")),
            "Ports": _display(hardware.field("ports")),
            "Battery": _display(hardware.field("battery")),
            "TPM / Hardware Security": _display(hardware.field("security_module")),
        },
        "hardware_check_left": {
            "Battery Capacity": _check_from_evidence(hardware.field("battery")),
            "CPU": _check_from_evidence(hardware.field("processor")),
            "Display": _check_from_evidence(hardware.field("displays"), functional_note=True),
            "PC Speaker": _check_from_evidence(hardware.field("audio_output"), functional_note=True),
            "Optical Drive": _check_from_evidence(hardware.field("optical_drive"), functional_note=True),
            "Network Adapter": _check_from_evidence(hardware.field("networks"), functional_note=True),
        },
        "hardware_check_right": {
            "Motherboard": _check_from_evidence(hardware.field("motherboard")),
            "Pointer": _check_from_evidence(hardware.field("pointer"), functional_note=True),
            "Keyboard": _check_from_evidence(hardware.field("keyboard"), functional_note=True),
            "Webcam": _check_from_evidence(hardware.field("cameras"), functional_note=True),
            "USB Ports": _check_from_evidence(hardware.field("ports"), functional_note=True),
            "Wi-Fi Adapter": _check_from_evidence(hardware.field("wifi"), functional_note=True),
        },
        "identifier_type": "report_id",
        "identifier_value": identifier,
        "generated_at": timestamp.isoformat(),
        "minimum_content_y": None,
    }
    # Preserve the previous programmatic key while rendering and documentation
    # use analysis-only language.
    report["erasure_results"] = report["analysis_results"]
    return report


def _join_values(values: list[str]) -> str:
    return ", ".join(value for value in values if value and value != "Not reported") or "Not reported"


def _status_color(value: str) -> tuple[float, float, float]:
    lowered = value.lower()
    if any(word in lowered for word in ("detected", "good", "verified", "passed")) and not lowered.startswith(
        "not detected"
    ):
        return (0.0, 0.48, 0.0)
    if any(
        phrase in lowered
        for phrase in (
            "unavailable",
            "not tested",
            "not detected",
            "not performed",
            "analysis only",
            "not reported",
        )
    ):
        return (0.78, 0.43, 0.0)
    return (0.0, 0.0, 0.0)


def _build_report_content(report: dict) -> str:
    layout = REPORT_LAYOUT
    parts: list[str] = []
    minimum_y = PAGE_HEIGHT

    def track_block(block_end_y: float) -> None:
        nonlocal minimum_y
        minimum_y = min(minimum_y, block_end_y + HELVETICA_DESCENT * 8.5)

    def add_text(
        text: str,
        x: float,
        y: float,
        size: float,
        font: str = "F1",
        color: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        nonlocal minimum_y
        minimum_y = min(minimum_y, y + HELVETICA_DESCENT * size)
        parts.append(_text_op(text, x, y, size, font=font, color=color))

    header = layout["header_bar"]
    parts.append(
        _rect_fill_op(
            header["x"],
            header["y"],
            header["width"],
            header["height"],
            header["color"],
        )
    )
    add_text(
        _single_line(
            report["header_bar"],
            PAGE_WIDTH - header["text_x"] - SAFE_RIGHT_MARGIN,
            header["text_size"],
        ),
        header["text_x"],
        _baseline_for_visual_center(header["center_y"], header["text_size"]),
        header["text_size"],
        color=(1, 1, 1),
    )

    row = layout["brand_row"]
    add_text(
        "Data Erasure Report",
        row["title_x"],
        _baseline_for_visual_center(row["center_y"], row["title_size"]),
        row["title_size"],
        font="F2",
    )
    parts.append(_build_logo_ops())

    sections = layout["sections"]
    parts.append(_section_title("Custom Fields", sections["custom_title_y"]))
    custom = report["custom_fields"]
    block, block_end = _label_value_block(
        "Asset ID:",
        custom["Asset ID"],
        22,
        sections["custom_row_y"],
        48,
        285 - (22 + 48),
        max_lines=1,
    )
    parts.append(block)
    track_block(block_end)
    block, block_end = _label_value_block(
        "Operator Name:",
        custom["Operator Name"],
        305,
        sections["custom_row_y"],
        75,
        573 - (305 + 75),
        max_lines=1,
    )
    parts.append(block)
    track_block(block_end)

    parts.append(_section_title("Analysis / Erasure Status", sections["analysis_title_y"]))
    analysis = report["analysis_results"]
    add_text(
        _single_line(analysis["Disk"], 573 - 22, 9.5, "F2"),
        22,
        sections["analysis_disk_y"],
        9.5,
        font="F2",
    )

    grid_rows = (
        (("Vendor", "Vendor"), ("Model", "Model"), ("Serial", "Serial")),
        (("Size", "Size"), ("Bus", "Bus"), ("Sectors", "Sectors")),
        (("HPA", "HPA"), ("DCO", "DCO"), ("Remapped", "Remapped Sector(s)")),
    )
    for y, row_cells in zip(layout["analysis"]["grid_y"], grid_rows):
        for x, right_x, (label, key) in zip(
            layout["analysis"]["grid_x"],
            layout["analysis"]["grid_right_x"],
            row_cells,
        ):
            block, block_end = _label_value_block(
                f"{label}:",
                analysis[key],
                x,
                y,
                layout["analysis"]["grid_label_width"],
                right_x - (x + layout["analysis"]["grid_label_width"]),
                max_lines=1,
            )
            parts.append(block)
            track_block(block_end)

    detail_rows = (
        ("Health Status", "Health Status"),
        ("Generated / End", "Generated / End"),
        ("Duration", "Duration"),
        ("Method", "Method"),
        ("Erasure Rounds", "Erasure Rounds"),
        ("Status / Report ID", "Status"),
    )
    for y, (label, key) in zip(layout["analysis"]["detail_y"], detail_rows):
        value = analysis[key]
        if key == "Status":
            value = f"{value}; ID {analysis['Report ID']}"
        block, block_end = _label_value_block(
            f"{label}:",
            value,
            layout["analysis"]["detail_x"],
            y,
            layout["analysis"]["detail_label_width"],
            layout["analysis"]["detail_right_x"]
            - (
                layout["analysis"]["detail_x"]
                + layout["analysis"]["detail_label_width"]
            ),
            value_font="F2" if key == "Status" else "F1",
            value_color=_status_color(value) if key in {"Status", "Health Status"} else (0, 0, 0),
            max_lines=1,
        )
        parts.append(block)
        track_block(block_end)

    parts.append(_section_title("Hardware Details", sections["hardware_title_y"]))
    hardware_items = list(report["hardware_details"].items())
    midpoint = (len(hardware_items) + 1) // 2
    columns = (hardware_items[:midpoint], hardware_items[midpoint:])
    for column_index, (x, items) in enumerate(
        zip((layout["hardware"]["left_x"], layout["hardware"]["right_x"]), columns)
    ):
        label_width = layout["hardware"]["label_width"][column_index]
        value_width = (
            layout["hardware"]["column_right_x"][column_index] - (x + label_width)
        )
        for index, (label, value) in enumerate(items):
            y = layout["hardware"]["start_y"] - index * layout["hardware"]["row_gap"]
            block, block_end = _label_value_block(
                f"{label}:",
                value,
                x,
                y,
                label_width,
                value_width,
                max_lines=1,
            )
            parts.append(block)
            track_block(block_end)

    parts.append(_section_title("Hardware Evidence Check", sections["checks_title_y"]))
    check_columns = (report["hardware_check_left"], report["hardware_check_right"])
    for column_index, (x, checks) in enumerate(
        zip((layout["checks"]["left_x"], layout["checks"]["right_x"]), check_columns)
    ):
        value_width = (
            layout["checks"]["column_right_x"][column_index]
            - (x + layout["checks"]["label_width"])
        )
        for index, (label, value) in enumerate(checks.items()):
            y = layout["checks"]["start_y"] - index * layout["checks"]["row_gap"]
            block, block_end = _label_value_block(
                f"{label}:",
                value,
                x,
                y,
                layout["checks"]["label_width"],
                value_width,
                value_color=_status_color(value),
                max_lines=2,
            )
            parts.append(block)
            track_block(block_end)

    if minimum_y < SAFE_BOTTOM_MARGIN:
        raise ValueError(f"Report content crossed safe bottom margin: {minimum_y:.1f}")
    report["minimum_content_y"] = minimum_y
    return "".join(parts)


def _build_report_pdf(content: str) -> bytes:
    content_bytes = content.encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(content_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + content_bytes
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
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


def get_device_identifier(snapshot: HardwareSnapshot | None = None) -> tuple[str, str]:
    hardware = snapshot or collect_hardware_snapshot()
    serial = hardware.field("serial")
    if serial.state == EvidenceState.DETECTED:
        return "serial_number", serial.value
    device_uuid = hardware.field("uuid")
    if device_uuid.state == EvidenceState.DETECTED:
        return "hardware_uuid", device_uuid.value
    return "unavailable", "Unavailable"


def _sanitize_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def generate_hardware_report(
    wipe_method: str,
    metadata: dict | None = None,
    output_dir: Path | None = None,
    snapshot: HardwareSnapshot | None = None,
    generated_at: datetime | None = None,
) -> Path:
    report = build_report_data(
        wipe_method,
        metadata=metadata,
        snapshot=snapshot,
        generated_at=generated_at,
    )
    directory = output_dir or Path(__file__).resolve().parents[2] / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    file_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ident = _sanitize_filename_part(report["identifier_value"])[:12]
    output_path = directory / f"reboot_hardware_analysis_{file_stamp}_{ident}.pdf"
    content = _build_report_content(report)
    output_path.write_bytes(_build_report_pdf(content))
    return output_path


def generate_erase_certificate(
    wipe_method: str,
    metadata: dict | None = None,
    output_dir: Path | None = None,
    snapshot: HardwareSnapshot | None = None,
    generated_at: datetime | None = None,
) -> Path:
    return generate_hardware_report(
        wipe_method,
        metadata=metadata,
        output_dir=output_dir,
        snapshot=snapshot,
        generated_at=generated_at,
    )


def open_certificate(path: Path) -> None:
    """Open a generated file; the Darwin branch is developer convenience only."""
    if platform.system() == "Linux":
        subprocess.run(["xdg-open", str(path)], check=False)
        return
    if platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    raise RuntimeError("Automatic report opening is supported on Linux production hosts only")
