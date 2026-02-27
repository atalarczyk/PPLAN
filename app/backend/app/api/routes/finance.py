"""Finance domain endpoints: rates and financial registers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.models.entities import MoneyCurrency, RateUnit
from app.services.finance_reporting_service import (
    FinanceReportingService,
    FinancialRequestCreateData,
    InvoiceCreateData,
    RateEntryInput,
    RevenueCreateData,
)

router = APIRouter(tags=["finance"])


class RateEntryPayload(BaseModel):
    performer_id: UUID
    project_id: UUID | None = None
    rate_unit: RateUnit
    rate_value: Decimal = Field(ge=0)
    effective_from_month: date
    effective_to_month: date | None = None


class RatesBulkUpsertPayload(BaseModel):
    entries: list[RateEntryPayload]


class FinancialRequestCreatePayload(BaseModel):
    request_no: str = Field(min_length=1, max_length=128)
    request_date: date
    month_start: date
    amount: Decimal = Field(ge=0)
    currency: MoneyCurrency = MoneyCurrency.PLN
    status: str = Field(default="draft", min_length=1, max_length=32)


class InvoiceCreatePayload(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=128)
    invoice_date: date
    month_start: date
    amount: Decimal = Field(ge=0)
    currency: MoneyCurrency = MoneyCurrency.PLN
    payment_status: str = Field(default="unpaid", min_length=1, max_length=32)
    payment_date: date | None = None


class RevenueCreatePayload(BaseModel):
    revenue_no: str = Field(min_length=1, max_length=128)
    recognition_date: date
    month_start: date
    amount: Decimal = Field(ge=0)
    currency: MoneyCurrency = MoneyCurrency.PLN


def _finance_service(db: Session) -> FinanceReportingService:
    return FinanceReportingService(db)


@router.get("/projects/{project_id}/rates")
def get_project_rates(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    rows = service.list_rates(context=context, project_id=project_id)
    return {"items": [service.serialize_rate(row) for row in rows]}


@router.get("/projects/{project_id}/finance-summary")
def get_project_finance_summary(
    project_id: UUID,
    from_month: date | None = None,
    to_month: date | None = None,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    return service.project_finance_summary(
        context=context,
        project_id=project_id,
        from_month=from_month,
        to_month=to_month,
    )


@router.put("/projects/{project_id}/rates/entries:bulk")
@router.put("/projects/{project_id}/rates/entries/bulk")
def put_project_rates_bulk(
    project_id: UUID,
    payload: RatesBulkUpsertPayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    rows = service.bulk_upsert_rates(
        context=context,
        project_id=project_id,
        entries=[
            RateEntryInput(
                performer_id=item.performer_id,
                project_id=item.project_id,
                rate_unit=item.rate_unit,
                rate_value=item.rate_value,
                effective_from_month=item.effective_from_month,
                effective_to_month=item.effective_to_month,
            )
            for item in payload.entries
        ],
    )
    return {"updated_entries": len(rows), "items": [service.serialize_rate(row) for row in rows]}


@router.get("/projects/{project_id}/financial-requests")
def list_financial_requests(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    rows = service.list_financial_requests(context=context, project_id=project_id)
    return {"items": [service.serialize_financial_request(row) for row in rows]}


@router.post("/projects/{project_id}/financial-requests", status_code=201)
def create_financial_request(
    project_id: UUID,
    payload: FinancialRequestCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    row = service.create_financial_request(
        context=context,
        project_id=project_id,
        data=FinancialRequestCreateData(
            request_no=payload.request_no,
            request_date=payload.request_date,
            month_start=payload.month_start,
            amount=payload.amount,
            currency=payload.currency,
            status=payload.status,
        ),
    )
    return service.serialize_financial_request(row)


@router.get("/projects/{project_id}/invoices")
def list_invoices(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    rows = service.list_invoices(context=context, project_id=project_id)
    return {"items": [service.serialize_invoice(row) for row in rows]}


@router.post("/projects/{project_id}/invoices", status_code=201)
def create_invoice(
    project_id: UUID,
    payload: InvoiceCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    row = service.create_invoice(
        context=context,
        project_id=project_id,
        data=InvoiceCreateData(
            invoice_no=payload.invoice_no,
            invoice_date=payload.invoice_date,
            month_start=payload.month_start,
            amount=payload.amount,
            currency=payload.currency,
            payment_status=payload.payment_status,
            payment_date=payload.payment_date,
        ),
    )
    return service.serialize_invoice(row)


@router.get("/projects/{project_id}/revenues")
def list_revenues(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    rows = service.list_revenues(context=context, project_id=project_id)
    return {"items": [service.serialize_revenue(row) for row in rows]}


@router.post("/projects/{project_id}/revenues", status_code=201)
def create_revenue(
    project_id: UUID,
    payload: RevenueCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _finance_service(db)
    row = service.create_revenue(
        context=context,
        project_id=project_id,
        data=RevenueCreateData(
            revenue_no=payload.revenue_no,
            recognition_date=payload.recognition_date,
            month_start=payload.month_start,
            amount=payload.amount,
            currency=payload.currency,
        ),
    )
    return service.serialize_revenue(row)
