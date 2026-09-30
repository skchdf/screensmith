# Small screen survival guide

1366×768 is the resolution most cheap laptops shipped with for a decade. It is
small. This is everything I have found that actually helps, ordered by how much
it helps.

Everything here is KDE Plasma on Wayland, Plasma 6.7.5.

## 1. Shrink the scale

The biggest single win, and the one the GUI does not offer below 100%.

```console
$ screensmith scale set eDP-1 0.75
```

1366×768 becomes a 1821×1024 workspace. See
[Sub-100% scaling](01-sub-100-scaling.md) for the details.

## 2. Shortcut: go back to 100% and just make the text smaller

If the reason you want sub-100% scale is "too much text", this is less
disorienting. Widgets keep their size; only text shrinks:

```console
$ screensmith font-dpi set 84
```

84 is about 87% of the usual 96. Below about 72 text gets uncomfortable.

The trade-off against scale: font DPI does not give you extra workspace, it
just fits more text into the same space. Scale does both.

## 3. Hide the panel and get the height back

The Plasma panel takes 30–50px. Auto-hide it:

```console
$ kwriteconfig6 --file plasmarc --group Plasma --key ApperiancePanelDefaultVisibility auto
```

Or in the GUI: right-click the panel → *Panel Settings* → *Visibility* →
*Auto hide*.

With a scale change on top, that is often enough.

## 4. Shrink window titlebars

KDE Frameworks 6 lets you set titlebar height explicitly:

```console
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key titleBarHeight "22"
```

And enable smaller buttons:

```console
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft ""
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnRight "⤵;⤬;⤫"
```

Restart KWin for either: `qdbus6 org.kde.KWin /KWin reconfigure`.

## 5. Use one virtual desktop, in a sensible shape

Plasma defaults to a 2×2 grid of virtual desktops on a small screen, which
gives you four tiny workspaces and means you always have windows on two of
them. One desktop, one row, is calmer:

```console
$ screensmith status                        # sanity check first
$ kwriteconfig6 --file kwinrc --group Desktops --key Number 1
$ kwriteconfig6 --file kwinrc --group Desktops --key Rows 1
```

Requires logging out and back in. Consider KWin's tiling scripting for
arranging windows instead of virtual desktops:

```console
$ kwriteconfig6 --file kwinrc --group Plugins --key kwinscriptEnabled true
```

## 6. Tiling with keyboard shortcuts

The highest-value change on a small screen, honestly. Drag-to-arrange is
wasteful when you have 768 vertical pixels.

KWin's built-in tiling (Plasma 6) works with `Meta` by default:

| Key | Action |
| --- | --- |
| `Meta+T` | tile / untile the focused window |
| `Meta+Shift+←` | move window to the left half |
| `Meta+Shift+→` | move to the right half |

Enable it in *System Settings → Desktop → Tiling*. More layouts live in
[krohnkite](https://invent.kde.org/plasma/kwin), which adds columns, grids and
resizable splits.

## 7. Trim the window decoration further

If you use Breeze or a similar theme, the titlebar padding is part of the
theme, not a setting. A small per-user theme override does more than the
options above.

## 8. Font choice matters more than size

At 768 pixels tall, a font with a tall x-height buys you more legible text at
the same nominal size. Good options:

- **Noto Sans** — high x-height, very legible, already on most systems
- **Inter** — designed for screen UI specifically
- **Cantarell** — the GNOME default, good hinting at small sizes

```console
$ fc-list | grep -i inter
```

Avoid serif or monospace as your UI font at this size — they cost vertical space
and read worse when small.

## 9. Reduce panel height

Plasma's panel respects a fixed height setting. Below ~28px the panel widgets
start getting cramped, so there is a floor.

## 10. Consider the external monitor, honestly

If you dock regularly, a 1080p external at 100% gives you 2560×1080 of
workspace for the cost of one cable. The laptop panel can stay at 0.75 and the
external at 1.0.

```console
$ screensmith scale set eDP-1 0.75
$ screensmith scale set HDMI-1 1
```

## What did not help

Recording honestly, since these come up:

- **Lowering the resolution.** 1366×768 → 1024×768 makes everything blurry
  and *reduces* your workspace. Modern panels interpolate; you get neither
  sharpness nor space.
- **Scaling the panel's "UI scale" in the display settings past 100%** — same
  feature as item 1, still no help below 100%.
- **Hiding the taskbar and using only the panel.** Manageable, but you lose
  window switching. KRunner (`Alt+Space`) covers most of it.

## A reasonable final configuration

For a 1366×768 panel:

```console
$ screensmith preset compact          # scale 0.75, PassThrough
$ screensmith font-dpi set 90
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key titleBarHeight "24"
$ kwriteconfig6 --file kwinrc --group Desktops --key Number 1
$ kwriteconfig6 --file kwinrc --group Desktops --key Rows 1
```

Log out, log back in, enable tiling, and bind `Meta+T`.

## Check it

```console
$ screensmith doctor
$ screensmith status
```

If `doctor` is clean and you have tiling bound, you have done about as much as
software can do about a 1366×768 panel.

Next: [Fixing blurry and mis-sized apps](03-blurry-apps.md).
