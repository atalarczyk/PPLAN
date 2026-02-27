"""Matrix read/write endpoints for planning and execution domain."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.services.planning_service import MatrixEntryInput, PlanningService

router = APIRouter(tags=["matrix"])


class MatrixBulkEntryPayload(BaseModel):
    task_id: UUID
    performer_id: UUID
    month_start: date
    planned_person_days: Decimal
    actual_person_days: Decimal


class MatrixBulkUpsertPayload(BaseModel):
    entries: list[MatrixBulkEntryPayload]


def _planning_service(db: Session) -> PlanningService:
    return PlanningService(db)


@router.get("/projects/{project_id}/matrix")
def get_project_matrix(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    return service.read_matrix(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
    )


@router.put("/projects/{project_id}/matrix/entries:bulk")
@router.put("/projects/{project_id}/matrix/entries/bulk")
def put_matrix_entries_bulk(
    project_id: UUID,
    payload: MatrixBulkUpsertPayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    result = service.bulk_upsert_matrix_entries(
        context=context,
        project_id=project_id,
        entries=[
            MatrixEntryInput(
                task_id=entry.task_id,
                performer_id=entry.performer_id,
                month_start=entry.month_start,
                planned_person_days=entry.planned_person_days,
                actual_person_days=entry.actual_person_days,
            )
            for entry in payload.entries
        ],
    )
    return {
        "updated_entries": result.updated_entries,
        "project_monthly_snapshots": [
            {
                "month_start": snapshot.month_start.isoformat(),
                "planned_person_days": str(snapshot.planned_person_days),
                "actual_person_days": str(snapshot.actual_person_days),
                "planned_cost": str(snapshot.planned_cost),
                "actual_cost": str(snapshot.actual_cost),
                "revenue_amount": str(snapshot.revenue_amount),
                "invoice_amount": str(snapshot.invoice_amount),
                "cumulative_planned_cost": str(snapshot.cumulative_planned_cost),
                "cumulative_actual_cost": str(snapshot.cumulative_actual_cost),
                "cumulative_revenue": str(snapshot.cumulative_revenue),
            }
            for snapshot in result.snapshots
        ],
    }
