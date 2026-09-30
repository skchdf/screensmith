# 小屏幕自救指南

1366×768 是廉价笔记本用了十年的分辨率。它很小。这是我能找到的**真正有帮助**的所有东西，按帮助大小排序。

全部基于 KDE Plasma + Wayland，Plasma 6.7.5。

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。

## 1. 把缩放调小

单项收益最大的一个，也是界面唯一不给 100% 以下的。

```console
$ screensmith scale set eDP-1 0.75
```

1366×768 变成 1821×1024 的工作区。详见[低于 100% 的缩放](01-sub-100-scaling.md)。

## 2. 偷懒方案：缩放回 100%，只把字调小

如果你想要低于 100% 的理由是"字太多了"，这个办法没那么让人晕头转向。控件保持原尺寸，只有文字缩小：

```console
$ screensmith font-dpi set 84
```

84 大约是常规 96 的 87%。低于 72 左右文字就难受了。

和调缩放相比的取舍：字体 DPI 不会给你额外的工作区，只是让同样空间里塞下更多文字。缩放两样都给。

## 3. 藏掉面板，把高度拿回来

Plasma 面板占 30–50px。设置自动隐藏：

```console
$ kwriteconfig6 --file plasmarc --group Plasma --key ApperiancePanelDefaultVisibility auto
```

或者用界面：右键面板 → *面板设置* → *可见性* → *自动隐藏*。

如果再叠加上缩放调整，通常就够了。

## 4. 压缩标题栏

KDE Frameworks 6 允许显式设置标题栏高度：

```console
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key titleBarHeight "22"
```

以及启用小按钮：

```console
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft ""
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnRight "⤵;⤬;⤫"
```

两个都需要重启 KWin：`qdbus6 org.kde.KWin /KWin reconfigure`。

## 5. 只用一个虚拟桌面，并排成合理的形状

Plasma 在小屏上默认是 2×2 的虚拟桌面网格，那会给你四个很小的空间，意味着你的窗口永远同时占着其中两个。改成单个、单行，会安静很多：

```console
$ screensmith status                        # 先做个检查
$ kwriteconfig6 --file kwinrc --group Desktops --key Number 1
$ kwriteconfig6 --file kwinrc --group Desktops --key Rows 1
```

需要注销重新登录。另一个思路是用 KWin 的平铺脚本来排布窗口，从而彻底不用虚拟桌面：

```console
$ kwriteconfig6 --file kwinrc --group Plugins --key kwinscriptEnabled true
```

## 6. 用键盘快捷键做平铺

在只有 768 像素高的屏幕上，这大概是**收益最高的单项改动**。当你只有 768 像素垂直空间时，拖拽排布是非常浪费的。

KWin 的内置平铺（Plasma 6）默认用 `Meta` 键：

| 按键 | 动作 |
| --- | --- |
| `Meta+T` | 平铺 / 取消平铺当前窗口 |
| `Meta+Shift+←` | 窗口移到左半边 |
| `Meta+Shift+→` | 窗口移到右半边 |

在*系统设置 → 桌面 → 平铺*里启用。更多布局在
[krohnkite](https://invent.kde.org/plasma/kwin)，它加了分栏、网格和可调整大小的分割。

## 7. 再压一点窗口装饰

如果你用 Breeze 或类似主题，标题栏内边距是主题的一部分，不是设置项。一个小的用户级主题覆盖比上面那些选项更有效。

## 8. 字体选择比字号更重要

在 768 像素的高度上，**x 高度**大的字体能在同样标称字号下塞下更多可读的文字。几个好选择：

- **Noto Sans** —— x 高度高，非常易读，多数系统自带
- **Inter** —— 专门为屏幕 UI 设计的
- **Cantarell** —— GNOME 默认字体，小字号下 hinting 不错

```console
$ fc-list | grep -i inter
```

这个尺寸下，避免用衬线或等宽字体做 UI 字体 —— 它们浪费垂直空间，而且变小时更难读。

## 9. 压缩面板高度

Plasma 的面板支持固定高度设置。低于约 28px 面板控件就开始挤了，所以这里有个下限。

## 10. 说实话，考虑外接显示器

如果你经常接外设，一台 1080p 外接显示器在 100% 下能给你 2560×1080 的工作区，代价只是一根线。笔记本屏保持 0.75，外接屏保持 1.0。

```console
$ screensmith scale set eDP-1 0.75
$ screensmith scale set HDMI-1 1
```

## 试过但没用的方法

如实记录，因为这些方法总会被人提起来：

- **降低分辨率。** 1366×768 → 1024×768 会让一切都变模糊，而且**减少**你的工作区。现代面板会插值，你既得不到清晰度也得不到空间。
- **在显示设置里把面板"UI 缩放"往上调过 100%** —— 和第 1 条是同一个功能，100% 以下同样没用。
- **只留任务栏不要面板。** 能凑合，但你会失去窗口切换。KRunner（`Alt+Space`）能覆盖大部分需求。

## 一份合理的最终配置

针对 1366×768 面板：

```console
$ screensmith preset compact          # 缩放 0.75 + PassThrough
$ screensmith font-dpi set 90
$ kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key titleBarHeight "24"
$ kwriteconfig6 --file kwinrc --group Desktops --key Number 1
$ kwriteconfig6 --file kwinrc --group Desktops --key Rows 1
```

注销、重新登录、启用平铺，绑定 `Meta+T`。

## 检查一下

```console
$ screensmith doctor
$ screensmith status
```

如果 `doctor` 是干净的，而且你绑好了平铺，那关于一块 1366×768 面板，软件能做的基本都做完了。

下一篇：[修复模糊和尺寸错误的程序](03-blurry-apps.md)。
