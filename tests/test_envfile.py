"""Tests for plasma-workspace/env plugins and the Qt/KDE scaling knobs."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support

from screensmith import envfile, qt

PLUGIN_TEXT = """[Desktop Entry]
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
Type=Application
X-Plasma-API=develprovenfalse
"""


class EnvPluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_home = Path(self.tmp.name)
        self.env = envfile.env_dir(self.config_home)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        self.env.mkdir(parents=True, exist_ok=True)
        path = self.env / f"{name}.desktop"
        path.write_text(text, encoding="utf-8")
        return path

    def test_env_dir_location(self):
        self.assertEqual(envfile.env_dir(self.config_home), self.config_home / "plasma-workspace" / "env")

    def test_load_env_on_a_missing_directory_is_empty(self):
        self.assertEqual(envfile.load_env(self.config_home), {})

    def test_parses_a_known_plugin(self):
        self.write("a", PLUGIN_TEXT)
        self.assertEqual(
            envfile.load_env(self.config_home), {"QT_SCALE_FACTOR_ROUNDING_POLICY": "PassThrough"}
        )

    def test_ignores_plugins_that_are_not_env_invocations(self):
        self.write("other", "[Desktop Entry]\nExec=/usr/bin/thing --flag\nType=Application\n")
        self.assertEqual(envfile.load_env(self.config_home), {})

    def test_later_files_win(self):
        self.write("10-first", "[Desktop Entry]\nExec=env FOO=one\nType=Application\n")
        self.write("20-second", "[Desktop Entry]\nExec=env FOO=two\nType=Application\n")
        self.assertEqual(envfile.load_env(self.config_home), {"FOO": "two"})

    def test_write_vars_produces_a_loadable_plugin(self):
        path = envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"FOO": "bar"})
        self.assertEqual(path.name, "screensmith-qt-scaling.desktop")
        self.assertEqual(envfile.load_env(self.config_home), {"FOO": "bar"})
        self.assertIn("Type=Application", path.read_text(encoding="utf-8"))

    def test_write_vars_round_trips_a_quoted_value(self):
        envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"GREETING": "hello world"})
        self.assertEqual(envfile.load_env(self.config_home), {"GREETING": "hello world"})

    def test_find_var_locates_the_owning_plugin(self):
        envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"FOO": "bar"})
        found = envfile.find_var(self.config_home, "FOO")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "screensmith-qt-scaling")

    def test_unset_removes_only_the_named_variable(self):
        envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"FOO": "bar", "BAZ": "qux"})
        removed = envfile.unset_vars(self.config_home, ["FOO"])
        self.assertEqual(removed, ["FOO"])
        self.assertEqual(envfile.load_env(self.config_home), {"BAZ": "qux"})

    def test_unset_deletes_the_file_once_empty(self):
        envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"FOO": "bar"})
        envfile.unset_vars(self.config_home, ["FOO"])
        self.assertFalse((self.env / "screensmith-qt-scaling.desktop").exists())

    def test_unset_of_an_absent_variable_reports_nothing(self):
        self.assertEqual(envfile.unset_vars(self.config_home, ["NOT_SET"]), [])

    def test_never_touches_another_plugin(self):
        self.write("someone-elses", PLUGIN_TEXT)
        envfile.write_vars(self.config_home, "screensmith-qt-scaling", {"FOO": "bar"})
        envfile.unset_vars(self.config_home, ["FOO"])
        self.assertEqual(
            envfile.load_env(self.config_home), {"QT_SCALE_FACTOR_ROUNDING_POLICY": "PassThrough"}
        )


class RoundingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_returns_none_by_default(self):
        self.assertIsNone(qt.get_rounding(self.home))

    def test_set_then_get(self):
        qt.set_rounding(self.home, "PassThrough")
        self.assertEqual(qt.get_rounding(self.home), "PassThrough")

    def test_set_rejects_unknown_policies(self):
        with self.assertRaises(ValueError):
            qt.set_rounding(self.home, "Sideways")

    def test_unset(self):
        qt.set_rounding(self.home, "PassThrough")
        self.assertTrue(qt.unset_rounding(self.home))
        self.assertIsNone(qt.get_rounding(self.home))

    def test_recommended_is_passthrough_for_fractional_scales(self):
        self.assertEqual(qt.recommended_rounding(0.75), "PassThrough")
        self.assertEqual(qt.recommended_rounding(1.0, 1.25), "PassThrough")

    def test_recommended_defaults_to_round_for_whole_scales(self):
        self.assertEqual(qt.recommended_rounding(1.0), "Round")
        self.assertEqual(qt.recommended_rounding(), "Round")

    def test_setting_rounding_preserves_a_font_dpi(self):
        qt.set_font_dpi(self.home, 120)
        qt.set_rounding(self.home, "PassThrough")
        self.assertEqual(qt.get_font_dpi(self.home), 120)
        self.assertEqual(qt.get_rounding(self.home), "PassThrough")


class FontDpiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_is_none(self):
        self.assertIsNone(qt.get_font_dpi(self.home))

    def test_set_and_get(self):
        qt.set_font_dpi(self.home, 144)
        self.assertEqual(qt.get_font_dpi(self.home), 144)

    def test_rejects_out_of_range(self):
        for bad in (0, 10, 5000):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                qt.set_font_dpi(self.home, bad)

    def test_unset(self):
        qt.set_font_dpi(self.home, 144)
        self.assertTrue(qt.unset_font_dpi(self.home))
        self.assertIsNone(qt.get_font_dpi(self.home))

    def test_a_non_numeric_value_in_the_file_reads_as_none(self):
        envfile.write_vars(self.home, "screensmith-qt-scaling", {"QT_FONT_DPI": "huge"})
        self.assertIsNone(qt.get_font_dpi(self.home))


class XwaylandScaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.kwinrc = self.home / "kwinrc"
        self.kwinrc.write_text(support.KWINRC_SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_an_existing_override(self):
        self.assertEqual(qt.get_xwayland_scale(self.home), 1.0)

    def test_default_when_the_file_is_absent(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(qt.get_xwayland_scale(Path(empty)), 1.0)

    def test_set_updates_the_xwayland_group_only(self):
        qt.set_xwayland_scale(self.home, 1.5)
        text = self.kwinrc.read_text(encoding="utf-8")
        self.assertIn("[Xwayland]\nScale=1.5\n", text)
        self.assertIn("[Effect-translucency]\nMenus=80", text)

    def test_set_creates_the_file_when_missing(self):
        with tempfile.TemporaryDirectory() as empty:
            home = Path(empty)
            qt.set_xwayland_scale(home, 2)
            self.assertEqual((home / "kwinrc").read_text(encoding="utf-8"), "[Xwayland]\nScale=2\n")

    def test_unset_removes_the_key_but_keeps_the_group(self):
        qt.set_xwayland_scale(self.home, 2)
        self.assertTrue(qt.unset_xwayland_scale(self.home))
        text = self.kwinrc.read_text(encoding="utf-8")
        self.assertNotIn("Scale=", text)
        self.assertIn("[Xwayland]", text)

    def test_unset_when_absent_reports_no_change(self):
        self.kwinrc.write_text("[Desktops]\nNumber=4\n", encoding="utf-8")
        self.assertFalse(qt.unset_xwayland_scale(self.home))

    def test_a_corrupt_value_falls_back_to_one(self):
        self.kwinrc.write_text("[Xwayland]\nScale=nonsense\n", encoding="utf-8")
        self.assertEqual(qt.get_xwayland_scale(self.home), 1.0)


if __name__ == "__main__":
    unittest.main()
