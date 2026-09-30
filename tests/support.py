"""Shared fixtures and helpers for the screensmith test suite."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screensmith.session import Session  # noqa: E402

# Verbatim `kscreen-doctor -o` output from KDE Plasma 6.7.5 on Wayland,
# including the escape sequences it emits when stdout is a TTY. Two outputs: a
# 1366x768 laptop panel scaled to 0.75, and a disconnected 1024x768 panel.
KSCREEN_DOCTOR_SAMPLE = """
Output: 1 LVDS-1 3c1c1f29-e7e2-4815-8686-01c82e6775e1
\t\x1b[32menabled\x1b[0m
\t\x1b[32mconnected\x1b[0m
\tpriority 1
\tPanel
\treplication source: 0
\tModes: \t\x1b[32m1:1366x768@60.07*\x1b[0m \t2:1024x768@59.92  3:1024x768@59.92
\tCustom modes: \tNone
\tGeometry: 0,0 1366x768
\tScale: \t\x1b[33m0.75\x1b[0m
\tRotation: \t1
\tOverscan: \t0
\tVrr: \t\x1b[32mincapable\x1b[0m

Output: 2 X11-0 23f31ad1-48d1-4746-95d3-6b22b8cdf1b9
\t\x1b[31mdisabled\x1b[0m
\t\x1b[31mdisconnected\x1b[0m
\tpriority 1
\tPanel
\tModes: \t1:1024x768@59.92*
\tCustom modes: \tNone
\tGeometry: 0,0 1024x768
\tScale: \t\x1b[33m1\x1b[0m
\tRotation: \t1
"""

KWINRC_SAMPLE = """[Desktops]
Number=4
Rows=1

[Effect-translucency]
Menus=80

[Tiling][07caa50c-c063-4689-9234-846f66543f76][3c1c1f29-e7e2-4815-8686-01c82e6775e1]
padding=4

[Xwayland]
Scale=1
"""

KWINOUTPUTCONFIG_SAMPLE = """[
    {
        "data": [
            {
                "connectorName": "LVDS-1",
                "scale": 1,
                "uuid": "3c1c1f29-e7e2-4815-8686-01c82e6775e1",
                "mode": {
                    "flags": 1,
                    "height": 768,
                    "refreshRate": 60072,
                    "width": 1366
                }
            },
            {
                "connectorName": "X11-0",
                "scale": 1,
                "uuid": "23f31ad1-48d1-4746-95d3-6b22b8cdf1b9",
                "mode": {
                    "flags": 1,
                    "height": 768,
                    "refreshRate": 59999,
                    "width": 1024
                }
            }
        ],
        "name": "outputs"
    },
    {
        "data": [
            {
                "lidClosed": false,
                "outputs": [
                    {
                        "enabled": true,
                        "outputIndex": 0,
                        "position": {
                            "x": 0,
                            "y": 0
                        },
                        "priority": 1,
                        "replicationSource": ""
                    }
                ]
            }
        ],
        "name": "setups"
    }
]
"""

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def fake_session(tmp_path: Path, *, session_type: str = "wayland", plasma: str = "6.7.5") -> Session:
    """A :class:`Session` pointing at a throwaway config home."""
    config = tmp_path / "config"
    config.mkdir(parents=True, exist_ok=True)
    return Session(type=session_type, plasma=plasma, config_home=config)
