"""Discovering outputs and reading/writing their scale factor.

There are two sources of truth and they can disagree:

``kscreen-doctor``
    Talks to the running KWin over KScreen's D-Bus API. Changes take effect
    immediately and KWin persists them to ``kwinoutputconfig.json`` itself.

``kwinoutputconfig.json``
    The file KWin reads at startup. Editing it directly only matters when no
    session is running, but it is the only way to script a display setup for a
    machine you cannot sit in front of.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import scale as scale_mod
from .session import CommandError, have, run

__all__ = ["Output", "parse_kscreen_doctor", "query_outputs", "set_live_scale", "KwinOutputConfig"]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_HEADER_RE = re.compile(r"^Output:\s*(?P<index>\d+)\s+(?P<name>\S+)(?:\s+(?P<uuid>[0-9A-Za-z-]+))?")
_SCALE_RE = re.compile(r"^\s*Scale:\s*(?P<scale>[\d.]+)")
_GEOMETRY_RE = re.compile(r"^\s*Geometry:\s*(?P<x>-?\d+),(?P<y>-?\d+)\s+(?P<w>\d+)x(?P<h>\d+)")
_MODES_RE = re.compile(r"^\s*Modes:\s*(?P<modes>.+)$")
# Within the Modes line the active one is tagged with a trailing '*'.
_ACTIVE_MODE_RE = re.compile(r"(?P<w>\d+)x(?P<h>\d+)@(?P<rate>[\d.]+)\*")


@dataclass(frozen=True)
class Output:
    """One display as KWin currently sees it."""

    name: str
    index: int
    scale: float = 1.0
    width: int = 0
    height: int = 0
    connected: bool = True
    enabled: bool = True
    uuid: str | None = None

    @property
    def is_fractional(self) -> bool:
        return scale_mod.is_fractional(self.scale)

    @property
    def logical(self) -> tuple[int, int]:
        """Size in logical pixels, i.e. what you actually get to place windows in."""
        return scale_mod.logical_geometry(self.width, self.height, self.scale)

    @property
    def logical_label(self) -> str:
        logical_w, logical_h = self.logical
        return f"{logical_w}x{logical_h}"


def parse_kscreen_doctor(text: str) -> list[Output]:
    """Parse ``kscreen-doctor -o`` output.

    Colour codes, tab alignment and the variable number of trailing detail
    lines differ between KScreen versions, so this matches on structure rather
    than on fixed positions. Unrecognised lines are ignored.
    """
    text = _ANSI_RE.sub("", text)

    outputs: list[Output] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("Output:"):
            if current is not None:
                parsed = _parse_block(current)
                if parsed is not None:
                    outputs.append(parsed)
            # The header line belongs to the block it introduces.
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        parsed = _parse_block(current)
        if parsed is not None:
            outputs.append(parsed)
    return outputs


def _parse_block(block: list[str]) -> Output | None:
    header = _HEADER_RE.match(block[0].strip()) if block else None
    if header is None:
        return None

    fields: dict[str, object] = {
        "name": header.group("name"),
        "index": int(header.group("index")),
        "uuid": header.group("uuid"),
    }

    for raw in block[1:]:
        line = raw.rstrip()
        lowered = line.strip().lower()

        # kscreen-doctor prints bare state words for the booleans, negated to
        # say the output is off or unplugged rather than on and present.
        if lowered in {"enabled", "connected"}:
            fields[lowered] = True
            continue
        if lowered == "disabled":
            fields["enabled"] = False
            continue
        if lowered == "disconnected":
            fields["connected"] = False
            continue

        if match := _SCALE_RE.match(line):
            fields["scale"] = float(match.group("scale"))
            continue

        if match := _GEOMETRY_RE.match(line):
            fields["width"] = int(match.group("w"))
            fields["height"] = int(match.group("h"))
            continue

        if match := _MODES_RE.match(line):
            if active := _ACTIVE_MODE_RE.search(match.group("modes")):
                fields.setdefault("width", int(active.group("w")))
                fields.setdefault("height", int(active.group("h")))
            continue

    return Output(
        name=str(fields["name"]),
        index=int(fields["index"]),  # type: ignore[arg-type]
        scale=float(fields.get("scale", 1.0)),  # type: ignore[arg-type]
        width=int(fields.get("width", 0)),  # type: ignore[arg-type]
        height=int(fields.get("height", 0)),  # type: ignore[arg-type]
        connected=bool(fields.get("connected", True)),
        enabled=bool(fields.get("enabled", True)),
        uuid=fields.get("uuid"),  # type: ignore[arg-type]
    )


def query_outputs(*, check: bool = True) -> list[Output]:
    """Ask the running KWin for its outputs.

    With ``check=False`` a failure yields an empty list instead of raising,
    which is what ``doctor`` wants when probing a headless box.
    """
    if not have("kscreen-doctor"):
        if check:
            raise CommandError(["kscreen-doctor"], 127, "not installed (package: kscreen)")
        # A missing binary is just another way of having nothing to report.
        return []
    proc = run(["kscreen-doctor", "-o"], check=check)
    return parse_kscreen_doctor(proc.stdout)


def set_live_scale(output: str, value: float) -> None:
    """Set *output*'s scale on the running session, atomically with any other change."""
    if not have("kscreen-doctor"):
        raise CommandError(["kscreen-doctor"], 127, "not installed (package: kscreen)")
    # Pass the number the way KScreen parses it, not via the user's original text.
    run(["kscreen-doctor", f"output.{output}.scale.{scale_mod.format_scale(value)}"])


class KwinOutputConfig:
    """Read/modify/write ``kwinoutputconfig.json``.

    Writes use ``indent=4``, which is the layout KWin itself produces, so a file
    that screensmith touched stays diff-friendly for the user.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def load_text(self) -> str:
        if not self.exists:
            raise FileNotFoundError(f"{self.path} does not exist (is Plasma running?)")
        return self.path.read_text(encoding="utf-8")

    def load(self) -> list[dict]:
        data = json.loads(self.load_text())
        if not isinstance(data, list):
            raise ValueError(f"{self.path}: expected a list at the top level")
        return data

    def dumps(self, data: list[dict]) -> str:
        return json.dumps(data, indent=4) + "\n"

    def connectors(self) -> list[str]:
        """Names of every output KWin has a record for, connected or not."""
        names = []
        for group in self.load():
            if group.get("name") != "outputs":
                continue
            for entry in group.get("data", []):
                if name := entry.get("connectorName"):
                    names.append(name)
        return names

    def scale_of(self, connector: str) -> float | None:
        for entry in self._entries():
            if entry.get("connectorName") == connector:
                value = entry.get("scale")
                return float(value) if value is not None else None
        return None

    def set_scale_text(self, text: str, connector: str, value: float) -> str:
        """Return *text* with *connector*'s scale set to *value*."""
        data = json.loads(text)
        for entry in self._entries_in(data):
            if entry.get("connectorName") == connector:
                entry["scale"] = value
                return self.dumps(data)
        known = ", ".join(e.get("connectorName", "?") for e in self._entries_in(data)) or "none"
        raise KeyError(f"no output named {connector!r} in this config (have: {known})")

    def _entries(self) -> list[dict]:
        return self._entries_in(self.load())

    @staticmethod
    def _entries_in(data: list[dict]) -> list[dict]:
        entries: list[dict] = []
        for group in data:
            if group.get("name") == "outputs":
                entries.extend(group.get("data", []))
        return entries
