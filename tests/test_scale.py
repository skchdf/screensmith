"""Tests for scale factor parsing, formatting and geometry."""

from __future__ import annotations

import unittest

from screensmith.scale import (
    MAX_SCALE,
    MIN_SCALE,
    ScaleError,
    describe_scale,
    format_scale,
    is_fractional,
    logical_geometry,
    parse_scale,
)


class ParseScaleTests(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(parse_scale("1.5"), 1.5)

    def test_integer_text(self):
        self.assertEqual(parse_scale("2"), 2.0)

    def test_percentage(self):
        self.assertEqual(parse_scale("150%"), 1.5)

    def test_percentage_below_one_hundred(self):
        self.assertEqual(parse_scale("75%"), 0.75)

    def test_percentage_with_a_space(self):
        self.assertEqual(parse_scale("75 %"), 0.75)

    def test_x_suffix(self):
        self.assertEqual(parse_scale("1.25x"), 1.25)

    def test_leading_dot(self):
        self.assertEqual(parse_scale(".5"), 0.5)

    def test_surrounding_whitespace(self):
        self.assertEqual(parse_scale("  1.25  "), 1.25)

    def test_native_numbers_pass_through(self):
        self.assertEqual(parse_scale(1.5), 1.5)
        self.assertEqual(parse_scale(2), 2.0)

    def test_rejects_garbage(self):
        for bad in ("", "big", "1.5.5", "%", "1,5", "one"):
            with self.subTest(bad=bad), self.assertRaises(ScaleError):
                parse_scale(bad)

    def test_rejects_booleans_which_are_ints(self):
        with self.assertRaises(ScaleError):
            parse_scale(True)

    def test_rejects_values_below_the_floor(self):
        with self.assertRaisesRegex(ScaleError, "out of range"):
            parse_scale("0.1")

    def test_rejects_values_above_the_ceiling(self):
        with self.assertRaisesRegex(ScaleError, "out of range"):
            parse_scale("64")

    def test_accepts_the_boundaries(self):
        self.assertEqual(parse_scale(str(MIN_SCALE)), MIN_SCALE)
        self.assertEqual(parse_scale(str(MAX_SCALE)), MAX_SCALE)


class FormatScaleTests(unittest.TestCase):
    def test_whole_numbers_lose_the_decimal(self):
        self.assertEqual(format_scale(1.0), "1")
        self.assertEqual(format_scale(2.0), "2")

    def test_fractions_are_kept(self):
        self.assertEqual(format_scale(0.75), "0.75")
        self.assertEqual(format_scale(1.25), "1.25")

    def test_trailing_zeros_are_trimmed(self):
        self.assertEqual(format_scale(2.50), "2.5")
        self.assertEqual(format_scale(1.0), "1")

    def test_never_uses_exponent_notation(self):
        self.assertEqual(format_scale(0.0001 * 10000), "1")

    def test_round_trips_through_parse(self):
        for value in (0.25, 0.75, 1.0, 1.5, 2.0, 3.25):
            with self.subTest(value=value):
                self.assertEqual(parse_scale(format_scale(value)), value)


class DescribeScaleTests(unittest.TestCase):
    def test_whole_number(self):
        self.assertEqual(describe_scale(1.0), "1 (100%)")

    def test_fraction(self):
        self.assertEqual(describe_scale(0.75), "0.75 (75%)")

    def test_fraction_that_is_not_a_whole_percent(self):
        self.assertEqual(describe_scale(1.25), "1.25 (125%)")


class IsFractionalTests(unittest.TestCase):
    def test_whole_numbers_are_not_fractional(self):
        for value in (1.0, 2.0, 3.0):
            self.assertFalse(is_fractional(value), value)

    def test_fractions_are_fractional(self):
        for value in (0.75, 1.25, 1.5, 2.75):
            self.assertTrue(is_fractional(value), value)

    def test_float_error_does_not_flip_the_test(self):
        # A value that should be 1 arrives as 1.0000000000000002 after arithmetic.
        self.assertFalse(is_fractional(1.0 + 1e-15))
        self.assertFalse(is_fractional(0.75 * 4 / 3))

    def test_sub_one_scales_are_fractional(self):
        # 0.75 is not a whole number, so Qt still needs PassThrough to honour it.
        self.assertTrue(is_fractional(0.75))


class LogicalGeometryTests(unittest.TestCase):
    def test_scale_one_is_a_no_op(self):
        self.assertEqual(logical_geometry(1920, 1080, 1.0), (1920, 1080))

    def test_doubling_halves_the_workspace(self):
        self.assertEqual(logical_geometry(1920, 1080, 2.0), (960, 540))

    def test_halving_the_scale_gives_a_bigger_workspace(self):
        # The case from the README: a 1366x768 panel at 0.75.
        self.assertEqual(logical_geometry(1366, 768, 0.75), (1821, 1024))

    def test_result_is_always_positive_at_the_minimum(self):
        self.assertEqual(logical_geometry(1366, 768, MIN_SCALE), (5464, 3072))


if __name__ == "__main__":
    unittest.main()
