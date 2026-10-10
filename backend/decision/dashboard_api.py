"""Dashboard adapter for the authenticated evaluation dataset."""

from fastapi import APIRouter, Body, HTTPException

from .dashboard_data import (
    DashboardDataUnavailable,
    load_dashboard_accounts,
    load_dashboard_cases,
    load_integration_overview,
    load_learning_overview,
    record_dashboard_decision,
    record_dashboard_execution,
    record_dashboard_follow_up,
)


router = APIRouter(prefix="/v1/dashboard", tags=["Dashboard"])


@router.get("/accounts", summary="List accounts from the authenticated backend dataset")
def list_dashboard_accounts() -> dict:
    try:
        return load_dashboard_accounts()
    except DashboardDataUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Authenticated backend dataset is not available.",
        ) from error


@router.get("/integrations", summary="Read source health and coverage from SQLite")
def dashboard_integrations() -> dict:
    try:
        return load_integration_overview()
    except DashboardDataUnavailable as error:
        raise HTTPException(status_code=503, detail="Integration health is not available.") from error


@router.get("/cases", summary="List persisted retention cases and capacity")
def dashboard_cases() -> dict:
    try:
        return load_dashboard_cases()
    except DashboardDataUnavailable as error:
        raise HTTPException(status_code=503, detail="Retention cases are not available.") from error


def _mutation_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail="Case not found.")
    if isinstance(error, ValueError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=503, detail="The case update could not be stored.")


@router.post("/cases/{case_id}/decision", summary="Persist a human decision")
def dashboard_case_decision(case_id: str, payload: dict = Body(...)) -> dict:
    try:
        return record_dashboard_decision(case_id, payload)
    except Exception as error:
        raise _mutation_error(error) from error


@router.post("/cases/{case_id}/execution", summary="Persist execution evidence")
def dashboard_case_execution(case_id: str, payload: dict = Body(...)) -> dict:
    try:
        return record_dashboard_execution(case_id, payload)
    except Exception as error:
        raise _mutation_error(error) from error


@router.post("/cases/{case_id}/follow-up", summary="Persist follow-up evidence")
def dashboard_case_follow_up(case_id: str, payload: dict = Body(...)) -> dict:
    try:
        return record_dashboard_follow_up(case_id, payload)
    except Exception as error:
        raise _mutation_error(error) from error


@router.get("/learning", summary="Read outcome maturity and model governance")
def dashboard_learning() -> dict:
    try:
        return load_learning_overview()
    except DashboardDataUnavailable as error:
        raise HTTPException(status_code=503, detail="Learning status is not available.") from error
