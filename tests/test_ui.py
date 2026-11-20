"""Tests for terminal rendering: colour gating and table layout."""

from __future__ import annotations

import contextlib
import io
import os
import unittest

from screensmith import ui


class TtyStream:
    """A stream that claims to be a terminal, so colour logic is exercised."""

    def __init__(self):
        self.buffer = io.StringIO()

    def isatty(self):
        return True

    def write(self, text):
        self.buffer.write(text)


@contextlib.contextmanager
def with_env(**values):
    """Set the given environment variables for the block; None removes a key."""
    saved = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class UseColourTests(unittest.TestCase):
    def test_disabled_without_a_tty(self):
        with with_env(NO_COLOR=None, TERM=None):
            self.assertFalse(ui.use_colour(io.StringIO()))

    def test_enabled_on_a_tty(self):
        with with_env(NO_COLOR=None, TERM="xterm-256color"):
            self.assertTrue(ui.use_colour(TtyStream()))

    def test_no_color_set_disables_colour(self):
        with with_env(NO_COLOR="1", TERM="xterm-256color"):
            self.assertFalse(ui.use_colour(TtyStream()))

    def test_an_empty_no_color_does_not_disable_colour(self):
        # Per https://no-color.org only a non-empty NO_COLOR counts.
        with with_env(NO_COLOR="", TERM="xterm-256color"):
            self.assertTrue(ui.use_colour(TtyStream()))

    def test_dumb_terminals_get_no_colour(self):
        with with_env(NO_COLOR=None, TERM="dumb"):
            self.assertFalse(ui.use_colour(TtyStream()))


class PaintTests(unittest.TestCase):
    def test_wraps_in_ansi_when_colour_is_on(self):
        with with_env(NO_COLOR=None, TERM="xterm"):
            self.assertEqual(ui.paint("error:", "error", stream=TtyStream()), "\033[31merror:\033[0m")

    def test_plain_when_colour_is_off(self):
        with with_env(NO_COLOR="1"):
            self.assertEqual(ui.paint("error:", "error", stream=TtyStream()), "error:")

    def test_unknown_style_is_left_alone(self):
        with with_env(NO_COLOR=None, TERM="xterm"):
            self.assertEqual(ui.paint("text", "no-such-style", stream=TtyStream()), "text")


class RenderTableTests(unittest.TestCase):
    def test_column_widths_fit_the_widest_cell(self):
        table = ui.render_table(["A", "B"], [["one", "1"], ["three", "22222"]])
        lines = table.splitlines()
        self.assertEqual(lines[0], "A      B")
        self.assertEqual(lines[1], "-----  -----")
        self.assertEqual(lines[2], "one    1")
        self.assertEqual(lines[3], "three  22222")

    def test_short_rows_are_padded_not_crashing(self):
        table = ui.render_table(["A", "B"], [["only-a"]])
        self.assertIn("only-a", table)

    def test_empty_rows_yield_an_empty_table(self):
        self.assertEqual(ui.render_table(["A"], []), "")


if __name__ == "__main__":
    unittest.main()
