"""Reporting endpoints for effort and cost analytics."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.services.finance_reporting_service import FinanceReportingService

router = APIRouter(prefix="/reports", tags=["reports"])


def _service(db: Session) -> FinanceReportingService:
    return FinanceReportingService(db)


@router.get("/projects/{project_id}/effort-by-performer")
def report_effort_by_performer(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    performer_id: list[UUID] | None = Query(default=None),
    task_id: list[UUID] | None = Query(default=None),
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.effort_report_by_performer(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
        performer_ids=performer_id,
        task_ids=task_id,
    )


@router.get("/projects/{project_id}/effort-by-task")
def report_effort_by_task(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    performer_id: list[UUID] | None = Query(default=None),
    task_id: list[UUID] | None = Query(default=None),
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.effort_report_by_task(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
        performer_ids=performer_id,
        task_ids=task_id,
    )


@router.get("/projects/{project_id}/cost-by-performer")
def report_cost_by_performer(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    performer_id: list[UUID] | None = Query(default=None),
    task_id: list[UUID] | None = Query(default=None),
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.cost_report_by_performer(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
        performer_ids=performer_id,
        task_ids=task_id,
    )


@router.get("/projects/{project_id}/cost-by-task")
def report_cost_by_task(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    performer_id: list[UUID] | None = Query(default=None),
    task_id: list[UUID] | None = Query(default=None),
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.cost_report_by_task(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
        performer_ids=performer_id,
        task_ids=task_id,
    )
