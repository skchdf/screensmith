# KDE Plasma 上低于 100% 的缩放

Plasma 的显示设置从 100% 起步，往上加。它没有任何办法让桌面**比面板报的还小** —— 至少在界面里没有。

KWin 没有这个限制。`kscreen-doctor` 乐于接受 0.25 到 10 之间的任何值，而小屏幕往往正好需要这个。

本文基于 Plasma 6.7.5 + Wayland 写成。验证方式是在一块 1366×768 面板上设成 0.75，然后读回会话报告的内容。

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。

## 你为什么会想要这个

1366×768 是廉价笔记本用了十年的分辨率。它很小。在 100% 下你得到一个 1366×768 的工作区，大概只放得下一个全屏浏览器窗口再加一个文件管理器。如果你能接受更小的字，降到 75% 就把它变成 1821×1024 的工作区，**面积增加 33%**。

算法很简单：KWin 用物理分辨率除以缩放系数，得到逻辑工作区。

```
逻辑宽度 = 1366 / 0.75 = 1821
逻辑高度 =  768 / 0.75 = 1024
```

| 缩放 | 工作区 | 相对 100% |
| --- | --- | --- |
| 1.0 | 1366×768 | 基准 |
| 0.875 | 1561×878 | 面积 +14% |
| 0.75 | 1821×1024 | 面积 +33% |
| 0.6 | 2277×1280 | 面积 +78% |

低于 0.7 左右就没意义了：文字小到读着难受，你会开始需要显示器的放大镜功能。

## 用 screensmith 来做

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

立刻生效。不用注销，不用重启。

如果你只想让**文字**变小而不是所有东西都变小，用字体 DPI，缩放保持 1：

```console
$ screensmith font-dpi set 84
```

这个改动更温和。所有东西保持原有布局，只有文字缩小。

## 手动操作

两种方式。除非你有特别的理由，否则用第一种。

### 正确的方式：kscreen-doctor

```console
$ kscreen-doctor output.LVDS-1.scale.0.75
```

它和正在运行的 KWin 通信，立刻生效，并且 KWin 会自己把结果持久化到 `~/.config/kwinoutputconfig.json`。它还会自动同步 `kwinrc` 里的 `[Xwayland] Scale` —— 这个细节否则你得自己处理。

确认生效了：

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

注意 `Geometry` 仍然显示 1366×768 —— 那是物理尺寸。逻辑工作区在这里不显示，所以 `screensmith outputs` 会单独把它列出来。

### 另一种方式：改 kwinoutputconfig.json

只有在会话没在运行时才有用：做机器预配置，或者通过 SSH 操作而没有活动会话。KWin 在会话启动时会覆盖这个文件，所以运行期间做的改动会被冲掉。

```console
$ cp ~/.config/kwinoutputconfig.json ~/.config/kwinoutputconfig.json.bak
$ ${EDITOR:-nano} ~/.config/kwinoutputconfig.json
```

找到你那块 connector 对应的条目，改它的 `"scale"`：

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

缩放是一个纯粹的倍数。是 `0.75`，不是 `75`。保持文件原有的四空格缩进 —— KWin 就是这么写的，而且格式被重排过的文件以后用 `git diff` 看会很难受。

同样的效果，一条命令：

```console
$ screensmith scale set LVDS-1 0.75 --offline
```

它会先备份，然后直白地告诉你运行中的会话会覆盖这个改动。

## 多显示器

每块输出有自己的缩放，而且**不必相同**。小笔记本屏配大外接显示器时这很有用：

```console
$ screensmith scale set LVDS-1 0.75
$ screensmith scale set HDMI-1 1
$ screensmith outputs
STATE  OUTPUT  SCALE  MODE      WORKSPACE
-----  ------  -----  --------  ----------------
on     LVDS-1  0.75   1366x768  1821x1024 logical
on     HDMI-1  1      2560x1440 2560x1440 logical
```

有个值得知道的坑：KWin 对 XWayland 只应用**一个全局**倍数（`kwinrc [Xwayland] Scale`），所以 X11 程序无法完美跟随按显示器不同的缩放。Wayland 程序处理得正确。如果你经常在不匹配的显示器上用很多 X11 软件，这会咬人。

## 改回去

```console
$ screensmith scale reset          # 所有启用的输出重置为 1
$ screensmith scale reset LVDS-1   # 只重置一块
```

或者 `kscreen-doctor output.LVDS-1.scale.1`。

## 如果看起来不对

跑一下诊断。它知道三件会让缩放看起来坏掉的事：

```console
$ screensmith doctor
[  warn ] Sub-100% scale: LVDS-1 scaled below 1.0 (system UI is drawn very small)
[  warn ] Rounding policy: unset, so Qt will use its default 'Round'
         A fractional scale with Round rounding makes widgets snap to whole
         multiples and look wrong. Run: screensmith rounding set PassThrough
```

舍入策略那条警告是要紧的。0.75 是分数缩放，而 Qt 的默认舍入会让控件渲染在整数倍上 —— 1× 或 2× —— 而不是你要的 0.75。修掉它，然后注销重新登录：

```console
$ screensmith rounding set PassThrough
```

那东西到底在做什么，见[修复模糊和尺寸错误的程序](03-blurry-apps.md)。

## 用脚本读回来

```console
$ screensmith --json scale get
{
  "LVDS-1": 0.75
}
```

## 它做不到的事

- **它不改分辨率。** 你的面板还是 1366×768。桌面只是"以为"自己有更多空间，于是画得更小。想要真正的更多像素，你需要一块分辨率更高的面板。
- **它对非 Qt 程序无效。** GTK4、Electron、Java 程序各自处理缩放的方式不同，有些直接无视。比如 Firefox 有自己的 `layout.css.devPixelsPerPx` 设置，KWin 的缩放完全不碰它。
- **它在 X11 会话下不适用。** 分数缩放是 KWin 的 Wayland 独占特性。如果你跑在 X11 上，`doctor` 会告诉你。

下一篇：[小屏幕自救指南](02-small-screen.md) —— 当屏幕真的很小时，还有哪些东西真的有用。
