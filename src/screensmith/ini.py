"""A line-preserving editor for the INI dialect KDE uses.

Plasma's config files are read by KConfig, which is *not* exactly Python's
INI. Two differences matter in practice:

* Keys and section names are case sensitive, and section names may contain
  further brackets, e.g. ``[Tiling][<uuid>]``.
* Round-tripping a file with comments must not destroy them.

``configparser`` handles neither, so screensmith edits the text directly and
leaves every line it does not care about byte-for-byte identical — including
CRLF line endings, which ``str.splitlines`` would silently flatten to LF.

Where a file is ambiguous, KConfig's own resolution rule is applied: within a
group the *last* assignment of a key wins, and a group name stated more than
once merges into one logical group whose later body overrides the earlier.
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

    Lines are split on ``"\\n"`` only (not ``str.splitlines``) so that indices
    stay in step with the other editing functions and CRLF endings survive a
    round trip. Duplicate section names each get their own span.
    """
    lines = text.split("\n")
    # Splitting text that ends with a newline leaves a phantom "" element; it
    # is not a line, so the last section must not swallow it.
    last = len(lines) - 1 if lines and lines[-1] == "" and text.endswith("\n") else len(lines)
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match:
            starts.append((match.group("name").strip(), index))

    for position, (name, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else last
        yield name, start, end


def _matching_keys(lines: list[str], spans: list[tuple[int, int]], key: str) -> list[int]:
    """Line offsets of every assignment to *key* inside the given group spans."""
    offsets: list[int] = []
    for start, end in spans:
        offsets.extend(
            offset
            for offset in range(start + 1, end)
            if (pair := split_kv(lines[offset])) is not None and pair[0] == key
        )
    return offsets


def get_value(text: str, group: str, key: str) -> str | None:
    """Return the value of *key* inside *group*, or None if it is not set.

    Follows KConfig: if a key or a whole group is stated more than once, the
    last assignment wins.
    """
    lines = text.split("\n")
    spans = [(start, end) for name, start, end in iter_groups(text) if name == group]
    value: str | None = None
    for offset in _matching_keys(lines, spans, key):
        pair = split_kv(lines[offset])
        if pair is not None:
            value = pair[1]
    return value


def set_value(text: str, group: str, key: str, value: str) -> str:
    """Return *text* with ``group/key`` set to *value*.

    The key is written into the *last* body of *group* (the one KConfig reads
    last, and therefore honours); any earlier assignments to the same key are
    removed so exactly one survives. If the key is absent it is appended after
    the last real assignment, so a trailing comment block stays attached to
    what it documents. If the group itself is missing, it is created at the end
    of the file, separated by a blank line so it does not run straight on from
    the previous group's body.
    """
    if "\n" in value or "\r" in value:
        raise ValueError(f"refusing to write a multi-line value for {group}/{key}")

    lines = text.split("\n")
    had_trailing_newline = text.endswith("\n") or text == ""

    spans = [(start, end) for name, start, end in iter_groups(text) if name == group]
    if spans:
        matches = _matching_keys(lines, spans, key)
        if matches:
            # Replace the last occurrence (the one KConfig honours) and drop the
            # rest; deleting bottom-up keeps the earlier offsets valid.
            lines[matches[-1]] = f"{key}={value}"
            for offset in reversed(matches[:-1]):
                del lines[offset]
            return _join(lines, had_trailing_newline)

        start, end = spans[-1]
        insert_at = start + 1
        for offset in range(start + 1, end):
            if split_kv(lines[offset]) is not None:
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
    """Return *text* with ``group/key`` deleted. No-op if it is not present.

    Every assignment to *key* in every body of *group* is removed.
    """
    lines = text.split("\n")
    had_trailing_newline = text.endswith("\n") or text == ""

    spans = [(start, end) for name, start, end in iter_groups(text) if name == group]
    matches = _matching_keys(lines, spans, key)
    if not matches:
        return text
    for offset in reversed(matches):
        del lines[offset]
    return _join(lines, had_trailing_newline)


def _join(lines: list[str], trailing_newline: bool) -> str:
    # The phantom "" from splitting newline-terminated text is not content;
    # drop it and re-add the terminator explicitly.
    if trailing_newline and lines and lines[-1] == "":
        lines = lines[:-1]
    out = "\n".join(lines)
    if trailing_newline and out:
        out += "\n"
    return out
