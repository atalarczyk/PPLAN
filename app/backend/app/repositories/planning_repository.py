"""Repository helpers for project planning and matrix domain."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    BusinessUnit,
    EffortMonthlyEntry,
    FinancialRequest,
    Invoice,
    Performer,
    PerformerRate,
    Project,
    ProjectMonthlySnapshot,
    ProjectStage,
    Revenue,
    Task,
    TaskPerformerAssignment,
)


class PlanningRepository:
    """Persistence operations used by project setup and matrix services."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------- Business units and projects ----------
    def get_business_unit(self, business_unit_id: UUID) -> BusinessUnit | None:
        return self.db.scalar(select(BusinessUnit).where(BusinessUnit.id == business_unit_id))

    def list_projects_for_business_unit(self, business_unit_id: UUID) -> list[Project]:
        return self.db.scalars(
            select(Project)
            .where(Project.business_unit_id == business_unit_id)
            .order_by(Project.code.asc())
        ).all()

    def get_project(self, project_id: UUID) -> Project | None:
        return self.db.scalar(select(Project).where(Project.id == project_id))

    def add_project(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        return project

    def delete_project(self, project: Project) -> None:
        self.db.delete(project)
        self.db.flush()

    # ---------- Stages ----------
    def list_stages(self, project_id: UUID) -> list[ProjectStage]:
        return self.db.scalars(
            select(ProjectStage)
            .where(ProjectStage.project_id == project_id)
            .order_by(ProjectStage.sequence_no.asc(), ProjectStage.name.asc())
        ).all()

    def get_stage(self, stage_id: UUID) -> ProjectStage | None:
        return self.db.scalar(select(ProjectStage).where(ProjectStage.id == stage_id))

    def add_stage(self, stage: ProjectStage) -> ProjectStage:
        self.db.add(stage)
        self.db.flush()
        return stage

    def delete_stage(self, stage: ProjectStage) -> None:
        self.db.delete(stage)
        self.db.flush()

    # ---------- Tasks ----------
    def list_tasks(self, project_id: UUID) -> list[Task]:
        return self.db.scalars(
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.sequence_no.asc(), Task.code.asc())
        ).all()

    def get_task(self, task_id: UUID) -> Task | None:
        return self.db.scalar(select(Task).where(Task.id == task_id))

    def add_task(self, task: Task) -> Task:
        self.db.add(task)
        self.db.flush()
        return task

    def delete_task(self, task: Task) -> None:
        self.db.delete(task)
        self.db.flush()

    # ---------- Performers ----------
    def list_performers_for_business_unit(self, business_unit_id: UUID) -> list[Performer]:
        return self.db.scalars(
            select(Performer)
            .where(Performer.business_unit_id == business_unit_id)
            .order_by(Performer.display_name.asc())
        ).all()

    def list_performers_for_project(self, project_id: UUID, business_unit_id: UUID) -> list[Performer]:
        performer_ids = self.db.scalars(
            select(TaskPerformerAssignment.performer_id)
            .join(Task, Task.id == TaskPerformerAssignment.task_id)
            .where(Task.project_id == project_id)
        ).all()
        if not performer_ids:
            return []

        return self.db.scalars(
            select(Performer)
            .where(
                and_(
                    Performer.id.in_(performer_ids),
                    Performer.business_unit_id == business_unit_id,
                )
            )
            .order_by(Performer.display_name.asc())
        ).all()

    def get_performer(self, performer_id: UUID) -> Performer | None:
        return self.db.scalar(select(Performer).where(Performer.id == performer_id))

    def add_performer(self, performer: Performer) -> Performer:
        self.db.add(performer)
        self.db.flush()
        return performer

    def delete_performer(self, performer: Performer) -> None:
        self.db.delete(performer)
        self.db.flush()

    # ---------- Task-performer assignments ----------
    def list_assignments_for_project(self, project_id: UUID) -> list[TaskPerformerAssignment]:
        return self.db.scalars(
            select(TaskPerformerAssignment)
            .join(Task, Task.id == TaskPerformerAssignment.task_id)
            .where(Task.project_id == project_id)
            .order_by(
                TaskPerformerAssignment.task_id.asc(),
                TaskPerformerAssignment.performer_id.asc(),
            )
        ).all()

    def get_assignment(self, task_id: UUID, performer_id: UUID) -> TaskPerformerAssignment | None:
        return self.db.scalar(
            select(TaskPerformerAssignment).where(
                and_(
                    TaskPerformerAssignment.task_id == task_id,
                    TaskPerformerAssignment.performer_id == performer_id,
                )
            )
        )

    def add_assignment(self, assignment: TaskPerformerAssignment) -> TaskPerformerAssignment:
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def delete_assignment(self, assignment: TaskPerformerAssignment) -> None:
        self.db.delete(assignment)
        self.db.flush()

    # ---------- Effort entries ----------
    def list_effort_entries(self, project_id: UUID, *, from_month: date, to_month: date) -> list[EffortMonthlyEntry]:
        return self.db.scalars(
            select(EffortMonthlyEntry)
            .where(
                and_(
                    EffortMonthlyEntry.project_id == project_id,
                    EffortMonthlyEntry.month_start >= from_month,
                    EffortMonthlyEntry.month_start <= to_month,
                )
            )
            .order_by(
                EffortMonthlyEntry.month_start.asc(),
                EffortMonthlyEntry.task_id.asc(),
                EffortMonthlyEntry.performer_id.asc(),
            )
        ).all()

    def list_effort_entries_filtered(
        self,
        project_id: UUID,
        *,
        from_month: date,
        to_month: date,
        task_ids: set[UUID] | None = None,
        performer_ids: set[UUID] | None = None,
    ) -> list[EffortMonthlyEntry]:
        conditions = [
            EffortMonthlyEntry.project_id == project_id,
            EffortMonthlyEntry.month_start >= from_month,
            EffortMonthlyEntry.month_start <= to_month,
        ]
        if task_ids:
            conditions.append(EffortMonthlyEntry.task_id.in_(task_ids))
        if performer_ids:
            conditions.append(EffortMonthlyEntry.performer_id.in_(performer_ids))

        return self.db.scalars(
            select(EffortMonthlyEntry)
            .where(and_(*conditions))
            .order_by(
                EffortMonthlyEntry.month_start.asc(),
                EffortMonthlyEntry.task_id.asc(),
                EffortMonthlyEntry.performer_id.asc(),
            )
        ).all()

    def list_effort_entries_for_business_unit(
        self,
        business_unit_id: UUID,
        *,
        from_month: date,
        to_month: date,
    ) -> list[EffortMonthlyEntry]:
        return self.db.scalars(
            select(EffortMonthlyEntry)
            .join(Project, Project.id == EffortMonthlyEntry.project_id)
            .where(
                and_(
                    Project.business_unit_id == business_unit_id,
                    EffortMonthlyEntry.month_start >= from_month,
                    EffortMonthlyEntry.month_start <= to_month,
                )
            )
            .order_by(
                EffortMonthlyEntry.month_start.asc(),
                EffortMonthlyEntry.project_id.asc(),
                EffortMonthlyEntry.task_id.asc(),
                EffortMonthlyEntry.performer_id.asc(),
            )
        ).all()

    def get_effort_entry(
        self,
        *,
        project_id: UUID,
        task_id: UUID,
        performer_id: UUID,
        month_start: date,
    ) -> EffortMonthlyEntry | None:
        return self.db.scalar(
            select(EffortMonthlyEntry).where(
                and_(
                    EffortMonthlyEntry.project_id == project_id,
                    EffortMonthlyEntry.task_id == task_id,
                    EffortMonthlyEntry.performer_id == performer_id,
                    EffortMonthlyEntry.month_start == month_start,
                )
            )
        )

    def add_effort_entry(self, entry: EffortMonthlyEntry) -> EffortMonthlyEntry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def aggregate_effort_by_month(self, project_id: UUID) -> dict[date, tuple[Decimal, Decimal]]:
        rows = self.db.execute(
            select(
                EffortMonthlyEntry.month_start,
                func.coalesce(func.sum(EffortMonthlyEntry.planned_person_days), Decimal("0.00")),
                func.coalesce(func.sum(EffortMonthlyEntry.actual_person_days), Decimal("0.00")),
            )
            .where(EffortMonthlyEntry.project_id == project_id)
            .group_by(EffortMonthlyEntry.month_start)
        ).all()
        return {month: (planned, actual) for month, planned, actual in rows}

    # ---------- Rates ----------
    def list_rates_for_business_unit(
        self,
        business_unit_id: UUID,
        *,
        project_id: UUID | None = None,
        performer_ids: set[UUID] | None = None,
    ) -> list[PerformerRate]:
        conditions = [PerformerRate.business_unit_id == business_unit_id]
        if project_id is not None:
            conditions.append(
                or_(
                    PerformerRate.project_id == project_id,
                    PerformerRate.project_id.is_(None),
                )
            )
        if performer_ids:
            conditions.append(PerformerRate.performer_id.in_(performer_ids))

        return self.db.scalars(
            select(PerformerRate)
            .where(and_(*conditions))
            .order_by(
                PerformerRate.performer_id.asc(),
                PerformerRate.project_id.asc(),
                PerformerRate.effective_from_month.asc(),
            )
        ).all()

    def get_rate(
        self,
        *,
        performer_id: UUID,
        project_id: UUID | None,
        effective_from_month: date,
    ) -> PerformerRate | None:
        return self.db.scalar(
            select(PerformerRate).where(
                and_(
                    PerformerRate.performer_id == performer_id,
                    PerformerRate.project_id == project_id,
                    PerformerRate.effective_from_month == effective_from_month,
                )
            )
        )

    def add_rate(self, rate: PerformerRate) -> PerformerRate:
        self.db.add(rate)
        self.db.flush()
        return rate

    def list_conflicting_rates(
        self,
        *,
        performer_id: UUID,
        project_id: UUID | None,
        effective_from_month: date,
        effective_to_month: date | None,
        exclude_rate_id: UUID | None,
    ) -> list[PerformerRate]:
        conditions = [
            PerformerRate.performer_id == performer_id,
            PerformerRate.project_id == project_id,
            PerformerRate.effective_from_month <= (effective_to_month or date.max),
            or_(
                PerformerRate.effective_to_month.is_(None),
                PerformerRate.effective_to_month >= effective_from_month,
            ),
        ]
        if exclude_rate_id is not None:
            conditions.append(PerformerRate.id != exclude_rate_id)

        return self.db.scalars(select(PerformerRate).where(and_(*conditions))).all()

    # ---------- Financial registers ----------
    def list_financial_requests(
        self,
        project_id: UUID,
        *,
        from_month: date | None = None,
        to_month: date | None = None,
    ) -> list[FinancialRequest]:
        conditions = [FinancialRequest.project_id == project_id]
        if from_month is not None:
            conditions.append(FinancialRequest.month_start >= from_month)
        if to_month is not None:
            conditions.append(FinancialRequest.month_start <= to_month)

        return self.db.scalars(
            select(FinancialRequest)
            .where(and_(*conditions))
            .order_by(FinancialRequest.month_start.asc(), FinancialRequest.request_date.asc())
        ).all()

    def add_financial_request(self, request: FinancialRequest) -> FinancialRequest:
        self.db.add(request)
        self.db.flush()
        return request

    def list_invoices(
        self,
        project_id: UUID,
        *,
        from_month: date | None = None,
        to_month: date | None = None,
    ) -> list[Invoice]:
        conditions = [Invoice.project_id == project_id]
        if from_month is not None:
            conditions.append(Invoice.month_start >= from_month)
        if to_month is not None:
            conditions.append(Invoice.month_start <= to_month)

        return self.db.scalars(
            select(Invoice)
            .where(and_(*conditions))
            .order_by(Invoice.month_start.asc(), Invoice.invoice_date.asc())
        ).all()

    def add_invoice(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def list_revenues(
        self,
        project_id: UUID,
        *,
        from_month: date | None = None,
        to_month: date | None = None,
    ) -> list[Revenue]:
        conditions = [Revenue.project_id == project_id]
        if from_month is not None:
            conditions.append(Revenue.month_start >= from_month)
        if to_month is not None:
            conditions.append(Revenue.month_start <= to_month)

        return self.db.scalars(
            select(Revenue)
            .where(and_(*conditions))
            .order_by(Revenue.month_start.asc(), Revenue.recognition_date.asc())
        ).all()

    def add_revenue(self, revenue: Revenue) -> Revenue:
        self.db.add(revenue)
        self.db.flush()
        return revenue

    def aggregate_invoices_by_month(self, project_id: UUID) -> dict[date, Decimal]:
        rows = self.db.execute(
            select(
                Invoice.month_start,
                func.coalesce(func.sum(Invoice.amount), Decimal("0.00")),
            )
            .where(Invoice.project_id == project_id)
            .group_by(Invoice.month_start)
        ).all()
        return {month: amount for month, amount in rows}

    def aggregate_revenues_by_month(self, project_id: UUID) -> dict[date, Decimal]:
        rows = self.db.execute(
            select(
                Revenue.month_start,
                func.coalesce(func.sum(Revenue.amount), Decimal("0.00")),
            )
            .where(Revenue.project_id == project_id)
            .group_by(Revenue.month_start)
        ).all()
        return {month: amount for month, amount in rows}

    # ---------- Snapshot reads for dashboards ----------
    def list_snapshots_for_business_unit(
        self,
        business_unit_id: UUID,
        *,
        from_month: date,
        to_month: date,
    ) -> list[ProjectMonthlySnapshot]:
        return self.db.scalars(
            select(ProjectMonthlySnapshot)
            .join(Project, Project.id == ProjectMonthlySnapshot.project_id)
            .where(
                and_(
                    Project.business_unit_id == business_unit_id,
                    ProjectMonthlySnapshot.month_start >= from_month,
                    ProjectMonthlySnapshot.month_start <= to_month,
                )
            )
            .order_by(ProjectMonthlySnapshot.month_start.asc(), ProjectMonthlySnapshot.project_id.asc())
        ).all()

    # ---------- Snapshots ----------
    def list_snapshots(self, project_id: UUID, *, from_month: date, to_month: date) -> list[ProjectMonthlySnapshot]:
        return self.db.scalars(
            select(ProjectMonthlySnapshot)
            .where(
                and_(
                    ProjectMonthlySnapshot.project_id == project_id,
                    ProjectMonthlySnapshot.month_start >= from_month,
                    ProjectMonthlySnapshot.month_start <= to_month,
                )
            )
            .order_by(ProjectMonthlySnapshot.month_start.asc())
        ).all()

    def get_snapshot(self, *, project_id: UUID, month_start: date) -> ProjectMonthlySnapshot | None:
        return self.db.scalar(
            select(ProjectMonthlySnapshot).where(
                and_(
                    ProjectMonthlySnapshot.project_id == project_id,
                    ProjectMonthlySnapshot.month_start == month_start,
                )
            )
        )

    def add_snapshot(self, snapshot: ProjectMonthlySnapshot) -> ProjectMonthlySnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    # ---------- Existence checks used for safe deletes ----------
    def task_count_in_stage(self, stage_id: UUID) -> int:
        return self.db.scalar(select(func.count()).select_from(Task).where(Task.stage_id == stage_id)) or 0

    def assignment_count_for_task(self, task_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(TaskPerformerAssignment)
                .where(TaskPerformerAssignment.task_id == task_id)
            )
            or 0
        )

    def effort_count_for_task(self, task_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count()).select_from(EffortMonthlyEntry).where(EffortMonthlyEntry.task_id == task_id)
            )
            or 0
        )

    def assignment_count_for_performer(self, performer_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(TaskPerformerAssignment)
                .where(TaskPerformerAssignment.performer_id == performer_id)
            )
            or 0
        )

    def effort_count_for_performer(self, performer_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EffortMonthlyEntry)
                .where(EffortMonthlyEntry.performer_id == performer_id)
            )
            or 0
        )

    def effort_count_for_assignment(self, task_id: UUID, performer_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EffortMonthlyEntry)
                .where(
                    and_(
                        EffortMonthlyEntry.task_id == task_id,
                        EffortMonthlyEntry.performer_id == performer_id,
                    )
                )
            )
            or 0
        )

    def stage_count_for_project(self, project_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count()).select_from(ProjectStage).where(ProjectStage.project_id == project_id)
            )
            or 0
        )

    def task_count_for_project(self, project_id: UUID) -> int:
        return self.db.scalar(select(func.count()).select_from(Task).where(Task.project_id == project_id)) or 0

    def effort_count_for_project(self, project_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EffortMonthlyEntry)
                .where(EffortMonthlyEntry.project_id == project_id)
            )
            or 0
        )

    def snapshot_count_for_project(self, project_id: UUID) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(ProjectMonthlySnapshot)
                .where(ProjectMonthlySnapshot.project_id == project_id)
            )
            or 0
        )

    def effort_outside_project_range_count(self, project_id: UUID, *, start_month: date, end_month: date) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EffortMonthlyEntry)
                .where(
                    and_(
                        EffortMonthlyEntry.project_id == project_id,
                        or_(
                            EffortMonthlyEntry.month_start < start_month,
                            EffortMonthlyEntry.month_start > end_month,
                        ),
                    )
                )
            )
            or 0
        )

    def delete_snapshots_outside_range(self, project_id: UUID, *, start_month: date, end_month: date) -> None:
        snapshots = self.db.scalars(
            select(ProjectMonthlySnapshot).where(
                and_(
                    ProjectMonthlySnapshot.project_id == project_id,
                    or_(
                        ProjectMonthlySnapshot.month_start < start_month,
                        ProjectMonthlySnapshot.month_start > end_month,
                    ),
                )
            )
        ).all()
        for snapshot in snapshots:
            self.db.delete(snapshot)
        self.db.flush()
