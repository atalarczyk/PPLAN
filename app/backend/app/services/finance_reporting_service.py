"""Finance, reporting, dashboard, and export service layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AppRole, RequestUserContext, has_business_unit_access
from app.core.config import get_settings
from app.models.entities import FinancialRequest, Invoice, MoneyCurrency, PerformerRate, Project, RateUnit, Revenue
from app.repositories.planning_repository import PlanningRepository
from app.services.planning_service import PlanningService, month_sequence, normalize_month_start

EDIT_ROLES = {AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN, AppRole.EDITOR}
VIEW_ROLES = {AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN, AppRole.EDITOR, AppRole.VIEWER}

ZERO = Decimal("0.00")
Q2 = Decimal("0.01")


@dataclass(slots=True)
class RateEntryInput:
    performer_id: UUID
    project_id: UUID | None
    rate_unit: RateUnit
    rate_value: Decimal
    effective_from_month: date
    effective_to_month: date | None


@dataclass(slots=True)
class FinancialRequestCreateData:
    request_no: str
    request_date: date
    month_start: date
    amount: Decimal
    currency: MoneyCurrency
    status: str


@dataclass(slots=True)
class InvoiceCreateData:
    invoice_no: str
    invoice_date: date
    month_start: date
    amount: Decimal
    currency: MoneyCurrency
    payment_status: str
    payment_date: date | None


@dataclass(slots=True)
class RevenueCreateData:
    revenue_no: str
    recognition_date: date
    month_start: date
    amount: Decimal
    currency: MoneyCurrency


@dataclass(slots=True)
class ExportFilePayload:
    media_type: str
    filename: str
    content: bytes


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Q2)


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == ZERO:
        return ZERO
    return (numerator / denominator).quantize(Q2)


class FinanceReportingService:
    """Service implementing phase-3 finance and analytics contracts."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PlanningRepository(db)
        self.settings = get_settings()

    # ---------- Access / scope ----------
    def _ensure_project_access(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        allowed_roles: set[AppRole],
    ) -> Project:
        project = self.repo.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        if not has_business_unit_access(
            context,
            business_unit_id=project.business_unit_id,
            allowed_roles=allowed_roles,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business unit scope permissions for this operation.",
            )
        return project

    def _ensure_business_unit_view_access(self, *, context: RequestUserContext, business_unit_id: UUID) -> None:
        if not has_business_unit_access(
            context,
            business_unit_id=business_unit_id,
            allowed_roles=VIEW_ROLES,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business unit scope permissions for this operation.",
            )

    # ---------- Serialization ----------
    @staticmethod
    def serialize_rate(rate: PerformerRate) -> dict[str, object]:
        return {
            "id": str(rate.id),
            "business_unit_id": str(rate.business_unit_id),
            "performer_id": str(rate.performer_id),
            "project_id": str(rate.project_id) if rate.project_id is not None else None,
            "rate_unit": rate.rate_unit.value,
            "rate_value": str(rate.rate_value),
            "effective_from_month": rate.effective_from_month.isoformat(),
            "effective_to_month": rate.effective_to_month.isoformat() if rate.effective_to_month else None,
        }

    @staticmethod
    def serialize_financial_request(row: FinancialRequest) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "request_no": row.request_no,
            "request_date": row.request_date.isoformat(),
            "month_start": row.month_start.isoformat(),
            "amount": str(row.amount),
            "currency": row.currency.value,
            "status": row.status,
        }

    @staticmethod
    def serialize_invoice(row: Invoice) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "invoice_no": row.invoice_no,
            "invoice_date": row.invoice_date.isoformat(),
            "month_start": row.month_start.isoformat(),
            "amount": str(row.amount),
            "currency": row.currency.value,
            "payment_status": row.payment_status,
            "payment_date": row.payment_date.isoformat() if row.payment_date else None,
        }

    @staticmethod
    def serialize_revenue(row: Revenue) -> dict[str, object]:
        return {
            "id": str(row.id),
            "project_id": str(row.project_id),
            "revenue_no": row.revenue_no,
            "recognition_date": row.recognition_date.isoformat(),
            "month_start": row.month_start.isoformat(),
            "amount": str(row.amount),
            "currency": row.currency.value,
        }

    # ---------- Rate logic ----------
    @staticmethod
    def _validate_rate_range(*, effective_from_month: date, effective_to_month: date | None) -> None:
        if effective_to_month is not None and effective_to_month < effective_from_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="effective_to_month must be greater than or equal to effective_from_month.",
            )

    @staticmethod
    def _validate_non_negative_amount(value: Decimal, field_name: str) -> None:
        if value < ZERO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} must be greater or equal zero.",
            )

    @staticmethod
    def _covers_month(rate: PerformerRate, month_start: date) -> bool:
        if month_start < rate.effective_from_month:
            return False
        if rate.effective_to_month is not None and month_start > rate.effective_to_month:
            return False
        return True

    def _resolve_effective_rate(
        self,
        *,
        rates_by_performer: dict[UUID, list[PerformerRate]],
        performer_id: UUID,
        month_start: date,
        project_id: UUID,
    ) -> PerformerRate | None:
        candidates = rates_by_performer.get(performer_id, [])
        project_specific = [
            rate
            for rate in candidates
            if rate.project_id == project_id and self._covers_month(rate, month_start)
        ]
        if project_specific:
            project_specific.sort(
                key=lambda row: (
                    row.effective_from_month,
                    row.effective_to_month or date.max,
                    str(row.id),
                ),
                reverse=True,
            )
            return project_specific[0]

        defaults = [
            rate
            for rate in candidates
            if rate.project_id is None and self._covers_month(rate, month_start)
        ]
        if not defaults:
            return None
        defaults.sort(
            key=lambda row: (
                row.effective_from_month,
                row.effective_to_month or date.max,
                str(row.id),
            ),
            reverse=True,
        )
        return defaults[0]

    def _rate_value_per_day(self, rate: PerformerRate) -> Decimal:
        if rate.rate_unit is RateUnit.DAY:
            return _q2(rate.rate_value)
        divisor = Decimal(str(self.settings.cost_fte_month_working_days))
        return _q2(rate.rate_value / divisor)

    def _project_rates_by_performer(self, project: Project) -> dict[UUID, list[PerformerRate]]:
        rates = self.repo.list_rates_for_business_unit(project.business_unit_id, project_id=project.id)
        rates_by_performer: dict[UUID, list[PerformerRate]] = {}
        for rate in rates:
            rates_by_performer.setdefault(rate.performer_id, []).append(rate)
        return rates_by_performer

    def _project_cost_entry_rows(
        self,
        *,
        project: Project,
        from_month: date,
        to_month: date,
        performer_filter_set: set[UUID] | None = None,
        task_filter_set: set[UUID] | None = None,
    ) -> list[dict[str, object]]:
        effort_entries = self.repo.list_effort_entries_filtered(
            project.id,
            from_month=from_month,
            to_month=to_month,
            task_ids=task_filter_set,
            performer_ids=performer_filter_set,
        )
        rates_by_performer = self._project_rates_by_performer(project)

        computed: list[dict[str, object]] = []
        for entry in effort_entries:
            rate = self._resolve_effective_rate(
                rates_by_performer=rates_by_performer,
                performer_id=entry.performer_id,
                month_start=entry.month_start,
                project_id=project.id,
            )
            if rate is None:
                per_day = ZERO
                rate_unit = None
            else:
                per_day = self._rate_value_per_day(rate)
                rate_unit = rate.rate_unit.value

            planned_cost = _q2(entry.planned_person_days * per_day)
            actual_cost = _q2(entry.actual_person_days * per_day)
            computed.append(
                {
                    "task_id": entry.task_id,
                    "performer_id": entry.performer_id,
                    "month_start": entry.month_start,
                    "planned_person_days": entry.planned_person_days,
                    "actual_person_days": entry.actual_person_days,
                    "planned_cost": planned_cost,
                    "actual_cost": actual_cost,
                    "rate_value_per_day": per_day,
                    "rate_unit": rate_unit,
                }
            )
        return computed

    def _project_monthly_rollups(
        self,
        *,
        project: Project,
        from_month: date,
        to_month: date,
    ) -> list[dict[str, object]]:
        months = month_sequence(from_month, to_month)
        cost_rows = self._project_cost_entry_rows(
            project=project,
            from_month=from_month,
            to_month=to_month,
        )

        effort_and_cost_by_month: dict[date, dict[str, Decimal]] = {
            month: {
                "planned_person_days": ZERO,
                "actual_person_days": ZERO,
                "planned_cost": ZERO,
                "actual_cost": ZERO,
            }
            for month in months
        }
        for row in cost_rows:
            month_key = row["month_start"]
            bucket = effort_and_cost_by_month.setdefault(
                month_key,
                {
                    "planned_person_days": ZERO,
                    "actual_person_days": ZERO,
                    "planned_cost": ZERO,
                    "actual_cost": ZERO,
                },
            )
            bucket["planned_person_days"] += row["planned_person_days"]
            bucket["actual_person_days"] += row["actual_person_days"]
            bucket["planned_cost"] += row["planned_cost"]
            bucket["actual_cost"] += row["actual_cost"]

        invoices = self.repo.aggregate_invoices_by_month(project.id)
        revenues = self.repo.aggregate_revenues_by_month(project.id)

        cumulative_planned_cost = ZERO
        cumulative_actual_cost = ZERO
        cumulative_revenue = ZERO
        output: list[dict[str, object]] = []

        for month in months:
            bucket = effort_and_cost_by_month.get(month) or {
                "planned_person_days": ZERO,
                "actual_person_days": ZERO,
                "planned_cost": ZERO,
                "actual_cost": ZERO,
            }
            planned_pd = _q2(bucket["planned_person_days"])
            actual_pd = _q2(bucket["actual_person_days"])
            planned_cost = _q2(bucket["planned_cost"])
            actual_cost = _q2(bucket["actual_cost"])
            invoice_amount = _q2(invoices.get(month, ZERO))
            revenue_amount = _q2(revenues.get(month, ZERO))

            cumulative_planned_cost = _q2(cumulative_planned_cost + planned_cost)
            cumulative_actual_cost = _q2(cumulative_actual_cost + actual_cost)
            cumulative_revenue = _q2(cumulative_revenue + revenue_amount)

            output.append(
                {
                    "month_start": month,
                    "planned_person_days": planned_pd,
                    "actual_person_days": actual_pd,
                    "planned_cost": planned_cost,
                    "actual_cost": actual_cost,
                    "invoice_amount": invoice_amount,
                    "revenue_amount": revenue_amount,
                    "cumulative_planned_cost": cumulative_planned_cost,
                    "cumulative_actual_cost": cumulative_actual_cost,
                    "cumulative_revenue": cumulative_revenue,
                }
            )
        return output

    @staticmethod
    def _rollups_to_serializable(rollups: list[dict[str, object]]) -> list[dict[str, str]]:
        return [
            {
                "month_start": row["month_start"].isoformat(),
                "planned_person_days": str(row["planned_person_days"]),
                "actual_person_days": str(row["actual_person_days"]),
                "planned_cost": str(row["planned_cost"]),
                "actual_cost": str(row["actual_cost"]),
                "invoice_amount": str(row["invoice_amount"]),
                "revenue_amount": str(row["revenue_amount"]),
                "cumulative_planned_cost": str(row["cumulative_planned_cost"]),
                "cumulative_actual_cost": str(row["cumulative_actual_cost"]),
                "cumulative_revenue": str(row["cumulative_revenue"]),
            }
            for row in rollups
        ]

    def project_finance_summary(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None = None,
        to_month: date | None = None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        summary_from = normalize_month_start(from_month or project.start_month)
        summary_to = normalize_month_start(to_month or project.end_month)
        if summary_from < project.start_month or summary_to > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requested summary month range must be within project month range.",
            )
        if summary_to < summary_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="to_month must be greater than or equal to from_month.",
            )

        rollups = self._project_monthly_rollups(project=project, from_month=summary_from, to_month=summary_to)
        return {
            "project_id": str(project.id),
            "from_month": summary_from.isoformat(),
            "to_month": summary_to.isoformat(),
            "months": self._rollups_to_serializable(rollups),
        }

    def list_rates(self, *, context: RequestUserContext, project_id: UUID) -> list[PerformerRate]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_rates_for_business_unit(
            project.business_unit_id,
            project_id=project.id,
        )

    def bulk_upsert_rates(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        entries: list[RateEntryInput],
    ) -> list[PerformerRate]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        performer_lookup = {
            performer.id: performer
            for performer in self.repo.list_performers_for_business_unit(project.business_unit_id)
        }

        normalized: list[RateEntryInput] = []
        seen_keys: set[tuple[UUID, UUID | None, date]] = set()
        for entry in entries:
            effective_from_month = normalize_month_start(entry.effective_from_month)
            effective_to_month = (
                normalize_month_start(entry.effective_to_month) if entry.effective_to_month is not None else None
            )
            self._validate_rate_range(
                effective_from_month=effective_from_month,
                effective_to_month=effective_to_month,
            )
            self._validate_non_negative_amount(entry.rate_value, "rate_value")

            performer = performer_lookup.get(entry.performer_id)
            if performer is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="performer_id must reference performer in project business unit.",
                )

            normalized_project_id = entry.project_id
            if normalized_project_id is not None and normalized_project_id != project.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="project_id for rate entry must be either null or current project id.",
                )

            dedup_key = (performer.id, normalized_project_id, effective_from_month)
            if dedup_key in seen_keys:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Duplicate rate key in bulk payload.",
                )
            seen_keys.add(dedup_key)

            normalized.append(
                RateEntryInput(
                    performer_id=performer.id,
                    project_id=normalized_project_id,
                    rate_unit=entry.rate_unit,
                    rate_value=entry.rate_value,
                    effective_from_month=effective_from_month,
                    effective_to_month=effective_to_month,
                )
            )

        persisted: list[PerformerRate] = []
        try:
            with self.db.begin_nested():
                for entry in normalized:
                    existing = self.repo.get_rate(
                        performer_id=entry.performer_id,
                        project_id=entry.project_id,
                        effective_from_month=entry.effective_from_month,
                    )
                    if existing is None:
                        row = PerformerRate(
                            business_unit_id=project.business_unit_id,
                            performer_id=entry.performer_id,
                            project_id=entry.project_id,
                            rate_unit=entry.rate_unit,
                            rate_value=entry.rate_value,
                            effective_from_month=entry.effective_from_month,
                            effective_to_month=entry.effective_to_month,
                        )
                        self.repo.add_rate(row)
                        target = row
                    else:
                        existing.rate_unit = entry.rate_unit
                        existing.rate_value = entry.rate_value
                        existing.effective_to_month = entry.effective_to_month
                        target = existing

                    overlap = self.repo.list_conflicting_rates(
                        performer_id=entry.performer_id,
                        project_id=entry.project_id,
                        effective_from_month=entry.effective_from_month,
                        effective_to_month=entry.effective_to_month,
                        exclude_rate_id=target.id,
                    )
                    if overlap:
                        scope = "project" if entry.project_id is not None else "business-unit default"
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                "Rate effective range overlaps existing "
                                f"{scope} rate for performer {entry.performer_id}."
                            ),
                        )
                    persisted.append(target)

                planning_service = PlanningService(self.db)
                planning_service.refresh_project_snapshots(project.id)
            self.db.commit()
        except HTTPException:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Rate upsert violated database constraints.",
            ) from exc

        return persisted

    # ---------- Financial registers ----------
    def list_financial_requests(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
    ) -> list[FinancialRequest]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_financial_requests(project.id)

    def create_financial_request(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: FinancialRequestCreateData,
    ) -> FinancialRequest:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        month_start = normalize_month_start(data.month_start)
        self._validate_non_negative_amount(data.amount, "amount")
        if month_start < project.start_month or month_start > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Financial register month_start must be within project month range.",
            )

        row = FinancialRequest(
            project_id=project.id,
            request_no=data.request_no.strip(),
            request_date=data.request_date,
            month_start=month_start,
            amount=data.amount,
            currency=data.currency,
            status=data.status.strip(),
        )
        self.repo.add_financial_request(row)
        PlanningService(self.db).refresh_project_snapshots(project.id)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_invoices(self, *, context: RequestUserContext, project_id: UUID) -> list[Invoice]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_invoices(project.id)

    def create_invoice(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: InvoiceCreateData,
    ) -> Invoice:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        month_start = normalize_month_start(data.month_start)
        self._validate_non_negative_amount(data.amount, "amount")
        if month_start < project.start_month or month_start > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Financial register month_start must be within project month range.",
            )

        row = Invoice(
            project_id=project.id,
            invoice_no=data.invoice_no.strip(),
            invoice_date=data.invoice_date,
            month_start=month_start,
            amount=data.amount,
            currency=data.currency,
            payment_status=data.payment_status.strip(),
            payment_date=data.payment_date,
        )
        self.repo.add_invoice(row)
        PlanningService(self.db).refresh_project_snapshots(project.id)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_revenues(self, *, context: RequestUserContext, project_id: UUID) -> list[Revenue]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_revenues(project.id)

    def create_revenue(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: RevenueCreateData,
    ) -> Revenue:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        month_start = normalize_month_start(data.month_start)
        self._validate_non_negative_amount(data.amount, "amount")
        if month_start < project.start_month or month_start > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Financial register month_start must be within project month range.",
            )

        row = Revenue(
            project_id=project.id,
            revenue_no=data.revenue_no.strip(),
            recognition_date=data.recognition_date,
            month_start=month_start,
            amount=data.amount,
            currency=data.currency,
        )
        self.repo.add_revenue(row)
        PlanningService(self.db).refresh_project_snapshots(project.id)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---------- Reports ----------
    def _report_month_range(self, project: Project, from_month: date | None, to_month: date | None) -> tuple[date, date, list[date]]:
        report_from = normalize_month_start(from_month or project.start_month)
        report_to = normalize_month_start(to_month or project.end_month)
        if report_from < project.start_month or report_to > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requested report month range must be within project month range.",
            )
        if report_to < report_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="to_month must be greater than or equal to from_month.",
            )
        return report_from, report_to, month_sequence(report_from, report_to)

    def _resolve_filters(
        self,
        *,
        project_id: UUID,
        business_unit_id: UUID,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> tuple[set[UUID] | None, set[UUID] | None, dict[UUID, str], dict[UUID, str], dict[UUID, str]]:
        tasks = self.repo.list_tasks(project_id)
        performers = self.repo.list_performers_for_business_unit(business_unit_id)
        stages = {stage.id: stage.name for stage in self.repo.list_stages(project_id)}

        task_map = {task.id: task for task in tasks}
        performer_map = {p.id: p for p in performers}

        task_filter_set = set(task_ids) if task_ids else None
        performer_filter_set = set(performer_ids) if performer_ids else None

        if task_filter_set:
            unknown = [str(tid) for tid in task_filter_set if tid not in task_map]
            if unknown:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown task_id values for this project: {', '.join(sorted(unknown))}",
                )
        if performer_filter_set:
            unknown = [str(pid) for pid in performer_filter_set if pid not in performer_map]
            if unknown:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown performer_id values for this project business unit: {', '.join(sorted(unknown))}",
                )

        task_labels = {task.id: task.name for task in tasks}
        performer_labels = {performer.id: performer.display_name for performer in performers}
        stage_labels = {task.id: stages.get(task.stage_id, "") for task in tasks}
        return performer_filter_set, task_filter_set, performer_labels, task_labels, stage_labels

    def _cost_entries(
        self,
        *,
        project: Project,
        from_month: date,
        to_month: date,
        performer_filter_set: set[UUID] | None,
        task_filter_set: set[UUID] | None,
    ) -> list[dict[str, object]]:
        return self._project_cost_entry_rows(
            project=project,
            from_month=from_month,
            to_month=to_month,
            performer_filter_set=performer_filter_set,
            task_filter_set=task_filter_set,
        )

    def effort_report_by_performer(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        report_from, report_to, months = self._report_month_range(project, from_month, to_month)
        performer_filter_set, task_filter_set, performer_labels, _, _ = self._resolve_filters(
            project_id=project.id,
            business_unit_id=project.business_unit_id,
            performer_ids=performer_ids,
            task_ids=task_ids,
        )

        entries = self.repo.list_effort_entries_filtered(
            project.id,
            from_month=report_from,
            to_month=report_to,
            task_ids=task_filter_set,
            performer_ids=performer_filter_set,
        )

        month_keys = [month.isoformat() for month in months]
        by_performer: dict[UUID, dict[str, Decimal]] = {}
        for row in entries:
            bucket = by_performer.setdefault(
                row.performer_id,
                {f"{month}_planned": ZERO for month in month_keys}
                | {f"{month}_actual": ZERO for month in month_keys},
            )
            key_month = row.month_start.isoformat()
            bucket[f"{key_month}_planned"] += row.planned_person_days
            bucket[f"{key_month}_actual"] += row.actual_person_days

        rows: list[dict[str, object]] = []
        performer_ids_sorted = sorted(by_performer.keys(), key=lambda pid: performer_labels.get(pid, str(pid)))
        for performer_id in performer_ids_sorted:
            bucket = by_performer[performer_id]
            month_values = []
            total_planned = ZERO
            total_actual = ZERO
            for month in month_keys:
                planned = _q2(bucket[f"{month}_planned"])
                actual = _q2(bucket[f"{month}_actual"])
                total_planned += planned
                total_actual += actual
                month_values.append(
                    {
                        "month_start": month,
                        "planned": str(planned),
                        "actual": str(actual),
                        "variance": str(_q2(actual - planned)),
                    }
                )

            rows.append(
                {
                    "performer_id": str(performer_id),
                    "performer_name": performer_labels.get(performer_id, str(performer_id)),
                    "months": month_values,
                    "totals": {
                        "planned": str(_q2(total_planned)),
                        "actual": str(_q2(total_actual)),
                        "variance": str(_q2(total_actual - total_planned)),
                    },
                }
            )

        return {
            "report_key": "effort-by-performer",
            "project_id": str(project.id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "months": month_keys,
            "rows": rows,
        }

    def effort_report_by_task(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        report_from, report_to, months = self._report_month_range(project, from_month, to_month)
        performer_filter_set, task_filter_set, _, task_labels, stage_labels = self._resolve_filters(
            project_id=project.id,
            business_unit_id=project.business_unit_id,
            performer_ids=performer_ids,
            task_ids=task_ids,
        )

        entries = self.repo.list_effort_entries_filtered(
            project.id,
            from_month=report_from,
            to_month=report_to,
            task_ids=task_filter_set,
            performer_ids=performer_filter_set,
        )

        month_keys = [month.isoformat() for month in months]
        by_task: dict[UUID, dict[str, Decimal]] = {}
        for row in entries:
            bucket = by_task.setdefault(
                row.task_id,
                {f"{month}_planned": ZERO for month in month_keys}
                | {f"{month}_actual": ZERO for month in month_keys},
            )
            key_month = row.month_start.isoformat()
            bucket[f"{key_month}_planned"] += row.planned_person_days
            bucket[f"{key_month}_actual"] += row.actual_person_days

        rows: list[dict[str, object]] = []
        task_ids_sorted = sorted(by_task.keys(), key=lambda tid: task_labels.get(tid, str(tid)))
        for task_id in task_ids_sorted:
            bucket = by_task[task_id]
            month_values = []
            total_planned = ZERO
            total_actual = ZERO
            for month in month_keys:
                planned = _q2(bucket[f"{month}_planned"])
                actual = _q2(bucket[f"{month}_actual"])
                total_planned += planned
                total_actual += actual
                month_values.append(
                    {
                        "month_start": month,
                        "planned": str(planned),
                        "actual": str(actual),
                        "variance": str(_q2(actual - planned)),
                    }
                )

            rows.append(
                {
                    "task_id": str(task_id),
                    "task_name": task_labels.get(task_id, str(task_id)),
                    "stage_name": stage_labels.get(task_id, ""),
                    "months": month_values,
                    "totals": {
                        "planned": str(_q2(total_planned)),
                        "actual": str(_q2(total_actual)),
                        "variance": str(_q2(total_actual - total_planned)),
                    },
                }
            )

        return {
            "report_key": "effort-by-task",
            "project_id": str(project.id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "months": month_keys,
            "rows": rows,
        }

    def cost_report_by_performer(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        report_from, report_to, months = self._report_month_range(project, from_month, to_month)
        performer_filter_set, task_filter_set, performer_labels, _, _ = self._resolve_filters(
            project_id=project.id,
            business_unit_id=project.business_unit_id,
            performer_ids=performer_ids,
            task_ids=task_ids,
        )

        entries = self._cost_entries(
            project=project,
            from_month=report_from,
            to_month=report_to,
            performer_filter_set=performer_filter_set,
            task_filter_set=task_filter_set,
        )

        month_keys = [month.isoformat() for month in months]
        by_performer: dict[UUID, dict[str, Decimal]] = {}
        for row in entries:
            performer_id = row["performer_id"]
            month_key = row["month_start"].isoformat()
            bucket = by_performer.setdefault(
                performer_id,
                {f"{month}_planned": ZERO for month in month_keys}
                | {f"{month}_actual": ZERO for month in month_keys},
            )
            bucket[f"{month_key}_planned"] += row["planned_cost"]
            bucket[f"{month_key}_actual"] += row["actual_cost"]

        rows: list[dict[str, object]] = []
        performer_ids_sorted = sorted(by_performer.keys(), key=lambda pid: performer_labels.get(pid, str(pid)))
        for performer_id in performer_ids_sorted:
            bucket = by_performer[performer_id]
            month_values = []
            total_planned = ZERO
            total_actual = ZERO
            for month in month_keys:
                planned = _q2(bucket[f"{month}_planned"])
                actual = _q2(bucket[f"{month}_actual"])
                total_planned += planned
                total_actual += actual
                month_values.append(
                    {
                        "month_start": month,
                        "planned_cost": str(planned),
                        "actual_cost": str(actual),
                        "variance": str(_q2(actual - planned)),
                    }
                )

            rows.append(
                {
                    "performer_id": str(performer_id),
                    "performer_name": performer_labels.get(performer_id, str(performer_id)),
                    "months": month_values,
                    "totals": {
                        "planned_cost": str(_q2(total_planned)),
                        "actual_cost": str(_q2(total_actual)),
                        "variance": str(_q2(total_actual - total_planned)),
                    },
                }
            )

        return {
            "report_key": "cost-by-performer",
            "project_id": str(project.id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "months": month_keys,
            "rows": rows,
        }

    def cost_report_by_task(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        report_from, report_to, months = self._report_month_range(project, from_month, to_month)
        performer_filter_set, task_filter_set, _, task_labels, stage_labels = self._resolve_filters(
            project_id=project.id,
            business_unit_id=project.business_unit_id,
            performer_ids=performer_ids,
            task_ids=task_ids,
        )

        entries = self._cost_entries(
            project=project,
            from_month=report_from,
            to_month=report_to,
            performer_filter_set=performer_filter_set,
            task_filter_set=task_filter_set,
        )

        month_keys = [month.isoformat() for month in months]
        by_task: dict[UUID, dict[str, Decimal]] = {}
        for row in entries:
            task_id = row["task_id"]
            month_key = row["month_start"].isoformat()
            bucket = by_task.setdefault(
                task_id,
                {f"{month}_planned": ZERO for month in month_keys}
                | {f"{month}_actual": ZERO for month in month_keys},
            )
            bucket[f"{month_key}_planned"] += row["planned_cost"]
            bucket[f"{month_key}_actual"] += row["actual_cost"]

        rows: list[dict[str, object]] = []
        task_ids_sorted = sorted(by_task.keys(), key=lambda tid: task_labels.get(tid, str(tid)))
        for task_id in task_ids_sorted:
            bucket = by_task[task_id]
            month_values = []
            total_planned = ZERO
            total_actual = ZERO
            for month in month_keys:
                planned = _q2(bucket[f"{month}_planned"])
                actual = _q2(bucket[f"{month}_actual"])
                total_planned += planned
                total_actual += actual
                month_values.append(
                    {
                        "month_start": month,
                        "planned_cost": str(planned),
                        "actual_cost": str(actual),
                        "variance": str(_q2(actual - planned)),
                    }
                )

            rows.append(
                {
                    "task_id": str(task_id),
                    "task_name": task_labels.get(task_id, str(task_id)),
                    "stage_name": stage_labels.get(task_id, ""),
                    "months": month_values,
                    "totals": {
                        "planned_cost": str(_q2(total_planned)),
                        "actual_cost": str(_q2(total_actual)),
                        "variance": str(_q2(total_actual - total_planned)),
                    },
                }
            )

        return {
            "report_key": "cost-by-task",
            "project_id": str(project.id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "months": month_keys,
            "rows": rows,
        }

    # ---------- Dashboards ----------
    def project_dashboard(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        report_from, report_to, months = self._report_month_range(project, from_month, to_month)
        rollups = self._project_monthly_rollups(project=project, from_month=report_from, to_month=report_to)
        rollups_by_month = {row["month_start"]: row for row in rollups}

        # cumulative planned vs actual cost trend
        cumulative_cost_trend = []
        # revenue and cost realization trend
        realization_trend = []
        for month in months:
            row = rollups_by_month.get(month)
            planned_cost = _q2(row["planned_cost"] if row else ZERO)
            actual_cost = _q2(row["actual_cost"] if row else ZERO)
            cumulative_planned = _q2(row["cumulative_planned_cost"] if row else ZERO)
            cumulative_actual = _q2(row["cumulative_actual_cost"] if row else ZERO)
            cumulative_revenue = _q2(row["cumulative_revenue"] if row else ZERO)

            cumulative_cost_trend.append(
                {
                    "month_start": month.isoformat(),
                    "planned_cost": str(planned_cost),
                    "actual_cost": str(actual_cost),
                    "cumulative_planned_cost": str(cumulative_planned),
                    "cumulative_actual_cost": str(cumulative_actual),
                }
            )

            margin = _q2(cumulative_revenue - cumulative_actual)
            realization_percent = _safe_div(cumulative_actual * Decimal("100.00"), cumulative_revenue)
            realization_trend.append(
                {
                    "month_start": month.isoformat(),
                    "cumulative_revenue": str(cumulative_revenue),
                    "cumulative_actual_cost": str(cumulative_actual),
                    "cumulative_margin": str(margin),
                    "realization_percent": str(realization_percent),
                }
            )

        # performer workload trend
        effort_entries = self.repo.list_effort_entries(project.id, from_month=report_from, to_month=report_to)
        performers = self.repo.list_performers_for_business_unit(project.business_unit_id)
        performer_labels = {p.id: p.display_name for p in performers}
        workload: dict[tuple[UUID, date], tuple[Decimal, Decimal]] = {}
        for entry in effort_entries:
            key = (entry.performer_id, entry.month_start)
            planned_prev, actual_prev = workload.get(key, (ZERO, ZERO))
            workload[key] = (planned_prev + entry.planned_person_days, actual_prev + entry.actual_person_days)

        workload_trend = []
        for performer_id in sorted({entry.performer_id for entry in effort_entries}, key=str):
            month_values = []
            for month in months:
                planned, actual = workload.get((performer_id, month), (ZERO, ZERO))
                month_values.append(
                    {
                        "month_start": month.isoformat(),
                        "planned_person_days": str(_q2(planned)),
                        "actual_person_days": str(_q2(actual)),
                    }
                )
            workload_trend.append(
                {
                    "performer_id": str(performer_id),
                    "performer_name": performer_labels.get(performer_id, str(performer_id)),
                    "months": month_values,
                }
            )

        return {
            "scope": "project",
            "project_id": str(project.id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "cumulative_cost_trend": cumulative_cost_trend,
            "workload_trend": workload_trend,
            "realization_trend": realization_trend,
        }

    def business_unit_dashboard(
        self,
        *,
        context: RequestUserContext,
        business_unit_id: UUID,
        from_month: date | None,
        to_month: date | None,
    ) -> dict[str, object]:
        self._ensure_business_unit_view_access(context=context, business_unit_id=business_unit_id)

        projects = self.repo.list_projects_for_business_unit(business_unit_id)
        if not projects:
            return {
                "scope": "business_unit",
                "business_unit_id": str(business_unit_id),
                "from_month": None,
                "to_month": None,
                "aggregated_cumulative_cost_trend": [],
                "workload_heatmap": [],
                "realization_trend": [],
            }

        min_project_month = min(project.start_month for project in projects)
        max_project_month = max(project.end_month for project in projects)
        report_from = normalize_month_start(from_month or min_project_month)
        report_to = normalize_month_start(to_month or max_project_month)
        if report_to < report_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="to_month must be greater than or equal to from_month.",
            )

        months = month_sequence(report_from, report_to)

        snapshots = self.repo.list_snapshots_for_business_unit(
            business_unit_id,
            from_month=report_from,
            to_month=report_to,
        )
        aggregate_by_month: dict[date, dict[str, Decimal]] = {
            month: {
                "planned_cost": ZERO,
                "actual_cost": ZERO,
                "revenue": ZERO,
                "cumulative_planned": ZERO,
                "cumulative_actual": ZERO,
                "cumulative_revenue": ZERO,
            }
            for month in months
        }

        for row in snapshots:
            bucket = aggregate_by_month.setdefault(
                row.month_start,
                {
                    "planned_cost": ZERO,
                    "actual_cost": ZERO,
                    "revenue": ZERO,
                    "cumulative_planned": ZERO,
                    "cumulative_actual": ZERO,
                    "cumulative_revenue": ZERO,
                },
            )
            bucket["planned_cost"] += row.planned_cost
            bucket["actual_cost"] += row.actual_cost
            bucket["revenue"] += row.revenue_amount

        cumulative_planned = ZERO
        cumulative_actual = ZERO
        cumulative_revenue = ZERO
        aggregated_cumulative_cost_trend = []
        realization_trend = []
        for month in months:
            bucket = aggregate_by_month.get(month) or {
                "planned_cost": ZERO,
                "actual_cost": ZERO,
                "revenue": ZERO,
                "cumulative_planned": ZERO,
                "cumulative_actual": ZERO,
                "cumulative_revenue": ZERO,
            }
            planned_cost = _q2(bucket["planned_cost"])
            actual_cost = _q2(bucket["actual_cost"])
            revenue = _q2(bucket["revenue"])

            cumulative_planned = _q2(cumulative_planned + planned_cost)
            cumulative_actual = _q2(cumulative_actual + actual_cost)
            cumulative_revenue = _q2(cumulative_revenue + revenue)

            aggregated_cumulative_cost_trend.append(
                {
                    "month_start": month.isoformat(),
                    "planned_cost": str(planned_cost),
                    "actual_cost": str(actual_cost),
                    "cumulative_planned_cost": str(cumulative_planned),
                    "cumulative_actual_cost": str(cumulative_actual),
                }
            )

            margin = _q2(cumulative_revenue - cumulative_actual)
            realization_percent = _safe_div(cumulative_actual * Decimal("100.00"), cumulative_revenue)
            realization_trend.append(
                {
                    "month_start": month.isoformat(),
                    "cumulative_revenue": str(cumulative_revenue),
                    "cumulative_actual_cost": str(cumulative_actual),
                    "cumulative_margin": str(margin),
                    "realization_percent": str(realization_percent),
                }
            )

        # workload heatmap by performer and month across BU projects
        effort_entries = self.repo.list_effort_entries_for_business_unit(
            business_unit_id,
            from_month=report_from,
            to_month=report_to,
        )
        performers = self.repo.list_performers_for_business_unit(business_unit_id)
        performer_labels = {p.id: p.display_name for p in performers}
        workload: dict[tuple[UUID, date], tuple[Decimal, Decimal]] = {}
        for entry in effort_entries:
            key = (entry.performer_id, entry.month_start)
            planned_prev, actual_prev = workload.get(key, (ZERO, ZERO))
            workload[key] = (planned_prev + entry.planned_person_days, actual_prev + entry.actual_person_days)

        workload_heatmap = []
        for performer_id in sorted({entry.performer_id for entry in effort_entries}, key=str):
            month_values = []
            for month in months:
                planned, actual = workload.get((performer_id, month), (ZERO, ZERO))
                month_values.append(
                    {
                        "month_start": month.isoformat(),
                        "planned_person_days": str(_q2(planned)),
                        "actual_person_days": str(_q2(actual)),
                    }
                )
            workload_heatmap.append(
                {
                    "performer_id": str(performer_id),
                    "performer_name": performer_labels.get(performer_id, str(performer_id)),
                    "months": month_values,
                }
            )

        return {
            "scope": "business_unit",
            "business_unit_id": str(business_unit_id),
            "from_month": report_from.isoformat(),
            "to_month": report_to.isoformat(),
            "aggregated_cumulative_cost_trend": aggregated_cumulative_cost_trend,
            "workload_heatmap": workload_heatmap,
            "realization_trend": realization_trend,
        }

    # ---------- Exports ----------
    @staticmethod
    def _flatten_report_rows(report_payload: dict[str, object]) -> list[dict[str, str]]:
        report_key = str(report_payload.get("report_key") or "report")
        rows = report_payload.get("rows")
        if not isinstance(rows, list):
            return []

        flat_rows: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            base_columns: dict[str, str] = {}
            for key in (
                "performer_id",
                "performer_name",
                "task_id",
                "task_name",
                "stage_name",
            ):
                if key in row and row[key] is not None:
                    base_columns[key] = str(row[key])

            month_rows = row.get("months")
            if not isinstance(month_rows, list):
                continue

            for month_row in month_rows:
                if not isinstance(month_row, dict):
                    continue
                record = dict(base_columns)
                record["report_key"] = report_key
                for field, value in month_row.items():
                    if value is not None:
                        record[str(field)] = str(value)
                flat_rows.append(record)
        return flat_rows

    def export_report(
        self,
        *,
        context: RequestUserContext,
        report_key: str,
        format_name: str,
        project_id: UUID,
        from_month: date | None,
        to_month: date | None,
        performer_ids: list[UUID] | None,
        task_ids: list[UUID] | None,
    ) -> ExportFilePayload:
        normalized_key = report_key.strip().lower()
        normalized_format = format_name.strip().lower()
        if normalized_format not in {"csv", "xlsx"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="format must be one of: csv, xlsx.",
            )

        report_dispatch = {
            "effort-by-performer": self.effort_report_by_performer,
            "effort-by-task": self.effort_report_by_task,
            "cost-by-performer": self.cost_report_by_performer,
            "cost-by-task": self.cost_report_by_task,
        }
        report_func = report_dispatch.get(normalized_key)
        if report_func is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown report_key for export.",
            )

        report_payload = report_func(
            context=context,
            project_id=project_id,
            from_month=from_month,
            to_month=to_month,
            performer_ids=performer_ids,
            task_ids=task_ids,
        )
        flattened = self._flatten_report_rows(report_payload)

        base_filename = f"{normalized_key}-{project_id}"
        if normalized_format == "csv":
            import csv
            import io

            fieldnames_set: set[str] = set()
            for row in flattened:
                fieldnames_set.update(row.keys())
            fieldnames = sorted(fieldnames_set)

            csv_bytes = b""
            if fieldnames:
                sio = io.StringIO()
                writer = csv.DictWriter(sio, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened)
                csv_bytes = sio.getvalue().encode("utf-8")
            return ExportFilePayload(
                media_type="text/csv; charset=utf-8",
                filename=f"{base_filename}.csv",
                content=bytes(csv_bytes),
            )

        # XLSX
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "report"

        fieldnames_set: set[str] = set()
        for row in flattened:
            fieldnames_set.update(row.keys())
        fieldnames = sorted(fieldnames_set)

        if fieldnames:
            sheet.append(fieldnames)
            for row in flattened:
                sheet.append([row.get(column, "") for column in fieldnames])

        output = BytesIO()
        workbook.save(output)
        return ExportFilePayload(
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{base_filename}.xlsx",
            content=output.getvalue(),
        )
