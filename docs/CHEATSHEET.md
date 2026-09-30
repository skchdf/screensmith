# Cheat sheet

Config file locations, the raw commands behind screensmith, and the settings
that are hard to find. Plasma 6.7, Wayland.

## Where scaling state lives

| What | File | Key | Takes effect |
| --- | --- | --- | --- |
| Per-display scale | `~/.config/kwinoutputconfig.json` | `data[].scale` | at session start |
| Per-display scale (live) | via D-Bus | `kscreen-doctor output.<NAME>.scale.<N>` | immediately |
| XWayland multiplier | `~/.config/kwinrc` | `[Xwayland] Scale` | immediately |
| Rounding policy | `~/.config/plasma-workspace/env/*.desktop` | `QT_SCALE_FACTOR_ROUNDING_POLICY` | next login |
| Font DPI | `~/.config/plasma-workspace/env/*.desktop` | `QT_FONT_DPI` | next login |
| Per-app env | `~/.config/plasma-workspace/env/*.desktop` | anything | next login |
| Panel visibility | `~/.config/plasmarc` | `Plasma/ApperiancePanelDefaultVisibility` | immediately |
| Virtual desktops | `~/.config/kwinrc` | `Desktops/Number`, `Desktops/Rows` | next login |
| Titlebar height | `~/.config/kwinrc` | `[org.kde.kdecoration2] titleBarHeight` | `qdbus6 org.kde.KWin /KWin reconfigure` |
| Tiling enabled | `~/.config/kwinrc` | `Plugins/kwinscriptEnabled` | `qdbus6 org.kde.KWin /KWin reconfigure` |

## screensmith commands

```console
# Inspection
screensmith status                     # one-screen summary
screensmith outputs                    # all displays, physical and logical
screensmith doctor                     # diagnose; exit 1 if any error

# Scale
screensmith scale get [OUTPUT]
screensmith scale set OUTPUT VALUE      # 1.25 or 125%
screensmith scale set OUTPUT VALUE --offline
screensmith scale reset [OUTPUT]

# Presets
screensmith preset compact             # 0.75
screensmith preset balanced            # 1.0
screensmith preset hi-dpi              # 2.0

# Sharpness
screensmith rounding get
screensmith rounding set PassThrough   # also: Round, Ceil, Floor
screensmith rounding reset

# Text and X11
screensmith font-dpi get
screensmith font-dpi set 96
screensmith font-dpi reset

screensmith xwayland get
screensmith xwayland set 1.25
screensmith xwayland reset

# Safety net
screensmith backup
screensmith restore DIR [--yes]
```

Every command takes `--json` before the subcommand:

```console
$ screensmith --json outputs
$ screensmith --json doctor
```

## The same thing without screensmith

```console
# Live scale
kscreen-doctor output.eDP-1.scale.1.25

# List everything KWin knows
kscreen-doctor -o

# XWayland scale
kwriteconfig6 --file kwinrc --group Xwayland --key Scale 1.25

# Any KConfig value
kwriteconfig6 --file <file> --group <group> --key <key> <value>

# Apply KWin changes without logging out
qdbus6 org.kde.KWin /KWin reconfigure

# Check the environment Plasma will give your apps
kwriteconfig6 --file plasmarc --group General --key ...   # not for env vars

# Which session am I in?
echo "$XDG_SESSION_TYPE"     # wayland or x11
```

## The env plugin format

`~/.config/plasma-workspace/env/anything.desktop`:

```ini
[Desktop Entry]
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
Type=Application
X-Plasma-API=develprovenfalse
```

Plasma sources every `env` invocation in that directory at login. Multiple
variables go on one `Exec` line, space separated:

```ini
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough QT_FONT_DPI=96
```

Only this directory works. `/etc/environment`, `~/.bashrc` and systemd user
environment are all ignored for applications Plasma spawns.

## Useful Qt variables

| Variable | Effect |
| --- | --- |
| `QT_SCALE_FACTOR_ROUNDING_POLICY` | `PassThrough` for correct fractional rendering |
| `QT_FONT_DPI` | Base font size Qt assumes. 96 is typical. |
| `QT_SCALE_FACTOR` | Override scale for one app only |
| `QT_SCREEN_SCALE_FACTORS` | Per-screen factors, e.g. `eDP-1=1.25;HDMI-1=1` |
| `QT_QPA_PLATFORM` | Force `wayland` or `xcb` |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | `0` disables automatic detection |

## Scale reference

| Factor | Percent | Typical use |
| --- | --- | --- |
| 0.5 | 50% | Very small text; usually too much |
| 0.75 | 75% | Small laptop panels |
| 0.875 | 87.5% | Mild reduction |
| 1 | 100% | Native |
| 1.25 | 125% | The common HiDPI step |
| 1.5 | 150% | 1080p on a 14" panel |
| 1.75 | 175% | 1440p on a 13" panel |
| 2 | 200% | 4K on a 15" panel |

## Recovery

```console
# Snapshot before experimenting
screensmith backup

# Restore
screensmith restore ~/.config/screensmith-backups/20260930-141205

# Undo copies of anything screensmith overwrote
ls ~/.config/screensmith-undo/

# Nuclear: reset every screensmith knob
screensmith scale reset
screensmith rounding reset
screensmith font-dpi reset
screensmith xwayland reset
```

## Gotchas

- **Env changes need a logout.** Not a restart of the app, not a KWin reload —
  a full logout. The most common reason people think a setting "didn't work".
- **Fractional scaling is Wayland-only.** On X11 KWin ignores it. Check with
  `echo $XDG_SESSION_TYPE`.
- **KWin overwrites `kwinoutputconfig.json` at session start.** Editing it
  while a session runs is pointless.
- **`[Xwayland] Scale` is session-wide**, not per-monitor. X11 apps cannot
  follow per-display scales exactly.
- **Changing scale via `kscreen-doctor` syncs `[Xwayland] Scale`** for you.
  Editing the two by different means is how they drift apart.
- **Do not lower your panel's native resolution** to get more space. You get
  blur, not room.
