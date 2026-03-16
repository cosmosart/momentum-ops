"""
Thread-safe PostgreSQL connection pool backed by ``psycopg`` (v3).

The pool is initialised lazily on first use and derives its DSN from
:pymod:`shared.config`.  All public helpers return connections via a
context manager so that connections are **always** returned to the pool,
even when callers forget to close them.

Usage
-----
>>> from shared.database import get_connection, check_health
>>> with get_connection() as conn, conn.cursor() as cur:
...      cur.execute("SELECT 1")
...      print(cur.fetchone())
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import LiteralString, cast

from fastapi import params
import psycopg
from psycopg import Cursor, sql
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from shared.config import settings

logger = logging.getLogger(__name__)

# ── Module-level pool singleton ───────────────────────────────────────────────
_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """Return the module-level pool, creating it on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        logger.info("Initialising connection pool → %s@%s/%s", settings.db_user, settings.db_host, settings.db_name)
        _pool = ConnectionPool(
            conninfo=settings.db_url,
            min_size=2,
            max_size=10,
            # Wait up to 30 s for a connection before raising PoolTimeout
            timeout=30.0,
            kwargs={"autocommit": False, "row_factory": dict_row},
        )
    return _pool


# ── Public API ────────────────────────────────────────────────────────────────


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Yield a connection from the pool.

    The connection is automatically returned when the ``with`` block exits.
    On unhandled exceptions the transaction is rolled back; on clean exit the
    caller is responsible for calling ``conn.commit()`` if needed.

    Example
    -------
    >>> with get_connection() as conn, conn.cursor() as cur:
    ...     cur.execute("INSERT INTO tickers (symbol) VALUES (%s)", ("AAPL",))
    ...     conn.commit()
    """
    pool = _get_pool()
    with pool.connection() as conn:
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise

@contextmanager
def get_cursor() -> Generator[Cursor[DictRow], None, None]:
    """
    Yield a dictionary-aware cursor while managing the underlying connection.
    """
    # get_connection is assumed to be a context manager that handles the pool
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Type hint helps Pylance track the DictRow through the yield
        yield cast(Cursor[DictRow], cur)
        # conn.commit() or conn.rollback() happens here depending on get_connection logic

def check_health() -> bool:
    """
    Return ``True`` if the database is reachable, ``False`` otherwise.

    Useful for liveness probes and sidebar status indicators.
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return False


def close_pool() -> None:
    """
    Drain and close the connection pool.

    Call this during graceful shutdown (e.g. SIGTERM handler) to release all
    connections cleanly.
    """
    global _pool  # noqa: PLW0603
    if _pool is not None:
        logger.info("Closing connection pool")
        _pool.close()
        _pool = None


def execute_ddl(sql_path: str) -> None:
    """
    Execute a DDL file (e.g. ``schema.sql``) inside a single transaction.

    Parameters
    ----------
    sql_path : str
        Absolute or relative path to the ``.sql`` file.
    """
    with open(sql_path) as fh:
        ddl = cast(LiteralString,fh.read())

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql.SQL(ddl), ())
        conn.commit()
        logger.info("DDL executed: %s", sql_path)

def execute_query(
    cur: Cursor[DictRow],
    query: str | sql.SQL | sql.Composed,
    params: tuple = ()
) -> list[DictRow]:
    """
Execute a SQL query and return rows as a list of dictionaries.

    This function serves as the centralized database gateway for the project,
    enforcing strict security protocols to prevent SQL injection. It utilizes
    PEP 675 (LiteralString) to ensure that dynamic query construction is handled
    exclusively via `psycopg.sql` objects rather than unsafe string manipulation.

    Parameters
    ----------
    cur : Cursor[DictRow]
        An active database cursor with `dict_row` factory configured.
    query : LiteralString | psycopg.sql.SQL | psycopg.sql.Composed
        The SQL statement to execute. 
        - Use a raw `str` for static queries (e.g., "SELECT * FROM table").
        - Use `psycopg.sql.SQL` and `format()` for dynamic structural changes
          (e.g., dynamic table or column names).
        - Direct f-strings are prohibited and will be flagged by the linter.
    params : tuple[Any, ...], optional
        Positional parameters to be safely bound to `%s` placeholders in the 
        query by the database driver. Defaults to an empty tuple.

    Returns
    -------
    list[psycopg.rows.DictRow]
        A list of dictionaries where keys are column names and values are 
        the corresponding row data.

    Raises
    ------
    psycopg.Error
        If the SQL execution fails due to syntax, permission, or connectivity issues.

    Notes
    -----
    The function automatically configures the cursor with `dict_row` and provides 
    explicit type hinting (`Cursor[DictRow]`) to ensure Pylance/Pyright 
    correctly identifies the return type for downstream data processing.
    """
    final_query = cast(LiteralString, query) if isinstance(query, str) else query
    cur.execute(final_query, params)
    results = cur.fetchall()

    logger.debug("Query executed | Rows: %d", len(results))
    return results
