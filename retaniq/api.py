"""Small WSGI surface for the two Part 1 public endpoints."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import Any, Callable

from .data_foundation import (
    DataFoundationError,
    SAFE_MESSAGES,
    authenticate_integration,
    authenticate_service_principal,
    get_integration_health,
    get_tenant_integration_health,
    ingest_event,
    record_integration_failure,
    initialize_database,
)

logger = logging.getLogger("retaniq.api")
MAX_BODY_BYTES = 64 * 1024


def _response(start_response: Callable, status: HTTPStatus, payload: dict[str, Any]):
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body))),
         ("Cache-Control", "no-store")],
    )
    return [body]


def _bearer(environ: dict[str, Any]) -> str | None:
    header = environ.get("HTTP_AUTHORIZATION", "")
    if not isinstance(header, str) or not header.startswith("Bearer "):
        return None
    token = header[7:]
    return token if token and " " not in token else None


def _status_for(error: DataFoundationError) -> HTTPStatus:
    return {
        "unauthorized": HTTPStatus.UNAUTHORIZED,
        "source_not_authorized": HTTPStatus.FORBIDDEN,
        "event_category_not_authorized": HTTPStatus.FORBIDDEN,
        "purpose_not_authorized": HTTPStatus.FORBIDDEN,
        "identity_not_mapped": HTTPStatus.UNPROCESSABLE_ENTITY,
        "idempotency_conflict": HTTPStatus.CONFLICT,
        "contract_conflict": HTTPStatus.CONFLICT,
        "not_found": HTTPStatus.NOT_FOUND,
        "invalid_contract": HTTPStatus.BAD_REQUEST,
        "invalid_import_mapping": HTTPStatus.BAD_REQUEST,
        "invalid_csv": HTTPStatus.BAD_REQUEST,
    }.get(error.code, HTTPStatus.BAD_REQUEST)


def create_app(database_path: str):
    initialize_database(database_path)

    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "")
        if (method, path) not in {
            ("POST", "/v1/ingest/events"), ("GET", "/v1/integrations"),
            ("GET", "/v1/admin/integrations"),
        }:
            return _response(start_response, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        principal = None
        try:
            if (method, path) == ("GET", "/v1/admin/integrations"):
                principal = authenticate_service_principal(database_path, _bearer(environ))
                return _response(
                    start_response, HTTPStatus.OK,
                    {"integrations": get_tenant_integration_health(database_path, principal)},
                )
            principal = authenticate_integration(database_path, _bearer(environ))
            if method == "GET":
                return _response(start_response, HTTPStatus.OK, {"integrations": get_integration_health(database_path, principal)})

            content_length = environ.get("CONTENT_LENGTH", "")
            if not content_length.isdigit() or int(content_length) <= 0 or int(content_length) > MAX_BODY_BYTES:
                record_integration_failure(database_path, principal, "invalid_event")
                raise DataFoundationError("invalid_event")
            if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
                record_integration_failure(database_path, principal, "invalid_event")
                raise DataFoundationError("invalid_event")
            try:
                raw = environ["wsgi.input"].read(int(content_length))
                payload = json.loads(raw.decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                record_integration_failure(database_path, principal, "invalid_event")
                raise DataFoundationError("invalid_event") from None
            result = ingest_event(database_path, principal, payload)
            status = HTTPStatus.OK if result["duplicate"] else HTTPStatus.CREATED
            return _response(start_response, status, result)
        except DataFoundationError as error:
            # Only static error codes are logged; request bodies, credentials, and field values are never logged.
            logger.warning("request rejected: %s", error.code)
            return _response(start_response, _status_for(error), {"error": error.code, "message": SAFE_MESSAGES[error.code]})
        except Exception:
            logger.error("request failed: internal_error")
            if principal is not None and method == "POST":
                try:
                    record_integration_failure(database_path, principal, "invalid_event")
                except DataFoundationError:
                    pass
            return _response(start_response, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

    return application
