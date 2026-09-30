# 速查表

配置文件的存放位置、screensmith 背后的原始命令，以及那些不好找的设置。基于 Plasma 6.7、Wayland 写成。

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。

## 缩放状态存在哪

| 是什么 | 文件 | 键 | 生效时机 |
| --- | --- | --- | --- |
| 每屏缩放 | `~/.config/kwinoutputconfig.json` | `data[].scale` | 会话启动时 |
| 每屏缩放（实时） | 通过 D-Bus | `kscreen-doctor output.<名字>.scale.<数值>` | 立刻 |
| XWayland 倍数 | `~/.config/kwinrc` | `[Xwayland] Scale` | 立刻 |
| 舍入策略 | `~/.config/plasma-workspace/env/*.desktop` | `QT_SCALE_FACTOR_ROUNDING_POLICY` | 下次登录 |
| 字体 DPI | `~/.config/plasma-workspace/env/*.desktop` | `QT_FONT_DPI` | 下次登录 |
| 单个程序的环境变量 | `~/.config/plasma-workspace/env/*.desktop` | 任意 | 下次登录 |
| 面板可见性 | `~/.config/plasmarc` | `Plasma/ApperiancePanelDefaultVisibility` | 立刻 |
| 虚拟桌面 | `~/.config/kwinrc` | `Desktops/Number`、`Desktops/Rows` | 下次登录 |
| 标题栏高度 | `~/.config/kwinrc` | `[org.kde.kdecoration2] titleBarHeight` | `qdbus6 org.kde.KWin /KWin reconfigure` |
| 平铺已启用 | `~/.config/kwinrc` | `Plugins/kwinscriptEnabled` | `qdbus6 org.kde.KWin /KWin reconfigure` |

## screensmith 命令

```console
# 查看
screensmith status                     # 一屏概览
screensmith outputs                    # 所有显示器，物理尺寸和逻辑尺寸
screensmith doctor                     # 诊断；有 error 时退出码为 1

# 缩放
screensmith scale get [输出]
screensmith scale set 输出 数值         # 1.25 或 125%
screensmith scale set 输出 数值 --offline
screensmith scale reset [输出]

# 预设
screensmith preset compact             # 0.75
screensmith preset balanced            # 1.0
screensmith preset hi-dpi              # 2.0

# 清晰度
screensmith rounding get
screensmith rounding set PassThrough   # 也可：Round、Ceil、Floor
screensmith rounding reset

# 文字与 X11
screensmith font-dpi get
screensmith font-dpi set 96
screensmith font-dpi reset

screensmith xwayland get
screensmith xwayland set 1.25
screensmith xwayland reset

# 兜底
screensmith backup
screensmith restore 目录 [--yes]
```

每个命令都支持把 `--json` 放在子命令前面：

```console
$ screensmith --json outputs
$ screensmith --json doctor
```

## 不用 screensmith 的话，同样效果怎么搞

```console
# 实时改缩放
kscreen-doctor output.eDP-1.scale.1.25

# 列出 KWin 知道的全部信息
kscreen-doctor -o

# XWayland 缩放
kwriteconfig6 --file kwinrc --group Xwayland --key Scale 1.25

# 任意 KConfig 值
kwriteconfig6 --file <文件> --group <分组> --key <键> <值>

# 不用注销就让 KWin 重新读取配置
qdbus6 org.kde.KWin /KWin reconfigure

# 我现在在哪个会话里？
echo "$XDG_SESSION_TYPE"     # wayland 或 x11
```

## env 插件的格式

`~/.config/plasma-workspace/env/随便起个名.desktop`：

```ini
[Desktop Entry]
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough
Type=Application
X-Plasma-API=develprovenfalse
```

Plasma 会在登录时加载该目录下每一条 `env` 开头的 `Exec`。多个变量写在同一行、空格分隔：

```ini
Exec=env QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough QT_FONT_DPI=96
```

**只有这个目录有效。** `/etc/environment`、`~/.bashrc` 和 systemd 的用户环境，对 Plasma 启动的程序统统无效。

## 常用的 Qt 环境变量

| 变量 | 作用 |
| --- | --- |
| `QT_SCALE_FACTOR_ROUNDING_POLICY` | 设成 `PassThrough` 才能正确渲染分数缩放 |
| `QT_FONT_DPI` | Qt 假定的基础字号，通常是 96 |
| `QT_SCALE_FACTOR` | 只覆盖单个程序的缩放 |
| `QT_SCREEN_SCALE_FACTORS` | 按屏指定，如 `eDP-1=1.25;HDMI-1=1` |
| `QT_QPA_PLATFORM` | 强制 `wayland` 或 `xcb` |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | `0` 表示关闭自动探测 |

## 缩放对照

| 倍数 | 百分比 | 典型用途 |
| --- | --- | --- |
| 0.5 | 50% | 文字太小，通常没必要 |
| 0.75 | 75% | 小屏幕笔记本 |
| 0.875 | 87.5% | 轻微缩小 |
| 1 | 100% | 原生 |
| 1.25 | 125% | 最常见的 HiDPI 档位 |
| 1.5 | 150% | 14 寸屏跑 1080p |
| 1.75 | 175% | 13 寸屏跑 1440p |
| 2 | 200% | 15 寸屏跑 4K |

## 恢复

```console
# 动手之前先做快照
screensmith backup

# 恢复
screensmith restore ~/.config/screensmith-backups/20260930-141205

# screensmith 覆盖掉的东西的副本
ls ~/.config/screensmith-undo/

# 核选项：重置所有 screensmith 管过的设置
screensmith scale reset
screensmith rounding reset
screensmith font-dpi reset
screensmith xwayland reset
```

## 容易踩的坑

- **环境变量的改动需要注销。** 不是重启那个程序，也不是 reload KWin —— 要完整注销一次。这是绝大多数人认为某个设置"没生效"的原因。
- **分数缩放只在 Wayland 上有。** X11 下 KWin 会忽略它。用 `echo $XDG_SESSION_TYPE` 确认。
- **KWin 会在会话启动时覆盖 `kwinoutputconfig.json`。** 会话运行期间改这个文件没有意义。
- **`[Xwayland] Scale` 是整个会话一个值**，不是按屏的。X11 程序无法精确跟随各屏不同的缩放。
- **用 `kscreen-doctor` 改缩放时，`[Xwayland] Scale` 会自动跟着同步。** 用不同方式改这两处，是它们走偏的原因。
- **不要靠降低面板原生分辨率来换空间。** 你得到的是模糊，不是房间。

---

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。
