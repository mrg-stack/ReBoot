"""Cross-platform hardware detection helpers used by the hardware screen."""

import platform
import psutil
import subprocess


def _read_sysctl_value(key):
    """Return a sysctl value string or None when unavailable."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", key],
            capture_output=True,
            text=True,
            check=False,
        )
        value = result.stdout.strip()
        return value if value else None
    except Exception:
        return None


def _format_cpu_frequency_ghz():
    """Return current CPU frequency in GHz when it can be resolved."""
    freq = psutil.cpu_freq()
    if freq and freq.current and freq.current > 0:
        # psutil returns MHz.
        return f"{freq.current / 1000:.2f} GHz"

    hz = _read_sysctl_value("hw.cpufrequency") or _read_sysctl_value("hw.cpufrequency_max")
    if not hz:
        return None

    try:
        return f"{int(hz) / 1_000_000_000:.2f} GHz"
    except ValueError:
        return None


def get_system_info():
    """Collect system information using an OS-specific strategy."""
    system = platform.system()

    if system == "Darwin":
        return get_mac_info()
    elif system == "Linux":
        return get_linux_info()
    else:
        return get_unknown_info()


def get_mac_info():
    """Collect macOS hardware details with Apple Silicon-friendly fallbacks."""
    brand = _read_sysctl_value("machdep.cpu.brand_string")
    chip = _read_sysctl_value("hw.model")
    model = brand or chip or "Unknown CPU"
    arch = platform.machine() or platform.processor() or "Unknown architecture"
    physical_cores = _read_sysctl_value("hw.physicalcpu") or str(psutil.cpu_count(logical=False) or "?")
    logical_cores = _read_sysctl_value("hw.logicalcpu") or str(psutil.cpu_count(logical=True) or "?")
    core_text = f"{physical_cores}C/{logical_cores}T"
    speed = _format_cpu_frequency_ghz()

    cpu_parts = [model]
    cpu_parts.append(f"({arch})")
    cpu_parts.append(core_text)
    if speed:
        cpu_parts.append(f"@ {speed}")

    cpu = " ".join(cpu_parts)

    ram_bytes = psutil.virtual_memory().total
    ram_gb = round(ram_bytes / (1024**3), 1)

    disk_bytes = psutil.disk_usage('/').total
    disk_gb = round(disk_bytes / (1024**3), 1)

    return {
        "cpu": cpu,
        "cpu_model": model,
        "cpu_arch": arch,
        "cpu_cores": core_text,
        "cpu_speed": speed or "Unknown speed",
        "ram": f"{ram_gb} GB ({int(ram_bytes / (1024**2))} MB)",
        "disk": f"{disk_gb} GB"
    }


def get_linux_info():
    """Collect Linux hardware details from inxi output."""
    try:
        result = subprocess.run(
            ["inxi", "-Fxz"],
            capture_output=True,
            text=True
        )
        output = result.stdout

        cpu = "Unknown CPU"
        ram = "Unknown RAM"
        disk = "Unknown Disk"

        for line in output.split("\n"):
            if "CPU:" in line:
                cpu = line.strip()
            elif "Memory:" in line:
                ram = line.strip()
            elif "Drives:" in line:
                disk = line.strip()

        return {
            "cpu": cpu,
            "cpu_model": cpu,
            "cpu_arch": "Unknown architecture",
            "cpu_cores": "Unknown cores",
            "cpu_speed": "Unknown speed",
            "ram": ram,
            "disk": disk
        }

    except Exception:
        return get_unknown_info()


def get_unknown_info():
    """Return a safe default payload for unsupported platforms."""
    return {
        "cpu": "Unknown CPU",
        "cpu_model": "Unknown CPU",
        "cpu_arch": "Unknown architecture",
        "cpu_cores": "Unknown cores",
        "cpu_speed": "Unknown speed",
        "ram": "Unknown RAM",
        "disk": "Unknown Disk"
    }