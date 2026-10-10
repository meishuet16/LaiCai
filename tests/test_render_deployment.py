import io
import importlib
import json
import sqlite3
import sys

import pytest

import retaniq.api as api
from retaniq.api import create_app
from retaniq.database_config import DatabaseConfig


def request(app, method, path):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = json.loads(b"".join(app(environ, start_response)))
    return response


def test_healthz_returns_ok_without_authentication(tmp_path):
    app = create_app(DatabaseConfig.from_value(tmp_path / "health.sqlite3"))
    response = request(app, "GET", "/healthz")
    assert response["status"] == "200 OK"
    assert response["body"] == {"status": "ok"}


@pytest.fixture
def load_render_wsgi():
    sys.modules.pop("render_wsgi", None)
    yield lambda: importlib.import_module("render_wsgi")
    sys.modules.pop("render_wsgi", None)


def test_wsgi_startup_initializes_selected_sqlite_file(tmp_path, monkeypatch, load_render_wsgi):
    database_path = tmp_path / "render.sqlite3"
    monkeypatch.setenv("RETAINIQ_DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("RETAINIQ_SQLITE_PATH", str(database_path))
    monkeypatch.delenv("RETAINIQ_DATABASE_URL", raising=False)

    application = load_render_wsgi().application

    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone() == ("schema_migrations",)
    assert request(application, "GET", "/healthz")["status"] == "200 OK"


def test_wsgi_startup_selects_supabase_configuration(monkeypatch, load_render_wsgi):
    project_ref = "a" * 20
    app_dsn = f"postgresql://app:fake-only@db.{project_ref}.supabase.co:5432/postgres?sslmode=require"
    monkeypatch.setenv("RETAINIQ_DATABASE_BACKEND", "supabase")
    monkeypatch.setenv("RETAINIQ_SUPABASE_PROJECT_URL", f"https://{project_ref}.supabase.co")
    monkeypatch.setenv("RETAINIQ_SUPABASE_EXPECTED_PROJECT_REF", project_ref)
    monkeypatch.setenv("RETAINIQ_SUPABASE_CONNECTION_MODE", "DIRECT")
    monkeypatch.setenv("RETAINIQ_SUPABASE_DB_APP_DSN", app_dsn)
    monkeypatch.delenv("RETAINIQ_DATABASE_URL", raising=False)
    monkeypatch.delenv("RETAINIQ_SQLITE_PATH", raising=False)
    monkeypatch.delenv("RETAINIQ_SUPABASE_DB_MIGRATION_DSN", raising=False)
    monkeypatch.delenv("RETAINIQ_SUPABASE_DB_MAINTENANCE_DSN", raising=False)
    received = []
    application = object()

    def fake_create_app(config):
        received.append(config)
        return application

    monkeypatch.setattr(api, "create_app", fake_create_app)

    assert load_render_wsgi().application is application
    assert len(received) == 1
    assert isinstance(received[0], DatabaseConfig)
    assert received[0].is_supabase
    assert received[0].is_postgresql
    assert received[0].postgresql_dsn == app_dsn
