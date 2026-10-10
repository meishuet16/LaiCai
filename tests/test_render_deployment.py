import io
import json

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
