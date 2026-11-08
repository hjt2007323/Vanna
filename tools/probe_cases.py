"""Data-driven probe cases for the G1 Vanna SQLite maintenance project.

The same inputs are executed against two runners:

* ``baseline`` - the frozen upstream file at commit
  ``365d0617c1a4567ffee1b19b40c27feb4206bfcf`` (vendored byte-for-byte in
  ``baseline/upstream_sql_runner.py``), loaded by path;
* ``after`` - the installed ``vanna.integrations.sqlite.sql_runner`` module,
  which resolves to the modified working tree (editable install).

Both runners are the *real* implementation; nothing here copies or mocks the
logic under test.  The module only owns fixtures, expectations and evidence
collection.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vanna.capabilities.sql_runner import RunSqlToolArgs

SEED_SQL = """\
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL
);
INSERT INTO products (name, price) VALUES ('apple', 1.5), ('banana', 0.5);
CREATE INDEX idx_products_name ON products(name);
CREATE TABLE empty_table (
    id INTEGER PRIMARY KEY,
    note TEXT
);
"""

#: Substrings carried by a genuine read-only refusal on this stack.  Checking
#: them keeps a SQL syntax error from being counted as a blocked write.
READ_ONLY_REFUSAL_TOKENS = (
    "not authorized",
    "authorization denied",
    "readonly",
    "read-only",
)


@dataclass(frozen=True)
class Case:
    """One probe: the SQL, the fixture mode and the expected observable result."""

    case_id: str
    category: str
    sql: str
    note: str = ""
    read_only: bool = False
    create_db: bool = True
    path_profile: str = "plain"  # "plain" | "space_hash"
    expected_kind: str = "rows"  # "rows" | "rows_affected" | "error"
    expected_rows: int | None = None
    expected_columns: tuple[str, ...] = ()
    expected_error_contains: tuple[str, ...] = ()
    verify_sql: str | None = None
    expected_verify: Any = None
    expect_db_unchanged: bool = False
    expect_no_db_created: bool = False
    expect_delete_ok: bool = False


# Real newlines are used in SQL fixtures on purpose: a printed "\n" would make
# the "leading comment" probe meaningless.
CASES: tuple[Case, ...] = (
    Case(
        "V0_normal_select",
        "normal_read",
        "SELECT id, name, price FROM products ORDER BY id",
        note="positive control: ordinary SELECT",
        expected_rows=2,
        expected_columns=("id", "name", "price"),
    ),
    Case(
        "V1_leading_comment_select",
        "query_compat",
        "-- leading comment\nSELECT id, name FROM products ORDER BY id",
        note="leading comment: upstream classifies on first token '--'",
        expected_rows=2,
        expected_columns=("id", "name"),
    ),
    Case(
        "V2_with_select",
        "query_compat",
        "WITH cheap AS (SELECT id, name FROM products WHERE price < 1) "
        "SELECT id, name FROM cheap ORDER BY id",
        note="CTE followed by SELECT: upstream first token WITH",
        expected_rows=1,
        expected_columns=("id", "name"),
    ),
    Case(
        "V3_values",
        "query_compat",
        "VALUES (1, 'alpha'), (2, 'beta')",
        note="VALUES is a row-returning statement: upstream first token VALUES",
        expected_rows=2,
        expected_columns=("column1", "column2"),
    ),
    Case(
        "V4_empty_result_columns",
        "empty_result",
        "SELECT id, name FROM products WHERE id < 0",
        note="0 rows must keep the requested column names and order",
        expected_rows=0,
        expected_columns=("id", "name"),
    ),
    Case(
        "V4b_empty_table",
        "empty_result",
        "SELECT id, note FROM empty_table ORDER BY id",
        note="empty table keeps its columns",
        expected_rows=0,
        expected_columns=("id", "note"),
    ),
    Case(
        "V5_default_insert_commit",
        "default_write",
        "INSERT INTO products (name, price) VALUES ('cherry', 2.25)",
        note="default write path keeps commit semantics",
        expected_kind="rows_affected",
        expected_rows=1,
        verify_sql="SELECT COUNT(*) FROM products",
        expected_verify=3,
    ),
    Case(
        "V5b_default_update_commit",
        "default_write",
        "UPDATE products SET price = price + 1 WHERE name = 'apple'",
        note="UPDATE commits; a reconnected reader sees the new value",
        expected_kind="rows_affected",
        expected_rows=1,
        verify_sql="SELECT price FROM products WHERE name = 'apple'",
        expected_verify=2.5,
    ),
    Case(
        "V6_insert_returning",
        "returning",
        "INSERT INTO products (name, price) VALUES ('date', 3.0) RETURNING id, name",
        note="RETURNING rows must be returned and committed, not silently dropped",
        expected_rows=1,
        expected_columns=("id", "name"),
        verify_sql="SELECT COUNT(*) FROM products WHERE name = 'date'",
        expected_verify=1,
    ),
    Case(
        "V6b_update_returning",
        "returning",
        "UPDATE products SET price = 9.0 WHERE name = 'banana' RETURNING id, price",
        note="UPDATE ... RETURNING returns the row and commits it",
        expected_rows=1,
        expected_columns=("id", "price"),
        verify_sql="SELECT price FROM products WHERE name = 'banana'",
        expected_verify=9.0,
    ),
    Case(
        "V6c_returning_zero_rows",
        "returning",
        "UPDATE products SET price = 0 WHERE id = -999 RETURNING id",
        note="RETURNING with no matched row: 0 rows plus the column, not rows_affected",
        expected_rows=0,
        expected_columns=("id",),
        verify_sql="SELECT COUNT(*) FROM products WHERE price = 0",
        expected_verify=0,
    ),
    Case(
        "V7a_readonly_insert",
        "read_only",
        "INSERT INTO products (name) VALUES ('hack')",
        note="read_only=True must reject writes through the database mechanism",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7b_readonly_cte_delete",
        "read_only",
        "WITH doomed AS (SELECT id FROM products WHERE id = 1) "
        "DELETE FROM products WHERE id IN (SELECT id FROM doomed)",
        note="a keyword check for SELECT would miss this CTE write",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7c_readonly_attach",
        "read_only",
        "ATTACH DATABASE '{workdir}/attached-escape.db' AS side_db",
        note="ATTACH must be refused so a read-only session cannot write elsewhere",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7d_readonly_pragma_write",
        "read_only",
        "PRAGMA user_version = 7",
        note="writing PRAGMA must be refused; user_version stays 0",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
        verify_sql="PRAGMA user_version",
        expected_verify=0,
    ),
    Case(
        "V7e_readonly_pragma_read",
        "read_only",
        "PRAGMA table_info(products)",
        note="read-only metadata pragma is allowed by the documented policy",
        read_only=True,
        expected_rows=3,
        expected_columns=("cid", "name", "type", "notnull", "dflt_value", "pk"),
        expect_db_unchanged=True,
    ),
    Case(
        "V7f_readonly_ddl",
        "read_only",
        "CREATE TABLE hack (id INTEGER)",
        note="DDL must be refused in read-only mode",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7g_readonly_load_extension",
        "read_only",
        "SELECT load_extension('{workdir}/evil.dll')",
        note="extension loading stays disabled/denied in read-only mode",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7h_readonly_vacuum_into",
        "read_only",
        "VACUUM INTO '{workdir}/vacuum-copy.db'",
        note="VACUUM INTO writes a new file and must be refused",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V7i_readonly_journal_mode",
        "read_only",
        "PRAGMA journal_mode = WAL",
        note="persistent PRAGMA settings must be refused",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
        verify_sql="PRAGMA journal_mode",
        expected_verify="delete",
    ),
    Case(
        "V7j_readonly_reindex",
        "read_only",
        "REINDEX idx_products_name",
        note="REINDEX rewrites index pages and must be refused",
        read_only=True,
        expected_kind="error",
        expect_db_unchanged=True,
    ),
    Case(
        "V8a_space_hash_path_select",
        "path",
        "SELECT id, name FROM products ORDER BY id",
        note="path with a space and '#' must be URI-encoded correctly",
        path_profile="space_hash",
        expected_rows=2,
        expected_columns=("id", "name"),
    ),
    Case(
        "V8b_space_hash_path_readonly",
        "path",
        "SELECT id, name FROM products ORDER BY id",
        note="same path, read-only URI mode",
        path_profile="space_hash",
        read_only=True,
        expected_rows=2,
        expected_columns=("id", "name"),
    ),
    Case(
        "V8c_readonly_missing_db",
        "path",
        "SELECT 1",
        note="read_only=True on a missing database: clear refusal, no file created",
        create_db=False,
        read_only=True,
        expected_kind="error",
        expect_no_db_created=True,
        expected_error_contains=("does not exist",),
    ),
    Case(
        "V9_error_then_delete",
        "lifecycle",
        "SELECT * FROM table_that_does_not_exist",
        note="after an exception the connection is closed and the file can be deleted",
        expected_kind="error",
        expect_delete_ok=True,
        expected_error_contains=("no such table",),
    ),
    Case(
        "V10_empty_sql",
        "compat",
        "",
        note="empty SQL: optional hardening (not a gate), stable error instead of IndexError",
        expected_kind="error",
    ),
    Case(
        "V11_delete_rows_affected",
        "default_write",
        "DELETE FROM products WHERE id = 1",
        note="DELETE keeps rows_affected contract",
        expected_kind="rows_affected",
        expected_rows=1,
        verify_sql="SELECT COUNT(*) FROM products",
        expected_verify=1,
    ),
    Case(
        "V12_duplicate_column_names",
        "compat",
        "SELECT id AS k, name AS k FROM products ORDER BY id LIMIT 1",
        note="bonus: positional construction keeps both duplicate-named columns",
        expected_rows=1,
        expected_columns=("k", "k"),
    ),
    Case(
        "V13_default_pragma_rows",
        "compat",
        "PRAGMA table_info(products)",
        note="consequence of description-based detection: row-returning non-SELECT statements now return rows",
        expected_rows=3,
        expected_columns=("cid", "name", "type", "notnull", "dflt_value", "pk"),
    ),
)


def sha256_file(path: Path) -> str | None:
    """Return the SHA256 of ``path`` or ``None`` when the file does not exist."""

    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    """Convert sqlite/pandas scalars into JSON friendly values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return repr(value)
        return value
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    item = getattr(value, "item", None)
    if callable(item):  # numpy scalar
        try:
            return _jsonable(item())
        except (TypeError, ValueError):
            pass
    return repr(value)


def create_seed_database(path: Path) -> None:
    """Create the fixture database with a normal, explicitly closed connection."""

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()


def read_value(path: Path, sql: str) -> Any:
    """Run a verification query on a fresh connection and close it explicitly.

    ``with sqlite3.connect(...)`` only manages transactions; it does not close
    the connection, so the connection is closed in ``finally``.
    """

    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(sql).fetchone()
        return None if row is None else _jsonable(row[0])
    finally:
        conn.close()


def case_path(workdir: Path, case: Case) -> Path:
    if case.path_profile == "space_hash":
        return workdir / "dir with space" / "my #1 shop.db"
    return workdir / "shop.db"


def _snapshot_files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def run_case(runner_factory: Any, case: Case, workdir: Path) -> dict[str, Any]:
    """Execute one probe against one runner and return the raw evidence record."""

    workdir.mkdir(parents=True, exist_ok=True)
    db_path = case_path(workdir, case)
    if case.create_db:
        create_seed_database(db_path)

    sql = case.sql.replace("{workdir}", workdir.as_posix())
    files_before = _snapshot_files(workdir)
    db_before = sha256_file(db_path)

    record: dict[str, Any] = {
        "case_id": case.case_id,
        "category": case.category,
        "sql": case.sql,
        "read_only": case.read_only,
        "note": case.note,
        "status": None,
        "rows": None,
        "columns": [],
        "values": [],
        "error_type": None,
        "error_message": None,
        "unsupported": False,
        "db_sha256_before": db_before,
        "db_sha256_after": None,
        "db_changed": None,
        "db_created": None,
        "new_files": [],
        "verification": None,
        "delete_after_error_ok": None,
        "duration_ms": None,
    }

    start = time.perf_counter()
    try:
        kwargs = {"read_only": True} if case.read_only else {}
        runner = runner_factory(str(db_path), **kwargs)
    except TypeError as exc:  # baseline has no read_only parameter
        record["status"] = "unsupported"
        record["unsupported"] = True
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
        record["db_sha256_after"] = db_before
        record["db_changed"] = False
        record["new_files"] = []
        record["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
        return record

    try:
        frame = asyncio.run(runner.run_sql(RunSqlToolArgs(sql=sql), None))
        record["status"] = "ok"
        record["rows"] = int(frame.shape[0])
        record["columns"] = [str(column) for column in frame.columns]
        record["values"] = [
            [_jsonable(value) for value in row]
            for row in frame.itertuples(index=False, name=None)
        ]
    except Exception as exc:  # noqa: BLE001 - evidence must capture every failure mode
        record["status"] = "error"
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
    finally:
        record["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)

    db_after = sha256_file(db_path)
    record["db_sha256_after"] = db_after
    record["db_changed"] = (db_before != db_after) if db_before is not None else None
    record["db_created"] = db_before is None and db_after is not None
    record["new_files"] = sorted(set(_snapshot_files(workdir)) - set(files_before))

    if case.verify_sql and db_path.exists():
        value = read_value(db_path, case.verify_sql)
        record["verification"] = {
            "sql": case.verify_sql,
            "value": value,
            "expected": _jsonable(case.expected_verify),
            "ok": value == case.expected_verify,
        }

    if case.expect_delete_ok and db_path.exists():
        try:
            db_path.unlink()
            record["delete_after_error_ok"] = True
        except OSError as exc:
            record["delete_after_error_ok"] = False
            record["delete_error"] = repr(exc)

    return record


def evaluate(case: Case, record: dict[str, Any]) -> dict[str, Any]:
    """Compare one evidence record with the expectation frozen for the case."""

    mismatches: list[str] = []
    refusal_tokens = case.expected_error_contains
    if not refusal_tokens and case.read_only and case.expected_kind == "error":
        refusal_tokens = READ_ONLY_REFUSAL_TOKENS

    if case.expected_kind == "error":
        if record["unsupported"]:
            mismatches.append(
                f"runner does not support read_only=True ({record['error_type']})"
            )
        elif record["status"] != "error":
            mismatches.append(
                f"expected an error, got {record['status']} "
                f"rows={record['rows']} columns={record['columns']}"
            )
        elif refusal_tokens:
            # A syntax error would also satisfy "some error was raised"; the
            # refusal must be recognisable as a refusal, otherwise a broken
            # probe can masquerade as a blocked write.
            message = (record.get("error_message") or "").lower()
            if not any(token.lower() in message for token in refusal_tokens):
                mismatches.append(
                    f"error {record.get('error_message')!r} does not match "
                    f"any of {list(refusal_tokens)}"
                )
    elif case.expected_kind == "rows_affected":
        if record["status"] != "ok":
            mismatches.append(
                f"expected rows_affected result, got {record['status']}: "
                f"{record['error_type']}: {record['error_message']}"
            )
        else:
            if record["columns"] != ["rows_affected"]:
                mismatches.append(f"columns {record['columns']} != ['rows_affected']")
            elif record["values"] != [[case.expected_rows]]:
                mismatches.append(
                    f"rows_affected {record['values']} != [[{case.expected_rows}]]"
                )
    else:  # "rows"
        if record["status"] != "ok":
            mismatches.append(
                f"expected rows, got {record['status']}: "
                f"{record['error_type']}: {record['error_message']}"
            )
        else:
            if case.expected_rows is not None and record["rows"] != case.expected_rows:
                mismatches.append(f"rows {record['rows']} != {case.expected_rows}")
            if list(case.expected_columns) and record["columns"] != list(
                case.expected_columns
            ):
                mismatches.append(
                    f"columns {record['columns']} != {list(case.expected_columns)}"
                )

    if case.expect_db_unchanged and record["db_changed"]:
        mismatches.append("database file changed in read-only mode")
    if case.expect_no_db_created and record["db_created"]:
        mismatches.append("missing database file was created")
    if case.expect_delete_ok and record["delete_after_error_ok"] is not True:
        mismatches.append("database file could not be deleted after the error")
    if case.verify_sql is not None:
        verification = record["verification"] or {}
        if verification.get("ok") is not True:
            mismatches.append(
                "verification failed: "
                f"{verification.get('sql')} -> {verification.get('value')!r} "
                f"(expected {verification.get('expected')!r})"
            )
    if case.read_only and record["new_files"]:
        mismatches.append(f"new files appeared: {record['new_files']}")

    return {"meets_expectation": not mismatches, "mismatches": mismatches}
