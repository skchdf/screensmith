"""The Qt/KDE knobs that decide how fractional scaling is actually rendered.

Three settings do most of the work, and they are confusingly spread out:

``QT_SCALE_FACTOR_ROUNDING_POLICY`` (env, next login)
    How Qt maps a fractional scale onto integer device pixels. With the default
    ``Round``, a 0.75 scale makes Qt snap to 1x or 2x and everything looks
    blurry or wrongly sized. ``PassThrough`` keeps 0.75 and renders correctly.

``QT_FONT_DPI`` (env, next login)
    Forces the base font size Qt assumes. Useful for shrinking text without
    shrinking widgets, or the reverse.

``kwinrc`` ``[Xwayland] Scale`` (instant)
    One multiplier applied to every X11 client. If it disagrees with your
    display scale, X11 apps end up mismatched against everything else.
"""

from __future__ import annotations

from pathlib import Path

from . import envfile, ini
from .fsutil import atomic_write, mode_of
from .scale import ScaleError, format_scale, is_fractional, parse_scale

__all__ = [
    "ROUNDING_POLICIES",
    "DEFAULT_ROUNDING",
    "PLUGIN_NAME",
    "recommended_rounding",
    "get_rounding",
    "set_rounding",
    "unset_rounding",
    "get_font_dpi",
    "set_font_dpi",
    "unset_font_dpi",
    "get_xwayland_scale",
    "set_xwayland_scale",
    "unset_xwayland_scale",
]

ROUNDING_POLICIES = ("PassThrough", "Round", "Ceil", "Floor")
DEFAULT_ROUNDING = "Round"

#: Name of the env plugin screensmith owns. Prefixed so it is obvious in a
#: directory of a dozen other plugins, and so we never trample a user's file.
PLUGIN_NAME = "screensmith-qt-scaling"

_FONT_DPI_RANGE = (48, 400)


def recommended_rounding(*scales: float) -> str:
    """The rounding policy that suits the given display scales.

    Fractional scales need ``PassThrough`` to look right. Whole-number scales
    work fine with Qt's default and keep ``PassThrough``'s subpixel jitter out.
    """
    return "PassThrough" if any(is_fractional(s) for s in scales) else DEFAULT_ROUNDING


def get_rounding(config_home: Path) -> str | None:
    value = envfile.load_env(config_home).get("QT_SCALE_FACTOR_ROUNDING_POLICY")
    return value or None


def set_rounding(config_home: Path, policy: str) -> Path:
    if policy not in ROUNDING_POLICIES:
        raise ValueError(f"rounding policy must be one of {', '.join(ROUNDING_POLICIES)}")
    variables = _current_vars(config_home)
    variables["QT_SCALE_FACTOR_ROUNDING_POLICY"] = policy
    return envfile.write_vars(config_home, PLUGIN_NAME, variables)


def unset_rounding(config_home: Path) -> bool:
    return bool(envfile.unset_vars(config_home, ["QT_SCALE_FACTOR_ROUNDING_POLICY"]))


def get_font_dpi(config_home: Path) -> int | None:
    value = envfile.load_env(config_home).get("QT_FONT_DPI")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def set_font_dpi(config_home: Path, dpi: int) -> Path:
    low, high = _FONT_DPI_RANGE
    if not low <= dpi <= high:
        raise ValueError(f"font DPI must be between {low} and {high}")
    variables = _current_vars(config_home)
    variables["QT_FONT_DPI"] = str(dpi)
    return envfile.write_vars(config_home, PLUGIN_NAME, variables)


def unset_font_dpi(config_home: Path) -> bool:
    return bool(envfile.unset_vars(config_home, ["QT_FONT_DPI"]))


def get_xwayland_scale(config_home: Path) -> float:
    """The global XWayland multiplier; 1.0 when unset, which is KWin's default."""
    path = Path(config_home) / "kwinrc"
    if not path.is_file():
        return 1.0
    raw = ini.get_value(path.read_text(encoding="utf-8"), "Xwayland", "Scale")
    if raw is None:
        return 1.0
    try:
        return parse_scale(raw)
    except ScaleError:
        return 1.0


def set_xwayland_scale(config_home: Path, value: float) -> Path:
    """Set the XWayland multiplier, taking effect immediately."""
    path = Path(config_home) / "kwinrc"
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    updated = ini.set_value(current, "Xwayland", "Scale", format_scale(value))
    atomic_write(path, updated, mode=mode_of(path))
    return path


def unset_xwayland_scale(config_home: Path) -> bool:
    """Drop the override so KWin uses its own default again."""
    path = Path(config_home) / "kwinrc"
    if not path.is_file():
        return False
    current = path.read_text(encoding="utf-8")
    updated = ini.remove_value(current, "Xwayland", "Scale")
    if updated == current:
        return False
    atomic_write(path, updated, mode=mode_of(path))
    return True


def _current_vars(config_home: Path) -> dict[str, str]:
    """Whatever screensmith's plugin already sets, so we never clobber our own keys."""
    plugin = envfile.Plugin(envfile.env_dir(config_home) / f"{PLUGIN_NAME}.desktop")
    return dict(plugin.variables)
