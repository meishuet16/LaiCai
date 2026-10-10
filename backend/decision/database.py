"""
database.py — PostgreSQL connection pool for the Decision Engine.

Uses psycopg2 SimpleConnectionPool.
tenant_id is ALWAYS derived from the authenticated request context,
never from a client-supplied body field.
"""

from __future__ import annotations
import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

from .config import settings

logger = logging.getLogger(__name__)

_pool: pg_pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    """Initialize the connection pool. Call once at app startup."""
    global _pool
    if _pool is not None:
        return
    logger.info("Initializing PostgreSQL connection pool...")
    _pool = pg_pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=settings.database_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    logger.info("Connection pool ready.")


def close_pool() -> None:
    """Cleanly close all connections. Call at app shutdown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Connection pool closed.")


def get_db() -> Generator:
    """
    FastAPI dependency — yields a psycopg2 connection from the pool.
    Commits on success, rolls back on any exception.
    If the pool is not initialized (e.g. running unit tests without DB), yields None.
    """
    if _pool is None:
        yield None
        return

    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
