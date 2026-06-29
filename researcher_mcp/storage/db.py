"""SQLite connection + initialization.

Usage::

    python -m researcher_mcp.storage.db init       # create tables
    python -m researcher_mcp.storage.db status      # show table row counts
    python -m researcher_mcp.storage.db reset       # DROP + recreate (asks)

A thin :func:`connect` helper returns a ``sqlite3.Connection`` with
``Row`` factory and foreign keys enabled. Use :func:`get_connection` as a
context manager for transactional work.
"""

from __future__ import annotations

import argparse
import contextlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from ..config import Config, get_config
from ..logging_utils import get_logger

log = get_logger("storage.db")

TABLES = (
    "papers", "paper_chunks", "ideas", "experiments",
    "experiment_runs", "agent_events", "budget_events",
)


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection with Row factory + FK enforcement."""
    cfg = get_config()
    path = db_path or cfg.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextlib.contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Transactional connection context manager (commits on success)."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(cfg: Config | None = None) -> Path:
    """Create all tables from ``schema.sql``. Idempotent."""
    cfg = cfg or get_config()
    cfg.ensure_dirs()
    schema_sql = cfg.schema_path.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema_sql)
    log.info("Initialized DB at %s", cfg.db_path)
    return cfg.db_path


def table_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    with get_connection() as conn:
        existing = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for t in TABLES:
            if t in existing:
                counts[t] = conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
            else:
                counts[t] = -1  # table missing
    return counts


def reset_db(confirm: bool) -> None:
    if not confirm:
        log.warning("reset requires --yes; aborting.")
        return
    with get_connection() as conn:
        # Disable FK enforcement so dropping parents before children does not
        # trip an implicit-DELETE FK violation (which would roll the whole
        # reset back and silently keep stale rows).
        conn.execute("PRAGMA foreign_keys = OFF;")
        for t in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
    init_db()
    log.info("DB reset complete.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="researcher_mcp.storage.db")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create tables")
    sub.add_parser("status", help="show row counts")
    rp = sub.add_parser("reset", help="drop and recreate all tables")
    rp.add_argument("--yes", action="store_true", help="confirm destructive reset")
    args = parser.parse_args(argv)

    cfg = get_config()
    if args.cmd == "init":
        path = init_db(cfg)
        print(f"DB initialized: {path}")
    elif args.cmd == "status":
        print(f"DB: {cfg.db_path}")
        for t, c in table_counts().items():
            print(f"  {t:18} {'(missing)' if c < 0 else c}")
    elif args.cmd == "reset":
        reset_db(args.yes)
        print("Reset done" if args.yes else "Reset skipped (pass --yes)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
