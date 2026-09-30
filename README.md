# screensmith

Display and scaling surgery for KDE Plasma — including the scale factors the
settings GUI will not offer you.

Plasma's display settings offer a fixed ladder: 100%, 125%, 150%, 175%, 200%,
and nothing below 100%. KWin itself has no such limit. If you want 75% on a
1366×768 laptop panel, or 137.5%, the GUI cannot get you there — you have to
edit `kwinoutputconfig.json` and hope you typed it right.

screensmith is a small CLI that does it properly, and tells you when the result
will look wrong.

```console
$ screensmith scale set LVDS-1 0.75
LVDS-1: 1 (100%) -> 0.75 (75%)
  workspace is now 1821x1024 logical pixels
```

## Why

Three things make display scaling on Plasma confusing, and all three are
things the settings UI either hides or gets wrong:

1. **There is no sub-100% option.** A small laptop screen often wants exactly
   that. KWin accepts any factor from 0.25 up.
2. **Fractional scale looks blurry for no obvious reason.** Qt's default
   `QT_SCALE_FACTOR_ROUNDING_POLICY=Round` snaps a 1.25 scale to integer device
   pixels, so widgets render at the wrong size and text looks soft. The fix is
   `PassThrough`, and it lives in an environment variable that you have to know
   to set *before* login.
3. **X11 apps drift out of step.** KWin applies the display scale to Wayland
   clients automatically, but XWayland clients go through
   `kwinrc [Xwayland] Scale`, a separate knob that defaults to 1.

`screensmith doctor` checks all three and tells you which one is biting you.

## Install

```console
$ git clone https://github.com/skchdf/screensmith
$ cd screensmith
$ python -m pip install --user .
```

No runtime dependencies. Python 3.10+. You need `kscreen-doctor`, which ships
with the `kscreen` package that Plasma already pulls in.

Shell completions are in `completions/`; copy the one for your shell to
`/etc/bash_completion.d/` or your `$fpath`.

## Use

Everything is a subcommand, and every command takes `--json` if you are
scripting it.

```console
$ screensmith status
Session  wayland, Plasma 6.7.5

STATE  OUTPUT  SCALE  MODE      WORKSPACE
-----  ------  -----  --------  ----------------
on     LVDS-1  1      1366x768  1366x768 logical

Rounding policy  unset
XWayland scale   1
Font DPI         default
```

### Scale a display

Accepts either a multiplier or a percentage, whichever your fingers remember:

```console
$ screensmith scale set LVDS-1 1.25      # multiplier
$ screensmith scale set LVDS-1 125%      # percentage, same result
$ screensmith scale set LVDS-1 0.75      # below 100%: 1366x768 -> 1821x1024
$ screensmith scale reset                # every enabled output back to 1
```

Set a display that is not plugged in right now (headless, or over SSH) by
writing the config file directly:

```console
$ screensmith scale set HDMI-1 2 --offline
```

KWin reads that file at session start. It will overwrite the value the moment
the session comes up, so this is for provisioning a machine, not for adjusting
the one in front of you.

### Make fractional scale sharp

```console
$ screensmith rounding set PassThrough
```

Needs a logout to take effect. `screensmith doctor` will keep reminding you
until it does.

### Text and X11 apps

```console
$ screensmith font-dpi set 120      # bigger text, same widget sizes
$ screensmith xwayland set 1.25      # scale X11 apps to match
$ screensmith xwayland reset         # let KWin derive it from the display
```

### Presets

If you would rather not think about it:

```console
$ screensmith preset compact     # 0.75 everywhere, sharp
$ screensmith preset balanced    # 1.0, sharp
$ screensmith preset hi-dpi      # 2.0, sharp
```

### Undo

```console
$ screensmith backup              # snapshot into ~/.config/screensmith-backups/
$ screensmith restore ~/.config/screensmith-backups/20260930-141205
```

Every write is also snapshotted to `~/.config/screensmith-undo/` first, so the
worst case is one directory of files to copy back by hand.

## Diagnose

```console
$ screensmith doctor
[  ok  ] Session: Wayland, Plasma 6.7.5
[  ok  ] kscreen-doctor: installed
[  ok  ] Outputs: LVDS-1 at 0.75
[ warn ] Sub-100% scale: LVDS-1 scaled below 1.0 (system UI is drawn very small)
         This is legal but hard to read. If you only wanted smaller text, prefer
         'screensmith font-dpi' and keep scale at 1.
[ warn ] Rounding policy: unset, so Qt will use its default 'Round'
         A fractional scale with Round rounding makes widgets snap to whole
         multiples and look wrong. Run: screensmith rounding set PassThrough
[  ok  ] XWayland scale: 0.75, matching display scale 0.75
[  ok  ] Font DPI: default
[  ok  ] kwinoutputconfig.json: records 2 output(s): LVDS-1, X11-0

5 ok, 2 warning(s), 0 error(s)
```

Exit status is 1 if anything is an error, so it works in a health check.

## How it works

Plasma's scaling state lives in four places, and they are not documented
anywhere obvious:

| What | Where | Takes effect |
| --- | --- | --- |
| Per-display scale | `kscreen-doctor`, persisted to `~/.config/kwinoutputconfig.json` | immediately |
| XWayland multiplier | `~/.config/kwinrc`, `[Xwayland] Scale` | immediately |
| Rounding policy | `~/.config/plasma-workspace/env/*.desktop` | next login |
| Font DPI | same | next login |

Env vars go in `plasma-workspace/env/` rather than `/etc/environment` or your
shell profile because Plasma launches apps itself and only sources that
directory. Screensmith writes an `env`-style plugin named
`screensmith-qt-scaling.desktop`, so it never touches a plugin you created.

Only the keys screensmith owns are ever written. Your `kwinrc` is edited in
place, line by line: comments, ordering and unrelated groups survive.

One thing KWin does for you, which is worth knowing because it is not obvious:
changing the display scale through `kscreen-doctor` (or the settings GUI)
keeps `[Xwayland] Scale` in step automatically. The two only drift when you
edit them by different means, or restore `kwinrc` from an old backup. `doctor`
checks for it.

## Safety

- Every config write is atomic (temp file, fsync, rename). KWin reads these
  files continuously; a half-written `kwinrc` can leave a session unconfigurable.
- Permissions are preserved on the files it rewrites.
- `--offline` writes take a backup first.
- `screensmith restore` asks before overwriting, and snapshots what it replaces.
- Invalid input is rejected with an explanation, never partially applied.

## Also in this repo

Tutorials in [`docs/tutorials/`](docs/tutorials/), written against a real
Plasma 6.7 session:

- [Sub-100% scaling, and why 75% is legal](docs/tutorials/01-sub-100-scaling.md)
- [Small screen survival guide](docs/tutorials/02-small-screen.md)
- [Fixing blurry and mis-sized apps](docs/tutorials/03-blurry-apps.md)

Plus a [cheat sheet](docs/CHEATSHEET.md) of the config paths and commands, and
[CONTRIBUTING.md](CONTRIBUTING.md) if you want to help.

## Development

```console
$ python -m unittest discover -s tests -t tests
```

178 tests, no dependencies. They are hermetic: a temporary config home, fixture
captures of `kscreen-doctor` output, and no reading of your actual session. They
pass identically here, on a live Plasma desktop, and on a bare CI runner with
`kscreen-doctor` off `$PATH`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Status

Beta, and specific about what has and has not been verified.

**Verified on this machine** (Plasma 6.7.5, Wayland, Arch Linux, kscreen 6.7.5):

- scale set / get / reset on a live output, and the value surviving in
  `kwinoutputconfig.json`
- `kwinrc` `[Xwayland] Scale` being updated by KWin in step with the display scale
- `status`, `outputs`, `doctor` against a real session
- `backup` and `restore` round-tripping real config files

**Verified only by tests**, i.e. against fixtures and mocked `kscreen-doctor`
output rather than a live session: multi-monitor layouts, `--offline`,
`preset`, the `restore` undo snapshots, and every `--json` mode.

**Not verified**: Plasma 5, non-KDE Wayland compositors, X11 sessions (where
fractional scaling does not exist), and Plasma versions other than 6.7.x.
Contributions with real-session output from those configurations are welcome.

It is also Linux-only and assumes `kscreen-doctor` is on `PATH`; the config-file
parts would work anywhere, but nothing has been tested there.

## License

MIT.
