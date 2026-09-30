"""Filesystem helpers shared across screensmith.

Every write goes through :func:`atomic_write`. KWin and plasmashell read these
files continuously; a half-written ``kwinrc`` can leave you with an
unconfigurable session, so "write a temp file, fsync, rename" is the minimum
acceptable behaviour.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

__all__ = ["atomic_write", "backup_file"]


def atomic_write(path: Path, text: str, *, mode: int = 0o644) -> None:
    """Write *text* to *path* atomically.

    The temp file is created in the destination directory so that the final
    ``os.replace`` stays on one filesystem and is therefore atomic.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        # Never leave a stray temp file behind on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    # Persist the rename itself, so a crash cannot resurrect the old contents.
    dir_fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    except OSError:
        pass  # Not all filesystems support directory fsync.
    finally:
        os.close(dir_fd)


def backup_file(path: Path, backup_dir: Path, *, label: str | None = None) -> Path | None:
    """Copy *path* into *backup_dir* and return the copy, or None if absent.

    *label* overrides the stored filename, which is how env plugins get an
    ``env-`` prefix to keep them from colliding with the main config files.
    """
    path = Path(path)
    if not path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / (label or path.name)
    shutil.copy2(path, dest)
    return dest


def mode_of(path: Path) -> int:
    """Permission bits of *path*, or 0644 if it does not exist.

    Preserving the mode matters for config files the user may have made
    group-writable or read-only on purpose.
    """
    try:
        return stat.S_IMODE(Path(path).stat().st_mode)
    except OSError:
        return 0o644
