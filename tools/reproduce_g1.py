"""One-command reproducer for the G1 Vanna SQLite maintenance work.

Runs the same probe inputs against

* the frozen upstream baseline (``baseline/upstream_sql_runner.py``), and
* the modified implementation (``vanna.integrations.sqlite.sql_runner``),

then writes machine readable JSON/CSV plus a human readable summary.

Usage (from the project root, inside the project venv):

    python tools/reproduce_g1.py
    python tools/reproduce_g1.py --side baseline
    python tools/reproduce_g1.py --out docs/evidence/reproduce-v1

Exit code is 0 when every ``after`` expectation holds (and when the baseline
run is requested on its own, because the baseline is expected to fail).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import platform
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.baseline_loader import (  # noqa: E402  (path bootstrap above)
    BASELINE_PATH,
    BASELINE_SHA256,
    load_baseline_runner,
    sha256_file,
)
from tools.probe_cases import (  # noqa: E402  (path bootstrap above)
    CASES,
    Case,
    evaluate,
    run_case,
)

CANDIDATE_MODULE = "vanna.integrations.sqlite.sql_runner"


def load_candidate_runner() -> tuple[Any, str]:
    """Import the working-tree SqliteRunner and return (class, module file)."""

    module = importlib.import_module(CANDIDATE_MODULE)
    runner_file = Path(module.__file__).resolve()
    return module.SqliteRunner, str(runner_file)


def _describe(record: dict[str, Any]) -> str:
    if record["unsupported"]:
        return f"unsupported: {record['error_type']}"
    if record["status"] == "error":
        return f"error: {record['error_type']}: {record['error_message']}"
    if record["status"] == "ok":
        if record["columns"] == ["rows_affected"]:
            return (
                f"rows_affected={record['values'][0][0] if record['values'] else None}"
            )
        return f"{record['rows']} rows {record['columns']}"
    return str(record["status"])


def run_side(
    runner_factory: Any, side: str, work_root: Path
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    for case in CASES:
        case_dir = work_root / side / case.case_id
        record = run_case(runner_factory, case, case_dir)
        record["side"] = side
        record.update(evaluate(case, record))
        records.append(record)
    counts = {
        "cases": len(records),
        "meets_expectation": sum(1 for r in records if r["meets_expectation"]),
        "rows_ok": sum(1 for r in records if r["status"] == "ok"),
        "errors": sum(1 for r in records if r["status"] == "error"),
        "unsupported": sum(1 for r in records if r["unsupported"]),
    }
    return records, counts


def _seed_case_lookup() -> dict[str, Case]:
    return {case.case_id: case for case in CASES}


def write_outputs(
    out_dir: Path,
    baseline_records: list[dict[str, Any]] | None,
    after_records: list[dict[str, Any]] | None,
    baseline_counts: dict[str, int] | None,
    after_counts: dict[str, int] | None,
    environment: dict[str, Any],
    cleanup: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = _seed_case_lookup()

    if baseline_records is not None:
        (out_dir / "baseline.json").write_text(
            json.dumps(baseline_records, ensure_ascii=False, indent=2),
            encoding="utf-8", newline="\n",
        )
    if after_records is not None:
        (out_dir / "after.json").write_text(
            json.dumps(after_records, ensure_ascii=False, indent=2),
            encoding="utf-8", newline="\n",
        )
    (out_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    (out_dir / "cleanup.json").write_text(
        json.dumps(cleanup, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    if (baseline_records is None) != (after_records is None):
        single_side, single_records, single_counts = (
            ("baseline", baseline_records, baseline_counts)
            if baseline_records is not None
            else ("after", after_records, after_counts)
        )
        lines = [
            f"# G1 Vanna SQLite: {single_side} run",
            "",
            f"Generated: {environment['generated_at']}",
            "",
            f"counts: {single_counts}",
            "",
            "| case | category | result | expectation |",
            "|---|---|---|---|",
        ]
        for record in single_records:
            lines.append(
                "| {case_id} | {category} | {result} | {verdict} |".format(
                    case_id=record["case_id"],
                    category=cases[record["case_id"]].category,
                    result=_describe(record).replace("|", "\\|"),
                    verdict="PASS" if record["meets_expectation"] else "FAIL",
                )
            )
        (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    if baseline_records is not None and after_records is not None:
        by_case_after = {r["case_id"]: r for r in after_records}
        rows: list[dict[str, Any]] = []
        for record in baseline_records:
            case_id = record["case_id"]
            after = by_case_after[case_id]
            rows.append(
                {
                    "case_id": case_id,
                    "category": cases[case_id].category,
                    "sql": record["sql"],
                    "baseline_status": record["status"],
                    "baseline_result": _describe(record),
                    "baseline_meets_expectation": record["meets_expectation"],
                    "after_status": after["status"],
                    "after_result": _describe(after),
                    "after_meets_expectation": after["meets_expectation"],
                    "after_mismatches": " | ".join(after["mismatches"]),
                }
            )
        fieldnames = list(rows[0].keys())
        with (out_dir / "comparison.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        (out_dir / "comparison.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )

        lines = [
            "# G1 Vanna SQLite: baseline vs after",
            "",
            f"Generated: {environment['generated_at']}",
            "",
            "| case | category | baseline | after | expectation (baseline / after) |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            lines.append(
                "| {case_id} | {category} | {baseline_result} | {after_result} | {b} / {a} |".format(
                    case_id=row["case_id"],
                    category=row["category"],
                    baseline_result=row["baseline_result"].replace("|", "\\|"),
                    after_result=row["after_result"].replace("|", "\\|"),
                    b="PASS" if row["baseline_meets_expectation"] else "FAIL",
                    a="PASS" if row["after_meets_expectation"] else "FAIL",
                )
            )
        lines += [
            "",
            f"baseline: {baseline_counts}",
            "",
            f"after: {after_counts}",
            "",
            f"cleanup: {cleanup}",
            "",
        ]
        (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        default=None,
        help="directory for JSON/CSV evidence (default: docs/evidence/reproduce-<timestamp>)",
    )
    parser.add_argument(
        "--side",
        choices=["both", "baseline", "after"],
        default="both",
        help="which side(s) to run (default: both)",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="keep the temporary work directory (default: remove and verify removal)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="only print the final verdict"
    )
    args = parser.parse_args(argv)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out).resolve()
        if args.out
        else PROJECT_ROOT / "docs" / "evidence" / f"reproduce-{timestamp}"
    )

    work_root = Path(tempfile.mkdtemp(prefix="g1-reproduce-"))
    environment: dict[str, Any] = {
        "generated_at": timestamp,
        "python": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "platform": platform.platform(),
        "sqlite_library": sqlite3.sqlite_version,
        "project_root": str(PROJECT_ROOT),
        "baseline_file": str(BASELINE_PATH),
        "baseline_sha256": sha256_file(BASELINE_PATH),
        "candidate_module": CANDIDATE_MODULE,
        "work_root": str(work_root),
        "keep_workdir": args.keep_workdir,
    }

    baseline_records = after_records = None
    baseline_counts = after_counts = None
    exit_code = 0

    try:
        if args.side in ("both", "baseline"):
            baseline_runner = load_baseline_runner()
            environment["baseline_runner"] = (
                f"{baseline_runner.__module__}.{baseline_runner.__qualname__}"
            )
            baseline_records, baseline_counts = run_side(
                baseline_runner, "baseline", work_root
            )

        if args.side in ("both", "after"):
            candidate_runner, candidate_file = load_candidate_runner()
            environment["candidate_file"] = candidate_file
            environment["candidate_sha256"] = sha256_file(Path(candidate_file))
            environment["candidate_runner"] = (
                f"{candidate_runner.__module__}.{candidate_runner.__qualname__}"
            )
            after_records, after_counts = run_side(candidate_runner, "after", work_root)
    finally:
        file_count = sum(1 for path in work_root.rglob("*") if path.is_file())
        if not args.keep_workdir:
            shutil.rmtree(work_root, ignore_errors=True)
        cleanup = {
            "work_root": str(work_root),
            "files_created": file_count,
            "removed": not work_root.exists(),
            "kept_by_request": args.keep_workdir,
            "remaining_entries": (
                sorted(str(p.relative_to(work_root)) for p in work_root.rglob("*"))
                if work_root.exists()
                else []
            ),
        }

    write_outputs(
        out_dir,
        baseline_records,
        after_records,
        baseline_counts,
        after_counts,
        environment,
        cleanup,
    )

    if not args.quiet:
        print(f"project root : {PROJECT_ROOT}")
        print(f"candidate    : {environment.get('candidate_file', 'n/a')}")
        print(f"baseline     : {environment['baseline_sha256']}")
        print(f"evidence     : {out_dir}")
        if baseline_counts:
            print(f"baseline     : {baseline_counts}")
        if after_counts:
            print(f"after        : {after_counts}")
        print(
            f"cleanup      : removed={cleanup['removed']} files={cleanup['files_created']}"
        )
        print()
        if after_records is not None:
            for record in after_records:
                status = "PASS" if record["meets_expectation"] else "FAIL"
                print(f"[{status}] {record['case_id']:<28} {_describe(record)}")
                for mismatch in record["mismatches"]:
                    print(f"         - {mismatch}")

    if (
        after_counts is not None
        and after_counts["meets_expectation"] != after_counts["cases"]
    ):
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
