"""Tests for the line-preserving KDE INI editor."""

from __future__ import annotations

import unittest

import support

from screensmith import ini


class GetValueTests(unittest.TestCase):
    def test_reads_a_plain_value(self):
        self.assertEqual(ini.get_value(support.KWINRC_SAMPLE, "Effect-translucency", "Menus"), "80")

    def test_returns_none_for_missing_key(self):
        self.assertIsNone(ini.get_value(support.KWINRC_SAMPLE, "Effect-translucency", "Borders"))

    def test_returns_none_for_missing_group(self):
        self.assertIsNone(ini.get_value(support.KWINRC_SAMPLE, "Nope", "Menus"))

    def test_group_names_are_case_sensitive(self):
        text = "[KDE]\nKey=value\n"
        self.assertIsNone(ini.get_value(text, "kde", "Key"))
        self.assertEqual(ini.get_value(text, "KDE", "Key"), "value")

    def test_handles_bracketed_group_names(self):
        text = "[Tiling][abc][def]\npadding=4\n"
        self.assertEqual(ini.get_value(text, "Tiling][abc][def", "padding"), "4")

    def test_ignores_comments_and_blanks(self):
        text = "[G]\n# key=comment\n; other=x\n\nkey=value\n"
        self.assertEqual(ini.get_value(text, "G", "key"), "value")

    def test_does_not_match_a_key_in_a_later_group(self):
        text = "[A]\nkey=1\n\n[B]\nkey=2\n"
        self.assertEqual(ini.get_value(text, "B", "key"), "2")


class SetValueTests(unittest.TestCase):
    def test_replaces_an_existing_value(self):
        result = ini.set_value(support.KWINRC_SAMPLE, "Xwayland", "Scale", "1.5")
        self.assertEqual(ini.get_value(result, "Xwayland", "Scale"), "1.5")

    def test_leaves_every_other_line_byte_identical(self):
        original = support.KWINRC_SAMPLE.splitlines(keepends=True)
        result = ini.set_value(support.KWINRC_SAMPLE, "Xwayland", "Scale", "1.5").splitlines(keepends=True)
        self.assertEqual(len(original), len(result))
        differing = [i for i, (a, b) in enumerate(zip(original, result, strict=True)) if a != b]
        self.assertEqual(differing, [len(original) - 1])

    def test_adds_a_key_to_an_existing_group(self):
        text = "[G]\na=1\n"
        result = ini.set_value(text, "G", "b", "2")
        self.assertEqual(result, "[G]\na=1\nb=2\n")

    def test_creates_a_missing_group(self):
        result = ini.set_value("[G]\na=1\n", "New", "b", "2")
        self.assertEqual(result, "[G]\na=1\n\n[New]\nb=2\n")

    def test_creates_the_file_from_empty(self):
        self.assertEqual(ini.set_value("", "G", "k", "v"), "[G]\nk=v\n")

    def test_preserves_comments(self):
        text = "# top of file\n[G]\n# about a\na=1\n"
        result = ini.set_value(text, "G", "b", "2")
        self.assertIn("# top of file", result)
        self.assertIn("# about a", result)

    def test_new_key_goes_above_a_trailing_comment(self):
        text = "[G]\na=1\n# trailing note\n"
        result = ini.set_value(text, "G", "b", "2")
        self.assertEqual(result, "[G]\na=1\nb=2\n# trailing note\n")

    def test_rejects_embedded_newlines(self):
        with self.assertRaises(ValueError):
            ini.set_value("[G]\n", "G", "k", "a\nb")

    def test_setting_the_same_value_is_idempotent(self):
        once = ini.set_value(support.KWINRC_SAMPLE, "Xwayland", "Scale", "2")
        twice = ini.set_value(once, "Xwayland", "Scale", "2")
        self.assertEqual(once, twice)


class RemoveValueTests(unittest.TestCase):
    def test_removes_the_line(self):
        result = ini.remove_value(support.KWINRC_SAMPLE, "Xwayland", "Scale")
        self.assertIsNone(ini.get_value(result, "Xwayland", "Scale"))
        self.assertIn("[Xwayland]", result)

    def test_missing_key_is_a_no_op(self):
        self.assertEqual(ini.remove_value(support.KWINRC_SAMPLE, "Xwayland", "Nope"), support.KWINRC_SAMPLE)

    def test_removing_from_an_empty_file_is_safe(self):
        self.assertEqual(ini.remove_value("", "G", "k"), "")


class SplitKvTests(unittest.TestCase):
    def test_plain_pair(self):
        self.assertEqual(ini.split_kv("Scale=1.5"), ("Scale", "1.5"))

    def test_keeps_equals_signs_in_the_value(self):
        self.assertEqual(ini.split_kv("Exec=env A=b=c"), ("Exec", "env A=b=c"))

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(ini.split_kv("  Scale = 2  "), ("Scale", "2"))

    def test_rejects_non_assignments(self):
        for line in ("", "   ", "# comment", "; comment", "[Section]"):
            self.assertIsNone(ini.split_kv(line), line)


class IterGroupsTests(unittest.TestCase):
    def test_covers_every_section(self):
        names = [name for name, _, _ in ini.iter_groups(support.KWINRC_SAMPLE)]
        self.assertIn("Desktops", names)
        self.assertIn("Xwayland", names)
        self.assertIn(
            "Tiling][07caa50c-c063-4689-9234-846f66543f76][3c1c1f29-e7e2-4815-8686-01c82e6775e1", names
        )

    def test_sections_are_disjoint_and_ordered(self):
        spans = list(ini.iter_groups(support.KWINRC_SAMPLE))
        for (_, _start_a, end_a), (_, start_b, _) in zip(spans, spans[1:], strict=False):
            self.assertLessEqual(end_a, start_b)

    def test_last_section_runs_to_end_of_file(self):
        lines = support.KWINRC_SAMPLE.splitlines()
        spans = list(ini.iter_groups(support.KWINRC_SAMPLE))
        self.assertEqual(spans[-1][2], len(lines))


if __name__ == "__main__":
    unittest.main()
