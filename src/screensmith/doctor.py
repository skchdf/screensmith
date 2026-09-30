"""Diagnostics: explain what is wrong with a display setup.

Every check returns zero or more :class:`Finding` objects rather than printing,
so the logic is unit-testable and the CLI stays free of formatting concerns.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import output as output_mod
from . import qt
from .scale import format_scale, is_fractional
from .session import Session, have

__all__ = ["Finding", "diagnose", "SEVERITIES"]

SEVERITIES = ("ok", "warn", "error")


@dataclass(frozen=True)
class Finding:
    """One diagnostic result."""

    severity: str
    title: str
    detail: str = ""
    hint: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}")


def diagnose(session: Session) -> list[Finding]:
    """Run every check against *session* and return the findings in order."""
    outputs = _safe_outputs()

    findings: list[Finding] = [
        _check_session(session),
        _check_tooling(),
        *_check_outputs(session, outputs),
        _check_rounding(session, outputs),
        _check_xwayland(session, outputs),
        _check_font_dpi(session),
        _check_config_file(session),
    ]
    return [f for f in findings if f is not None]


def _safe_outputs() -> list[output_mod.Output]:
    """Query KWin for its outputs, returning an empty list on any failure."""
    if not have("kscreen-doctor"):
        return []
    try:
        return output_mod.query_outputs(check=False)
    except Exception:  # noqa: BLE001 - diagnostics must never crash
        return []


def _check_session(session: Session) -> Finding:
    version = session.plasma or "unknown version"
    if session.is_wayland:
        return Finding("ok", "Session", f"Wayland, Plasma {version}")
    return Finding(
        "error",
        "Session",
        f"{session.type}, Plasma {version}",
        "KWin only does fractional scaling on Wayland. Log in on a Wayland "
        "session (Settings -> Sessions) or the scale commands will be ignored.",
    )


def _check_tooling() -> Finding:
    if have("kscreen-doctor"):
        return Finding("ok", "kscreen-doctor", "installed")
    return Finding(
        "error",
        "kscreen-doctor",
        "not found on PATH",
        "Install the kscreen package; it ships the tool that talks to KWin.",
    )


def _check_outputs(session: Session, outputs: list[output_mod.Output]) -> list[Finding]:
    if not have("kscreen-doctor"):
        return []
    if not outputs:
        return [Finding("warn", "Outputs", "KWin reported no outputs, or could not be queried")]

    findings: list[Finding] = []
    active = [o for o in outputs if o.enabled]
    summary = ", ".join(f"{o.name} at {format_scale(o.scale)}" for o in outputs)
    findings.append(Finding("ok", "Outputs", summary))

    shrunk = [o for o in active if o.scale < 1.0]
    if shrunk:
        names = ", ".join(o.name for o in shrunk)
        findings.append(
            Finding(
                "warn",
                "Sub-100% scale",
                f"{names} scaled below 1.0 (system UI is drawn very small)",
                "This is legal but hard to read. If you only wanted smaller "
                "text, prefer 'screensmith font-dpi' and keep scale at 1.",
            )
        )

    return findings


def _check_rounding(session: Session, outputs: list[output_mod.Output]) -> Finding:
    policy = qt.get_rounding(session.config_home)
    fractional = any(o.is_fractional for o in outputs if o.enabled)

    if not fractional:
        if policy is None:
            return Finding("ok", "Rounding policy", "not set (fine: no fractional scales in use)")
        return Finding("ok", "Rounding policy", f"{policy} (set, but no fractional scales are active)")

    if policy is None:
        return Finding(
            "warn",
            "Rounding policy",
            "unset, so Qt will use its default 'Round'",
            "A fractional scale with Round rounding makes widgets snap to whole "
            "multiples and look wrong. Run: screensmith rounding set PassThrough",
        )
    if policy != "PassThrough":
        return Finding(
            "warn",
            "Rounding policy",
            f"{policy}, but a fractional scale is active",
            "Run: screensmith rounding set PassThrough",
        )
    return Finding("ok", "Rounding policy", "PassThrough (correct for fractional scaling)")


def _check_xwayland(session: Session, outputs: list[output_mod.Output]) -> Finding:
    """Check the XWayland multiplier against the display scales.

    Worth a check at all, because KWin keeps ``[Xwayland] Scale`` in step with
    the display scale automatically when you change it through the settings GUI
    or kscreen-doctor. It only drifts when the two are edited by different
    means, or when kwinrc is restored from an old backup.
    """
    value = qt.get_xwayland_scale(session.config_home)
    enabled = [o.scale for o in outputs if o.enabled]

    if value == 1.0:
        if any(is_fractional(s) for s in enabled):
            return Finding(
                "warn",
                "XWayland scale",
                "1, while a fractional display scale is active",
                "X11 apps will not pick up the fractional factor and will look "
                "smaller than everything else. Run: screensmith xwayland set to "
                "match your display scale",
            )
        return Finding("ok", "XWayland scale", "1 (correct for whole-number display scales)")

    if enabled and all(abs(value - s) < 1e-9 for s in enabled):
        shown = " and ".join(format_scale(s) for s in enabled)
        return Finding("ok", "XWayland scale", f"{format_scale(value)}, matching display scale {shown}")

    return Finding(
        "warn",
        "XWayland scale",
        f"{format_scale(value)} in kwinrc, but the display scale is "
        + " and ".join(format_scale(s) for s in enabled or [1.0]),
        "X11 apps use this multiplier instead of your display scale, so they "
        "will look out of step with everything else. Run: screensmith xwayland reset",
    )


def _check_font_dpi(session: Session) -> Finding:
    dpi = qt.get_font_dpi(session.config_home)
    if dpi is None:
        return Finding("ok", "Font DPI", "default")
    return Finding(
        "ok",
        "Font DPI",
        f"{dpi} (QT_FONT_DPI override)",
        "Applies at next login. Set it back with 'screensmith font-dpi reset'.",
    )


def _check_config_file(session: Session) -> Finding:
    config = output_mod.KwinOutputConfig(session.config_home / "kwinoutputconfig.json")
    if not config.exists:
        return Finding(
            "warn",
            "kwinoutputconfig.json",
            "missing",
            "KWin will not remember your scale across reboots without it.",
        )
    try:
        connectors = config.connectors()
    except (OSError, ValueError) as exc:
        return Finding("error", "kwinoutputconfig.json", f"unreadable: {exc}")
    return Finding(
        "ok", "kwinoutputconfig.json", f"records {len(connectors)} output(s): {', '.join(connectors)}"
    )


def summarise(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity, for a one-line summary."""
    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        counts[finding.severity] += 1
    return counts
