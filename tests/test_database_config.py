import tempfile
import unittest
from pathlib import Path

from retaniq.database_config import (
    DatabaseConfig,
    DatabaseConfigurationError,
    POSTGRESQL_BACKEND,
    SQLITE_BACKEND,
)


class DatabaseConfigTests(unittest.TestCase):
    def test_existing_sqlite_path_is_backward_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retaniq.sqlite3"
            config = DatabaseConfig.from_value(path)
        self.assertEqual(config.backend, SQLITE_BACKEND)
        self.assertEqual(config.sqlite_path, str(path))

    def test_windows_sqlite_path_is_not_misread_as_a_url_scheme(self):
        path = r"C:\Users\User\RetainIQ\data\retaniq.sqlite3"
        config = DatabaseConfig.from_value(path)
        self.assertEqual(config.backend, SQLITE_BACKEND)
        self.assertEqual(config.sqlite_path, path)

    def test_sqlite_url_and_in_memory_database_are_supported(self):
        file_config = DatabaseConfig.from_value("sqlite:///C:/RetainIQ/data/retaniq.sqlite3")
        memory_config = DatabaseConfig.from_value("sqlite:///:memory:")
        self.assertEqual(file_config.sqlite_path, "C:/RetainIQ/data/retaniq.sqlite3")
        self.assertEqual(memory_config.sqlite_path, ":memory:")

    def test_environment_configuration_is_explicit(self):
        config = DatabaseConfig.from_environment({"RETAINIQ_DATABASE_URL": "sqlite:///:memory:"})
        self.assertEqual(config.sqlite_path, ":memory:")
        config = DatabaseConfig.from_environment(
            {
                "RETAINIQ_DATABASE_BACKEND": "sqlite",
                "RETAINIQ_SQLITE_PATH": r"C:\data\retaniq.sqlite3",
            },
        )
        self.assertEqual(config.sqlite_path, r"C:\data\retaniq.sqlite3")
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment({})

    def test_environment_backend_must_match_environment_url(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_environment(
                {
                    "RETAINIQ_DATABASE_BACKEND": "sqlite",
                    "RETAINIQ_DATABASE_URL": "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
                },
            )

    def test_secure_postgresql_dsn_is_recognized(self):
        config = DatabaseConfig.from_value(
            "postgresql://alice:s3cret@db.example.test:5432/retaniq?sslmode=verify-full",
        )
        self.assertEqual(config.backend, POSTGRESQL_BACKEND)
        self.assertIn("db.example.test", config.postgresql_dsn)
        self.assertNotIn("s3cret", repr(config))
        self.assertIn("***", repr(config))

    def test_local_insecure_postgresql_requires_an_explicit_test_opt_in(self):
        dsn = "postgresql://alice:s3cret@localhost:5432/retaniq?sslmode=disable"
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_value(dsn)
        config = DatabaseConfig.from_value(dsn, allow_insecure_local_postgresql=True)
        self.assertTrue(config.is_postgresql)

    def test_invalid_schemes_and_empty_targets_are_rejected(self):
        for value in ("", "mysql://user:pass@host/db", "postgres://user:pass@host/db"):
            with self.subTest(value=value):
                with self.assertRaises(DatabaseConfigurationError):
                    DatabaseConfig.from_value(value)

    def test_explicit_postgresql_never_falls_back_to_a_filesystem_path(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_value(r"C:\temp\retaniq.sqlite3", backend="postgresql")

    def test_direct_config_constructor_rejects_a_foreign_backend_url(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig(
                SQLITE_BACKEND,
                "postgresql://alice:secret@db.example.test/retaniq?sslmode=verify-full",
            )

    def test_postgresql_dsn_requires_secure_remote_tls(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_value("postgresql://alice:secret@db.example.test/retaniq")
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseConfig.from_value(
                "postgresql://alice:secret@db.example.test/retaniq?sslmode=disable",
            )

    def test_parsing_does_not_create_a_database_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-created.sqlite3"
            DatabaseConfig.from_value(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
