# 贡献指南

screensmith 是个小工具，依赖足迹被刻意控制得很小。大部分改动应该属于下面三类之一。

> **本项目全程由 OpenCode 自动生成，无人工干预。** 未经人工撰写或审阅。

## 环境准备

```console
$ git clone https://github.com/skchdf/screensmith
$ cd screensmith
$ python -m venv --system-site-packages .venv
$ .venv/bin/python -m pip install -e .
```

无运行时依赖，并且请保持这样。一个需要虚拟环境的桌面工具，就是没人愿意用的桌面工具。如果某个改动看起来需要加依赖，那它多半是应该改成 shell 调用 `kscreen-doctor`。

## 测试

```console
$ python -m unittest discover -s tests -t tests
```

这条路径是受支持的，不需要装任何东西。如果你手头有 `pytest` 也能用，因为测试都是普通的 `unittest.TestCase` 类。

**测试套件绝不允许依赖它所运行的那台机器。** 这不是风格偏好：测试应该在你的笔记本上、在运行 Plasma 的会话里、以及在没有任何 Plasma 的 CI runner 上**结果完全一致**。为此必须中和掉三样东西，而且 `CliTestCase.run_cli` 和 `test_doctor.py` 里的 `_run` 三样都做了：

- `Session.probe`，它会读取真实的 `$XDG_SESSION_TYPE` 和 Plasma 版本
- `have("kscreen-doctor")`，在 Plasma 桌面上是 True，在 CI 上是 False
- `query_outputs`，它会调用正在运行的 KWin

样本数据（抓下来的 `kscreen-doctor` 输出、`kwinrc`、`kwinoutputconfig.json`）都在 `tests/support.py`。配置目录用临时目录。

如果你写了个依赖上面那些东西存在于环境中的测试，它会在本地通过、在 CI 挂掉。`status` 和 `doctor` 已经有针对"kscreen-doctor 不存在"这条路径的显式测试，动这两个命令时记得保住这份覆盖。

可以直接这样检查有没有意外的环境依赖：

```console
$ PATH=/usr/bin:/bin python -m unittest discover -s tests -t tests
```

目前 178 个测试。加了行为不加测试，review 的时候一定会被问。

## 代码风格

```console
$ pip install ruff
$ ruff check src tests
$ ruff format --check src tests
```

行长 110。公开函数要有类型标注，每个模块顶部写 `from __future__ import annotations`。

文档字符串解释**为什么**，不是**是什么**。如果一行代码需要注释来说明它在干什么，那说明代码写错了。

## 动手改之前值得知道的事

**配置写入必须保持原子性。** `fsutil.atomic_write` 的流程是写临时文件、fsync、rename、再 fsync 目录。KWin 和 plasmashell 一直在读这些文件，写坏一半的 `kwinrc` 可能导致会话起不来。不要把它换成普通的 `write_text`。

**不要用 `configparser` 解析 KDE 的 INI。** 它默认大小写不敏感，而且会搞坏 KWin 用的 `[Tiling][uuid]` 这种分组名。`ini.py` 是原地改文本，这样注释和顺序才能活下来。有个测试断言所有没碰过的行都是逐字节一致的；别让它挂。

**环境变量的改动只在登录时生效。** 任何碰到 `plasma-workspace/env` 的操作都必须告诉用户去注销再登录。不要让命令暗示它已经生效了。

**保留文件权限。** `fsutil.mode_of` 存在的原因是用户可能特意把自己的配置改成组可写。

**只拥有你自己的 key，不要拥有整个文件。** screensmith 只写一个 env 插件，`screensmith-qt-scaling.desktop`。绝不要碰用户自己建的插件，也绝不要写 `~/.config/environment`。

**文档要诚实。** 教程里引用的是真实命令输出。你改了某条消息，就把 README 和教程一起更新。如果 README 里有什么结论没在真实会话上验证过，那就在"状态"一节里写明，而不是让人以为验证过。

## 新增一个命令

1. 把逻辑放进对应模块（`scale.py`、`qt.py`、`envfile.py`、`output.py`）里，尽量写成纯函数，这样不用会话就能测。
2. 在 `cli.py` 里加 argparse 接线和一层很薄的 `cmd_*` 处理函数。
3. 如果输出值得写脚本，给这个命令加一个 `--json` 模式。
4. 处理函数放 `tests/test_cli.py` 的测试，逻辑放对应模块自己的测试文件。
5. 更新 README 的命令列表，以及 `docs/CHEATSHEET.md`。
6. 在 `completions/screensmith.bash` 里加对应的补全分支。

## 提交信息和 PR

解释思路，而不是复述 diff。如果发现了什么出乎意料的事情 —— 某个 KWin 行为和预期不符、某个配置文件和文档说的不一样 —— 就算你没改它，也请在 PR 描述里写出来。那通常是一次贡献里最有价值的部分。

## 已验证的配置

README 里列出了在真实硬件上跑过什么、哪些只是对着样本数据测过。如果你能在这个清单之外的环境里跑一下 screensmith，请开 PR 或 issue 把输出贴上来 —— 哪怕只是一句"Plasma 6.1 的 X11 会话下能跑"也有用。
