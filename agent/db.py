"""
Database connection settings shared by every tool.

Hosted Postgres (Neon, Supabase, Render) hands you one connection string,
so DATABASE_URL wins when set. Locally and in docker-compose the separate
POSTGRES_* variables are used instead.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# libpq options that asyncpg does not understand. asyncpg would forward them
# to the server as settings and the connection would fail.
_UNSUPPORTED_PARAMS = {"channel_binding"}


def _clean_dsn(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "postgres":
        parts = parts._replace(scheme="postgresql")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _UNSUPPORTED_PARAMS]
    if not any(k == "sslmode" for k, _ in query) and parts.hostname not in {
        "localhost",
        "127.0.0.1",
        "db",
    }:
        query.append(("sslmode", "require"))
    return urlunsplit(parts._replace(query=urlencode(query)))


def connect_kwargs() -> dict[str, Any]:
    """Keyword arguments for asyncpg.connect()."""
    url = os.getenv("DATABASE_URL")
    if url:
        return {"dsn": _clean_dsn(url)}
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "argus"),
        "password": os.getenv("POSTGRES_PASSWORD", "argus_secret"),
        "database": os.getenv("POSTGRES_DB", "argus_db"),
    }


SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed.sql"
EVAL_FIXTURES_FILE = Path(__file__).resolve().parent.parent / "data" / "eval_fixtures.sql"

# The seed data describes the world as of this moment. Tools measure their
# time windows back from the transaction's own timestamp; this is only the
# fallback when a caller doesn't pass one.
REFERENCE_TIME = datetime(2026, 6, 19, tzinfo=UTC)


async def seed_if_empty() -> bool:
    """
    Load data/seed.sql when the database has no transactions table yet.

    Lets a fresh hosted database work on first deploy with no manual psql step.
    Returns True when seeding ran.
    """
    import asyncpg

    conn = await asyncpg.connect(**connect_kwargs())
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.transactions') IS NOT NULL")
        if exists:
            return False
        await conn.execute(SEED_FILE.read_text(encoding="utf-8"))
        return True
    finally:
        await conn.close()


async def load_eval_fixtures() -> None:
    """
    Insert the history behind tests/evals/cases.json (data/eval_fixtures.sql).

    Safe to run on every startup: every row uses ON CONFLICT DO NOTHING, so an
    existing database (e.g. the live Neon one) picks up new fixture rows once.
    """
    import asyncpg

    conn = await asyncpg.connect(**connect_kwargs())
    try:
        await conn.execute(EVAL_FIXTURES_FILE.read_text(encoding="utf-8"))
    finally:
        await conn.close()
