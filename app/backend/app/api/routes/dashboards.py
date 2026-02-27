"""Dashboard endpoints for project and business-unit trends."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.services.finance_reporting_service import FinanceReportingService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


def _service(db: Session) -> FinanceReportingService:
    return FinanceReportingService(db)


@router.get("/projects/{project_id}")
def get_project_dashboard(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.project_dashboard(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
    )


@router.get("/business-units/{business_unit_id}")
def get_business_unit_dashboard(
    business_unit_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _service(db)
    return service.business_unit_dashboard(
        context=context,
        business_unit_id=business_unit_id,
        from_month=from_month,
        to_month=to_month,
    )

