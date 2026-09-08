"""Linux x86-64 hardware summary used by the hardware screen."""

from pathlib import Path

from services.hardware_report import (
    CommandRunner,
    HardwareSnapshot,
    collect_hardware_snapshot,
    create_development_snapshot,
    run_command,
)


def get_system_info(
    os_name: str | None = None,
    machine: str | None = None,
    runner: CommandRunner = run_command,
    root: Path = Path("/"),
    *,
    development_mode: bool = False,
    snapshot: HardwareSnapshot | None = None,
) -> dict[str, str | bool]:
    """Return a normalized production or explicitly simulated summary.

    Unsupported operating systems and architectures raise
    ``UnsupportedPlatformError`` from the report collector instead of
    returning misleading placeholder or host-specific data.
    """
    if development_mode:
        if snapshot is not None and not snapshot.simulated:
            raise ValueError("development_mode requires a simulated hardware snapshot")
        hardware = snapshot or create_development_snapshot()
    else:
        hardware = snapshot or collect_hardware_snapshot(
            os_name=os_name,
            machine=machine,
            runner=runner,
            root=root,
        )
    return system_info_from_snapshot(hardware)


def system_info_from_snapshot(snapshot: HardwareSnapshot) -> dict[str, str | bool]:
    disk = snapshot.first_disk()
    disk_text = disk.capacity if disk else snapshot.disk_probe.display()
    cpu_model = snapshot.field("processor").display()
    cpu_cores = snapshot.field("cpu_cores").display()
    cpu_threads = snapshot.field("cpu_threads").display()
    cpu_topology = f"{cpu_threads} / {cpu_cores}"
    cpu_speed = snapshot.field("cpu_speed").display()
    return {
        "cpu": f"{cpu_model} ({snapshot.architecture}) {cpu_topology} @ {cpu_speed}",
        "cpu_model": cpu_model,
        "cpu_arch": snapshot.architecture,
        "cpu_cores": cpu_topology,
        "cpu_threads": cpu_threads,
        "cpu_speed": cpu_speed,
        "ram": snapshot.field("memory").display(),
        "disk": disk_text,
        "simulated": snapshot.simulated,
    }


def get_linux_info(
    machine: str | None = None,
    runner: CommandRunner = run_command,
    root: Path = Path("/"),
) -> dict[str, str]:
    """Compatibility wrapper for the Linux-only hardware UI path."""
    return get_system_info("Linux", machine=machine, runner=runner, root=root)
