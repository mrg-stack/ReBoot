from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from services.certificate import (  # noqa: E402
    HELVETICA_ASCENT,
    HELVETICA_DESCENT,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    SAFE_BOTTOM_MARGIN,
    SAFE_LEFT_MARGIN,
    SAFE_RIGHT_MARGIN,
    _build_report_content,
    _build_report_pdf,
    _text_width,
    build_report_data,
    generate_hardware_report,
    header_alignment_geometry,
)
from services.hardware_report import (  # noqa: E402
    CommandResult,
    Evidence,
    EvidenceState,
    UnsupportedPlatformError,
    _combine_evidence,
    collect_hardware_snapshot,
    create_development_snapshot,
    detected,
    not_detected,
    not_tested,
    unavailable,
)
from services.system_info import get_system_info  # noqa: E402
from core.hardware import HardwareScreen  # noqa: E402
from core.recommendation import RecommendationScreen  # noqa: E402
from core.secure_erase import SecureEraseScreen  # noqa: E402
from ui.welcome import WelcomeScreen  # noqa: E402


def write_text(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def build_linux_fixture(root: Path) -> None:
    dmi = {
        "sys_vendor": "Example PC Corporation",
        "product_name": "Example Workstation 7000",
        "product_serial": "SYSTEM-SERIAL",
        "product_uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "product_sku": "PC-7000",
        "chassis_type": "3",
        "board_vendor": "Example Boards",
        "board_name": "X64-Pro",
        "board_version": "1.0",
        "bios_vendor": "Example Firmware",
        "bios_version": "2.4.1",
        "bios_date": "08/20/2026",
    }
    for name, value in dmi.items():
        write_text(root, f"sys/class/dmi/id/{name}", value)

    write_text(
        root,
        "proc/cpuinfo",
        "\n".join(
            [
                "processor : 0",
                "physical id : 0",
                "core id : 0",
                "model name : Example x86-64 CPU",
                "cpu MHz : 3200.000",
                "",
                "processor : 1",
                "physical id : 0",
                "core id : 0",
                "model name : Example x86-64 CPU",
                "cpu MHz : 3200.000",
            ]
        ),
    )
    write_text(root, "proc/meminfo", "MemTotal:       16384000 kB\n")
    write_text(
        root,
        "proc/bus/input/devices",
        'N: Name="AT Translated Set 2 keyboard"\n\nN: Name="USB Optical Mouse"\n',
    )
    write_text(root, "proc/asound/cards", " 0 [PCH            ]: HDA-Intel - Example HD Audio\n")
    write_text(
        root,
        "proc/asound/pcm",
        "00-00: Example Analog : playback 1 : capture 1\n",
    )

    write_text(root, "sys/class/net/enp0s1/operstate", "up\n")
    write_text(root, "sys/class/net/wlp2s0/operstate", "down\n")
    (root / "sys/class/net/enp0s1/device").mkdir(parents=True)
    (root / "sys/class/net/wlp2s0/device").mkdir(parents=True)
    (root / "sys/class/net/wlp2s0/wireless").mkdir(parents=True)

    write_text(root, "sys/class/power_supply/BAT0/type", "Battery\n")
    write_text(root, "sys/class/power_supply/BAT0/capacity", "87\n")
    write_text(root, "sys/class/power_supply/BAT0/status", "Discharging\n")
    write_text(root, "sys/class/power_supply/BAT0/cycle_count", "112\n")

    write_text(root, "sys/class/tpm/tpm0/device/description", "TPM 2.0 Device\n")
    write_text(root, "sys/class/tpm/tpm0/tpm_version_major", "2\n")
    write_text(root, "sys/class/video4linux/video0/name", "Integrated Webcam\n")
    (root / "dev").mkdir(parents=True)
    (root / "dev/video0").touch()

    write_text(root, "sys/class/drm/card0-HDMI-A-1/status", "connected\n")
    write_text(root, "sys/class/drm/card0-HDMI-A-1/modes", "1920x1080\n1280x720\n")
    write_text(root, "sys/class/drm/card0-DP-1/status", "disconnected\n")

    write_text(root, "sys/bus/thunderbolt/devices/domain0/device_name", "USB4 host router\n")
    write_text(root, "sys/bus/thunderbolt/devices/domain0/vendor_name", "Example Silicon\n")

    efivar = root / "sys/firmware/efi/efivars/SecureBoot-fixture"
    efivar.parent.mkdir(parents=True)
    efivar.write_bytes(b"\x07\x00\x00\x00\x01")

    (root / "sys/class/block").mkdir(parents=True)
    (root / "sys/class/block/sr0").mkdir()


def linux_runner(args: list[str]) -> CommandResult:
    if args[0] == "lsblk":
        return CommandResult(
            tuple(args),
            0,
            json.dumps(
                {
                    "blockdevices": [
                        {
                            "name": "sda",
                            "path": "/dev/sda",
                            "type": "disk",
                            "size": 512000000000,
                            "model": "Example SSD",
                            "serial": "DISK-ONLY-SERIAL",
                            "tran": "sata",
                            "vendor": "Example Storage",
                            "log-sec": 512,
                            "rota": False,
                            "state": "running",
                            "rev": "1A",
                            "rm": False,
                        },
                        {
                            "name": "sr0",
                            "path": "/dev/sr0",
                            "type": "rom",
                            "model": "DVD-RW",
                            "vendor": "Example Optical",
                        },
                    ]
                }
            ),
        )
    if args[0] == "lspci":
        return CommandResult(
            tuple(args),
            0,
            "\n".join(
                [
                    "00:02.0 VGA compatible controller: Example Integrated Graphics",
                    "00:1f.3 Audio device: Example HD Audio",
                    "00:17.0 SATA controller: Example SATA Controller",
                    "00:14.0 USB controller: Example xHCI Controller",
                    "00:07.0 USB4 controller: Example USB4 Host Interface",
                ]
            ),
        )
    if args[0] == "lsusb":
        return CommandResult(
            tuple(args),
            0,
            "Bus 001 Device 002: ID 1234:5678 Example USB Keyboard\n",
        )
    return CommandResult(tuple(args), None, error="unexpected command")


class HardwareReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture_root = ROOT / "tests/.hardware-report-fixture"
        shutil.rmtree(self.fixture_root, ignore_errors=True)
        build_linux_fixture(self.fixture_root)

    def tearDown(self):
        shutil.rmtree(self.fixture_root, ignore_errors=True)

    def collect(self, runner=linux_runner, machine="x86_64"):
        return collect_hardware_snapshot(
            "Linux",
            machine=machine,
            runner=runner,
            root=self.fixture_root,
        )

    def test_linux_x86_64_collection_covers_report_evidence(self):
        snapshot = self.collect()

        self.assertEqual(snapshot.os_name, "Linux")
        self.assertEqual(snapshot.architecture, "x86_64")
        self.assertEqual(snapshot.field("manufacturer").value, "Example PC Corporation")
        self.assertEqual(snapshot.field("chassis_type").value, "Desktop (DMI 3)")
        self.assertEqual(snapshot.field("processor").value, "Example x86-64 CPU")
        self.assertEqual(snapshot.field("cpu_cores").value, "1 physical core")
        self.assertEqual(snapshot.field("cpu_threads").value, "2 logical threads")
        self.assertEqual(snapshot.field("cpu_speed").value, "3.20 GHz")
        self.assertIn("16.8 GB", snapshot.field("memory").value)
        self.assertIn("1920x1080", snapshot.field("displays").value)
        self.assertIn("USB4", snapshot.field("thunderbolt").value)
        self.assertIn("USB4", snapshot.field("ports").value)
        self.assertIn("Secure Boot enabled", snapshot.field("bios_features").value)
        self.assertIn("/dev/sr0", snapshot.field("optical_drive").value)
        self.assertIn("Integrated Webcam", snapshot.field("cameras").value)
        self.assertIn("TPM 2.0", snapshot.field("security_module").value)
        self.assertEqual(snapshot.field("keyboard").state, EvidenceState.DETECTED)
        self.assertEqual(snapshot.field("pointer").state, EvidenceState.DETECTED)
        self.assertEqual(snapshot.field("audio_input").state, EvidenceState.DETECTED)
        self.assertEqual(snapshot.field("audio_output").state, EvidenceState.DETECTED)

    def test_amd64_alias_is_normalized(self):
        snapshot = self.collect(machine="amd64")
        self.assertEqual(snapshot.architecture, "x86_64")

    def test_darwin_is_rejected_before_any_probe(self):
        calls = []

        def runner(args):
            calls.append(args)
            return CommandResult(tuple(args), 0)

        with self.assertRaisesRegex(UnsupportedPlatformError, "supports Linux only"):
            collect_hardware_snapshot("Darwin", machine="x86_64", runner=runner)
        self.assertEqual(calls, [])

    def test_linux_arm64_is_rejected_before_any_probe(self):
        calls = []

        def runner(args):
            calls.append(args)
            return CommandResult(tuple(args), 0)

        with self.assertRaisesRegex(UnsupportedPlatformError, "x86-64.*arm64"):
            collect_hardware_snapshot("Linux", machine="arm64", runner=runner)
        self.assertEqual(calls, [])

    def test_development_snapshot_is_deterministic_and_never_probes_darwin(self):
        first = create_development_snapshot()
        second = create_development_snapshot()

        self.assertEqual(first, second)
        self.assertTrue(first.simulated)
        self.assertEqual(first.os_name, "Linux")
        self.assertEqual(first.architecture, "x86_64")
        self.assertEqual(first.field("manufacturer").value, "ReBoot Development Fixture")
        self.assertEqual(first.field("model").value, "Simulated AMD64 PC")
        self.assertEqual(first.field("serial").value, "SIMULATED-SYSTEM-SERIAL")
        self.assertEqual(first.first_disk().model, "Simulated NVMe SSD")

        runner = Mock(side_effect=AssertionError("development mode must not run probes"))
        with patch(
            "services.system_info.collect_hardware_snapshot",
            side_effect=AssertionError("production collector must not run"),
        ) as collector:
            info = get_system_info(
                "Darwin",
                machine="arm64",
                runner=runner,
                development_mode=True,
            )

        collector.assert_not_called()
        runner.assert_not_called()
        self.assertTrue(info["simulated"])
        self.assertEqual(info["cpu_arch"], "x86_64")
        self.assertIn("Simulated x86-64 Processor", info["cpu_model"])

    def test_successful_empty_probe_differs_from_unavailable_probe(self):
        def empty_runner(args):
            if args[0] == "lsblk":
                return CommandResult(tuple(args), 0, '{"blockdevices": []}')
            return CommandResult(tuple(args), 0, "")

        empty = self.collect(runner=empty_runner)
        missing = self.collect(
            runner=lambda args: CommandResult(tuple(args), None, error="tool missing")
        )

        self.assertEqual(empty.disk_probe.state, EvidenceState.NOT_DETECTED)
        self.assertEqual(empty.field("usb_devices").state, EvidenceState.NOT_DETECTED)
        self.assertEqual(missing.disk_probe.state, EvidenceState.UNAVAILABLE)
        self.assertEqual(missing.field("usb_devices").state, EvidenceState.UNAVAILABLE)
        self.assertIn("tool missing", missing.field("usb_devices").display())

    def test_cpu_threads_remain_detected_when_physical_topology_is_unavailable(self):
        write_text(
            self.fixture_root,
            "proc/cpuinfo",
            "\n\n".join(
                f"processor : {index}\nmodel name : Example CPU"
                for index in range(4)
            ),
        )

        snapshot = self.collect()

        self.assertEqual(snapshot.field("cpu_cores").state, EvidenceState.UNAVAILABLE)
        self.assertIn("physical core topology", snapshot.field("cpu_cores").display())
        self.assertEqual(snapshot.field("cpu_threads"), detected("4 logical threads"))
        report = build_report_data("quick", snapshot=snapshot, report_id="CPU-UNKNOWN")
        self.assertIn("4 logical threads", report["hardware_details"]["CPU Topology"])
        self.assertIn(
            "Unavailable (physical core topology not reported)",
            report["hardware_details"]["CPU Topology"],
        )
        self.assertIn("4 logical threads", _build_report_content(report))

    def test_network_collection_excludes_virtual_and_unbacked_interfaces(self):
        virtual_names = (
            "lo",
            "docker0",
            "br0",
            "br-deadbeef",
            "virbr0",
            "veth1234",
            "dummy0",
            "tun0",
            "tap0",
            "tailscale0",
            "wg0",
            "vxlan0",
        )
        for name in virtual_names:
            write_text(self.fixture_root, f"sys/class/net/{name}/operstate", "up\n")
            (self.fixture_root / f"sys/class/net/{name}/device").mkdir(parents=True)
        write_text(self.fixture_root, "sys/class/net/mystery0/operstate", "up\n")

        snapshot = self.collect()
        networks = snapshot.field("networks")

        self.assertEqual(networks.state, EvidenceState.DETECTED)
        self.assertIn("enp0s1", networks.value)
        self.assertIn("wlp2s0", networks.value)
        for name in (*virtual_names, "mystery0"):
            self.assertNotIn(name, networks.value)

    def test_combined_evidence_truth_table_preserves_uncertainty(self):
        cases: tuple[tuple[str, list[Evidence], EvidenceState], ...] = (
            ("detected overrides unavailable", [detected("USB"), unavailable("PCI")], EvidenceState.DETECTED),
            ("detected overrides absent", [detected("USB"), not_detected()], EvidenceState.DETECTED),
            ("unavailable plus absent", [unavailable("PCI"), not_detected()], EvidenceState.UNAVAILABLE),
            ("unavailable plus not tested", [unavailable("PCI"), not_tested()], EvidenceState.UNAVAILABLE),
            ("not tested plus absent", [not_tested(), not_detected()], EvidenceState.NOT_TESTED),
            ("all absent", [not_detected(), not_detected()], EvidenceState.NOT_DETECTED),
        )
        for label, components, expected in cases:
            with self.subTest(label):
                combined = _combine_evidence(components, "combined probe unavailable")
                self.assertEqual(combined.state, expected)

    def test_report_is_analysis_only_and_uses_actual_disk_data(self):
        snapshot = self.collect()
        report = build_report_data(
            "secure",
            metadata={"asset_id": "", "operator_name": "Test Operator", "chassis_type": "Desktop"},
            snapshot=snapshot,
            generated_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
            report_id="REPORT-123",
        )
        rendered = json.dumps(report)

        self.assertEqual(report["custom_fields"]["Asset ID"], "Not provided")
        self.assertEqual(report["analysis_results"]["Serial"], "DISK-ONLY-SERIAL")
        self.assertNotEqual(report["analysis_results"]["Serial"], "SYSTEM-SERIAL")
        self.assertEqual(report["analysis_results"]["Size"], "512.0 GB")
        self.assertEqual(report["analysis_results"]["Sectors"], "1000000000")
        self.assertEqual(report["analysis_results"]["Erasure Rounds"], "0")
        self.assertEqual(report["analysis_results"]["Duration"], "Not applicable")
        self.assertEqual(report["analysis_results"]["Status"], "Analysis only - erasure not performed")
        self.assertIn("(requested, not executed)", report["analysis_results"]["Method"])
        self.assertEqual(report["hardware_details"]["Manufacturer"], "Example PC Corporation")
        self.assertTrue(
            report["hardware_check_right"]["USB Ports"].startswith(
                "Detected (function not tested;"
            )
        )
        self.assertNotIn("NOT IMPLEMENTED", rendered.upper())
        self.assertNotIn("ERASED (SIMULATED)", rendered.upper())
        self.assertNotIn("SUCCESSFUL", rendered.upper())
        self.assertFalse(report["simulated"])
        self.assertNotIn("DEVELOPMENT SIMULATION", rendered.upper())

    def test_simulated_report_is_unmistakable_and_contains_no_host_data(self):
        output_dir = ROOT / "artifacts/test-simulation-output"
        shutil.rmtree(output_dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, output_dir, True)
        generated_at = datetime(2026, 9, 8, 10, 30, tzinfo=timezone.utc)

        with patch(
            "services.certificate.collect_hardware_snapshot",
            side_effect=AssertionError("production collector must not run"),
        ) as collector:
            path = generate_hardware_report(
                "secure",
                output_dir=output_dir,
                generated_at=generated_at,
                development_mode=True,
            )
        collector.assert_not_called()

        self.assertTrue(path.name.startswith("reboot_development_simulation_"))
        raw = path.read_bytes()
        self.assertIn(
            b"DEVELOPMENT SIMULATION - NOT A REAL HARDWARE REPORT",
            raw,
        )
        self.assertIn(b"Development simulation - erasure not performed", raw)
        self.assertIn(b"SIMULATED-DISK-SERIAL", raw)
        self.assertIn(b"Simulated AMD64 PC", raw)
        self.assertIn(b"512.0 GB \\(simulated\\)", raw)
        for forbidden in (b"Apple", b"Darwin", b"macOS", b"MacBook", b"Mac mini"):
            self.assertNotIn(forbidden, raw)

        report = build_report_data(
            "secure",
            snapshot=create_development_snapshot(),
            generated_at=generated_at,
        )
        content = _build_report_content(report)
        self.assertTrue(report["simulated"])
        self.assertEqual(report["analysis_results"]["Report ID"], "SIMULATED-REPORT-ID")
        self.assertGreaterEqual(report["minimum_content_y"], SAFE_BOTTOM_MARGIN)
        self.assertIn("Development Simulation Report", content)

    def test_normal_injected_linux_snapshot_is_not_labeled_simulation(self):
        report = build_report_data(
            "quick",
            snapshot=self.collect(),
            generated_at=datetime(2026, 9, 8, 10, 45, tzinfo=timezone.utc),
            report_id="REAL-FIXTURE-REPORT",
        )
        content = _build_report_content(report)

        self.assertFalse(report["simulated"])
        self.assertEqual(report["report_title"], "Data Erasure Report")
        self.assertEqual(
            report["analysis_results"]["Status"],
            "Analysis only - erasure not performed",
        )
        self.assertNotIn("DEVELOPMENT SIMULATION", content)

    def test_header_text_and_wordmark_share_visual_center(self):
        geometry = header_alignment_geometry()

        self.assertAlmostEqual(geometry["title_visual_center"], geometry["row_center"], places=6)
        self.assertAlmostEqual(geometry["logo_visual_center"], geometry["row_center"], places=6)
        self.assertAlmostEqual(
            geometry["title_visual_center"],
            geometry["logo_visual_center"],
            places=6,
        )

    def test_content_stays_above_margin_and_pdf_is_valid(self):
        report = build_report_data("quick", snapshot=self.collect(), report_id="REPORT-456")
        report["custom_fields"]["Asset ID"] = "W" * 200
        report["hardware_details"]["TPM / Hardware Security"] = (
            "Sécurité matérielle " + "W" * 200
        )
        report["hardware_check_right"]["USB Ports"] = "Detected (" + "W" * 200 + ")"
        content = _build_report_content(report)
        pdf = _build_report_pdf(content)

        self.assertGreaterEqual(report["minimum_content_y"], SAFE_BOTTOM_MARGIN)
        text_pattern = re.compile(
            r"BT\n/(?P<font>F[12]) (?P<size>[\d.]+) Tf\n"
            r"[\d.]+ [\d.]+ [\d.]+ rg\n"
            r"(?P<x>[\d.]+) (?P<y>[\d.]+) Td\n"
            r"\((?P<text>(?:\\.|[^\\)])*)\) Tj\nET"
        )
        operations = list(text_pattern.finditer(content))
        self.assertGreater(len(operations), 50)
        for operation in operations:
            font = operation.group("font")
            size = float(operation.group("size"))
            x = float(operation.group("x"))
            y = float(operation.group("y"))
            text = re.sub(r"\\(.)", r"\1", operation.group("text"))
            with self.subTest(text=text):
                self.assertGreaterEqual(x, SAFE_LEFT_MARGIN)
                self.assertLessEqual(
                    x + _text_width(text, size, font),
                    PAGE_WIDTH - SAFE_RIGHT_MARGIN + 0.01,
                )
                self.assertGreaterEqual(
                    y + HELVETICA_DESCENT * size,
                    SAFE_BOTTOM_MARGIN,
                )
                self.assertLessEqual(y + HELVETICA_ASCENT * size, PAGE_HEIGHT)
        self.assertIn("(TPM / Hardware Security:)", content)
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/MediaBox [0 0 595 842]", pdf)
        self.assertIn(b"Data Erasure Report", pdf)
        self.assertNotIn(b"NOT IMPLEMENTED", pdf.upper())
        self.assertNotIn(b"ERASED (SIMULATED)", pdf.upper())

    def test_hardware_ui_summary_uses_normalized_collector(self):
        info = get_system_info(
            "Linux",
            machine="x86_64",
            runner=linux_runner,
            root=self.fixture_root,
        )

        self.assertEqual(info["cpu_model"], "Example x86-64 CPU")
        self.assertEqual(info["cpu_arch"], "x86_64")
        self.assertEqual(info["cpu_cores"], "2 logical threads / 1 physical core")
        self.assertEqual(info["cpu_threads"], "2 logical threads")
        self.assertEqual(info["disk"], "512.0 GB")

    def test_secure_erase_routes_block_cleanly_on_unsupported_platform(self):
        for install_os, generator_name in (
            (True, "generate_hardware_report"),
            (False, "generate_erase_certificate"),
        ):
            screen = SimpleNamespace(
                install_os=install_os,
                wipe_method="secure",
                asset_id_input=SimpleNamespace(text=lambda: "ASSET"),
                operator_name_input=SimpleNamespace(text=lambda: "Operator"),
                chassis_type_combo=SimpleNamespace(currentText=lambda: "Desktop"),
            )
            error = UnsupportedPlatformError("Linux x86-64 only")
            with self.subTest(install_os=install_os), patch(
                f"core.secure_erase.{generator_name}",
                side_effect=error,
            ), patch("core.secure_erase.QMessageBox.critical") as critical, patch(
                "core.secure_erase.open_certificate"
            ) as opener:
                SecureEraseScreen.perform_wipe(screen)
                critical.assert_called_once_with(
                    screen,
                    "Hardware report unavailable",
                    "Linux x86-64 only",
                )
                opener.assert_not_called()

    def test_development_mode_propagates_through_every_route(self):
        checkbox = SimpleNamespace(isChecked=lambda: True)

        welcome_hardware = SimpleNamespace(
            development_mode_checkbox=checkbox,
            close=Mock(),
        )
        with patch("ui.welcome.HardwareScreen") as hardware_factory:
            hardware_factory.return_value.show = Mock()
            WelcomeScreen.open_hardware_screen(welcome_hardware)
        hardware_factory.assert_called_once_with(development_mode=True)

        welcome_erase = SimpleNamespace(
            development_mode_checkbox=checkbox,
            close=Mock(),
        )
        with patch("ui.welcome.SecureEraseScreen") as erase_factory:
            erase_factory.return_value.show = Mock()
            WelcomeScreen.secure_erase_only(welcome_erase)
        erase_factory.assert_called_once_with(
            previous_screen=welcome_erase,
            install_os=False,
            development_mode=True,
        )

        hardware = SimpleNamespace(development_mode=True, close=Mock())
        with patch("core.hardware.RecommendationScreen") as recommendation_factory:
            recommendation_factory.return_value.show = Mock()
            HardwareScreen.go_to_recommendation(hardware)
        recommendation_factory.assert_called_once_with(development_mode=True)

        recommendation = SimpleNamespace(
            development_mode=True,
            install_os=True,
            close=Mock(),
        )
        with patch("core.recommendation.SecureEraseScreen") as secure_factory:
            secure_factory.return_value.show = Mock()
            RecommendationScreen.continue_clicked(recommendation)
        secure_factory.assert_called_once_with(
            previous_screen=recommendation,
            install_os=True,
            development_mode=True,
        )

        secure = SimpleNamespace(
            development_mode=True,
            install_os=True,
            wipe_method="secure",
            asset_id_input=SimpleNamespace(text=lambda: "SIM-ASSET"),
            operator_name_input=SimpleNamespace(text=lambda: "Developer"),
            chassis_type_combo=SimpleNamespace(currentText=lambda: "Desktop"),
        )
        with patch(
            "core.secure_erase.generate_hardware_report",
            return_value=ROOT / "artifacts/simulated.pdf",
        ) as generator, patch("core.secure_erase.open_certificate"):
            SecureEraseScreen.perform_wipe(secure)
        generator.assert_called_once_with(
            "secure",
            {
                "asset_id": "SIM-ASSET",
                "operator_name": "Developer",
                "chassis_type": "Desktop",
            },
            development_mode=True,
        )

    def test_generator_writes_to_requested_project_artifact_directory(self):
        output_dir = ROOT / "artifacts/test-output"
        shutil.rmtree(output_dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, output_dir, True)

        path = generate_hardware_report("secure", output_dir=output_dir, snapshot=self.collect())

        self.assertEqual(path.parent, output_dir)
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
