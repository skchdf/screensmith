"""Tests for the atomic write / backup filesystem helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from screensmith.fsutil import atomic_write, backup_file, mode_of


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_the_content(self):
        path = self.home / "kwinrc"
        atomic_write(path, "[G]\nk=v\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "[G]\nk=v\n")

    def test_no_temp_file_is_left_behind(self):
        path = self.home / "kwinrc"
        atomic_write(path, "data\n")
        leftovers = [p.name for p in self.home.iterdir()]
        self.assertEqual(leftovers, ["kwinrc"])

    def test_preserves_the_existing_mode(self):
        path = self.home / "kwinrc"
        path.write_text("old\n", encoding="utf-8")
        os.chmod(path, 0o600)
        atomic_write(path, "new\n")
        self.assertEqual(mode_of(path), 0o600)

    def test_replaces_content_atomically_across_rewrites(self):
        path = self.home / "kwinrc"
        atomic_write(path, "first\n")
        atomic_write(path, "second\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "second\n")

    def test_a_symlink_target_is_updated_and_the_link_kept(self):
        # Dotfile managers keep ~/.config/kwinrc as a symlink into a repo;
        # replacing the link itself would silently break that setup.
        real = self.home / "real-kwinrc"
        real.write_text("old\n", encoding="utf-8")
        link = self.home / "kwinrc"
        link.symlink_to(real)
        atomic_write(link, "new\n")
        self.assertTrue(link.is_symlink())
        self.assertEqual(real.read_text(encoding="utf-8"), "new\n")
        self.assertEqual(link.read_text(encoding="utf-8"), "new\n")

    def test_creates_missing_parent_directories(self):
        atomic_write(self.home / "plasma-workspace" / "env" / "a.desktop", "x\n")
        self.assertTrue((self.home / "plasma-workspace" / "env" / "a.desktop").exists())


class BackupFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_returns_none(self):
        self.assertIsNone(backup_file(self.home / "nope", self.home / "backups"))

    def test_copies_content_and_metadata(self):
        path = self.home / "kwinrc"
        path.write_text("data\n", encoding="utf-8")
        os.chmod(path, 0o640)
        dest = backup_file(path, self.home / "backups")
        self.assertIsNotNone(dest)
        self.assertEqual(dest.read_text(encoding="utf-8"), "data\n")
        self.assertEqual(mode_of(dest), 0o640)

    def test_label_renames_the_copy(self):
        path = self.home / "plugin.desktop"
        path.write_text("data\n", encoding="utf-8")
        dest = backup_file(path, self.home / "backups", label="env-plugin.desktop")
        self.assertEqual(dest.name, "env-plugin.desktop")


if __name__ == "__main__":
    unittest.main()
