# 修复模糊和尺寸错误的程序

你设了一个分数缩放 —— 1.25、1.5、0.75 —— 然后有些东西看起来发虚，有些尺寸不对，还有个程序看起来完全正常。这不是你的错觉。这里涉及**三个互相独立的机制**，而它们默认并不一致。

先讲心智模型，再讲怎么修。

## 三个机制

**1. 合成器缩放。** 就是显示设置里设的，或者用 `screensmith scale set` 设的。KWin 按这个系数渲染 Wayland 表面。这部分是**正确的，不是问题所在**。

**2. Qt 的舍入策略。** Qt 程序默认并不按任意分数系数渲染。`QT_SCALE_FACTOR_ROUNDING_POLICY` 默认是 `Round`，意思是 1.25 的缩放会被变成最近的 1× 或 2×。你设的 1.25 悄悄变成了 1×，于是控件尺寸不对、文字发虚。设成 `PassThrough` 就是告诉 Qt 老实用 1.25。

这几乎总是"我设了缩放结果更糟"的元凶。

**3. 程序自己那套像素观。** 有几个工具包和浏览器带着**独立于以上全部**的缩放设置。Firefox 有，Chromium 有，某些 Java 程序也有。

## 按顺序修

### 设置舍入策略

```console
$ screensmith rounding set PassThrough
```

它会写 `~/.config/plasma-workspace/env/screensmith-qt-scaling.desktop`：

```ini
[Desktop Entry]
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
Type=Application
X-Plasma-API=develprovenfalse
```

**注销后重新登录。** 环境变量是在你的会话启动时读取的。这是大家会跳过的一步，然后得出"screensmith 没用"的结论。

为什么是 `plasma-workspace/env/` 目录，而不是 `~/.bashrc` 或 `/etc/environment`：**是 Plasma 在启动你的程序**，而它只加载那个目录。你的 shell 配置根本不参与。

确认生效：

```console
$ screensmith rounding get
PassThrough
```

四个可选值：

| 值 | 行为 |
| --- | --- |
| `PassThrough` | 老实使用分数系数。正确，只是稍慢一点。 |
| `Round` | 吸附到最近的整数倍。Qt 的默认值，也是问题的来源。 |
| `Ceil` | 向上取整。 |
| `Floor` | 向下取整。 |

只要有分数缩放在生效，就优先用 `PassThrough`。

### 确认没有别的东西覆盖它

```console
$ screensmith doctor
[  warn ] Rounding policy: unset, so Qt will use its default 'Round'
         A fractional scale with Round rounding makes widgets snap to whole
         multiples and look wrong. Run: screensmith rounding set PassThrough
```

如果 `doctor` 干净但东西还是不对，那说明 Plasma 之外有东西在设这个变量。找一下：

```console
$ grep -rn SCALE_FACTOR_ROUNDING ~/.bashrc ~/.profile ~/.zshrc /etc/environment 2>/dev/null
```

找到了就删掉。对 Plasma 启动的程序，`plasma-workspace/env/` 优先，但你的终端可能持不同意见，进而导致它的子进程行为异常。

## 各程序的单独修复

这些超出了 screensmith 的范围，但也会是你花时间最多的部分，因为每个程序都有自己那套意见。

### Firefox

Firefox 会无视合成器缩放，除非你明确告诉它，所以它通常就是那个看起来不对的。

```
about:config
```

| 首选项 | 值 | 为什么 |
| --- | --- | --- |
| `layout.css.devPixelsPerPx` | 你的缩放，比如 `1.25` | 让 Firefox 知道真实系数 |
| `layout.css.cachedPixelsPerPx` | `1` | 允许它在 DPI 变化时重新渲染 |
| `gfx.webrender.software` | 文字有问题时设 `true` | 强制软件光栅化 |

Firefox 自己也带一个按显示器选的缩放选择器。合成器缩放是分数的时候，`about:config` 比那个选择器更靠谱，因为选择器只提供整数百分比。

### Chromium 和 Electron

Chromium 在 Wayland 下会接上合成器缩放。如果看起来不对：

```console
$ chromium --force-device-scale-factor=1.25
```

想永久生效就用启动器覆盖。**不要**全局设置 —— Chromium 会把它应用到每个窗口包括弹出窗口，导致尺寸对不上。

Electron 程序（Slack、Discord、VS Code）吃同一个标志。VS Code 还认 `"window.titleBarStyle"`，以及编辑器缩放：

```json
{ "editor.fontSize": 15 }
```

### GTK 程序

GTK4 程序尊重合成器缩放。如果某个不对，检查是不是被强制指定了：

```console
$ gsettings get org.gnome.desktop.interface text-scaling-factor
```

那里出现非默认的 `1.0` 会和合成器缩放打架。如果不是你有意设的，就重置掉。

### Java 程序

Java 自己的缩放独立而且出名地顽固：

```console
$ java -Dsun.java2d.uiScale=1.25 -jar something.jar
```

加上 `-Dsun.java2d.uiScale=1` 可以**禁用** Java 缩放、交给合成器处理，在 Wayland 上这通常更好。

### Wine

Wine 程序跟随的是 XWayland 倍数，而不是合成器缩放。如果某个 X11 程序尺寸不对，几乎肯定是 XWayland 那个开关：

```console
$ screensmith xwayland get
$ screensmith xwayland set 1.25
```

KWin 在你通过界面或 `kscreen-doctor` 改缩放时会自动保持这个同步，所以你很少需要手动动它。它走偏通常是因为 `kwinrc` 从旧备份里被恢复了。`screensmith doctor` 会标记这种情况：

```console
$ screensmith doctor
[  warn ] XWayland scale: 1.25 in kwinrc, but the display scale is 1
```

### 完全无视一切的程序

有些就是没法正确缩放，没有办法。显示像素画的图片查看器、某些对像素有硬编码假设的科学工具、某些游戏。没有解法；你要么改程序自己的设置，要么把窗口开成它合适的大小。

## 怎么判断你遇到的是哪种问题

```console
$ screensmith doctor
$ screensmith outputs
```

| 症状 | 原因 | 解法 |
| --- | --- | --- |
| 所有东西都发虚 | 舍入策略 | `screensmith rounding set PassThrough`，注销 |
| 控件尺寸不对、文字发虚 | 舍入策略 | 同上 |
| 只有一个程序不对，别的正常 | 程序自身的缩放 | 见上面各程序章节 |
| X11 程序比其他的都小 | XWayland 缩放 | `screensmith xwayland set <缩放>` |
| 改完配置后好了 | 进程是旧的 | 注销重新登录 |

如果问题是**在改完缩放后立刻出现、并且影响所有东西**，那就是舍入策略。这是常见情况，也是 screensmith 在你设分数缩放的那一刻就警告你的原因：

```console
$ screensmith scale set eDP-1 1.25
eDP-1: 1 (100%) -> 1.25 (125%)
warning: 1.25 (125%) is a fractional scale but QT_SCALE_FACTOR_ROUNDING_POLICY is
unset; widgets may render blurry. Try: screensmith rounding set PassThrough
```

## 推倒重来

```console
$ screensmith scale reset
$ screensmith rounding reset
$ screensmith font-dpi reset
$ screensmith xwayland reset
```

然后注销重新登录。注意**各程序自己的设置** —— Firefox 的 `devPixelsPerPx`、Chromium 的启动标志 —— 这些上述命令都不会碰，你得单独撤销。

在你在意的机器上做实验之前：

```console
$ screensmith backup
$ ls ~/.config/screensmith-backups/
```

如果搞得一团糟：

```console
$ screensmith restore ~/.config/screensmith-backups/20260930-141205
```

## 关于性能的一点说明

`PassThrough` 让 Qt 真正按分数设备像素比渲染，而不是吸附到整数倍。在现代硬件上这个差别察觉不到。在弱核显上跑大屏加 1.75，可能会感觉到合成开销。真遇到这种情况，`Round` 就是性能上的逃生口 —— 代价是尺寸不对，而尺寸不对正是本文要解决的东西。

---

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。
