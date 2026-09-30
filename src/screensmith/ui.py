"""Terminal rendering: aligned tables, colour, and the plain-text fallbacks.

Colour is emitted only when stdout is a TTY and ``NO_COLOR`` is unset, per
https://no-color.org. Everything degrades to readable ASCII so piping into a
file or a pager does not produce escape soup.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Sequence
from typing import Any

__all__ = ["use_colour", "paint", "render_table", "emit_json", "warn", "fail"]

_COLOURS = {
    "ok": "32",  # green
    "warn": "33",  # yellow
    "error": "31",  # red
    "dim": "2",
    "bold": "1",
}


def use_colour(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def paint(text: str, style: str, *, stream=None) -> str:
    """Wrap *text* in an ANSI style, or return it unchanged if colour is off."""
    if not use_colour(stream):
        return text
    code = _COLOURS.get(style)
    return f"\033[{code}m{text}\033[0m" if code else text


def render_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render a left-aligned fixed-width table.

    Column widths are measured on the raw values, so a cell containing a colour
    escape does not skew the layout — call :func:`paint` *after* rendering.
    """
    body = [[("" if cell is None else str(cell)) for cell in row] for row in rows]
    if not body:
        return ""

    widths = [len(h) for h in headers]
    for row in body:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))

    def line(cells: Sequence[str]) -> str:
        parts = [cells[i].ljust(widths[i]) if i < len(cells) else "" for i in range(len(widths))]
        return "  ".join(parts).rstrip()

    out = [line(list(headers)), "  ".join("-" * w for w in widths)]
    out.extend(line(row) for row in body)
    return "\n".join(out)


def emit_json(payload: Any) -> None:
    """Print *payload* as JSON. Used by every command's ``--json`` mode."""
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def warn(message: str) -> None:
    print(f"{paint('warning:', 'warn')}: {message}", file=sys.stderr)


def fail(message: str) -> int:
    """Report an error and return the process exit status to use.

    Returning 1 lets call sites write ``raise SystemExit(ui.fail(...))``, which
    keeps the "print it, then quit non-zero" pair in one place.
    """
    print(f"{paint('error:', 'error')}: {message}", file=sys.stderr)
    return 1
