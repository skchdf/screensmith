"""Probing the live desktop session.

Everything here is deliberately defensive: screensmith should print a useful
error on a machine that is not running Plasma, not a traceback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "config_home",
    "session_type",
    "plasma_version",
    "have",
    "run",
    "CommandError",
    "Session",
]


class CommandError(RuntimeError):
    """A helper command exited non-zero."""

    def __init__(self, argv: list[str], returncode: int, stderr: str) -> None:
        self.argv = argv
        self.returncode = returncode
        self.stderr = stderr.strip()
        shown = " ".join(argv)
        detail = f": {self.stderr}" if self.stderr else ""
        super().__init__(f"`{shown}` exited {returncode}{detail}")


def config_home() -> Path:
    """``$XDG_CONFIG_HOME``, falling back to ``~/.config``."""
    value = os.environ.get("XDG_CONFIG_HOME")
    if value:
        return Path(value)
    return Path.home() / ".config"


def session_type() -> str:
    """Return ``"wayland"``, ``"x11"`` or ``"tty"``.

    ``WAYLAND_DISPLAY`` wins when both are set, because that is the session
    that actually owns the screen; ``DISPLAY`` is also exported into Wayland
    sessions for XWayland clients.
    """
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "tty"


def have(command: str) -> bool:
    """True if *command* is on ``PATH``."""
    return shutil.which(command) is not None


def run(argv: list[str], *, check: bool = True, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    """Run *argv*, capturing text output."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CommandError(argv, 127, str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(argv, 124, f"timed out after {timeout:g}s") from exc

    if check and proc.returncode != 0:
        raise CommandError(argv, proc.returncode, proc.stderr)
    return proc


def plasma_version() -> str | None:
    """Best-effort Plasma/KWin version string, or None if we cannot tell."""
    for argv in (["kwin_wayland", "--version"], ["plasmashell", "--version"], ["kwin_x11", "--version"]):
        if not have(argv[0]):
            continue
        try:
            proc = run(argv, check=False)
        except CommandError:
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            # e.g. "kwin 6.7.5" -> "6.7.5"
            return proc.stdout.strip().split()[-1]
    return None


@dataclass(frozen=True)
class Session:
    """A snapshot of the desktop session, captured once per invocation."""

    type: str
    plasma: str | None
    config_home: Path

    @property
    def is_wayland(self) -> bool:
        return self.type == "wayland"

    @property
    def supports_fractional(self) -> bool:
        """KWin only does fractional scaling under Wayland."""
        return self.is_wayland

    @classmethod
    def probe(cls) -> Session:
        return cls(type=session_type(), plasma=plasma_version(), config_home=config_home())
