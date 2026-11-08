"""SQLite implementation of SqlRunner interface."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from vanna.capabilities.sql_runner import SqlRunner, RunSqlToolArgs
from vanna.core.tool import ToolContext

#: PRAGMAs that only read schema/connection metadata.  They are the only
#: PRAGMAs accepted on a read-only connection.  PRAGMAs that can change
#: schema, files or persistent settings (``user_version``, ``journal_mode``,
#: ``writable_schema``, ``optimize``, ...) are refused.
_READ_ONLY_PRAGMAS = frozenset(
    {
        "collation_list",
        "compile_options",
        "database_list",
        "foreign_key_check",
        "foreign_key_list",
        "freelist_count",
        "index_info",
        "index_list",
        "index_xinfo",
        "integrity_check",
        "page_count",
        "page_size",
        "quick_check",
        "schema_version",
        "table_info",
        "table_list",
        "table_xinfo",
    }
)


def _denied_authorizer_actions() -> frozenset[int]:
    """Return the SQLite authorizer actions refused on a read-only connection.

    The authorizer is the statement-level guard; ``mode=ro`` and
    ``PRAGMA query_only`` are the connection- and database-level guards.  All
    three are used together so that read-only mode never depends on inspecting
    SQL keywords.
    """

    names = (
        "SQLITE_ALTER_TABLE",
        "SQLITE_ANALYZE",
        "SQLITE_ATTACH",
        "SQLITE_CREATE_INDEX",
        "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE",
        "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW",
        "SQLITE_CREATE_TRIGGER",
        "SQLITE_CREATE_VTABLE",
        "SQLITE_CREATE_VIEW",
        "SQLITE_DELETE",
        "SQLITE_DETACH",
        "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX",
        "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW",
        "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW",
        "SQLITE_DROP_VTABLE",
        "SQLITE_INSERT",
        "SQLITE_REINDEX",
        "SQLITE_UPDATE",
    )
    return frozenset(getattr(sqlite3, name) for name in names if hasattr(sqlite3, name))


_DENIED_ACTIONS = _denied_authorizer_actions()


class SqliteRunner(SqlRunner):
    """SQLite implementation of the SqlRunner interface."""

    def __init__(self, database_path: str, read_only: bool = False):
        """Initialize with a SQLite database path.

        Args:
            database_path: Path to the SQLite database file
            read_only: When ``True`` the file is opened with a ``mode=ro``
                URI, ``PRAGMA query_only`` and an authorizer that refuses
                writes, ``ATTACH``/``DETACH`` and write-capable PRAGMAs.
                The database file must already exist; it is never created.
                Defaults to ``False``, preserving the upstream read/write
                behaviour.
        """
        self.database_path = database_path
        self.read_only = read_only

    def _connect(self) -> sqlite3.Connection:
        """Open the connection, applying the read-only guards when requested."""

        if not self.read_only:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            return conn

        if str(self.database_path) == ":memory:":
            raise ValueError(
                "read_only=True requires a file-backed SQLite database; "
                "':memory:' cannot be opened read-only"
            )

        path = Path(self.database_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(
                f"read-only SQLite database does not exist: {path} "
                "(read_only=True never creates a database)"
            )

        # Path.as_uri() percent-encodes spaces, '#' and non-ASCII characters,
        # so the '?mode=ro' query string cannot be truncated by the path.
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row

        # Connection-level guard: the engine itself refuses write statements,
        # including writes hidden in CTEs or triggers.
        conn.execute("PRAGMA query_only = ON")

        # Statement-level guard: available from Python 3.11.  Older runtimes
        # keep mode=ro + query_only only, which is recorded in the docs.
        set_authorizer = getattr(conn, "set_authorizer", None)
        if set_authorizer is not None:
            set_authorizer(self._authorize)
        return conn

    @staticmethod
    def _authorize(
        action: int,
        arg1: Optional[str],
        arg2: Optional[str],
        dbname: Optional[str],
        source: Optional[str],
    ) -> int:
        """Authorizer callback used by read-only connections."""

        if action in _DENIED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA:
            if (arg1 or "").lower() in _READ_ONLY_PRAGMAS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        """Execute SQL query against SQLite database and return results as DataFrame.

        Result sets are detected from ``cursor.description`` instead of the
        first SQL keyword, so leading comments, ``WITH`` and ``VALUES``
        statements keep their rows.  A statement that both returns rows and
        modifies data (``RETURNING``) is committed after its rows are consumed,
        so closing the connection cannot roll the change back.

        Args:
            args: SQL query arguments
            context: Tool execution context

        Returns:
            DataFrame with query results, or ``rows_affected`` for statements
            that do not return a result set

        Raises:
            ValueError: If the SQL statement is empty
            FileNotFoundError: If ``read_only=True`` and the database is missing
            sqlite3.Error: If query execution fails
        """
        if not args.sql or not args.sql.strip():
            raise ValueError("SQL statement must not be empty")

        # Connect to the database
        conn = self._connect()
        cursor = conn.cursor()

        try:
            # Execute the query
            cursor.execute(args.sql)

            if cursor.description is not None:
                # Any statement with a result set (SELECT, WITH ... SELECT,
                # VALUES, INSERT/UPDATE/DELETE ... RETURNING, row-returning
                # PRAGMAs) is treated as a result-set query.
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                # RETURNING opens a write transaction.  Commit only after the
                # result set has been consumed, otherwise SQLite refuses with
                # "cannot commit transaction - SQL statements in progress".
                if conn.in_transaction:
                    conn.commit()

                if not rows:
                    # Keep the requested columns for empty results.
                    return pd.DataFrame([], columns=columns)

                # Build positionally so duplicate column names are not merged.
                return pd.DataFrame([tuple(row) for row in rows], columns=columns)

            # For non-result statements (INSERT, UPDATE, DELETE, DDL, etc.)
            conn.commit()
            rows_affected = cursor.rowcount
            # Return a DataFrame indicating rows affected
            return pd.DataFrame({"rows_affected": [rows_affected]})

        finally:
            cursor.close()
            conn.close()
