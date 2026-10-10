"""Explicit administrator setup for disposable PostgreSQL security tests."""

from pathlib import Path

from retaniq.database import connect_database
from retaniq.postgresql_migrations import split_sql_statements


def bootstrap_test_roles(config):
    """Idempotently create only reviewed NOLOGIN capability roles."""
    script = Path(__file__).resolve().parents[1] / "security" / "postgresql" / "role_bootstrap.sql"
    connection = connect_database(config)
    try:
        connection.raw_connection.autocommit = True
        for statement in split_sql_statements(script.read_text(encoding="utf-8")):
            connection.raw_connection.execute(statement)
    finally:
        connection.close()
