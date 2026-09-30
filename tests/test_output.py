"""Tests for kscreen-doctor output parsing and kwinoutputconfig.json editing."""

from __future__ import annotations

import json
import unittest

import support

from screensmith.output import KwinOutputConfig, Output, parse_kscreen_doctor


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.outputs = parse_kscreen_doctor(support.KSCREEN_DOCTOR_SAMPLE)

    def test_finds_every_output(self):
        self.assertEqual(len(self.outputs), 2)

    def test_reads_names_in_order(self):
        self.assertEqual([o.name for o in self.outputs], ["LVDS-1", "X11-0"])

    def test_reads_index_and_uuid(self):
        self.assertEqual(self.outputs[0].index, 1)
        self.assertEqual(self.outputs[0].uuid, "3c1c1f29-e7e2-4815-8686-01c82e6775e1")

    def test_strips_ansi_around_the_scale(self):
        self.assertEqual(self.outputs[0].scale, 0.75)

    def test_reads_the_geometry(self):
        self.assertEqual((self.outputs[0].width, self.outputs[0].height), (1366, 768))

    def test_reads_enabled_and_connected_state(self):
        self.assertTrue(self.outputs[0].enabled)
        self.assertTrue(self.outputs[0].connected)
        self.assertFalse(self.outputs[1].enabled)
        self.assertFalse(self.outputs[1].connected)

    def test_scale_one_is_not_fractional(self):
        self.assertFalse(self.outputs[1].is_fractional)

    def test_scale_below_one_is_fractional(self):
        self.assertTrue(Output("eDP-1", 1, scale=0.75).is_fractional)

    def test_fractional_detection(self):
        self.assertTrue(Output("eDP-1", 1, scale=1.25).is_fractional)

    def test_logical_size_accounts_for_scale(self):
        self.assertEqual(self.outputs[0].logical, (1821, 1024))
        self.assertEqual(self.outputs[0].logical_label, "1821x1024")

    def test_falls_back_to_the_active_mode_when_geometry_is_absent(self):
        text = (
            "Output: 3 DP-2 abc-123\n\tenabled\n\tconnected\n"
            "\tModes: \t1:2560x1440@59.95*\n\tCustom modes: \tNone\n\tScale: \t2\n"
        )
        outputs = parse_kscreen_doctor(text)
        self.assertEqual((outputs[0].width, outputs[0].height), (2560, 1440))
        self.assertEqual(outputs[0].logical, (1280, 720))

    def test_defaults_to_scale_one_when_absent(self):
        text = "Output: 4 DP-3 def-456\n\tenabled\n\tGeometry: 0,0 800x600\n"
        self.assertEqual(parse_kscreen_doctor(text)[0].scale, 1.0)

    def test_handles_colourless_output(self):
        plain = (
            support.KSCREEN_DOCTOR_SAMPLE.replace("\x1b[32m", "")
            .replace("\x1b[33m", "")
            .replace("\x1b[31m", "")
            .replace("\x1b[0m", "")
        )
        self.assertEqual(parse_kscreen_doctor(plain), parse_kscreen_doctor(support.KSCREEN_DOCTOR_SAMPLE))

    def test_empty_input_yields_no_outputs(self):
        self.assertEqual(parse_kscreen_doctor(""), [])
        self.assertEqual(parse_kscreen_doctor("no outputs here\n"), [])


class KwinOutputConfigTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "kwinoutputconfig.json"
        self.path.write_text(support.KWINOUTPUTCONFIG_SAMPLE, encoding="utf-8")
        self.config = KwinOutputConfig(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_and_lists_connectors(self):
        self.assertEqual(self.config.connectors(), ["LVDS-1", "X11-0"])

    def test_reads_scale(self):
        self.assertEqual(self.config.scale_of("LVDS-1"), 1.0)

    def test_set_scale_text_updates_the_right_output(self):
        """Round-trip through the written file, not just the returned text."""
        updated = self.config.set_scale_text(self.config.load_text(), "LVDS-1", 0.75)

        round_tripped = self.path.parent / "roundtrip.json"
        round_tripped.write_text(updated, encoding="utf-8")
        reloaded = KwinOutputConfig(round_tripped)
        self.assertEqual(reloaded.scale_of("LVDS-1"), 0.75)
        self.assertEqual(reloaded.scale_of("X11-0"), 1.0)

    def test_set_scale_text_preserves_other_keys(self):
        text = self.config.load_text()
        updated = json.loads(self.config.set_scale_text(text, "X11-0", 1.5))
        lvds = next(e for e in updated[0]["data"] if e["connectorName"] == "LVDS-1")
        self.assertEqual(lvds["scale"], 1.0)
        self.assertEqual(lvds["uuid"], "3c1c1f29-e7e2-4815-8686-01c82e6775e1")
        self.assertEqual(lvds["mode"]["refreshRate"], 60072)

    def test_set_scale_text_rejects_unknown_connectors(self):
        with self.assertRaises(KeyError):
            self.config.set_scale_text(self.config.load_text(), "HDMI-9", 2.0)

    def test_output_is_indent_four_to_match_kwin(self):
        updated = self.config.set_scale_text(self.config.load_text(), "LVDS-1", 2.0)
        self.assertIn('\n    {\n        "data": [', updated)
        self.assertTrue(updated.endswith("\n"))

    def test_missing_file_raises_clearly(self):
        from pathlib import Path

        missing = KwinOutputConfig(Path(self.tmp.name) / "nope.json")
        self.assertFalse(missing.exists)
        with self.assertRaises(FileNotFoundError):
            missing.load_text()


if __name__ == "__main__":
    unittest.main()
