"""A line-preserving editor for the INI dialect KDE uses.

Plasma's config files are read by KConfig, which is *not* exactly Python's
INI. Two differences matter in practice:

* Keys and section names are case sensitive, and section names may contain
  further brackets, e.g. ``[Tiling][<uuid>]``.
* Round-tripping a file with comments must not destroy them.

``configparser`` handles neither, so screensmith edits the text directly and
leaves every line it does not care about byte-for-byte identical.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

__all__ = ["get_value", "set_value", "remove_value", "iter_groups", "split_kv"]

_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]*(?:\][^\]]*)*)\]\s*$")
_KV_RE = re.compile(r"^(?P<key>[^=:\s][^=:]*?)\s*[=:]\s*(?P<value>.*)$")


def split_kv(line: str) -> tuple[str, str] | None:
    """Split an INI assignment into ``(key, value)``, or None if it is not one.

    Handles both ``key=value`` and KDE's occasional ``key[locale]=value``.
    Comments (``#`` or ``;``) and blank lines return None.
    """
    stripped = line.strip()
    if not stripped or stripped[0] in "#;":
        return None
    match = _KV_RE.match(stripped)
    if not match:
        return None
    return match.group("key"), match.group("value")


def iter_groups(text: str) -> Iterator[tuple[str, int, int]]:
    """Yield ``(section_name, start_line, end_line)`` for every section.

    ``end_line`` is exclusive and always greater than ``start_line``, so
    ``lines[start:end]`` is the section body. Text before the first section
    header is never yielded; it belongs to no group.
    """
    lines = text.splitlines()
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match:
            starts.append((match.group("name").strip(), index))

    for position, (name, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        yield name, start, end


def get_value(text: str, group: str, key: str) -> str | None:
    """Return the value of *key* inside *group*, or None if it is not set."""
    for name, start, end in iter_groups(text):
        if name != group:
            continue
        for line in text.splitlines()[start + 1 : end]:
            pair = split_kv(line)
            if pair and pair[0] == key:
                return pair[1]
    return None


def set_value(text: str, group: str, key: str, value: str) -> str:
    """Return *text* with ``group/key`` set to *value*.

    Appends the key to the end of its group if missing, and appends the whole
    group to the end of the file if the group itself is missing.
    """
    if "\n" in value or "\r" in value:
        raise ValueError(f"refusing to write a multi-line value for {group}/{key}")

    lines = text.splitlines()
    had_trailing_newline = text.endswith("\n") or text == ""

    for name, start, end in iter_groups(text):
        if name != group:
            continue
        for offset in range(start + 1, end):
            pair = split_kv(lines[offset])
            if pair and pair[0] == key:
                lines[offset] = f"{key}={value}"
                return _join(lines, had_trailing_newline)
        # Key is absent. Insert after the last real assignment so a trailing
        # comment block stays attached to what it documents.
        insert_at = start + 1
        for offset in range(start + 1, end):
            if _is_assignment(lines[offset]):
                insert_at = offset + 1
        lines.insert(insert_at, f"{key}={value}")
        return _join(lines, had_trailing_newline)

    # Group is absent: create it at the end of the file, separated by a blank
    # line so it does not run straight on from the previous group's body.
    body = lines[:]
    while body and not body[-1].strip():
        body.pop()
    if body:
        body.append("")
    body.extend([f"[{group}]", f"{key}={value}"])
    return _join(body, True)


def remove_value(text: str, group: str, key: str) -> str:
    """Return *text* with ``group/key`` deleted. No-op if it is not present."""
    lines = text.splitlines()
    had_trailing_newline = text.endswith("\n") or text == ""

    for name, start, end in iter_groups(text):
        if name != group:
            continue
        for offset in range(start + 1, end):
            pair = split_kv(lines[offset])
            if pair and pair[0] == key:
                del lines[offset]
                return _join(lines, had_trailing_newline)
    return text


def _is_assignment(line: str) -> bool:
    return split_kv(line) is not None


def _join(lines: list[str], trailing_newline: bool) -> str:
    out = "\n".join(lines)
    if trailing_newline and out:
        out += "\n"
    return out
