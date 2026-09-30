# Fixing blurry and mis-sized apps

You set a fractional scale — 1.25, 1.5, 0.75 — and now some things look soft,
some are the wrong size, and one app is definitely fine. That is not your
imagination. Three independent mechanisms are involved and they do not agree by
default.

This is the mental model, then the fix.

## The three mechanisms

**1. The compositor scale.** What you set in display settings, or with
`screensmith scale set`. KWin renders Wayland surfaces at this factor. This
part works correctly and is not the problem.

**2. Qt's rounding policy.** Qt apps do not render at arbitrary fractional
factors by default. `QT_SCALE_FACTOR_ROUNDING_POLICY` defaults to `Round`,
which means a scale of 1.25 becomes 1× or 2× — whichever is nearer. Your
1.25 scale quietly turned into 1×, so widgets are the wrong size and text is
soft. Setting `PassThrough` tells Qt to use 1.25 literally.

This is almost always the cause of "I set the scale and it looks worse".

**3. The app's own idea of pixel size.** Several toolkit and browser
applications carry their own scale settings that are independent of everything
above. Firefox has one. Chromium has one. Some Java apps have one.

## The fix, in order

### Set the rounding policy

```console
$ screensmith rounding set PassThrough
```

That writes `~/.config/plasma-workspace/env/screensmith-qt-scaling.desktop`:

```ini
[Desktop Entry]
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
Type=Application
X-Plasma-API=develprovenfalse
```

**Log out and back in.** Environment variables are read when your session
starts. This is the step people skip, then conclude screensmith does not work.

Why the `plasma-workspace/env/` directory and not `~/.bashrc` or
`/etc/environment`: Plasma launches your applications itself, and it only
sources that directory. Your shell profile is not involved.

Check it took:

```console
$ screensmith rounding get
PassThrough
```

The four values:

| Value | Behaviour |
| --- | --- |
| `PassThrough` | Use the fractional factor literally. Correct, if slightly slower. |
| `Round` | Nearest whole multiple. Qt's default, and the source of the problem. |
| `Ceil` | Round up. |
| `Floor` | Round down. |

Prefer `PassThrough` whenever a fractional scale is active.

### Confirm nothing is overriding it

```console
$ screensmith doctor
[  warn ] Rounding policy: unset, so Qt will use its default 'Round'
         A fractional scale with Round rounding makes widgets snap to whole
         multiples and look wrong. Run: screensmith rounding set PassThrough
```

If `doctor` is clean and things still look wrong, something outside Plasma is
setting the variable. Check for a stray definition:

```console
$ grep -rn SCALE_FACTOR_ROUNDING ~/.bashrc ~/.profile ~/.zshrc /etc/environment 2>/dev/null
```

One exists, delete it. Plasma's env directory wins for Plasma-spawned apps
anyway, but your terminal might disagree, which causes its children to
misbehave.

## Per-application fixes

These are outside screensmith's scope, and also the part you will spend the
most time on, because each application has its own opinion.

### Firefox

Firefox ignores the compositor scale unless you tell it otherwise, and it is
usually the one that looks wrong.

```
about:config
```

| Preference | Value | Why |
| --- | --- | --- |
| `layout.css.devPixelsPerPx` | your scale, e.g. `1.25` | tell Firefox the real factor |
| `layout.css.cachedPixelsPerPx` | `1` | let it re-render on DPI change |
| `gfx.webrender.software` | `true` if text is broken | force the software rasteriser |

Firefox also ships its own per-display scale picker. `about:config` is more
reliable when the compositor scale is fractional, because the picker only
offers whole percentages.

### Chromium and Electron

Chromium picks up the compositor scale on Wayland. If it looks wrong:

```console
$ chromium --force-device-scale-factor=1.25
```

For a permanent fix, use a launcher override. Do not set this globally —
Chromium applies it to every window including popups, which causes mismatched
sizes.

Electron apps (Slack, Discord, VS Code) each take the same flag. VS Code also
honours `"window.titleBarStyle"` and, for editor scaling:

```json
{ "editor.fontSize": 15 }
```

### GTK apps

GTK4 apps respect the compositor scale. If one is off, check that it is not
being forced:

```console
$ gsettings get org.gnome.desktop.interface text-scaling-factor
```

A non-default `1.0` there fights the compositor scale. Reset it if you did not
set it on purpose.

### Java apps

Java's own scaling is separate and famously stubborn:

```console
$ java -Dsun.java2d.uiScale=1.25 -jar something.jar
```

Add `-Dsun.java2d.uiScale=1` to *disable* Java's scaling and let the compositor
handle it, which is usually better on Wayland.

### Wine

Wine applications scale with the XWayland multiplier, not the compositor scale.
If an X11 app is the wrong size, it is almost always the XWayland knob:

```console
$ screensmith xwayland get
$ screensmith xwayland set 1.25
```

KWin keeps this in step with your display scale automatically when you change
the scale through Plasma or `kscreen-doctor`, so you rarely need to touch it.
It drifts when `kwinrc` gets restored from an old backup. `screensmith doctor`
flags that:

```console
$ screensmith doctor
[  warn ] XWayland scale: 1.25 in kwinrc, but the display scale is 1
```

### Apps that ignore everything

Some will not scale correctly, full stop. Image viewers showing pixel art,
some scientific tools with hard-coded assumptions, certain games. There is no
fix; you change the application's own settings or you run it in a window sized
to suit.

## Working out which problem you have

```console
$ screensmith doctor
$ screensmith outputs
```

| Symptom | Cause | Fix |
| --- | --- | --- |
| Everything is soft | Rounding policy | `screensmith rounding set PassThrough`, log out |
| Widgets wrong size, text soft | Rounding policy | Same |
| One app wrong, rest fine | App-specific scale | See above, per application |
| X11 apps smaller than the rest | XWayland scale | `screensmith xwayland set <scale>` |
| Fixed after a config change | Stale process | Log out and back in |

If the problem started right after a scale change and affects *everything*, it
is the rounding policy. That is the common case, and it is why `screensmith`
warns you at the moment you set a fractional scale:

```console
$ screensmith scale set eDP-1 1.25
eDP-1: 1 (100%) -> 1.25 (125%)
warning: 1.25 (125%) is a fractional scale but QT_SCALE_FACTOR_ROUNDING_POLICY is
unset; widgets may render blurry. Try: screensmith rounding set PassThrough
```

## Starting over

```console
$ screensmith scale reset
$ screensmith rounding reset
$ screensmith font-dpi reset
$ screensmith xwayland reset
```

Then log out and in. Note that per-application settings — Firefox's
`devPixelsPerPx`, a Chromium flag — are not touched by any of these. You have
to undo those separately.

Before experimenting on a machine you care about:

```console
$ screensmith backup
$ ls ~/.config/screensmith-backups/
```

And if you break something badly:

```console
$ screensmith restore ~/.config/screensmith-backups/20260930-141205
```

## A note on performance

`PassThrough` makes Qt render at genuinely fractional device scales instead of
snapping to whole multiples. On modern hardware this is not perceptible. On a
weak integrated GPU with a large screen at 1.75, you may notice compositing
cost. If so, `Round` is the performance escape hatch — at the cost of correct
sizing, which is the whole point of this document.
