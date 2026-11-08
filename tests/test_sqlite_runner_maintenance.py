"""Regression tests for the maintained Vanna SQLite runner.

Every test talks to a real, temporary SQLite database created with the
standard library; nothing is mocked and no SQL is rewritten before it reaches
:class:`SqliteRunner`.  The tests cover the upstream compatibility problem
(result sets classified by the first SQL keyword), the empty-result column
loss, the ``RETURNING`` commit failure, and the optional read-only mode.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from vanna.capabilities.sql_runner import RunSqlToolArgs
from vanna.integrations.sqlite import SqliteRunner

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


def _run(runner: SqliteRunner, sql: str) -> pd.DataFrame:
    return asyncio.run(runner.run_sql(RunSqlToolArgs(sql=sql), None))


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _scalar(path: Path, sql: str):
    """Read a single value with an explicitly closed connection."""

    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(sql).fetchone()
        return None if row is None else row[0]
    finally:
        conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "shop.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    return path


# ---------------------------------------------------------------------------
# compatibility of the original constructor and contract
# ---------------------------------------------------------------------------


def test_constructor_default_parameters_are_compatible(db_path: Path) -> None:
    runner = SqliteRunner(str(db_path))
    assert runner.database_path == str(db_path)
    assert runner.read_only is False

    parameters = inspect.signature(SqliteRunner.__init__).parameters
    assert list(parameters) == ["self", "database_path", "read_only"]
    assert parameters["read_only"].default is False


def test_run_sql_is_async() -> None:
    assert inspect.iscoroutinefunction(SqliteRunner.run_sql)


def test_plain_select_returns_rows_and_columns(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)), "SELECT id, name, price FROM products ORDER BY id"
    )
    assert frame.shape == (2, 3)
    assert list(frame.columns) == ["id", "name", "price"]
    assert frame["name"].tolist() == ["apple", "banana"]


def test_leading_comment_select_returns_rows(db_path: Path) -> None:
    sql = "-- a leading comment\nSELECT id, name FROM products ORDER BY id"
    frame = _run(SqliteRunner(str(db_path)), sql)
    assert frame.shape == (2, 2)
    assert list(frame.columns) == ["id", "name"]


def test_with_select_returns_rows(db_path: Path) -> None:
    sql = (
        "WITH cheap AS (SELECT id, name FROM products WHERE price < 1) "
        "SELECT id, name FROM cheap ORDER BY id"
    )
    frame = _run(SqliteRunner(str(db_path)), sql)
    assert frame.shape == (1, 2)
    assert frame.iloc[0]["name"] == "banana"


def test_values_returns_rows(db_path: Path) -> None:
    frame = _run(SqliteRunner(str(db_path)), "VALUES (1, 'alpha'), (2, 'beta')")
    assert frame.shape == (2, 2)
    assert list(frame.columns) == ["column1", "column2"]
    assert frame["column1"].tolist() == [1, 2]


def test_empty_result_keeps_columns_and_order(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "SELECT id, name FROM products WHERE id < 0",
    )
    assert frame.shape == (0, 2)
    assert list(frame.columns) == ["id", "name"]


def test_empty_table_keeps_columns(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)), "SELECT id, note FROM empty_table ORDER BY id"
    )
    assert frame.shape == (0, 2)
    assert list(frame.columns) == ["id", "note"]


def test_duplicate_column_names_are_preserved(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "SELECT id AS k, name AS k FROM products ORDER BY id LIMIT 1",
    )
    assert frame.shape == (1, 2)
    assert list(frame.columns) == ["k", "k"]
    assert frame.iloc[0].tolist() == [1, "apple"]


def test_row_returning_pragma_in_default_mode(db_path: Path) -> None:
    frame = _run(SqliteRunner(str(db_path)), "PRAGMA table_info(products)")
    assert frame.shape == (3, 6)
    assert list(frame.columns) == ["cid", "name", "type", "notnull", "dflt_value", "pk"]


# ---------------------------------------------------------------------------
# default read/write behaviour must stay intact
# ---------------------------------------------------------------------------


def test_default_insert_commits_and_reconnect_sees_row(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "INSERT INTO products (name, price) VALUES ('cherry', 2.25)",
    )
    assert list(frame.columns) == ["rows_affected"]
    assert frame.iloc[0, 0] == 1
    assert _scalar(db_path, "SELECT COUNT(*) FROM products") == 3
    assert _scalar(db_path, "SELECT price FROM products WHERE name = 'cherry'") == 2.25


def test_default_update_commits(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "UPDATE products SET price = price + 1 WHERE name = 'apple'",
    )
    assert frame.iloc[0, 0] == 1
    assert _scalar(db_path, "SELECT price FROM products WHERE name = 'apple'") == 2.5


def test_delete_reports_rows_affected(db_path: Path) -> None:
    frame = _run(SqliteRunner(str(db_path)), "DELETE FROM products WHERE id = 1")
    assert list(frame.columns) == ["rows_affected"]
    assert frame.iloc[0, 0] == 1
    assert _scalar(db_path, "SELECT COUNT(*) FROM products") == 1


def test_insert_returning_returns_rows_and_commits(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "INSERT INTO products (name, price) VALUES ('date', 3.0) RETURNING id, name",
    )
    assert frame.shape == (1, 2)
    assert list(frame.columns) == ["id", "name"]
    assert frame.iloc[0]["name"] == "date"
    assert _scalar(db_path, "SELECT COUNT(*) FROM products WHERE name = 'date'") == 1


def test_update_returning_multiple_rows_and_commit(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "UPDATE products SET price = price + 10 RETURNING id, price",
    )
    assert frame.shape == (2, 2)
    assert list(frame.columns) == ["id", "price"]
    assert sorted(frame["price"].tolist()) == [10.5, 11.5]
    assert _scalar(db_path, "SELECT price FROM products WHERE name = 'apple'") == 11.5


def test_returning_with_no_matching_rows_keeps_columns(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path)),
        "UPDATE products SET price = 0 WHERE id = -999 RETURNING id",
    )
    assert frame.shape == (0, 1)
    assert list(frame.columns) == ["id"]
    assert _scalar(db_path, "SELECT COUNT(*) FROM products WHERE price = 0") == 0


# ---------------------------------------------------------------------------
# optional read-only mode: database-level refusal, not keyword matching
# ---------------------------------------------------------------------------


def test_read_only_select_works_and_file_is_unchanged(db_path: Path) -> None:
    before = _sha256(db_path)
    frame = _run(
        SqliteRunner(str(db_path), read_only=True),
        "SELECT id, name FROM products ORDER BY id",
    )
    assert frame.shape == (2, 2)
    assert _sha256(db_path) == before


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO products (name) VALUES ('hack')",
        "UPDATE products SET name = 'hack'",
        "DELETE FROM products",
        "WITH doomed AS (SELECT id FROM products) DELETE FROM products "
        "WHERE id IN (SELECT id FROM doomed)",
        "CREATE TABLE hack (id INTEGER)",
        "DROP TABLE products",
        "PRAGMA user_version = 7",
        "PRAGMA journal_mode = WAL",
        "REINDEX idx_products_name",
        "ANALYZE",
        "CREATE TEMP TABLE hack (id INTEGER)",
    ],
)
def test_read_only_rejects_writes(db_path: Path, sql: str) -> None:
    before = _sha256(db_path)
    with pytest.raises(sqlite3.DatabaseError):
        _run(SqliteRunner(str(db_path), read_only=True), sql)
    assert _sha256(db_path) == before
    assert _scalar(db_path, "SELECT COUNT(*) FROM products") == 2


def test_read_only_rejects_attach_and_creates_no_file(
    db_path: Path, tmp_path: Path
) -> None:
    escape = tmp_path / "attached-escape.db"
    with pytest.raises(sqlite3.DatabaseError):
        _run(
            SqliteRunner(str(db_path), read_only=True),
            f"ATTACH DATABASE '{escape.as_posix()}' AS side_db",
        )
    assert not escape.exists()


def test_read_only_rejects_vacuum_into(db_path: Path, tmp_path: Path) -> None:
    copy = tmp_path / "vacuum-copy.db"
    with pytest.raises(sqlite3.DatabaseError):
        _run(
            SqliteRunner(str(db_path), read_only=True),
            f"VACUUM INTO '{copy.as_posix()}'",
        )
    assert not copy.exists()


def test_read_only_rejects_load_extension(db_path: Path, tmp_path: Path) -> None:
    with pytest.raises(sqlite3.Error):
        _run(
            SqliteRunner(str(db_path), read_only=True),
            f"SELECT load_extension('{(tmp_path / 'evil.dll').as_posix()}')",
        )


def test_read_only_allows_metadata_pragma(db_path: Path) -> None:
    frame = _run(
        SqliteRunner(str(db_path), read_only=True),
        "PRAGMA table_info(products)",
    )
    assert frame.shape == (3, 6)
    assert list(frame.columns) == ["cid", "name", "type", "notnull", "dflt_value", "pk"]


def test_read_only_write_pragma_does_not_change_value(db_path: Path) -> None:
    with pytest.raises(sqlite3.DatabaseError):
        _run(SqliteRunner(str(db_path), read_only=True), "PRAGMA user_version = 7")
    assert _scalar(db_path, "PRAGMA user_version") == 0


def test_read_only_missing_database_is_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.db"
    with pytest.raises(FileNotFoundError):
        _run(SqliteRunner(str(missing), read_only=True), "SELECT 1")
    assert not missing.exists()


def test_read_only_memory_database_is_rejected() -> None:
    with pytest.raises(ValueError):
        _run(SqliteRunner(":memory:", read_only=True), "SELECT 1")


def test_read_only_failed_write_does_not_poison_later_reads(db_path: Path) -> None:
    runner = SqliteRunner(str(db_path), read_only=True)
    with pytest.raises(sqlite3.DatabaseError):
        _run(runner, "DELETE FROM products")
    frame = _run(runner, "SELECT COUNT(*) AS n FROM products")
    assert frame.iloc[0]["n"] == 2


# ---------------------------------------------------------------------------
# paths, lifecycle and error feedback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("read_only", [False, True])
def test_path_with_spaces_hash_and_unicode(tmp_path: Path, read_only: bool) -> None:
    folder = tmp_path / "data dir 数据"
    folder.mkdir()
    path = folder / "shop #1 100%.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    frame = _run(
        SqliteRunner(str(path), read_only=read_only),
        "SELECT id, name FROM products ORDER BY id",
    )
    assert frame.shape == (2, 2)
    assert list(frame.columns) == ["id", "name"]


def test_read_only_accepts_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = sqlite3.connect(str(tmp_path / "shop.db"))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    monkeypatch.chdir(tmp_path)
    frame = _run(
        SqliteRunner("shop.db", read_only=True), "SELECT COUNT(*) AS n FROM products"
    )
    assert frame.iloc[0]["n"] == 2


def test_connection_released_after_query_error(tmp_path: Path) -> None:
    path = tmp_path / "lifecycle.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(sqlite3.OperationalError):
        _run(SqliteRunner(str(path)), "SELECT * FROM table_that_does_not_exist")
    path.unlink()  # succeeds only when no handle is still open
    assert not path.exists()


def test_connection_released_after_read_only_refusal(tmp_path: Path) -> None:
    path = tmp_path / "lifecycle-ro.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(sqlite3.DatabaseError):
        _run(
            SqliteRunner(str(path), read_only=True),
            "INSERT INTO products (name) VALUES ('x')",
        )
    path.unlink()
    assert not path.exists()


@pytest.mark.parametrize("sql", ["", "   ", "\n\t "])
def test_empty_sql_raises_value_error(db_path: Path, sql: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        _run(SqliteRunner(str(db_path)), sql)
