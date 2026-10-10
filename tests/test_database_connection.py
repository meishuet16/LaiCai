import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retaniq.database import (
    DatabaseConnection,
    DatabaseDriverUnavailable,
    DatabaseTransactionError,
    PostgreSQLSchemaNotReady,
    UnsupportedDatabaseOperation,
    connect_database,
)
from retaniq.database_config import DatabaseConfig
from retaniq.data_foundation import initialize_database


class DatabaseConnectionTests(unittest.TestCase):
    def test_sqlite_connection_opens_with_foreign_keys_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_database(Path(directory) / "connection.sqlite3")
            self.assertEqual(connection.backend, "sqlite")
            self.assertIsInstance(connection.execute("SELECT 1"), sqlite3.Cursor)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            connection.close()
            self.assertTrue(connection.closed)
            connection.close()

    def test_sqlite_transaction_commits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "commit.sqlite3"
            with connect_database(path) as connection:
                with connection.transaction():
                    connection.execute("CREATE TABLE values_table (value INTEGER NOT NULL)")
                    connection.execute("INSERT INTO values_table(value) VALUES (?)", (7,))
            with connect_database(path) as connection:
                self.assertEqual(connection.execute("SELECT value FROM values_table").fetchone()[0], 7)

    def test_sqlite_transaction_rolls_back_on_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollback.sqlite3"
            with connect_database(path) as connection:
                connection.execute("CREATE TABLE values_table (value INTEGER NOT NULL)")
                connection.commit()
                with self.assertRaisesRegex(RuntimeError, "rollback sentinel"):
                    with connection.transaction(immediate=True):
                        connection.execute("INSERT INTO values_table(value) VALUES (?)", (9,))
                        raise RuntimeError("rollback sentinel")
            with connect_database(path) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM values_table").fetchone()[0], 0)

    def test_nested_transactions_are_explicitly_unsupported(self):
        with tempfile.TemporaryDirectory() as directory:
            with connect_database(Path(directory) / "nested.sqlite3") as connection:
                with connection.transaction():
                    with self.assertRaises(DatabaseTransactionError):
                        with connection.transaction():
                            pass

    def test_resource_is_closed_after_transaction_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_database(Path(directory) / "failure.sqlite3")
            with self.assertRaises(RuntimeError):
                with connection:
                    raise RuntimeError("failure sentinel")
            self.assertTrue(connection.closed)

    def test_postgresql_schema_operations_fail_before_any_sqlite_fallback(self):
        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        with self.assertRaises(PostgreSQLSchemaNotReady):
            initialize_database(config)

    def test_missing_postgresql_driver_is_reported_without_fallback(self):
        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        with patch.dict(sys.modules, {"psycopg": None, "psycopg.rows": None}):
            with self.assertRaises(DatabaseDriverUnavailable) as raised:
                DatabaseConnection.open(config)
        self.assertNotIn("secret", str(raised.exception))

    def test_postgresql_migration_script_operation_is_not_claimed_ready(self):
        config = DatabaseConfig.from_value(
            "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
        )
        fake = DatabaseConnection(config, object())
        with self.assertRaises(UnsupportedDatabaseOperation):
            fake.executescript("CREATE TABLE unsupported (id INTEGER)")


if __name__ == "__main__":
    unittest.main()
