# Contributing

Screensmith is a small tool with a deliberately small dependency footprint. Most
contributions should be one of the three things below.

## Setup

```console
$ git clone https://github.com/skchdf/screensmith
$ cd screensmith
$ python -m venv --system-site-packages .venv
$ .venv/bin/python -m pip install -e .
```

No runtime dependencies, and please keep it that way. A desktop utility that
needs a virtualenv is a desktop utility nobody runs. If a change seems to want
a dependency, it probably wants a shell-out to `kscreen-doctor` instead.

## Tests

```console
$ python -m unittest discover -s tests -t tests
```

That path is the supported one and needs nothing installed. `pytest` works too
if you have it, since the tests are plain `unittest.TestCase` classes.

**The suite must not touch the machine it runs on.** This is not a stylistic
preference: the tests are expected to pass identically on your laptop, on a
Plasma session, and on a bare CI runner. Three things have to be neutralised
for that, and all three are done in `CliTestCase.run_cli` and
`_run` in `test_doctor.py`:

- `Session.probe`, which reads the real `$XDG_SESSION_TYPE` and Plasma version
- `have("kscreen-doctor")`, which is true on a Plasma desktop and false on CI
- `query_outputs`, which shells out to the running KWin

Fixture data (captured `kscreen-doctor` output, `kwinrc`,
`kwinoutputconfig.json`) lives in `tests/support.py`. Config homes are
temporary directories.

If you add a test that depends on any of the above being present in the
environment, it will pass locally and fail in CI. `status` and `doctor` have
explicit tests for the "kscreen-doctor is missing" path; keep that coverage when
touching either.

You can check for accidental environment dependencies by running the suite with
`kscreen-doctor` off `$PATH`:

```console
$ PATH=/usr/bin:/bin python -m unittest discover -s tests -t tests
```

178 tests currently. Adding behaviour without adding a test will be asked about
in review.

## Style

```console
$ pip install ruff
$ ruff check src tests
$ ruff format --check src tests
```

Line length 110. Type hints on public functions, `from __future__ import
annotations` at the top of every module.

Docstrings explain *why*, not *what*. If a line of code needs a comment to say
what it does, the code is written wrong.

## Things worth knowing before you change them

**Config writes must stay atomic.** `fsutil.atomic_write` writes a temp file,
fsyncs, renames, then fsyncs the directory. KWin and plasmashell read these
files continuously; a half-written `kwinrc` can leave a session that will not
start. Do not replace it with a plain `write_text`.

**Do not parse KDE INI with `configparser`.** It is case-insensitive by
default and mangles the `[Tiling][uuid]` section names KWin uses. `ini.py` edits
text in place so comments and ordering survive. There is a test asserting that
every untouched line is byte-identical; keep it passing.

**Env-var settings only take effect at login.** Anything touching
`plasma-workspace/env` must tell the user to log out and back in. Do not let a
command imply it has already taken effect.

**Preserve file permissions.** `fsutil.mode_of` exists because a user may have
made their config group-writable deliberately.

**Own your keys, do not own the file.** Screensmith writes exactly one env
plugin, `screensmith-qt-scaling.desktop`. Never touch a plugin the user
created, and never write to `~/.config/environment`.

**Stay honest in the docs.** The tutorials quote real command output. If you
change a message, update the README and the tutorials. If a claim in the README
has not been verified on a real session, say so in the Status section rather
than implying it was.

## Adding a command

1. Put the logic in the relevant module (`scale.py`, `qt.py`, `envfile.py`,
   `output.py`) as pure functions where possible, so it is testable without a
   session.
2. Add the argparse wiring and a thin `cmd_*` handler in `cli.py`.
3. Give the command a `--json` mode if its output is worth scripting.
4. Tests in `tests/test_cli.py` for the handler, in the module's own test file
   for the logic.
5. README command list, and `docs/CHEATSHEET.md`.
6. Add a bash completion branch in `completions/screensmith.bash`.

## Commit messages and PRs

Explain the reasoning, not the diff. If you found something surprising — a
KWin behaviour you did not expect, a config file that does not match the
documentation — say so in the PR description even if you did not change it.
That is usually the most valuable part of a contribution.

## Verified configurations

The README lists what has been exercised on real hardware and what has only
been tested against fixtures. If you can run screensmith on something not in
that list, please open a PR or an issue with the output — even a "works on
Plasma 6.1, X11 session" note is useful.
