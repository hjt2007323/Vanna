"""Regenerate docs/evidence/manifest.json (path, size, SHA256) for the checkout.

The manifest covers every file in the working tree except VCS data, the local
virtualenv and Python caches, so a reviewer can hash any delivered artifact
and compare.  Run it after changing files:

    python tools/make_manifest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()
    except OSError:  # pragma: no cover - git always present in this project
        return ""


def collect(skip_path: Path | None = None) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(PROJECT_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if skip_path is not None and path.resolve() == skip_path.resolve():
            continue  # a manifest cannot contain its own hash
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix in SKIP_SUFFIXES:
            continue
        entries.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "docs" / "evidence" / "manifest.json"),
        help="output path (default: docs/evidence/manifest.json)",
    )
    args = parser.parse_args(argv)

    entries = collect(Path(args.out))
    manifest_relative = Path(args.out).resolve().relative_to(PROJECT_ROOT).as_posix()
    status = [
        line
        for line in git("status", "--porcelain").splitlines()
        if manifest_relative not in line
    ]
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "project_root": str(PROJECT_ROOT),
        "git_head": git("rev-parse", "HEAD"),
        "git_head_short": git("rev-parse", "--short", "HEAD"),
        "git_status_excluding_manifest": status,
        "entry_count": len(entries),
        "total_bytes": sum(int(entry["bytes"]) for entry in entries),
        "entries": entries,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out} ({payload['entry_count']} entries, {payload['total_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
