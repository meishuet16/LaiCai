"""Small WSGI surface for the two Part 1 public endpoints."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import parse_qs, unquote

from .data_foundation import (
    DataFoundationError,
    SAFE_MESSAGES,
    authenticate_integration,
    authenticate_service_principal,
    get_integration_health,
    get_tenant_integration_health,
    get_account_snapshot_as_of,
    get_observation_coverage_as_of,
    get_prediction_by_id,
    get_prediction_history,
    ingest_event,
    record_integration_failure,
    initialize_database,
)
from .database_config import DatabaseConfig, resolve_database_config
from .postgresql_migrations import verify_postgresql_schema

logger = logging.getLogger("retaniq.api")
MAX_BODY_BYTES = 64 * 1024
MAX_QUERY_BYTES = 2048


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


def create_app(database_path: str | DatabaseConfig):
    database = resolve_database_config(database_path)
    if database.is_postgresql:
        verify_postgresql_schema(database)
    else:
        initialize_database(database)

    def application(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "")
        query_string = environ.get("QUERY_STRING", "")
        prediction_id = None
        history_account_id = None
        data_account_id = None
        if path.startswith("/v1/predictions/") and len(path) > len("/v1/predictions/"):
            prediction_id = unquote(path[len("/v1/predictions/"):])
        elif path.startswith("/v1/data/accounts/") and path.endswith("/history"):
            data_account_id = unquote(path[len("/v1/data/accounts/"):-len("/history")].strip("/"))
        elif path == "/v1/predictions":
            history_account_id = True
        allowed = {
            ("POST", "/v1/ingest/events"), ("GET", "/v1/integrations"),
            ("GET", "/v1/admin/integrations"), ("GET", "/v1/predictions"),
        }
        if prediction_id is not None:
            allowed.add(("GET", path))
        if data_account_id is not None:
            allowed.add(("GET", path))
        if (method, path) not in allowed:
            return _response(start_response, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        principal = None
        try:
            if len(query_string.encode("utf-8")) > MAX_QUERY_BYTES:
                raise DataFoundationError("invalid_contract")
            try:
                query = parse_qs(query_string, keep_blank_values=True, strict_parsing=True)
            except ValueError:
                raise DataFoundationError("invalid_contract") from None
            if prediction_id is not None:
                if query:
                    raise DataFoundationError("invalid_contract")
                principal = authenticate_service_principal(database, _bearer(environ))
                return _response(start_response, HTTPStatus.OK, {
                    "prediction": get_prediction_by_id(database, principal, prediction_id),
                })
            if history_account_id is not None:
                if set(query) - {"customer_id", "limit", "offset"} or any(len(values) != 1 for values in query.values()):
                    raise DataFoundationError("invalid_contract")
                customer_ids = query.get("customer_id", [])
                if len(customer_ids) != 1 or not customer_ids[0]:
                    raise DataFoundationError("invalid_contract")
                try:
                    limit = int(query.get("limit", ["25"])[0])
                    offset = int(query.get("offset", ["0"])[0])
                except ValueError:
                    raise DataFoundationError("invalid_contract") from None
                principal = authenticate_service_principal(database, _bearer(environ))
                return _response(start_response, HTTPStatus.OK, get_prediction_history(
                    database, principal, customer_ids[0], limit=limit, offset=offset,
                ))
            if data_account_id is not None:
                if set(query) != {"as_of"} or len(query["as_of"]) != 1 or not query["as_of"][0]:
                    raise DataFoundationError("invalid_contract")
                principal = authenticate_service_principal(database, _bearer(environ))
                if (principal.role != "analyst" or "retention_inference" not in principal.authorized_purposes
                        or "billing_valuation" in principal.authorized_purposes):
                    raise DataFoundationError("purpose_not_authorized")
                cutoff = query["as_of"][0]
                cutoff_candidate = cutoff[:-1] + "+00:00" if cutoff.endswith("Z") else cutoff
                try:
                    parsed_cutoff = datetime.fromisoformat(cutoff_candidate)
                except (ValueError, OverflowError):
                    raise DataFoundationError("invalid_contract") from None
                if parsed_cutoff.tzinfo is None or parsed_cutoff > datetime.now(timezone.utc):
                    raise DataFoundationError("invalid_contract")
                account = get_account_snapshot_as_of(database, principal, data_account_id, cutoff)
                coverage = get_observation_coverage_as_of(database, principal, data_account_id, cutoff)
                return _response(start_response, HTTPStatus.OK, {
                    "account": account,
                    "source_coverage": coverage,
                    "cutoff": {"as_of": account["as_of"], "input_data_as_of": account["input_data_as_of"]},
                    "source_freshness_status": "unknown",
                })
            if (method, path) == ("GET", "/v1/admin/integrations"):
                principal = authenticate_service_principal(database, _bearer(environ))
                return _response(
                    start_response, HTTPStatus.OK,
                    {"integrations": get_tenant_integration_health(database, principal)},
                )
            principal = authenticate_integration(database, _bearer(environ))
            if method == "GET":
                return _response(start_response, HTTPStatus.OK, {"integrations": get_integration_health(database, principal)})

            content_length = environ.get("CONTENT_LENGTH", "")
            if not content_length.isdigit() or int(content_length) <= 0 or int(content_length) > MAX_BODY_BYTES:
                record_integration_failure(database, principal, "invalid_event")
                raise DataFoundationError("invalid_event")
            if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
                record_integration_failure(database, principal, "invalid_event")
                raise DataFoundationError("invalid_event")
            try:
                raw = environ["wsgi.input"].read(int(content_length))
                payload = json.loads(raw.decode("utf-8"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                record_integration_failure(database, principal, "invalid_event")
                raise DataFoundationError("invalid_event") from None
            result = ingest_event(database, principal, payload)
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
                    record_integration_failure(database, principal, "invalid_event")
                except DataFoundationError:
                    pass
            return _response(start_response, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

    return application
