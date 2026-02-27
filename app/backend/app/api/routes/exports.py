"""Export endpoint for report datasets."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.services.finance_reporting_service import FinanceReportingService

router = APIRouter(prefix="/exports", tags=["exports"])


def _service(db: Session) -> FinanceReportingService:
    return FinanceReportingService(db)


@router.get("/{report_key}")
def export_report(
    report_key: str,
    format: str = Query(default="xlsx"),
    project_id: UUID = Query(...),
    from_month: date | None = Query(default=None),
    to_month: date | None = Query(default=None),
    performer_id: list[UUID] | None = Query(default=None),
    task_id: list[UUID] | None = Query(default=None),
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _service(db)
    exported = service.export_report(
        context=context,
        report_key=report_key,
        format_name=format,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
        performer_ids=performer_id,
        task_ids=task_id,
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )
