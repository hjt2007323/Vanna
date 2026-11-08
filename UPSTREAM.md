# Upstream provenance — G1 Vanna SQLite maintenance

This directory is a maintenance checkout of Vanna, not a fork with upstream
history. It is not the whole Vanna project and no upstream merge is claimed
(the upstream repository is archived).

| Item | Value |
|---|---|
| Upstream repository | https://github.com/vanna-ai/vanna |
| Fixed commit | `365d0617c1a4567ffee1b19b40c27feb4206bfcf` |
| Package version at that commit | `vanna 2.0.2` (`pyproject.toml`) |
| License | MIT — `LICENSE` kept byte-identical (`Copyright (c) 2024 Vanna.AI`) |
| Upstream state | `archived = true`; no pull request was opened and none is claimed |
| Retrieval method | commit tarball from codeload (see below) |
| Archive URL | `https://codeload.github.com/vanna-ai/vanna/tar.gz/365d0617c1a4567ffee1b19b40c27feb4206bfcf` |
| Archive SHA256 | `45ce2b5df2d1c448db2ebadfebf207797cec1d6fc5fbc50a4e7ef773bc1f4716` |
| Archive size | 3 823 520 bytes |
| Unpacked with | `tar.exe -xzf` on Windows 11 (26200), 2026-11-07 |
| Unpacked top level | `vanna-365d0617c1a4567ffee1b19b40c27feb4206bfcf/` |
| Changed source file | `src/vanna/integrations/sqlite/sql_runner.py` |
| Changed source SHA256 (upstream) | `830dd109940121c871af4f9a6c16950f36e70a92745a224bca4152e448681ca6` (2 118 bytes) |
| Changed source SHA256 (this checkout) | see `docs/evidence/manifest.json` |
| Vendored baseline copy | `baseline/upstream_sql_runner.py` — byte-identical to upstream, hash re-checked at run time by `tools/baseline_loader.py` |

## Why codeload instead of `git clone`

On this machine `git ls-remote https://github.com/vanna-ai/vanna.git` and
`git clone` both fail with `Recv failure: Connection was reset`, while
`codeload.github.com`, `raw.githubusercontent.com` and `pypi.org` are
reachable. The commit archive therefore came from codeload.

The archive has **no `.git` directory**. The local Git history in this
checkout was created from the archive:

* the first commit is the unpacked upstream tree (byte-identical files);
* later commits are this maintenance work.

Consequence, stated explicitly: **local commit hashes are not upstream
hashes**, and this checkout cannot be pushed to the upstream repository as a
fast-forward of `365d0617`.

## Verify the baseline yourself

```powershell
Get-FileHash baseline\upstream_sql_runner.py -Algorithm SHA256
# 830DD109940121C871AF4F9A6C16950F36E70A92745A224BCA4152E448681CA6

python tools\reproduce_g1.py --side baseline
```

`tools/reproduce_g1.py` refuses to run if
`baseline/upstream_sql_runner.py` does not match `830dd109…`, so a silently
"upgraded" or edited baseline cannot be used as evidence.

## What was not changed

Only these paths differ from the unpacked upstream tree:

| Path | Kind |
|---|---|
| `src/vanna/integrations/sqlite/sql_runner.py` | source change (the subject of G1) |
| `tests/test_sqlite_runner_maintenance.py` | new regression tests |
| `tools/` | new reproducer / demo / not part of the package |
| `baseline/` | vendored upstream file for before/after comparison |
| `docs/` | delivery document and evidence |
| `UPSTREAM.md`, `requirements-lock.txt`, `patches/` | provenance and change history |
| `README.md`, `.gitignore` | maintenance note at the top; local venv/cache ignores |
| `.gitattributes` | pins `text=auto eol=lf` so hashed artifacts survive a clone |

No other database runner, no Rust/JS/frontend file and no packaging metadata
was modified.
