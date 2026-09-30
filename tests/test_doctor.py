"""Tests for the doctor checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from screensmith import doctor
from screensmith.output import Output
from screensmith.session import Session


def _session(session_type: str = "wayland") -> Session:
    return Session(type=session_type, plasma="6.7.5", config_home=Path("/nonexistent"))


def _run(session: Session, *, outputs: list[Output], have_kscreen: bool = True):
    with (
        mock.patch.object(doctor, "have", return_value=have_kscreen),
        mock.patch.object(doctor.output_mod, "query_outputs", return_value=outputs),
    ):
        return doctor.diagnose(session)


def _by_title(findings, needle: str):
    return [f for f in findings if needle in f.title]


class SessionCheckTests(unittest.TestCase):
    def test_wayland_is_ok(self):
        findings = _run(_session("wayland"), outputs=[])
        self.assertEqual(_by_title(findings, "Session")[0].severity, "ok")

    def test_x11_is_an_error_because_fractional_scaling_needs_wayland(self):
        findings = _run(_session("x11"), outputs=[])
        session_finding = _by_title(findings, "Session")[0]
        self.assertEqual(session_finding.severity, "error")
        self.assertIn("Wayland", session_finding.hint)


class ToolingCheckTests(unittest.TestCase):
    def test_missing_kscreen_is_an_error(self):
        findings = _run(_session(), outputs=[], have_kscreen=False)
        self.assertEqual(_by_title(findings, "kscreen-doctor")[0].severity, "error")

    def test_missing_kscreen_skips_output_checks(self):
        findings = _run(_session(), outputs=[], have_kscreen=False)
        self.assertEqual(_by_title(findings, "Outputs"), [])

    def test_a_query_failure_degrades_without_crashing(self):
        with (
            mock.patch.object(doctor, "have", return_value=True),
            mock.patch.object(doctor.output_mod, "query_outputs", side_effect=OSError("no dbus")),
        ):
            findings = doctor.diagnose(_session())
        # Must not raise; the outputs check reports the loss instead.
        self.assertEqual(_by_title(findings, "Outputs")[0].severity, "warn")
        self.assertEqual(_by_title(findings, "Session")[0].severity, "ok")


class OutputCheckTests(unittest.TestCase):
    def test_reports_the_active_scale(self):
        findings = _run(_session(), outputs=[Output("eDP-1", 1, scale=1.0, width=1920, height=1080)])
        detail = _by_title(findings, "Outputs")[0].detail
        self.assertIn("eDP-1 at 1", detail)

    def test_sub_100_scale_is_flagged(self):
        findings = _run(_session(), outputs=[Output("eDP-1", 1, scale=0.75, width=1366, height=768)])
        warning = _by_title(findings, "Sub-100%")[0]
        self.assertEqual(warning.severity, "warn")
        self.assertIn("eDP-1", warning.detail)

    def test_no_outputs_is_a_warning(self):
        findings = _run(_session(), outputs=[])
        self.assertEqual(_by_title(findings, "Outputs")[0].severity, "warn")


class RoundingCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def diagnose(self, outputs):
        session = Session(type="wayland", plasma="6.7.5", config_home=self.home)
        return _run(session, outputs=outputs)

    def test_fractional_without_a_policy_warns(self):
        findings = self.diagnose([Output("eDP-1", 1, scale=1.25, width=1920, height=1080)])
        finding = _by_title(findings, "Rounding")[0]
        self.assertEqual(finding.severity, "warn")
        self.assertIn("PassThrough", finding.hint)

    def test_fractional_with_the_wrong_policy_warns(self):
        from screensmith import qt

        qt.set_rounding(self.home, "Round")
        findings = self.diagnose([Output("eDP-1", 1, scale=1.25, width=1920, height=1080)])
        self.assertEqual(_by_title(findings, "Rounding")[0].severity, "warn")

    def test_fractional_with_passthrough_is_ok(self):
        from screensmith import qt

        qt.set_rounding(self.home, "PassThrough")
        findings = self.diagnose([Output("eDP-1", 1, scale=1.25, width=1920, height=1080)])
        finding = _by_title(findings, "Rounding")[0]
        self.assertEqual(finding.severity, "ok")
        self.assertIn("PassThrough", finding.detail)

    def test_whole_scale_without_a_policy_is_ok(self):
        findings = self.diagnose([Output("eDP-1", 1, scale=2.0, width=3840, height=2160)])
        self.assertEqual(_by_title(findings, "Rounding")[0].severity, "ok")

    def test_sub_100_scale_also_needs_passthrough(self):
        # 0.75 is still a fractional scale, so Qt needs PassThrough to honour it
        # instead of rounding up to 1x and rendering everything oversized.
        findings = self.diagnose([Output("eDP-1", 1, scale=0.75, width=1366, height=768)])
        self.assertEqual(_by_title(findings, "Rounding")[0].severity, "warn")


class XwaylandCheckTests(unittest.TestCase):
    """KWin keeps [Xwayland] Scale in step with the display scale on its own, so
    only a genuine mismatch should be flagged."""

    def test_matching_override_is_ok(self):
        with tempfile.TemporaryDirectory() as home:
            from screensmith import qt

            qt.set_xwayland_scale(Path(home), 1.25)
            findings = _run(
                Session(type="wayland", plasma="6", config_home=Path(home)),
                outputs=[Output("eDP-1", 1, scale=1.25, width=1920, height=1080)],
            )
            finding = _by_title(findings, "XWayland")[0]
            self.assertEqual(finding.severity, "ok")
            self.assertIn("matching display scale", finding.detail)

    def test_mismatched_override_warns(self):
        with tempfile.TemporaryDirectory() as home:
            from screensmith import qt

            qt.set_xwayland_scale(Path(home), 2)
            findings = _run(
                Session(type="wayland", plasma="6", config_home=Path(home)),
                outputs=[Output("eDP-1", 1, scale=1.0, width=1920, height=1080)],
            )
            finding = _by_title(findings, "XWayland")[0]
            self.assertEqual(finding.severity, "warn")
            self.assertIn("xwayland reset", finding.hint)

    def test_scale_of_one_with_a_fractional_display_warns(self):
        findings = _run(
            _session(),
            outputs=[Output("eDP-1", 1, scale=1.25, width=1920, height=1080)],
        )
        finding = _by_title(findings, "XWayland")[0]
        self.assertEqual(finding.severity, "warn")
        self.assertIn("fractional", finding.detail)

    def test_scale_of_one_with_a_whole_display_is_ok(self):
        findings = _run(
            _session(),
            outputs=[Output("eDP-1", 1, scale=2.0, width=3840, height=2160)],
        )
        self.assertEqual(_by_title(findings, "XWayland")[0].severity, "ok")

    def test_no_outputs_at_all_is_not_an_error(self):
        findings = _run(_session(), outputs=[])
        finding = _by_title(findings, "XWayland")[0]
        self.assertEqual(finding.severity, "ok")
        self.assertIn("1", finding.detail)


class ConfigFileCheckTests(unittest.TestCase):
    def test_missing_file_warns(self):
        with tempfile.TemporaryDirectory() as home:
            findings = _run(Session(type="wayland", plasma="6", config_home=Path(home)), outputs=[])
            self.assertEqual(_by_title(findings, "kwinoutputconfig.json")[0].severity, "warn")

    def test_present_file_is_ok(self):
        import support

        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "kwinoutputconfig.json").write_text(
                support.KWINOUTPUTCONFIG_SAMPLE, encoding="utf-8"
            )
            findings = _run(Session(type="wayland", plasma="6", config_home=Path(home)), outputs=[])
            finding = _by_title(findings, "kwinoutputconfig.json")[0]
            self.assertEqual(finding.severity, "ok")
            self.assertIn("LVDS-1", finding.detail)

    def test_unreadable_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "kwinoutputconfig.json").write_text("{not json", encoding="utf-8")
            findings = _run(Session(type="wayland", plasma="6", config_home=Path(home)), outputs=[])
            self.assertEqual(_by_title(findings, "kwinoutputconfig.json")[0].severity, "error")


class SummaryTests(unittest.TestCase):
    def test_counts_add_up(self):
        findings = _run(
            _session("wayland"),
            outputs=[Output("eDP-1", 1, scale=0.75, width=1366, height=768)],
        )
        counts = doctor.summarise(findings)
        self.assertEqual(sum(counts.values()), len(findings))
        self.assertEqual(counts["error"], 0)

    def test_severity_is_validated(self):
        with self.assertRaises(ValueError):
            doctor.Finding("catastrophe", "Nope")


if __name__ == "__main__":
    unittest.main()
