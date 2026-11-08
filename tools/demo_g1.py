"""Guided demo for the G1 Vanna SQLite maintenance work.

Two modes:

    python tools/demo_g1.py
        Runs a scripted tour on a synthetic temporary database: normal SELECT,
        leading comment, CTE, VALUES, empty result columns, default write,
        RETURNING, read-only refusals, special-character path and cleanup.
        The frozen upstream runner is called on the same input for every step,
        so the "before / after" difference is visible in one command.

    python tools/demo_g1.py --sql "SELECT * FROM products" --read-only
        Runs one statement through the real ``SqliteRunner`` and prints the
        rows, the columns, or the refusal reason.  Exit code is 1 on error.

Everything runs against a throw-away database under the system temp folder;
the directory is removed at the end and the removal is reported.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.baseline_loader import load_baseline_runner, sha256_file  # noqa: E402
from tools.probe_cases import (  # noqa: E402
    Case,
    create_seed_database,
    evaluate,
    run_case,
)

import pandas as pd  # noqa: E402

from vanna.capabilities.sql_runner import RunSqlToolArgs  # noqa: E402
from vanna.integrations.sqlite import SqliteRunner  # noqa: E402


DEMO_STEPS: tuple[Case, ...] = (
    Case(
        "demo_1_normal_select",
        "normal read (control)",
        "SELECT id, name, price FROM products ORDER BY id",
        note="ordinary SELECT keeps working",
        expected_rows=2,
        expected_columns=("id", "name", "price"),
    ),
    Case(
        "demo_2_leading_comment",
        "query compatibility",
        "-- dashboard query\nSELECT id, name FROM products ORDER BY id",
        note="a leading comment must not hide the result set",
        expected_rows=2,
        expected_columns=("id", "name"),
    ),
    Case(
        "demo_3_with_select",
        "query compatibility",
        "WITH cheap AS (SELECT id, name FROM products WHERE price < 1) "
        "SELECT id, name FROM cheap ORDER BY id",
        note="CTE followed by SELECT",
        expected_rows=1,
        expected_columns=("id", "name"),
    ),
    Case(
        "demo_4_values",
        "query compatibility",
        "VALUES (1, 'alpha'), (2, 'beta')",
        note="VALUES is a result-set statement",
        expected_rows=2,
        expected_columns=("column1", "column2"),
    ),
    Case(
        "demo_5_empty_result",
        "empty result",
        "SELECT id, name FROM products WHERE id < 0",
        note="0 rows must keep the requested columns",
        expected_rows=0,
        expected_columns=("id", "name"),
    ),
    Case(
        "demo_6_default_insert",
        "default write",
        "INSERT INTO products (name, price) VALUES ('cherry', 2.25)",
        note="default mode still writes and commits",
        expected_kind="rows_affected",
        expected_rows=1,
        verify_sql="SELECT COUNT(*) FROM products",
        expected_verify=3,
    ),
    Case(
        "demo_7_insert_returning",
        "RETURNING",
        "INSERT INTO products (name, price) VALUES ('date', 3.0) RETURNING id, name",
        note="RETURNING rows are returned and committed",
        expected_rows=1,
        expected_columns=("id", "name"),
        verify_sql="SELECT COUNT(*) FROM products WHERE name = 'date'",
        expected_verify=1,
    ),
    Case(
        "demo_8_readonly_insert",
        "read-only mode",
        "INSERT INTO products (name) VALUES ('hack')",
        note="read_only=True refuses writes through the database engine",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "demo_9_readonly_cte_delete",
        "read-only mode",
        "WITH doomed AS (SELECT id FROM products) DELETE FROM products "
        "WHERE id IN (SELECT id FROM doomed)",
        note="a SELECT keyword check would miss this write",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "demo_10_readonly_attach",
        "read-only mode",
        "ATTACH DATABASE '{workdir}/attached-escape.db' AS side_db",
        note="ATTACH cannot be used to write around the read-only mode",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "demo_11_readonly_pragma",
        "read-only mode",
        "PRAGMA user_version = 7",
        note="write-capable PRAGMAs are refused",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
        verify_sql="PRAGMA user_version",
        expected_verify=0,
    ),
    Case(
        "demo_12_readonly_missing_db",
        "read-only mode",
        "SELECT 1",
        note="a missing database is reported and never created",
        create_db=False,
        read_only=True,
        expected_kind="error",
        expect_no_db_created=True,
    ),
    Case(
        "demo_13_space_hash_path",
        "path handling",
        "SELECT id, name FROM products ORDER BY id",
        note="space, '#' and unicode in the path are URI-encoded",
        path_profile="space_hash",
        expected_rows=2,
        expected_columns=("id", "name"),
    ),
    Case(
        "demo_14_lifecycle",
        "lifecycle",
        "SELECT * FROM table_that_does_not_exist",
        note="after an error the connection is closed and the file can be deleted",
        expected_kind="error",
        expect_delete_ok=True,
    ),
)


def _format_frame(frame: pd.DataFrame, limit: int = 8) -> str:
    if frame.empty:
        return f"0 rows, columns={list(frame.columns)}"
    body = frame.head(limit).to_string(index=False)
    suffix = (
        "" if frame.shape[0] <= limit else f"\n... ({frame.shape[0] - limit} more rows)"
    )
    return f"{frame.shape[0]} rows, columns={list(frame.columns)}\n{body}{suffix}"


def _describe(record: dict[str, Any]) -> str:
    if record["unsupported"]:
        return (
            f"unsupported: {record['error_type']} (upstream has no read_only parameter)"
        )
    if record["status"] == "error":
        return f"{record['error_type']}: {record['error_message']}"
    if record["columns"] == ["rows_affected"]:
        return f"write accepted, rows_affected={record['values'][0][0]}"
    return f"{record['rows']} rows, columns={record['columns']}"


def _verdict(step: Case, after: dict[str, Any], upstream: dict[str, Any] | None) -> str:
    if not after["meets_expectation"]:
        return "UNEXPECTED: " + " | ".join(after["mismatches"])
    if upstream is None:
        return "OK"
    if upstream["unsupported"]:
        return "NEW: upstream cannot do this at all"
    if upstream["meets_expectation"]:
        return "same as upstream"
    return "FIXED: upstream behaviour was wrong for this input"


def run_single_sql(sql: str, read_only: bool, keep: bool) -> int:
    work = Path(tempfile.mkdtemp(prefix="g1-demo-"))
    db = work / "shop.db"
    try:
        create_seed_database(db)
        before = sha256_file(db)
        print(f"database : {db}")
        print(f"read_only: {read_only}")
        print(f"sql      : {sql}")
        print()
        runner = SqliteRunner(str(db), read_only=read_only)
        try:
            import asyncio

            frame = asyncio.run(runner.run_sql(RunSqlToolArgs(sql=sql), None))
        except Exception as exc:  # noqa: BLE001 - the demo must show the real error
            print(f"error    : {type(exc).__name__}: {exc}")
            if read_only:
                print("note     : read-only mode refuses writes at the SQLite level")
            return 1
        print(_format_frame(frame))
        if read_only:
            print(f"database unchanged: {sha256_file(db) == before}")
        if frame.empty and frame.shape[1] and list(frame.columns) != ["rows_affected"]:
            print(
                "note     : a 0-row DataFrame keeps its columns; it does not mean 'no columns'"
            )
        return 0
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def run_guided(use_upstream: bool, keep: bool) -> int:
    work = Path(tempfile.mkdtemp(prefix="g1-demo-"))
    failures = 0
    fixed = 0
    try:
        print("G1 Vanna SQLite maintenance demo")
        print("=" * 72)
        print(f"project : {PROJECT_ROOT}")
        print(f"python  : {sys.version.split()[0]}  sqlite: {sqlite3.sqlite_version}")
        print(f"workdir : {work}  (synthetic fixture, removed at the end)")
        print()

        after_runner = SqliteRunner
        upstream_runner = load_baseline_runner() if use_upstream else None

        for index, step in enumerate(DEMO_STEPS, start=1):
            after_dir = work / "after" / step.case_id
            upstream_dir = work / "upstream" / step.case_id
            rendered_sql = step.sql.replace("{workdir}", after_dir.as_posix())
            after = run_case(after_runner, step, after_dir)
            after.update(evaluate(step, after))
            upstream = (
                run_case(upstream_runner, step, upstream_dir)
                if upstream_runner is not None
                else None
            )
            if upstream is not None:
                upstream.update(evaluate(step, upstream))
            verdict = _verdict(step, after, upstream)
            if not after["meets_expectation"]:
                failures += 1
            elif upstream is not None and not upstream["meets_expectation"]:
                fixed += 1

            print(f"[{index}/{len(DEMO_STEPS)}] {step.category}: {step.note}")
            print(f"  SQL      : {rendered_sql.strip()}")
            if after["status"] == "ok" and after["columns"] != ["rows_affected"]:
                print(
                    f"  result   : {_format_frame(pd.DataFrame(after['values'], columns=after['columns']))}"
                )
            else:
                print(f"  result   : {_describe(after)}")
            if upstream is not None:
                print(f"  upstream : {_describe(upstream)}")
            if after["read_only"]:
                print(
                    "  file     : unchanged={unchanged} new_files={new}".format(
                        unchanged=not after["db_changed"],
                        new=after["new_files"] or "none",
                    )
                )
            if after["verification"]:
                check = after["verification"]
                print(
                    f"  reconnect: {check['sql']} -> {check['value']!r} (expected {check['expected']!r})"
                )
            if after["delete_after_error_ok"] is not None:
                print(
                    f"  cleanup  : database file deletable after the error: {after['delete_after_error_ok']}"
                )
            print(f"  verdict  : {verdict}")
            print()

        print("-" * 72)
        print(
            f"steps: {len(DEMO_STEPS)}  failures: {failures}  fixed vs upstream: {fixed}"
        )
        return 1 if failures else 0
    finally:
        files = (
            sum(1 for path in work.rglob("*") if path.is_file()) if work.exists() else 0
        )
        if not keep:
            shutil.rmtree(work, ignore_errors=True)
        print(f"cleanup: files created={files} removed={not work.exists()}")
        if keep:
            print(f"cleanup: work directory kept at {work}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sql", default=None, help="run a single SQL statement and exit"
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="with --sql: open the demo database read-only",
    )
    parser.add_argument(
        "--no-upstream",
        action="store_true",
        help="guided mode: skip the frozen upstream comparison",
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the temporary demo directory"
    )
    args = parser.parse_args(argv)

    if args.sql is not None:
        return run_single_sql(args.sql, args.read_only, args.keep)
    if args.read_only:
        parser.error("--read-only is only used together with --sql")
    return run_guided(not args.no_upstream, args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
