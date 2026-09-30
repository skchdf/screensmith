# Sub-100% scaling on KDE Plasma

Plasma's display settings start at 100% and go up. There is no way to make the
desktop *smaller* than the panel reports — through the GUI.

KWin has no such restriction. `kscreen-doctor` will happily accept anything from
0.25 upward, and on a small screen that is often exactly what you want.

Written against Plasma 6.7.5 on Wayland. Verified by setting 0.75 on a
1366×768 panel and reading back what the session reported.

## Why you might want it

A 1366×768 laptop panel is small. At 100% you get a 1366×768 workspace, which
fits maybe one full-size browser window side by side with a file manager. If
you are willing to accept smaller text, dropping to 75% turns that into a
1821×1024 workspace. That is a 33% increase in area.

The arithmetic is simple: KWin divides the physical resolution by the scale
factor to get the logical workspace.

```
logical width  = 1366 / 0.75 = 1821
logical height =  768 / 0.75 = 1024
```

| Scale | Workspace | Compared to 100% |
| --- | --- | --- |
| 1.0 | 1366×768 | baseline |
| 0.875 | 1561×878 | +14% area |
| 0.75 | 1821×1024 | +33% area |
| 0.6 | 2277×1280 | +78% area |

Going much below about 0.7 stops being useful: text gets too small to read
comfortably, and you start needing the display's magnifier.

## Doing it with screensmith

```console
$ screensmith outputs
NAME    UUID                                  ENABLED  PLUGGED  SCALE  MODE      LOGICAL
------  ------------------------------------  -------  -------  -----  --------  --------
LVDS-1  3c1c1f29-e7e2-4815-8686-01c82e6775e1  on       yes      1      1366x768  1366x768

$ screensmith scale set LVDS-1 0.75
LVDS-1: 1 (100%) -> 0.75 (75%)
  workspace is now 1821x1024 logical pixels
warning: 0.75 (75%) is a fractional scale but QT_SCALE_FACTOR_ROUNDING_POLICY is
unset; widgets may render blurry. Try: screensmith rounding set PassThrough
```

It applies immediately. No logout, no restart.

If you only want smaller *text* rather than smaller everything, use font DPI
instead and leave scale at 1:

```console
$ screensmith font-dpi set 84
```

That is a gentler change. Everything keeps its layout; only text shrinks.

## Doing it by hand

Two ways. Use the first unless you have a reason not to.

### The right way: kscreen-doctor

```console
$ kscreen-doctor output.LVDS-1.scale.0.75
```

This talks to the running KWin, applies the change immediately, and KWin
persists it to `~/.config/kwinoutputconfig.json` for you. It also keeps
`kwinrc`'s `[Xwayland] Scale` in step automatically, which is the detail you
would otherwise have to handle yourself.

Confirm it stuck:

```console
$ kscreen-doctor -o | grep -A8 LVDS-1
Output: 1 LVDS-1 3c1c1f29-e7e2-4815-8686-01c82e6775e1
	enabled
	connected
	priority 1
	Panel
	Modes: 	1:1366x768@60.07*
	Custom modes: 	None
	Geometry: 0,0 1366x768
	Scale: 	0.75
```

Note that `Geometry` still reads 1366×768 — that is the physical size. The
logical workspace is not shown here, which is why `screensmith outputs` prints
it separately.

### The other way: editing kwinoutputconfig.json

Only useful when no session is running: provisioning a machine, or over SSH
with no active session. KWin overwrites this file when the session starts, so
changes made while it is running get clobbered.

```console
$ cp ~/.config/kwinoutputconfig.json ~/.config/kwinoutputconfig.json.bak
$ ${EDITOR:-nano} ~/.config/kwinoutputconfig.json
```

Find the entry for your connector and change its `"scale"`:

```json
{
    "connectorName": "LVDS-1",
    "scale": 0.75,
    "uuid": "3c1c1f29-e7e2-4815-8686-01c82e6775e1",
    "mode": {
        "flags": 1,
        "height": 768,
        "refreshRate": 60072,
        "width": 1366
    }
}
```

The scale is a plain multiplier. `0.75`, not `75`. Match the existing file's
four-space indentation so the diff stays readable — KWin writes it that way and
a reformatted file is unpleasant to `git diff` later.

Same effect, one command:

```console
$ screensmith scale set LVDS-1 0.75 --offline
```

This takes a backup first, then tells you plainly that a running session will
overwrite it.

## Multiple displays

Each output has its own scale, and they do not have to match. This is useful
when you have a small laptop panel and a large external monitor:

```console
$ screensmith scale set LVDS-1 0.75
$ screensmith scale set HDMI-1 1
$ screensmith outputs
STATE  OUTPUT  SCALE  MODE      WORKSPACE
-----  ------  -----  --------  ----------------
on     LVDS-1  0.75   1366x768  1821x1024 logical
on     HDMI-1  1      2560x1440 2560x1440 logical
```

Caveat worth knowing: KWin applies a *single* XWayland multiplier session-wide
(`kwinrc [Xwayland] Scale`), so X11 apps cannot follow per-monitor scales
perfectly. Wayland apps handle it correctly. If you use a lot of X11
software on mismatched monitors, this bites.

## Going back

```console
$ screensmith scale reset          # every enabled output to 1
$ screensmith scale reset LVDS-1   # just one
```

Or `kscreen-doctor output.LVDS-1.scale.1`.

## If it looks wrong

Run the diagnostic. It knows about the three things that make scaling look
broken:

```console
$ screensmith doctor
[  warn ] Sub-100% scale: LVDS-1 scaled below 1.0 (system UI is drawn very small)
[  warn ] Rounding policy: unset, so Qt will use its default 'Round'
         A fractional scale with Round rounding makes widgets snap to whole
         multiples and look wrong. Run: screensmith rounding set PassThrough
```

The rounding-policy warning is the one that matters. 0.75 is a fractional
scale, and Qt's default rounding makes widgets render at whole multiples —
1× or 2× — rather than the 0.75 you asked for. Fix it, then log out and back
in:

```console
$ screensmith rounding set PassThrough
```

See [Fixing blurry and mis-sized apps](03-blurry-apps.md) for what that is
actually doing.

## Reading the config back

If you want to script against this:

```console
$ screensmith --json scale get
{
  "LVDS-1": 0.75
}
```

## What this does not do

- **It does not change resolution.** Your panel is still 1366×768. The desktop
  just believes it has more room, and draws smaller. If you want genuinely
  more pixels, you need a higher-resolution panel.
- **It does not help non-Qt apps.** GTK4, Electron and Java applications each
  handle scaling differently, and some ignore it. Firefox, for example, needs
  its own `layout.css.devPixelsPerPx` setting, which KWin's scale does not
  touch.
- **It does not apply to X11 sessions.** Fractional scaling is a Wayland-only
  feature in KWin. `screensmith doctor` will say so if you are on X11.

Next: [small screen survival guide](02-small-screen.md) —
the other things that help when a screen is genuinely small.
