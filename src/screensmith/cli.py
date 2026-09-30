"""Command line interface for screensmith."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import __version__, doctor, envfile, qt, ui
from . import output as output_mod
from .fsutil import atomic_write, backup_file, mode_of
from .output import KwinOutputConfig
from .scale import (
    ScaleError,
    describe_scale,
    format_scale,
    is_fractional,
    logical_geometry,
    parse_scale,
)
from .session import CommandError, Session, have

__all__ = ["main", "build_parser"]


@dataclass(frozen=True)
class Preset:
    """A named bundle of settings, so people need not remember three commands."""

    scale: float
    rounding: str
    summary: str


PRESETS: dict[str, Preset] = {
    "compact": Preset(0.75, "PassThrough", "Shrink everything, for small laptop screens"),
    "balanced": Preset(1.0, "PassThrough", "Native size with sharp rendering"),
    "hi-dpi": Preset(2.0, "PassThrough", "Double size, for high-resolution panels"),
}

#: Config files screensmith may write, snapshotted and restored under their
#: real names. Env plugins are namespaced with an ``env-`` prefix so they cannot
#: collide with these (see :func:`_destination_for`).
_BACKUP_FILES = ("kwinrc", "kwinoutputconfig.json")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _json_mode(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def _pick_output(session: Session, requested: str | None) -> output_mod.Output:
    """Resolve *requested* (a connector name or uuid) to a live output."""
    outputs = output_mod.query_outputs()
    if requested is None:
        enabled = [o for o in outputs if o.enabled]
        if not enabled:
            raise SystemExit(ui.fail("no enabled outputs to work with"))
        if len(enabled) == 1:
            return enabled[0]
        names = ", ".join(o.name for o in enabled)
        raise SystemExit(ui.fail(f"several outputs are active ({names}); name one explicitly"))

    for item in outputs:
        if requested == item.name or (item.uuid and requested == item.uuid):
            return item
    known = ", ".join(o.name for o in outputs) or "none"
    raise SystemExit(ui.fail(f"no output named {requested!r} (available: {known})"))


def _config(session: Session) -> KwinOutputConfig:
    return KwinOutputConfig(session.config_home / "kwinoutputconfig.json")


def _log_out_of_scale(session: Session, note: str) -> None:
    """Remind the user that env-var changes only land at the next login."""
    if session.is_wayland:
        ui.warn(f"{note} (takes effect after you log out and back in)")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def cmd_status(session: Session, args: argparse.Namespace) -> int:
    outputs = output_mod.query_outputs(check=False)
    payload = {
        "session": session.type,
        "plasma": session.plasma,
        "config_home": str(session.config_home),
        "outputs": [
            {
                "name": o.name,
                "scale": o.scale,
                "enabled": o.enabled,
                "connected": o.connected,
                "mode": f"{o.width}x{o.height}",
                "logical": f"{o.logical[0]}x{o.logical[1]}",
                "fractional": o.is_fractional,
            }
            for o in outputs
        ],
        "rounding_policy": qt.get_rounding(session.config_home),
        "xwayland_scale": qt.get_xwayland_scale(session.config_home),
        "font_dpi": qt.get_font_dpi(session.config_home),
    }

    if _json_mode(args):
        ui.emit_json(payload)
        return 0

    print(f"{ui.paint('Session', 'bold')}  {session.type}, Plasma {session.plasma or '?'}")
    print()
    if outputs:
        rows = [
            [
                ("on" if o.enabled else "off"),
                o.name,
                format_scale(o.scale),
                f"{o.width}x{o.height}",
                f"{o.logical_label} logical",
                "fractional" if o.is_fractional else "",
            ]
            for o in outputs
        ]
        print(ui.render_table(["STATE", "OUTPUT", "SCALE", "MODE", "WORKSPACE", ""], rows))
    else:
        ui.warn("KWin reported no outputs")
    print()
    print(f"{ui.paint('Rounding policy', 'bold')}  {payload['rounding_policy'] or 'unset'}")
    print(f"{ui.paint('XWayland scale', 'bold')}  {format_scale(payload['xwayland_scale'])}")
    print(f"{ui.paint('Font DPI', 'bold')}        {payload['font_dpi'] or 'default'}")
    return 0


def cmd_outputs(session: Session, args: argparse.Namespace) -> int:
    outputs = output_mod.query_outputs()
    if _json_mode(args):
        ui.emit_json([o.__dict__ for o in outputs])
        return 0

    rows = [
        [
            o.name,
            o.uuid or "",
            "on" if o.enabled else "off",
            "yes" if o.connected else "no",
            format_scale(o.scale),
            f"{o.width}x{o.height}",
            f"{o.logical_label}",
        ]
        for o in outputs
    ]
    print(ui.render_table(["NAME", "UUID", "ENABLED", "PLUGGED", "SCALE", "MODE", "LOGICAL"], rows))
    return 0


def cmd_doctor(session: Session, args: argparse.Namespace) -> int:
    findings = doctor.diagnose(session)
    if _json_mode(args):
        ui.emit_json([f.__dict__ for f in findings])
        return 1 if any(f.severity == "error" for f in findings) else 0

    icons = {
        "ok": ui.paint("  ok  ", "ok"),
        "warn": ui.paint(" warn ", "warn"),
        "error": ui.paint("error ", "error"),
    }
    for finding in findings:
        print(f"[{icons[finding.severity]}] {ui.paint(finding.title, 'bold')}: {finding.detail}")
        if finding.hint and finding.severity != "ok":
            for line in _wrap(finding.hint, 74):
                print(f"         {line}")
    counts = doctor.summarise(findings)
    print()
    print(f"{counts['ok']} ok, {counts['warn']} warning(s), {counts['error']} error(s)")
    return 1 if counts["error"] else 0


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width) or [""]


def cmd_scale_get(session: Session, args: argparse.Namespace) -> int:
    outputs = output_mod.query_outputs()
    if args.output:
        target = _pick_output(session, args.output)
        outputs = [target]

    if _json_mode(args):
        ui.emit_json({o.name: o.scale for o in outputs})
        return 0

    for item in outputs:
        print(f"{item.name}: {describe_scale(item.scale)} ({item.logical_label} logical)")
    return 0


def cmd_scale_set(session: Session, args: argparse.Namespace) -> int:
    value = parse_scale(args.value)

    if args.offline:
        config = _config(session)
        text = config.load_text()
        connector = args.output
        if connector is None:
            recorded = config.connectors()
            if len(recorded) != 1:
                raise SystemExit(
                    ui.fail(
                        f"--offline needs an explicit output (config has: {', '.join(recorded) or 'none'})"
                    )
                )
            connector = recorded[0]
        try:
            updated = config.set_scale_text(text, connector, value)
        except KeyError as exc:
            raise SystemExit(ui.fail(str(exc))) from exc
        backup_file(config.path, config.path.parent / "screensmith-backups")
        atomic_write(config.path, updated, mode=mode_of(config.path))
        print(f"{connector}: scale {format_scale(value)} written to {config.path}")
        ui.warn(
            "KWin will overwrite this file when the session starts; apply it from a running session instead"
        )
        return 0

    target = _pick_output(session, args.output)
    before = target.scale
    try:
        output_mod.set_live_scale(target.name, value)
    except CommandError as exc:
        raise SystemExit(ui.fail(str(exc))) from exc

    if _json_mode(args):
        ui.emit_json({"output": target.name, "before": before, "after": value})
        return 0

    print(f"{target.name}: {describe_scale(before)} -> {describe_scale(value)}")
    if target.width and target.height:
        logical_w, logical_h = logical_geometry(target.width, target.height, value)
        print(f"  workspace is now {logical_w}x{logical_h} logical pixels")

    policy = qt.get_rounding(session.config_home)
    if is_fractional(value) and policy != "PassThrough":
        print()
        ui.warn(
            f"{describe_scale(value)} is a fractional scale but "
            f"QT_SCALE_FACTOR_ROUNDING_POLICY is {policy or 'unset'}; "
            f"widgets may render blurry. Try: screensmith rounding set PassThrough"
        )
    return 0


def cmd_scale_reset(session: Session, args: argparse.Namespace) -> int:
    targets = [args.output] if args.output else [o.name for o in output_mod.query_outputs() if o.enabled]
    for name in targets:
        target = _pick_output(session, name)
        try:
            output_mod.set_live_scale(target.name, 1.0)
        except CommandError as exc:
            raise SystemExit(ui.fail(str(exc))) from exc
        print(f"{target.name}: scale reset to 1")
    return 0


def cmd_xwayland(session: Session, args: argparse.Namespace) -> int:
    path = session.config_home / "kwinrc"
    if args.action == "get":
        value = qt.get_xwayland_scale(session.config_home)
        if _json_mode(args):
            ui.emit_json(value)
        else:
            print(describe_scale(value))
        return 0
    if args.action == "reset":
        if qt.unset_xwayland_scale(session.config_home):
            print(f"removed the XWayland scale override from {path}")
        else:
            print("no XWayland scale override was set")
        return 0

    value = parse_scale(args.value)
    qt.set_xwayland_scale(session.config_home, value)
    print(f"XWayland scale: {describe_scale(value)} ({path})")
    return 0


def cmd_rounding(session: Session, args: argparse.Namespace) -> int:
    if args.action == "get":
        policy = qt.get_rounding(session.config_home)
        if _json_mode(args):
            ui.emit_json(policy)
        else:
            print(policy or f"unset (Qt default: {qt.DEFAULT_ROUNDING})")
        return 0
    if args.action == "reset":
        if qt.unset_rounding(session.config_home):
            print("removed QT_SCALE_FACTOR_ROUNDING_POLICY; Qt will use its default")
        else:
            print("QT_SCALE_FACTOR_ROUNDING_POLICY was not set by screensmith")
        _log_out_of_scale(session, "this change")
        return 0

    try:
        path = qt.set_rounding(session.config_home, args.value)
    except ValueError as exc:
        raise SystemExit(ui.fail(str(exc))) from exc
    print(f"QT_SCALE_FACTOR_ROUNDING_POLICY={args.value} ({path})")
    _log_out_of_scale(session, "this change")
    return 0


def cmd_font_dpi(session: Session, args: argparse.Namespace) -> int:
    if args.action == "get":
        dpi = qt.get_font_dpi(session.config_home)
        if _json_mode(args):
            ui.emit_json(dpi)
        else:
            print(f"{dpi}" if dpi else "default")
        return 0
    if args.action == "reset":
        if qt.unset_font_dpi(session.config_home):
            print("removed the QT_FONT_DPI override")
        else:
            print("QT_FONT_DPI was not set by screensmith")
        _log_out_of_scale(session, "this change")
        return 0

    try:
        dpi = int(args.value)
    except ValueError as exc:
        raise SystemExit(ui.fail(f"font DPI must be a whole number, got {args.value!r}")) from exc
    try:
        path = qt.set_font_dpi(session.config_home, dpi)
    except ValueError as exc:
        raise SystemExit(ui.fail(str(exc))) from exc
    print(f"QT_FONT_DPI={dpi} ({path})")
    _log_out_of_scale(session, "this change")
    return 0


def cmd_preset(session: Session, args: argparse.Namespace) -> int:
    preset = PRESETS[args.name]
    targets = [args.output] if args.output else [o.name for o in output_mod.query_outputs() if o.enabled]
    if not targets:
        raise SystemExit(ui.fail("no enabled outputs to configure"))

    print(f"preset '{args.name}': {preset.summary}")
    for name in targets:
        target = _pick_output(session, name)
        try:
            output_mod.set_live_scale(target.name, preset.scale)
        except CommandError as exc:
            raise SystemExit(ui.fail(str(exc))) from exc
        print(f"  scale {target.name} -> {describe_scale(preset.scale)}")
    qt.set_rounding(session.config_home, preset.rounding)
    print(f"  rounding policy -> {preset.rounding}")
    _log_out_of_scale(session, "the rounding policy change")
    return 0


def cmd_backup(session: Session, args: argparse.Namespace) -> int:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = (
        Path(args.directory).expanduser()
        if args.directory
        else session.config_home / "screensmith-backups" / stamp
    )
    destination.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for filename in _BACKUP_FILES:
        copied = backup_file(session.config_home / filename, destination, label=filename)
        if copied:
            written.append(copied.name)

    for plugin in sorted(envfile.env_dir(session.config_home).glob("*.desktop")):
        # Prefixed so a plugin named "kwinrc.desktop" cannot masquerade as the
        # real kwinrc during a restore.
        copied = backup_file(plugin, destination, label=f"env-{plugin.name}")
        if copied:
            written.append(copied.name)

    if _json_mode(args):
        ui.emit_json({"directory": str(destination), "files": written})
        return 0
    print(f"backed up {len(written)} file(s) to {destination}")
    for name in written:
        print(f"  {name}")
    return 0


def cmd_restore(session: Session, args: argparse.Namespace) -> int:
    source = Path(args.directory).expanduser()
    if not source.is_dir():
        raise SystemExit(ui.fail(f"{source} is not a directory"))

    files = sorted(p for p in source.iterdir() if p.is_file())
    if not files:
        raise SystemExit(ui.fail(f"{source} contains no files to restore"))

    if not args.yes:
        print(f"about to restore {len(files)} file(s) from {source}:")
        for item in files:
            print(f"  {item.name}")
        answer = input("continue? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("aborted")
            return 1

    for item in files:
        target = _destination_for(session, item.name)
        if target is None:
            ui.warn(f"skipping {item.name}: no known destination")
            continue
        backup_file(target, target.parent / "screensmith-undo")
        atomic_write(target, item.read_text(encoding="utf-8"), mode=mode_of(target))
        print(f"restored {item.name} -> {target}")
    ui.warn("log out and back in for the restored settings to take full effect")
    return 0


def _destination_for(session: Session, filename: str) -> Path | None:
    if filename in _BACKUP_FILES:
        return session.config_home / filename
    if filename.startswith("env-"):
        stem = filename[len("env-") :]
        if not stem or "/" in stem:
            return None
        return envfile.env_dir(session.config_home) / f"{stem}.desktop"
    return None


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screensmith",
        description="Display and scaling surgery for KDE Plasma, including the "
        "scale factors the settings GUI will not offer you.",
        epilog="Run 'screensmith doctor' if something looks wrong.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    sub.add_parser("status", help="one-screen summary of the current setup").set_defaults(func=cmd_status)
    sub.add_parser("outputs", help="list displays KWin knows about").set_defaults(func=cmd_outputs)
    sub.add_parser("doctor", help="diagnose scaling problems").set_defaults(func=cmd_doctor)

    scale = sub.add_parser("scale", help="per-display scale factor").add_subparsers(
        dest="action", metavar="ACTION", required=True
    )
    scale_get = scale.add_parser("get", help="show the current scale factor")
    scale_get.add_argument("output", nargs="?", help="connector name, e.g. eDP-1")
    scale_get.set_defaults(func=cmd_scale_get)
    scale_set = scale.add_parser("set", help="set a scale factor (accepts 1.5 or 150 percent)")
    scale_set.add_argument("output", help="connector name, e.g. eDP-1")
    scale_set.add_argument("value", help="a multiplier or a percentage")
    scale_set.add_argument(
        "--offline",
        action="store_true",
        help="write kwinoutputconfig.json instead of talking to a running KWin",
    )
    scale_set.set_defaults(func=cmd_scale_set)
    scale_reset = scale.add_parser("reset", help="set scale back to 1")
    scale_reset.add_argument("output", nargs="?", help="connector name; defaults to all enabled outputs")
    scale_reset.set_defaults(func=cmd_scale_reset)

    xwayland = sub.add_parser("xwayland", help="the global multiplier applied to X11 apps").add_subparsers(
        dest="action", metavar="ACTION", required=True
    )
    xwayland.add_parser("get", help="show the XWayland scale").set_defaults(func=cmd_xwayland)
    xwayland_set = xwayland.add_parser("set", help="set the XWayland scale")
    xwayland_set.add_argument("value", help="a multiplier or a percentage")
    xwayland_set.set_defaults(func=cmd_xwayland)
    xwayland.add_parser("reset", help="drop the override").set_defaults(func=cmd_xwayland)

    rounding = sub.add_parser(
        "rounding", help="QT_SCALE_FACTOR_ROUNDING_POLICY, i.e. sharp fractional scaling"
    ).add_subparsers(dest="action", metavar="ACTION", required=True)
    rounding.add_parser("get", help="show the policy").set_defaults(func=cmd_rounding)
    rounding_set = rounding.add_parser("set", help="set the policy")
    rounding_set.add_argument(
        "value", choices=qt.ROUNDING_POLICIES, help="one of: " + ", ".join(qt.ROUNDING_POLICIES)
    )
    rounding_set.set_defaults(func=cmd_rounding)
    rounding.add_parser("reset", help="remove the override").set_defaults(func=cmd_rounding)

    font = sub.add_parser("font-dpi", help="QT_FONT_DPI, the base size Qt assumes for text").add_subparsers(
        dest="action", metavar="ACTION", required=True
    )
    font.add_parser("get", help="show the font DPI").set_defaults(func=cmd_font_dpi)
    font_set = font.add_parser("set", help="set the font DPI")
    font_set.add_argument("value", help="a whole number, 96 is typical")
    font_set.set_defaults(func=cmd_font_dpi)
    font.add_parser("reset", help="remove the override").set_defaults(func=cmd_font_dpi)

    preset = sub.add_parser("preset", help="apply a named bundle of settings").add_subparsers(
        dest="name", metavar="NAME", required=True
    )
    for name, spec in PRESETS.items():
        sub_preset = preset.add_parser(name, help=spec.summary)
        sub_preset.add_argument("output", nargs="?", help="connector name; defaults to all enabled outputs")
        sub_preset.set_defaults(func=cmd_preset)

    backup = sub.add_parser("backup", help="snapshot the config files screensmith touches")
    backup.add_argument("directory", nargs="?", help="where to write the snapshot")
    backup.set_defaults(func=cmd_backup)

    restore = sub.add_parser("restore", help="restore a snapshot made by 'backup'")
    restore.add_argument("directory", help="snapshot directory")
    restore.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    restore.set_defaults(func=cmd_restore)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return 0

    # `status` and `doctor` degrade gracefully without KScreen; the rest cannot.
    if not have("kscreen-doctor") and args.command in {"outputs", "scale"}:
        raise SystemExit(ui.fail("kscreen-doctor is required (package: kscreen)"))

    try:
        session = Session.probe()
        return int(args.func(session, args))
    except CommandError as exc:
        raise SystemExit(ui.fail(str(exc))) from exc
    except ScaleError as exc:
        raise SystemExit(ui.fail(str(exc))) from exc
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
