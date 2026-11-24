"""Database layer for DashZone Milestone 3.

Every call goes through the Milestone 2 procedures, functions and views in
the SQL Server database (LocalDeliveryMarketplace_Team_00). The backend never
writes to the tables directly; it only calls the objects the milestone gave us.

Connection settings come from environment variables (see .env.example).
Each helper opens its own connection and closes it; autocommit is on because
the procedures manage their own writes.
"""

import datetime
import decimal
import logging
import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("dashzone.db")


class DatabaseError(Exception):
    """A database call failed. Routers turn this into a generic user-facing
    failure; the real error is only logged server-side."""


def _connection_string() -> str:
    server = os.environ.get("DB_SERVER", "localhost")
    database = os.environ.get("DB_NAME", "LocalDeliveryMarketplace_Team_00")
    user = os.environ.get("DB_USER", "sa")
    password = os.environ.get("DB_PASSWORD", "")
    driver = os.environ.get("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )


def get_connection():
    return pyodbc.connect(_connection_string(), autocommit=True)


def ping() -> bool:
    """True when the database answers, False otherwise. Used by /health."""
    try:
        conn = get_connection()
    except pyodbc.Error:
        return False
    try:
        conn.cursor().execute("SELECT 1")
        return True
    except pyodbc.Error:
        return False
    finally:
        conn.close()


def _serialize(value):
    """Make a pyodbc value JSON-safe."""
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def _rows_to_dicts(cursor):
    cols = [c[0] for c in cursor.description]
    return [
        {col: _serialize(val) for col, val in zip(cols, row)}
        for row in cursor.fetchall()
    ]


def _run(sql, params=()):
    """Run a plain SELECT and return the rows as a list of dicts."""
    try:
        conn = get_connection()
    except pyodbc.Error:
        logger.exception("Could not connect to the database")
        raise DatabaseError("connect failed")
    try:
        cur = conn.cursor()
        cur.execute(sql, list(params))
        return _rows_to_dicts(cur)
    except pyodbc.Error:
        logger.exception("Database query failed: %s", sql)
        raise DatabaseError("query failed")
    finally:
        conn.close()


def call_proc(proc_name, params=()):
    """Call a stored procedure and return (return_code, rows).

    Runs: DECLARE @rc INT; EXEC @rc = dbo.Proc @p1=?, ...; SELECT @rc AS return_code;
    Any result sets the procedure returns are collected as rows; the return
    code comes from the final SELECT. Extra "rows affected" messages are
    skipped so the connection stays clean.
    """
    placeholders = ", ".join("?" for _ in params)
    exec_sql = f"EXEC @rc = dbo.{proc_name}"
    if placeholders:
        exec_sql += f" {placeholders}"
    batch = f"DECLARE @rc INT; {exec_sql}; SELECT @rc AS return_code;"
    try:
        conn = get_connection()
    except pyodbc.Error:
        logger.exception("Could not connect to the database")
        raise DatabaseError("connect failed")
    try:
        cur = conn.cursor()
        cur.execute(batch, list(params))
        rc = None
        rows = []
        while True:
            if cur.description is not None:
                cols = [c[0] for c in cur.description]
                fetched = cur.fetchall()
                if (
                    len(cols) == 1
                    and cols[0].lower() == "return_code"
                    and len(fetched) == 1
                ):
                    rc = fetched[0][0]
                else:
                    rows.extend(
                        {col: _serialize(v) for col, v in zip(cols, r)}
                        for r in fetched
                    )
            if not cur.nextset():
                break
        return (int(rc) if rc is not None else -1), rows
    except pyodbc.Error:
        logger.exception("Stored procedure failed: %s", proc_name)
        raise DatabaseError("procedure failed")
    finally:
        conn.close()


def call_scalar(func_name, params=()):
    """Call a scalar function and return its single value (or None)."""
    placeholders = ", ".join("?" for _ in params)
    sql = f"SELECT dbo.{func_name}({placeholders}) AS result"
    rows = _run(sql, params)
    if not rows:
        return None
    return _serialize(rows[0]["result"])


def call_table_func(func_name, params=()):
    """Call a table-valued function and return its rows as a list of dicts."""
    placeholders = ", ".join("?" for _ in params)
    sql = f"SELECT * FROM dbo.{func_name}({placeholders})"
    return _run(sql, params)


def query_view(view_name, where="", params=()):
    """SELECT * FROM a view, with an optional WHERE clause (use ? placeholders)."""
    sql = f"SELECT * FROM dbo.{view_name}"
    if where:
        sql += f" WHERE {where}"
    return _run(sql, params)
