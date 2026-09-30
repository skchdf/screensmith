# screensmith

KDE Plasma 的显示与缩放手术刀 —— 包括设置界面不给你看的那部分缩放选项。

Plasma 的显示设置只有一条固定的阶梯：100%、125%、150%、175%、200%，而且**最低只到 100%**。KWin 本身没有这个限制。如果你想要 75%（比如 1366×768 的笔记本屏），或者 137.5%，界面做不到 —— 你只能去改 `kwinoutputconfig.json`，然后祈祷自己没敲错。

screensmith 是个小命令行工具，把这件事做对，并且会在结果看起来不对的时候告诉你。

> **本项目全程由 OpenCode 自动生成，无人工干预。** 代码、文档、测试均由 AI 代理独立产出，未经人工撰写或审阅。请据此谨慎评估内容质量。

```console
$ screensmith scale set LVDS-1 0.75
LVDS-1: 1 (100%) -> 0.75 (75%)
  workspace is now 1821x1024 logical pixels
```

## 为什么需要它

Plasma 的缩放有三件事让人困惑，而且**每一件都是设置界面要么藏起来、要么搞错的**：

1. **没有低于 100% 的选项。** 小屏幕笔记本经常正好需要这个。KWin 接受 0.25 到 10 之间的任何值。
2. **分数缩放莫名其妙地糊。** Qt 的默认 `QT_SCALE_FACTOR_ROUNDING_POLICY=Round` 会把 1.25 吸附到整数设备像素，结果就是控件尺寸不对、文字发虚。解法是 `PassThrough`，但它藏在一个环境变量里，你必须事先就知道要在登录**之前**设好它。
3. **X11 程序会掉队。** KWin 会自动把显示缩放应用到 Wayland 客户端，但 XWayland 客户端走的是 `kwinrc [Xwayland] Scale`，一个默认值为 1 的独立开关。

`screensmith doctor` 会把这三件事全查一遍，并告诉你是哪一件在折磨你。

## 安装

```console
$ git clone https://github.com/skchdf/screensmith
$ cd screensmith
$ python -m pip install --user .
```

无运行时依赖。Python 3.10 以上。你需要 `kscreen-doctor`，它由 Plasma 本来就装的 `kscreen` 软件包提供。

Shell 补全在 `completions/` 目录，把对应你 shell 的那个文件拷到 `/etc/bash_completion.d/` 或你的 `$fpath`。

## 使用

全部是子命令，每个命令都支持放在子命令前面的 `--json`，方便写脚本。

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

### 调整某块屏幕的缩放

倍数和百分比都认，看你手指头记得哪种：

```console
$ screensmith scale set LVDS-1 1.25      # 倍数
$ screensmith scale set LVDS-1 125%      # 百分比，结果相同
$ screensmith scale set LVDS-1 0.75      # 低于 100%：1366x768 -> 1821x1024
$ screensmith scale reset                # 所有启用的输出重置回 1
```

想给当前没插着的屏幕设置（比如无头机器，或者 SSH 上去时），直接写配置文件：

```console
$ screensmith scale set HDMI-1 2 --offline
```

KWin 会在会话启动时读这个文件。会话运行期间做的改动会被覆盖，所以这个命令是用来给机器做预配置的，不是用来调整眼前这台。

### 让分数缩放变清晰

```console
$ screensmith rounding set PassThrough
```

需要注销后重新登录才生效。在那之前 `screensmith doctor` 会一直提醒你。

### 文字与 X11 程序

```console
$ screensmith font-dpi set 120      # 文字变大，控件尺寸不变
$ screensmith xwayland set 1.25      # 让 X11 程序跟上缩放
$ screensmith xwayland reset         # 交回给 KWin 按显示缩放推导
```

### 预设

懒得想就用预设：

```console
$ screensmith preset compact     # 全部 0.75，且清晰
$ screensmith preset balanced    # 1.0，且清晰
$ screensmith preset hi-dpi      # 2.0，且清晰
```

### 撤销

```console
$ screensmith backup              # 快照存到 ~/.config/screensmith-backups/
$ screensmith restore ~/.config/screensmith-backups/20260930-141205
```

每次写入前也都会快照到 `~/.config/screensmith-undo/`，所以最坏情况不过是多了一个目录让你手动拷回来。

## 诊断

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

只要有 error，退出码就是 1，所以可以直接用在健康检查脚本里。

## 原理

Plasma 的缩放状态分散在四个地方，而且没有任何一个地方有文档：

| 是什么 | 在哪里 | 生效时机 |
| --- | --- | --- |
| 每块屏幕的缩放 | `kscreen-doctor`，持久化到 `~/.config/kwinoutputconfig.json` | 立刻 |
| XWayland 倍数 | `~/.config/kwinrc`，`[Xwayland] Scale` | 立刻 |
| 舍入策略 | `~/.config/plasma-workspace/env/*.desktop` | 下次登录 |
| 字体 DPI | 同上 | 下次登录 |

环境变量要放在 `plasma-workspace/env/`，而不是 `/etc/environment` 或你的 shell 配置里，因为**是 Plasma 在启动你的程序**，而它只加载那个目录。screensmith 会写一个名叫 `screensmith-qt-scaling.desktop` 的 env 插件，所以你自建的插件永远不会被碰到。

screensmith 只写它自己那几项 key。你的 `kwinrc` 是逐行原地修改的：注释、顺序、以及无关的分组都会原样保留。

有一件 KWin 会替你做、但并不显然因而值得知道的事：通过 `kscreen-doctor`（或设置界面）改显示缩放时，`[Xwayland] Scale` 会**自动保持同步**。这两个值只在你用不同方式改它们、或者从旧备份里恢复 `kwinrc` 时才会走偏。`doctor` 会检查这一点。

## 安全性

- 所有配置写入都是原子的（临时文件 → fsync → rename）。KWin 一直在读这些文件，写坏一半的 `kwinrc` 可能导致会话无法配置。
- 重写文件时保留原有权限位。
- `--offline` 写入前会先备份。
- `screensmith restore` 覆盖前会先询问，并把被覆盖的内容另存一份。
- 非法输入会被拒绝并给出解释，绝不会部分生效。

## 仓库里还有

`docs/tutorials/` 下的教程，基于真实的 Plasma 6.7 会话写成：

- [低于 100% 的缩放，以及 75% 为什么合法](docs/tutorials/01-sub-100-scaling.md)
- [小屏幕自救指南](docs/tutorials/02-small-screen.md)
- [修复模糊和尺寸错误的程序](docs/tutorials/03-blurry-apps.md)

还有一份[速查表](docs/CHEATSHEET.md)，列出配置路径和命令。想参与开发看 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 开发

```console
$ python -m unittest discover -s tests -t tests
```

178 个测试，零依赖。它们是 hermetic 的：使用临时配置目录、`kscreen-doctor` 输出的固定样本，完全不读取你真实的会话状态。在本机、真实的 Plasma 桌面上、以及把 `kscreen-doctor` 从 `$PATH` 移除的干净 CI runner 上，结果完全一致。

## 状态

Beta，并且对哪些验证过、哪些没验证说得很具体。

**在本机验证过**（Plasma 6.7.5、Wayland、Arch Linux、kscreen 6.7.5）：

- 在活动输出上执行 scale set / get / reset，以及数值确实写进了 `kwinoutputconfig.json`
- KWin 让 `kwinrc` 的 `[Xwayland] Scale` 随显示缩放同步更新
- `status`、`outputs`、`doctor` 对着真实会话运行
- `backup` 和 `restore` 对真实配置文件的往返

**仅通过测试验证**（即对着样本数据和 mock 过的 `kscreen-doctor` 输出，而不是真实会话）：多显示器布局、`--offline`、`preset`、`restore` 的撤销快照，以及全部 `--json` 模式。

**未验证**：Plasma 5、非 KDE 的 Wayland 合成器、X11 会话（那里根本不存在分数缩放），以及 6.7.x 以外的 Plasma 版本。欢迎带着这些环境下的真实输出来提交 PR。

另外它是仅限 Linux 的，并且假定 `kscreen-doctor` 在 `PATH` 上。配置文件那部分逻辑换个平台也能跑，但没有任何测试覆盖。

## 许可

MIT。

---

> **本项目全程由 OpenCode 自动生成，无人工干预。** 代码、文档、测试均由 AI 代理独立产出，未经人工撰写或审阅。
