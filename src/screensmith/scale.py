"""Parsing, formatting and validating display scale factors."""

from __future__ import annotations

import re

__all__ = [
    "MIN_SCALE",
    "MAX_SCALE",
    "ScaleError",
    "parse_scale",
    "format_scale",
    "describe_scale",
    "is_fractional",
    "logical_geometry",
]

#: Below this the result is unreadable rather than "small".
MIN_SCALE = 0.25
#: Above this you are wasting a panel on one window.
MAX_SCALE = 10.0

# Accepts: 1, 1.5, 0.75, 150%, 150 % (with an optional space), 1.5x
_SCALE_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)?|\.\d+)\s*(?P<unit>%|x)?\s*$", re.IGNORECASE)


class ScaleError(ValueError):
    """Raised when a scale factor cannot be parsed or is out of range."""


def parse_scale(text: str | float | int) -> float:
    """Parse a user-supplied scale factor.

    Understands both the multiplier form KWin stores (``1.5``) and the
    percentage form people read in the settings UI (``150%``).

    >>> parse_scale("150%")
    1.5
    >>> parse_scale("0.75")
    0.75
    """
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        value = float(text)
    else:
        match = _SCALE_RE.match(str(text))
        if not match:
            raise ScaleError(f"cannot read {text!r} as a scale factor (try 1.5 or 150%)")
        value = float(match.group("num"))
        if match.group("unit") == "%":
            value /= 100.0

    if not MIN_SCALE <= value <= MAX_SCALE:
        raise ScaleError(
            f"scale {format_scale(value)} is out of range; "
            f"pick something between {format_scale(MIN_SCALE)} and {format_scale(MAX_SCALE)}"
        )
    return value


def format_scale(value: float) -> str:
    """Render a scale the way KWin stores it: no trailing zeros, no exponent.

    >>> format_scale(1.0)
    '1'
    >>> format_scale(0.75)
    '0.75'
    >>> format_scale(2.50)
    '2.5'
    """
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def describe_scale(value: float) -> str:
    """Human-facing rendering, e.g. ``0.75 (75%)``."""
    percent = value * 100
    percent_text = f"{percent:.0f}" if percent == int(percent) else f"{percent:.2f}".rstrip("0").rstrip(".")
    return f"{format_scale(value)} ({percent_text}%)"


def is_fractional(value: float) -> bool:
    """True when *value* is not a whole number.

    Fractional scales are the ones that need ``QT_SCALE_FACTOR_ROUNDING_POLICY``
    to keep XWayland and GTK applications sharp.
    """
    return abs(value - round(value)) > 1e-9


def logical_geometry(width: int, height: int, scale: float) -> tuple[int, int]:
    """Return the logical (coordinate) size of a physical surface at *scale*.

    KWin reports ``Geometry`` in logical pixels, so a 1366x768 panel at 0.75
    behaves like a 1821x1024 desktop.
    """
    return round(width / scale), round(height / scale)
