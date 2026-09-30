"""Plasma's ``plasma-workspace/env`` mechanism.

Any ``*.desktop`` file dropped into ``~/.config/plasma-workspace/env/`` whose
``Exec`` line is an ``env`` invocation gets sourced into the environment of
every process Plasma launches on the next login. This is the only supported way
to change Qt's scaling behaviour globally — editing ``/etc/environment`` is
ignored for apps started by the shell.

File shape, as written by Plasma itself::

    [Desktop Entry]
    Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
    Type=Application
    X-Plasma-API=develprovenfalse
"""

from __future__ import annotations

import shlex
from pathlib import Path

from . import ini
from .fsutil import atomic_write, mode_of

__all__ = ["env_dir", "Plugin", "load_env", "write_vars", "unset_vars", "find_var"]

_DESKTOP_ENTRY = "Desktop Entry"
_API_MARKER = "X-Plasma-API=develprovenfalse"


def env_dir(config_home: Path) -> Path:
    """Where Plasma looks for environment plugins."""
    return Path(config_home) / "plasma-workspace" / "env"


def _split_exec(exec_line: str) -> tuple[str, list[str]]:
    """Return ``(command, args)`` for an Exec line, or ``("", [])`` if unusable."""
    try:
        tokens = shlex.split(exec_line, comments=False, posix=True)
    except ValueError:
        return "", []
    if not tokens:
        return "", []
    return tokens[0], tokens[1:]


def _parse_env_plugin(text: str) -> dict[str, str]:
    """Extract ``VAR=value`` pairs from a plugin's Exec line."""
    command, args = _split_exec(ini.get_value(text, _DESKTOP_ENTRY, "Exec") or "")
    if command != "env":
        return {}
    variables: dict[str, str] = {}
    for arg in args:
        name, sep, value = arg.partition("=")
        if sep and name and name.replace("_", "").isalnum():
            variables[name] = value
    return variables


def _render_env_plugin(variables: dict[str, str]) -> str:
    assignment = " ".join(f"{name}={shlex.quote(value)}" for name, value in variables.items())
    return f"[{_DESKTOP_ENTRY}]\nExec=env {assignment}\nType=Application\n{_API_MARKER}\n"


class Plugin:
    """A single ``.desktop`` file in the env directory."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.text = self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        self.variables = _parse_env_plugin(self.text)

    @property
    def name(self) -> str:
        return self.path.stem

    def save(self, variables: dict[str, str]) -> None:
        atomic_write(self.path, _render_env_plugin(variables), mode=mode_of(self.path))
        self.variables = dict(variables)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


def _iter_plugins(directory: Path) -> list[Plugin]:
    if not directory.is_dir():
        return []
    # Sort so a later file deterministically wins; Plasma does not define an order.
    return [Plugin(p) for p in sorted(directory.glob("*.desktop"))]


def load_env(config_home: Path) -> dict[str, str]:
    """All variables Plasma will export, with later files overriding earlier ones."""
    merged: dict[str, str] = {}
    for plugin in _iter_plugins(env_dir(config_home)):
        merged.update(plugin.variables)
    return merged


def find_var(config_home: Path, name: str) -> Plugin | None:
    """The plugin that defines *name*, if any."""
    for plugin in _iter_plugins(env_dir(config_home)):
        if name in plugin.variables:
            return plugin
    return None


def write_vars(config_home: Path, plugin_name: str, variables: dict[str, str]) -> Path:
    """Create or update *plugin_name* so it exports exactly *variables*."""
    plugin = Plugin(env_dir(config_home) / f"{plugin_name}.desktop")
    plugin.save(variables)
    return plugin.path


def unset_vars(config_home: Path, names: list[str]) -> list[str]:
    """Remove *names*, deleting the plugin file once it becomes empty.

    Returns the names that were actually defined.
    """
    removed: list[str] = []
    for plugin in _iter_plugins(env_dir(config_home)):
        remaining = {k: v for k, v in plugin.variables.items() if k not in names}
        if len(remaining) == len(plugin.variables):
            continue
        removed.extend(k for k in plugin.variables if k in names)
        if remaining:
            plugin.save(remaining)
        else:
            plugin.delete()
    return removed
