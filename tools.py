"""
Tools the agent can call.

The only tool here is `query_data`, which runs a read-only SQL query against the
programs dataset. The CSV is loaded into an in-memory SQLite database so you can
use plain SQL (the same skill you'd use against PostgreSQL in production).

`query_data` validates that a query is a single, read-only SELECT statement and
returns its rows, without letting a bad or unsafe query crash the agent.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path
from typing import List

DATA_PATH = Path(__file__).resolve().parent / "data" / "programs.csv"

COLUMNS = [
    ("program_id", "TEXT"),
    ("program_name", "TEXT"),
    ("region", "TEXT"),
    ("sector", "TEXT"),
    ("year", "INTEGER"),
    ("budget_usd", "INTEGER"),
    ("people_served", "INTEGER"),
    ("status", "TEXT"),
]


def load_programs_db(csv_path: Path = DATA_PATH) -> sqlite3.Connection:
    """Load the CSV into a fresh in-memory SQLite DB and return the connection."""
    con = sqlite3.connect(":memory:")
    col_defs = ", ".join(f"{name} {sqltype}" for name, sqltype in COLUMNS)
    con.execute(f"CREATE TABLE programs ({col_defs})")
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        names = [c[0] for c in COLUMNS]
        placeholders = ", ".join("?" for _ in names)
        con.executemany(
            f"INSERT INTO programs VALUES ({placeholders})",
            [tuple(row[n] for n in names) for row in reader],
        )
    return con



_DISALLOWED_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "vacuum",
)

ALLOWED_COLUMNS = frozenset(name for name, _ in COLUMNS)


def _table_columns(con: sqlite3.Connection, table: str = "programs") -> set:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def query_data(sql: str, con: sqlite3.Connection | None = None) -> List[list]:
    """
    Run a read-only SQL query against the `programs` table and return rows.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("query_data: sql must be a non-empty string")

    statement = sql.strip().rstrip(";").strip()

    if ";" in statement:
        raise ValueError("query_data: only a single statement is allowed")

    if not re.match(r"(?is)^select\b", statement):
        raise ValueError("query_data: only SELECT statements are allowed")

    lowered = statement.lower()
    for keyword in _DISALLOWED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise ValueError(f"query_data: disallowed keyword {keyword!r}")

    if con is None:
        con = load_programs_db()

    try:
        cursor = con.execute(statement)
        returned_columns = [d[0] for d in cursor.description] if cursor.description else []
        table_columns = _table_columns(con)
        leaked = [c for c in returned_columns if c in table_columns and c not in ALLOWED_COLUMNS]
        if leaked:
            raise ValueError(f"query_data: query returns disallowed column(s): {leaked}")
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise ValueError(f"query_data: query failed: {e}") from e

    return [list(row) for row in rows]
