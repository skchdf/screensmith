"""screensmith — display & scaling surgery for KDE Plasma.

The Plasma settings GUI only offers a fixed ladder of scale factors starting at
100%, and it refuses to go below that. KWin itself has no such limit. This
package wraps the handful of knobs that actually control display scaling,
fractional-scaling sharpness and XWayland size, and exposes them as a CLI.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
