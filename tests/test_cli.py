"""End-to-end tests for the CLI, against a throwaway config home."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support

from screensmith import cli
from screensmith.session import Session


class CliTestCase(unittest.TestCase):
    """Base class that makes the CLI testable without a desktop session.

    Two things must be neutralised or the suite passes on a developer's laptop
    and fails on CI: the availability check for `kscreen-doctor`, and the probe
    that reads the real session. Both are patched in :meth:`run_cli`, so no test
    can accidentally depend on the machine it runs on.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / "kwinrc").write_text(support.KWINRC_SAMPLE, encoding="utf-8")
        (self.home / "kwinoutputconfig.json").write_text(support.KWINOUTPUTCONFIG_SAMPLE, encoding="utf-8")
        self.session = Session(type="wayland", plasma="6.7.5", config_home=self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv: str, have_kscreen: bool = True) -> tuple[int, str, str]:
        """Invoke main() with a fake session, capturing stdout and stderr."""
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(Session, "probe", return_value=self.session),
            mock.patch.object(cli, "have", return_value=have_kscreen),
            mock.patch.object(cli.output_mod, "have", return_value=have_kscreen),
            mock.patch.object(cli.doctor, "have", return_value=have_kscreen),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue(), err.getvalue()

    def patch_outputs(self, *outputs):
        """Context manager substituting the live output list."""
        return mock.patch.object(cli.output_mod, "query_outputs", return_value=list(outputs))


class ParserTests(CliTestCase):
    def test_version_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_no_command_prints_help(self):
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("usage:", out)

    def test_scale_requires_an_action(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["scale"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_unknown_command_is_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["frobnicate"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_every_preset_is_reachable(self):
        for name in cli.PRESETS:
            with self.subTest(preset=name):
                parser = cli.build_parser()
                args = parser.parse_args(["preset", name])
                self.assertEqual(args.name, name)
                self.assertEqual(args.func, cli.cmd_preset)


class RoundingCliTests(CliTestCase):
    def test_get_before_set(self):
        code, out, _ = self.run_cli("rounding", "get")
        self.assertEqual(code, 0)
        self.assertIn("unset", out)

    def test_set_then_get(self):
        self.run_cli("rounding", "set", "PassThrough")
        code, out, _ = self.run_cli("rounding", "get")
        self.assertEqual(out.strip(), "PassThrough")

    def test_reset(self):
        self.run_cli("rounding", "set", "PassThrough")
        code, out, _ = self.run_cli("rounding", "reset")
        self.assertEqual(code, 0)
        _, out, _ = self.run_cli("rounding", "get")
        self.assertIn("unset", out)

    def test_json_output(self):
        self.run_cli("rounding", "set", "Ceil")
        code, out, _ = self.run_cli("--json", "rounding", "get")
        self.assertEqual(json.loads(out), "Ceil")

    def test_invalid_policy_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit):
            cli.main(["rounding", "set", "Sideways"])


class FontDpiCliTests(CliTestCase):
    def test_default(self):
        _, out, _ = self.run_cli("font-dpi", "get")
        self.assertIn("default", out)

    def test_set_and_reset(self):
        code, out, _ = self.run_cli("font-dpi", "set", "120")
        self.assertEqual(code, 0)
        self.assertIn("120", out)
        _, out, _ = self.run_cli("font-dpi", "get")
        self.assertEqual(out.strip(), "120")

        code, _, _ = self.run_cli("font-dpi", "reset")
        self.assertEqual(code, 0)
        _, out, _ = self.run_cli("font-dpi", "get")
        self.assertIn("default", out)

    def test_non_numeric_is_a_clean_error_not_a_traceback(self):
        code, _, err = self.run_cli("font-dpi", "set", "big")
        self.assertEqual(code, 1)
        self.assertIn("whole number", err)
        self.assertNotIn("Traceback", err)


class XwaylandCliTests(CliTestCase):
    def test_get_reads_kwinrc(self):
        _, out, _ = self.run_cli("xwayland", "get")
        self.assertIn("100%", out)

    def test_set_writes_kwinrc(self):
        code, out, _ = self.run_cli("xwayland", "set", "150%")
        self.assertEqual(code, 0)
        self.assertIn("150%", out)
        self.assertIn("Scale=1.5", (self.home / "kwinrc").read_text(encoding="utf-8"))

    def test_reset_removes_the_key(self):
        self.run_cli("xwayland", "set", "2")
        self.run_cli("xwayland", "reset")
        self.assertNotIn("Scale=", (self.home / "kwinrc").read_text(encoding="utf-8"))

    def test_reset_removes_the_key_from_the_sample_config(self):
        # KWINRC_SAMPLE ships with an explicit Scale=1, so there is something to remove.
        _, out, _ = self.run_cli("xwayland", "reset")
        self.assertIn("removed the XWayland scale override", out)

    def test_reset_reports_when_there_is_nothing_to_remove(self):
        (self.home / "kwinrc").write_text("[Desktops]\nNumber=4\n", encoding="utf-8")
        _, out, _ = self.run_cli("xwayland", "reset")
        self.assertIn("no XWayland scale override", out)


class BackupRestoreTests(CliTestCase):
    def test_backup_collects_the_files(self):
        code, out, _ = self.run_cli("backup")
        self.assertEqual(code, 0)
        target = self.home / "screensmith-backups"
        stamped = list(target.iterdir())
        self.assertEqual(len(stamped), 1)
        names = {p.name for p in stamped[0].iterdir()}
        self.assertIn("kwinrc", names)
        self.assertIn("kwinoutputconfig.json", names)

    def test_backup_includes_env_plugins(self):
        self.run_cli("rounding", "set", "PassThrough")
        self.run_cli("backup")
        target = next((self.home / "screensmith-backups").iterdir())
        names = {p.name for p in target.iterdir()}
        self.assertIn("env-screensmith-qt-scaling.desktop", names)

    def test_restore_puts_env_plugins_back(self):
        self.run_cli("rounding", "set", "PassThrough")
        self.run_cli("backup")
        snapshot = next((self.home / "screensmith-backups").iterdir())
        self.run_cli("rounding", "reset")
        self.run_cli("restore", str(snapshot), "--yes")
        _, out, _ = self.run_cli("rounding", "get")
        self.assertEqual(out.strip(), "PassThrough")

    def test_restore_puts_content_back(self):
        self.run_cli("rounding", "set", "PassThrough")
        self.run_cli("backup")
        snapshot = next((self.home / "screensmith-backups").iterdir())

        self.run_cli("rounding", "reset")
        self.run_cli("xwayland", "set", "3")
        self.assertIn("Scale=3", (self.home / "kwinrc").read_text(encoding="utf-8"))

        code, out, _ = self.run_cli("restore", str(snapshot), "--yes")
        self.assertEqual(code, 0)
        self.assertNotIn("Scale=3", (self.home / "kwinrc").read_text(encoding="utf-8"))

    def test_restore_leaves_an_undo_copy(self):
        self.run_cli("backup")
        snapshot = next((self.home / "screensmith-backups").iterdir())
        self.run_cli("xwayland", "set", "4")
        self.run_cli("restore", str(snapshot), "--yes")
        undo = self.home / "screensmith-undo"
        self.assertTrue(any("kwinrc" in p.name for p in undo.iterdir()))

    def test_restore_of_a_missing_directory_fails_cleanly(self):
        code, _, err = self.run_cli("restore", str(self.home / "nope"), "--yes")
        self.assertEqual(code, 1)
        self.assertIn("not a directory", err)

    def test_restore_skips_unknown_filenames(self):
        stray = self.home / "stray"
        stray.mkdir()
        (stray / "README.txt").write_text("hello", encoding="utf-8")
        code, _, err = self.run_cli("restore", str(stray), "--yes")
        self.assertEqual(code, 0)
        self.assertIn("no known destination", err)

    def test_restore_declined(self):
        self.run_cli("backup")
        snapshot = next((self.home / "screensmith-backups").iterdir())
        with mock.patch("builtins.input", return_value="n"):
            code, out, _ = self.run_cli("restore", str(snapshot))
        self.assertEqual(code, 1)
        self.assertIn("aborted", out)


class ScaleCliTests(CliTestCase):
    def setUp(self):
        super().setUp()
        from screensmith.output import parse_kscreen_doctor

        self.outputs = parse_kscreen_doctor(support.KSCREEN_DOCTOR_SAMPLE)

    def test_get_all(self):
        with mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs):
            code, out, _ = self.run_cli("scale", "get")
        self.assertEqual(code, 0)
        self.assertIn("LVDS-1: 0.75 (75%)", out)

    def test_get_named_output(self):
        with mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs):
            _, out, _ = self.run_cli("scale", "get", "X11-0")
        self.assertIn("X11-0: 1 (100%)", out)

    def test_get_unknown_output_lists_what_exists(self):
        with mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs):
            code, _, err = self.run_cli("scale", "get", "HDMI-7")
        self.assertEqual(code, 1)
        self.assertIn("LVDS-1", err)

    def test_set_reports_before_and_after(self):
        calls: list[list[str]] = []

        def fake_set(name, value):
            calls.append([name, value])

        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(cli.output_mod, "set_live_scale", side_effect=fake_set),
        ):
            code, out, _ = self.run_cli("scale", "set", "LVDS-1", "1.25")

        self.assertEqual(code, 0)
        self.assertEqual(calls, [["LVDS-1", 1.25]])
        self.assertIn("0.75 (75%) -> 1.25 (125%)", out)
        self.assertIn("workspace is now", out)

    def test_set_accepts_a_percentage(self):
        calls: list[list[str]] = []
        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(cli.output_mod, "set_live_scale", side_effect=lambda n, v: calls.append(v)),
        ):
            self.run_cli("scale", "set", "LVDS-1", "150%")
        self.assertEqual(calls, [1.5])

    def test_set_rejects_a_nonsense_value(self):
        with mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs):
            code, _, err = self.run_cli("scale", "set", "LVDS-1", "enormous")
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)

    def test_set_warns_when_rounding_policy_is_wrong(self):
        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(cli.output_mod, "set_live_scale"),
        ):
            _, _, err = self.run_cli("scale", "set", "LVDS-1", "1.25")
        self.assertIn("ROUNDING_POLICY", err)

    def test_set_does_not_warn_when_passthrough_is_set(self):
        self.run_cli("rounding", "set", "PassThrough")
        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(cli.output_mod, "set_live_scale"),
        ):
            _, _, err = self.run_cli("scale", "set", "LVDS-1", "1.25")
        self.assertNotIn("ROUNDING_POLICY", err)

    def test_set_json_mode(self):
        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(cli.output_mod, "set_live_scale"),
        ):
            code, out, _ = self.run_cli("--json", "scale", "set", "LVDS-1", "2")
        self.assertEqual(json.loads(out), {"output": "LVDS-1", "before": 0.75, "after": 2.0})

    def test_reset(self):
        calls = []
        with (
            mock.patch.object(cli.output_mod, "query_outputs", return_value=self.outputs),
            mock.patch.object(
                cli.output_mod, "set_live_scale", side_effect=lambda n, v: calls.append((n, v))
            ),
        ):
            self.run_cli("scale", "reset")
        self.assertEqual(calls, [("LVDS-1", 1.0)])

    def test_offline_writes_the_json_file(self):
        code, out, _ = self.run_cli("scale", "set", "LVDS-1", "0.8", "--offline")
        self.assertEqual(code, 0)
        text = (self.home / "kwinoutputconfig.json").read_text(encoding="utf-8")
        self.assertIn('"scale": 0.8', text)

    def test_offline_takes_a_backup_first(self):
        self.run_cli("scale", "set", "LVDS-1", "0.8", "--offline")
        backups = self.home / "screensmith-backups"
        self.assertTrue(any(backups.rglob("kwinoutputconfig.json")))

    def test_offline_rejects_an_unknown_output(self):
        code, _, err = self.run_cli("scale", "set", "HDMI-9", "2", "--offline")
        self.assertEqual(code, 1)
        self.assertIn("no output named", err)


class StatusTests(CliTestCase):
    def test_status_renders_a_table(self):
        from screensmith.output import parse_kscreen_doctor

        with mock.patch.object(
            cli.output_mod, "query_outputs", return_value=parse_kscreen_doctor(support.KSCREEN_DOCTOR_SAMPLE)
        ):
            code, out, _ = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("LVDS-1", out)
        self.assertIn("1821x1024", out)

    def test_status_json_shape(self):
        from screensmith.output import parse_kscreen_doctor

        with mock.patch.object(
            cli.output_mod, "query_outputs", return_value=parse_kscreen_doctor(support.KSCREEN_DOCTOR_SAMPLE)
        ):
            _, out, _ = self.run_cli("--json", "status")
        payload = json.loads(out)
        self.assertEqual(payload["session"], "wayland")
        self.assertEqual(payload["outputs"][0]["logical"], "1821x1024")
        # LVDS-1 is at 0.75 in the sample, which is fractional.
        self.assertIs(payload["outputs"][0]["fractional"], True)

    def test_doctor_returns_zero_when_nothing_is_wrong(self):
        code, out, _ = self.run_cli("doctor")
        self.assertEqual(code, 0)
        self.assertIn("ok,", out)

    def test_doctor_reports_an_error_when_kscreen_is_absent(self):
        code, out, _ = self.run_cli("doctor", have_kscreen=False)
        self.assertEqual(code, 1)
        self.assertIn("kscreen-doctor", out)

    def test_doctor_reports_an_error_on_an_x11_session(self):
        self.session = Session(type="x11", plasma="6.7.5", config_home=self.home)
        code, out, _ = self.run_cli("doctor")
        self.assertEqual(code, 1)
        self.assertIn("Wayland", out)

    def test_scale_without_kscreen_fails_cleanly(self):
        code, _, err = self.run_cli("scale", "get", have_kscreen=False)
        self.assertEqual(code, 1)
        self.assertIn("kscreen-doctor is required", err)

    def test_outputs_without_kscreen_fails_cleanly(self):
        code, _, err = self.run_cli("outputs", have_kscreen=False)
        self.assertEqual(code, 1)
        self.assertIn("kscreen-doctor is required", err)

    def test_status_still_renders_without_kscreen(self):
        # status and doctor degrade instead of refusing to run.
        code, out, _ = self.run_cli("status", have_kscreen=False)
        self.assertEqual(code, 0)
        self.assertIn("Session", out)


if __name__ == "__main__":
    unittest.main()
