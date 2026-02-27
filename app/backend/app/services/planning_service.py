"""Application service for project setup lifecycle and matrix engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AppRole, RequestUserContext, has_business_unit_access
from app.core.config import get_settings
from app.models.entities import (
    EffortMonthlyEntry,
    PerformerRate,
    Performer,
    Project,
    ProjectMonthlySnapshot,
    ProjectStage,
    ProjectStatus,
    RateUnit,
    Task,
    TaskPerformerAssignment,
)
from app.repositories.planning_repository import PlanningRepository


EDIT_ROLES = {AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN, AppRole.EDITOR}
VIEW_ROLES = {AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN, AppRole.EDITOR, AppRole.VIEWER}

ZERO = Decimal("0.00")
Q2 = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Q2)


@dataclass(slots=True)
class ProjectCreateData:
    code: str
    name: str
    description: str | None
    start_month: date
    end_month: date
    status: ProjectStatus


@dataclass(slots=True)
class ProjectUpdateData:
    code: str | None = None
    name: str | None = None
    description: str | None = None
    start_month: date | None = None
    end_month: date | None = None
    status: ProjectStatus | None = None


@dataclass(slots=True)
class StageCreateData:
    name: str
    start_month: date
    end_month: date
    color_token: str
    sequence_no: int


@dataclass(slots=True)
class StageUpdateData:
    name: str | None = None
    start_month: date | None = None
    end_month: date | None = None
    color_token: str | None = None
    sequence_no: int | None = None


@dataclass(slots=True)
class TaskCreateData:
    stage_id: UUID
    code: str
    name: str
    sequence_no: int
    active: bool = True


@dataclass(slots=True)
class TaskUpdateData:
    stage_id: UUID | None = None
    code: str | None = None
    name: str | None = None
    sequence_no: int | None = None
    active: bool | None = None


@dataclass(slots=True)
class PerformerCreateData:
    external_ref: str | None
    display_name: str
    active: bool = True


@dataclass(slots=True)
class PerformerUpdateData:
    external_ref: str | None = None
    display_name: str | None = None
    active: bool | None = None


@dataclass(slots=True)
class AssignmentCreateData:
    task_id: UUID
    performer_id: UUID


@dataclass(slots=True)
class MatrixEntryInput:
    task_id: UUID
    performer_id: UUID
    month_start: date
    planned_person_days: Decimal
    actual_person_days: Decimal


@dataclass(slots=True)
class MatrixUpsertResult:
    updated_entries: int
    snapshots: list[ProjectMonthlySnapshot]


def normalize_month_start(value: date) -> date:
    if value.day != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="month_start must be first day of calendar month.",
        )
    return date(value.year, value.month, 1)


def month_sequence(start_month: date, end_month: date) -> list[date]:
    current = date(start_month.year, start_month.month, 1)
    end = date(end_month.year, end_month.month, 1)
    months: list[date] = []
    while current <= end:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


class PlanningService:
    """Service implementing phase-2 planning structure and matrix rules."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PlanningRepository(db)
        self.settings = get_settings()

    @staticmethod
    def _rate_covers_month(rate: PerformerRate, month_start: date) -> bool:
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
        project_id: UUID,
        month_start: date,
    ) -> PerformerRate | None:
        candidates = rates_by_performer.get(performer_id, [])
        project_specific = [
            row
            for row in candidates
            if row.project_id == project_id and self._rate_covers_month(row, month_start)
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
            row
            for row in candidates
            if row.project_id is None and self._rate_covers_month(row, month_start)
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
        return _q2(rate.rate_value / Decimal(str(self.settings.cost_fte_month_working_days)))

    # ---------- Scope + RBAC ----------
    def ensure_can_view_business_unit(self, *, context: RequestUserContext, business_unit_id: UUID) -> None:
        if not has_business_unit_access(context, business_unit_id=business_unit_id, allowed_roles=VIEW_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business unit scope permissions for this operation.",
            )

    def ensure_can_edit_business_unit(self, *, context: RequestUserContext, business_unit_id: UUID) -> None:
        if not has_business_unit_access(context, business_unit_id=business_unit_id, allowed_roles=EDIT_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business unit scope permissions for this operation.",
            )

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

    # ---------- Serialization ----------
    @staticmethod
    def serialize_project(project: Project) -> dict[str, object]:
        return {
            "id": str(project.id),
            "business_unit_id": str(project.business_unit_id),
            "code": project.code,
            "name": project.name,
            "description": project.description,
            "start_month": project.start_month.isoformat(),
            "end_month": project.end_month.isoformat(),
            "status": project.status.value,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }

    @staticmethod
    def serialize_stage(stage: ProjectStage) -> dict[str, object]:
        return {
            "id": str(stage.id),
            "project_id": str(stage.project_id),
            "name": stage.name,
            "start_month": stage.start_month.isoformat(),
            "end_month": stage.end_month.isoformat(),
            "color_token": stage.color_token,
            "sequence_no": stage.sequence_no,
        }

    @staticmethod
    def serialize_task(task: Task) -> dict[str, object]:
        return {
            "id": str(task.id),
            "project_id": str(task.project_id),
            "stage_id": str(task.stage_id),
            "code": task.code,
            "name": task.name,
            "sequence_no": task.sequence_no,
            "active": task.active,
        }

    @staticmethod
    def serialize_performer(performer: Performer) -> dict[str, object]:
        return {
            "id": str(performer.id),
            "business_unit_id": str(performer.business_unit_id),
            "external_ref": performer.external_ref,
            "display_name": performer.display_name,
            "active": performer.active,
        }

    @staticmethod
    def serialize_assignment(assignment: TaskPerformerAssignment) -> dict[str, object]:
        return {
            "task_id": str(assignment.task_id),
            "performer_id": str(assignment.performer_id),
        }

    # ---------- Project CRUD ----------
    def list_projects(self, *, context: RequestUserContext, business_unit_id: UUID) -> list[Project]:
        unit = self.repo.get_business_unit(business_unit_id)
        if unit is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business unit not found.")
        self.ensure_can_view_business_unit(context=context, business_unit_id=business_unit_id)
        return self.repo.list_projects_for_business_unit(business_unit_id)

    def create_project(
        self,
        *,
        context: RequestUserContext,
        business_unit_id: UUID,
        data: ProjectCreateData,
    ) -> Project:
        unit = self.repo.get_business_unit(business_unit_id)
        if unit is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business unit not found.")

        self.ensure_can_edit_business_unit(context=context, business_unit_id=business_unit_id)

        start_month = normalize_month_start(data.start_month)
        end_month = normalize_month_start(data.end_month)
        if end_month < start_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_month must be greater than or equal to start_month.",
            )

        now = datetime.utcnow()
        project = Project(
            business_unit_id=business_unit_id,
            code=data.code.strip(),
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            start_month=start_month,
            end_month=end_month,
            status=data.status,
            created_at=now,
            updated_at=now,
        )

        self.repo.add_project(project)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists in this business unit.",
            ) from exc

        self.db.refresh(project)
        return project

    def get_project(self, *, context: RequestUserContext, project_id: UUID) -> Project:
        return self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)

    def update_project(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: ProjectUpdateData,
    ) -> Project:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        target_start = project.start_month
        target_end = project.end_month
        if data.start_month is not None:
            target_start = normalize_month_start(data.start_month)
        if data.end_month is not None:
            target_end = normalize_month_start(data.end_month)
        if target_end < target_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_month must be greater than or equal to start_month.",
            )

        if self.repo.effort_outside_project_range_count(
            project.id,
            start_month=target_start,
            end_month=target_end,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot shrink project month range while effort entries exist outside new range.",
            )

        if data.code is not None:
            project.code = data.code.strip()
        if data.name is not None:
            project.name = data.name.strip()
        if data.description is not None:
            project.description = data.description.strip() if data.description else None

        project.start_month = target_start
        project.end_month = target_end
        if data.status is not None:
            project.status = data.status
        project.updated_at = datetime.utcnow()

        self.repo.delete_snapshots_outside_range(project.id, start_month=target_start, end_month=target_end)
        self.refresh_project_snapshots(project.id)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists in this business unit.",
            ) from exc

        self.db.refresh(project)
        return project

    def delete_project(self, *, context: RequestUserContext, project_id: UUID) -> None:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        if self.repo.stage_count_for_project(project.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete project with existing stages.",
            )
        if self.repo.task_count_for_project(project.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete project with existing tasks.",
            )
        if self.repo.effort_count_for_project(project.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete project with existing effort entries.",
            )
        if self.repo.snapshot_count_for_project(project.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete project with existing snapshots.",
            )

        self.repo.delete_project(project)
        self.db.commit()

    # ---------- Stage CRUD ----------
    def list_stages(self, *, context: RequestUserContext, project_id: UUID) -> list[ProjectStage]:
        self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_stages(project_id)

    def create_stage(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: StageCreateData,
    ) -> ProjectStage:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        start_month = normalize_month_start(data.start_month)
        end_month = normalize_month_start(data.end_month)
        if end_month < start_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="stage end_month must be greater than or equal to start_month.",
            )
        if start_month < project.start_month or end_month > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stage month range must be within project month range.",
            )

        stage = ProjectStage(
            project_id=project_id,
            name=data.name.strip(),
            start_month=start_month,
            end_month=end_month,
            color_token=data.color_token.strip(),
            sequence_no=data.sequence_no,
        )
        self.repo.add_stage(stage)
        self.db.commit()
        self.db.refresh(stage)
        return stage

    def update_stage(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        stage_id: UUID,
        data: StageUpdateData,
    ) -> ProjectStage:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        stage = self.repo.get_stage(stage_id)
        if stage is None or stage.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project stage not found.")

        target_start = stage.start_month
        target_end = stage.end_month
        if data.start_month is not None:
            target_start = normalize_month_start(data.start_month)
        if data.end_month is not None:
            target_end = normalize_month_start(data.end_month)

        if target_end < target_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="stage end_month must be greater than or equal to start_month.",
            )
        if target_start < project.start_month or target_end > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stage month range must be within project month range.",
            )

        if data.name is not None:
            stage.name = data.name.strip()
        if data.color_token is not None:
            stage.color_token = data.color_token.strip()
        if data.sequence_no is not None:
            stage.sequence_no = data.sequence_no
        stage.start_month = target_start
        stage.end_month = target_end

        self.db.commit()
        self.db.refresh(stage)
        return stage

    def delete_stage(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        stage_id: UUID,
    ) -> None:
        self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        stage = self.repo.get_stage(stage_id)
        if stage is None or stage.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project stage not found.")
        if self.repo.task_count_in_stage(stage.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete stage with existing tasks.",
            )
        self.repo.delete_stage(stage)
        self.db.commit()

    # ---------- Task CRUD ----------
    def list_tasks(self, *, context: RequestUserContext, project_id: UUID) -> list[Task]:
        self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_tasks(project_id)

    def create_task(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: TaskCreateData,
    ) -> Task:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        stage = self.repo.get_stage(data.stage_id)
        if stage is None or stage.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="stage_id must reference a stage in this project.",
            )

        task = Task(
            project_id=project_id,
            stage_id=data.stage_id,
            code=data.code.strip(),
            name=data.name.strip(),
            sequence_no=data.sequence_no,
            active=data.active,
        )
        self.repo.add_task(task)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task code already exists in this project.",
            ) from exc

        self.db.refresh(task)
        return task

    def update_task(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        task_id: UUID,
        data: TaskUpdateData,
    ) -> Task:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        task = self.repo.get_task(task_id)
        if task is None or task.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        if data.stage_id is not None:
            stage = self.repo.get_stage(data.stage_id)
            if stage is None or stage.project_id != project.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="stage_id must reference a stage in this project.",
                )
            task.stage_id = data.stage_id

        if data.code is not None:
            task.code = data.code.strip()
        if data.name is not None:
            task.name = data.name.strip()
        if data.sequence_no is not None:
            task.sequence_no = data.sequence_no
        if data.active is not None:
            task.active = data.active

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task code already exists in this project.",
            ) from exc

        self.db.refresh(task)
        return task

    def delete_task(self, *, context: RequestUserContext, project_id: UUID, task_id: UUID) -> None:
        self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        task = self.repo.get_task(task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        if self.repo.assignment_count_for_task(task.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete task with performer assignments.",
            )
        if self.repo.effort_count_for_task(task.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete task with effort entries.",
            )
        self.repo.delete_task(task)
        self.db.commit()

    # ---------- Performer CRUD ----------
    def list_project_performers(self, *, context: RequestUserContext, project_id: UUID) -> list[Performer]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_performers_for_business_unit(project.business_unit_id)

    def create_project_performer(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: PerformerCreateData,
    ) -> Performer:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        performer = Performer(
            business_unit_id=project.business_unit_id,
            external_ref=data.external_ref.strip() if data.external_ref else None,
            display_name=data.display_name.strip(),
            active=data.active,
        )
        self.repo.add_performer(performer)
        self.db.commit()
        self.db.refresh(performer)
        return performer

    def update_project_performer(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        performer_id: UUID,
        data: PerformerUpdateData,
    ) -> Performer:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        performer = self.repo.get_performer(performer_id)
        if performer is None or performer.business_unit_id != project.business_unit_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performer not found.")

        if data.external_ref is not None:
            performer.external_ref = data.external_ref.strip() if data.external_ref else None
        if data.display_name is not None:
            performer.display_name = data.display_name.strip()
        if data.active is not None:
            performer.active = data.active

        self.db.commit()
        self.db.refresh(performer)
        return performer

    def delete_project_performer(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        performer_id: UUID,
    ) -> None:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)
        performer = self.repo.get_performer(performer_id)
        if performer is None or performer.business_unit_id != project.business_unit_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performer not found.")

        if self.repo.assignment_count_for_performer(performer.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete performer with task assignments.",
            )
        if self.repo.effort_count_for_performer(performer.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete performer with effort entries.",
            )
        self.repo.delete_performer(performer)
        self.db.commit()

    # ---------- Assignments ----------
    def list_assignments(self, *, context: RequestUserContext, project_id: UUID) -> list[TaskPerformerAssignment]:
        self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)
        return self.repo.list_assignments_for_project(project_id)

    def create_assignment(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        data: AssignmentCreateData,
    ) -> TaskPerformerAssignment:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        task = self.repo.get_task(data.task_id)
        if task is None or task.project_id != project.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="task_id must reference a task in this project.",
            )

        performer = self.repo.get_performer(data.performer_id)
        if performer is None or performer.business_unit_id != project.business_unit_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="performer_id must reference performer in project business unit.",
            )

        assignment = TaskPerformerAssignment(task_id=task.id, performer_id=performer.id)
        self.repo.add_assignment(assignment)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task-performer assignment already exists.",
            ) from exc

        self.db.refresh(assignment)
        return assignment

    def delete_assignment(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        task_id: UUID,
        performer_id: UUID,
    ) -> None:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        task = self.repo.get_task(task_id)
        if task is None or task.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        performer = self.repo.get_performer(performer_id)
        if performer is None or performer.business_unit_id != project.business_unit_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performer not found.")

        assignment = self.repo.get_assignment(task_id, performer_id)
        if assignment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task-performer assignment not found.")

        if self.repo.effort_count_for_assignment(task_id, performer_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete assignment with existing effort entries.",
            )

        self.repo.delete_assignment(assignment)
        self.db.commit()

    # ---------- Matrix read ----------
    def read_matrix(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        from_month: date | None = None,
        to_month: date | None = None,
    ) -> dict[str, object]:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=VIEW_ROLES)

        matrix_from = normalize_month_start(from_month or project.start_month)
        matrix_to = normalize_month_start(to_month or project.end_month)
        if matrix_from < project.start_month or matrix_to > project.end_month:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requested matrix month range must be within project month range.",
            )
        if matrix_to < matrix_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="to_month must be greater than or equal to from_month.",
            )

        months = month_sequence(matrix_from, matrix_to)
        stages = self.repo.list_stages(project.id)
        tasks = self.repo.list_tasks(project.id)
        performers = self.repo.list_performers_for_project(project.id, project.business_unit_id)
        assignments = self.repo.list_assignments_for_project(project.id)
        entries = self.repo.list_effort_entries(project.id, from_month=matrix_from, to_month=matrix_to)
        snapshots = self.repo.list_snapshots(project.id, from_month=matrix_from, to_month=matrix_to)

        entry_map: dict[tuple[UUID, UUID, date], EffortMonthlyEntry] = {
            (entry.task_id, entry.performer_id, entry.month_start): entry for entry in entries
        }

        performer_month_totals: dict[tuple[UUID, date], tuple[Decimal, Decimal]] = {}
        task_month_totals: dict[tuple[UUID, date], tuple[Decimal, Decimal]] = {}
        for entry in entries:
            p_key = (entry.performer_id, entry.month_start)
            t_key = (entry.task_id, entry.month_start)

            p_planned, p_actual = performer_month_totals.get(p_key, (ZERO, ZERO))
            performer_month_totals[p_key] = (
                p_planned + entry.planned_person_days,
                p_actual + entry.actual_person_days,
            )

            t_planned, t_actual = task_month_totals.get(t_key, (ZERO, ZERO))
            task_month_totals[t_key] = (
                t_planned + entry.planned_person_days,
                t_actual + entry.actual_person_days,
            )

        snapshot_map = {snapshot.month_start: snapshot for snapshot in snapshots}

        assignment_set = {(assignment.task_id, assignment.performer_id) for assignment in assignments}
        task_assignments: dict[UUID, list[UUID]] = {}
        for task_id, performer_id in assignment_set:
            task_assignments.setdefault(task_id, []).append(performer_id)
        for values in task_assignments.values():
            values.sort(key=str)

        stage_rows = [self.serialize_stage(stage) for stage in stages]
        task_rows = [
            {
                **self.serialize_task(task),
                "monthly_totals": [
                    {
                        "month_start": month.isoformat(),
                        "planned_person_days": str(task_month_totals.get((task.id, month), (ZERO, ZERO))[0]),
                        "actual_person_days": str(task_month_totals.get((task.id, month), (ZERO, ZERO))[1]),
                    }
                    for month in months
                ],
                "performer_ids": [str(pid) for pid in task_assignments.get(task.id, [])],
            }
            for task in tasks
        ]

        performer_rows = [
            {
                **self.serialize_performer(performer),
                "monthly_totals": [
                    {
                        "month_start": month.isoformat(),
                        "planned_person_days": str(
                            performer_month_totals.get((performer.id, month), (ZERO, ZERO))[0]
                        ),
                        "actual_person_days": str(
                            performer_month_totals.get((performer.id, month), (ZERO, ZERO))[1]
                        ),
                    }
                    for month in months
                ],
            }
            for performer in performers
        ]

        matrix_entries: list[dict[str, str]] = []
        for task in tasks:
            for performer_id in task_assignments.get(task.id, []):
                for month in months:
                    entry = entry_map.get((task.id, performer_id, month))
                    matrix_entries.append(
                        {
                            "task_id": str(task.id),
                            "performer_id": str(performer_id),
                            "month_start": month.isoformat(),
                            "planned_person_days": str(entry.planned_person_days if entry else ZERO),
                            "actual_person_days": str(entry.actual_person_days if entry else ZERO),
                        }
                    )

        snapshot_rows = []
        for month in months:
            snap = snapshot_map.get(month)
            snapshot_rows.append(
                {
                    "month_start": month.isoformat(),
                    "planned_person_days": str(snap.planned_person_days if snap else ZERO),
                    "actual_person_days": str(snap.actual_person_days if snap else ZERO),
                    "planned_cost": str(snap.planned_cost if snap else ZERO),
                    "actual_cost": str(snap.actual_cost if snap else ZERO),
                    "revenue_amount": str(snap.revenue_amount if snap else ZERO),
                    "invoice_amount": str(snap.invoice_amount if snap else ZERO),
                    "cumulative_planned_cost": str(snap.cumulative_planned_cost if snap else ZERO),
                    "cumulative_actual_cost": str(snap.cumulative_actual_cost if snap else ZERO),
                    "cumulative_revenue": str(snap.cumulative_revenue if snap else ZERO),
                }
            )

        return {
            "project": self.serialize_project(project),
            "months": [month.isoformat() for month in months],
            "stages": stage_rows,
            "tasks": task_rows,
            "performers": performer_rows,
            "assignments": [self.serialize_assignment(assignment) for assignment in assignments],
            "entries": matrix_entries,
            "project_monthly_snapshots": snapshot_rows,
        }

    # ---------- Matrix write ----------
    def bulk_upsert_matrix_entries(
        self,
        *,
        context: RequestUserContext,
        project_id: UUID,
        entries: list[MatrixEntryInput],
    ) -> MatrixUpsertResult:
        project = self._ensure_project_access(context=context, project_id=project_id, allowed_roles=EDIT_ROLES)

        task_by_id = {task.id: task for task in self.repo.list_tasks(project.id)}
        performer_by_id = {
            performer.id: performer
            for performer in self.repo.list_performers_for_project(project.id, project.business_unit_id)
        }
        assignment_set = {
            (assignment.task_id, assignment.performer_id)
            for assignment in self.repo.list_assignments_for_project(project.id)
        }

        normalized: list[MatrixEntryInput] = []
        seen_keys: set[tuple[UUID, UUID, date]] = set()
        for payload in entries:
            month = normalize_month_start(payload.month_start)

            if payload.planned_person_days < ZERO or payload.actual_person_days < ZERO:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="planned_person_days and actual_person_days must be greater or equal zero.",
                )

            if month < project.start_month or month > project.end_month:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Matrix edits outside project month range are rejected.",
                )

            task = task_by_id.get(payload.task_id)
            if task is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="task_id must reference task in this project.",
                )
            if not task.active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Edits for inactive task are rejected.",
                )

            performer = performer_by_id.get(payload.performer_id)
            if performer is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="performer_id must reference performer in project business unit.",
                )
            if not performer.active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Edits for inactive performer are rejected.",
                )

            if (task.id, performer.id) not in assignment_set:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Task-performer pair must be assigned before matrix edits.",
                )

            dedup_key = (task.id, performer.id, month)
            if dedup_key in seen_keys:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Duplicate matrix entry key in bulk payload.",
                )
            seen_keys.add(dedup_key)

            normalized.append(
                MatrixEntryInput(
                    task_id=task.id,
                    performer_id=performer.id,
                    month_start=month,
                    planned_person_days=payload.planned_person_days,
                    actual_person_days=payload.actual_person_days,
                )
            )

        try:
            with self.db.begin_nested():
                for payload in normalized:
                    row = self.repo.get_effort_entry(
                        project_id=project.id,
                        task_id=payload.task_id,
                        performer_id=payload.performer_id,
                        month_start=payload.month_start,
                    )
                    if row is None:
                        self.repo.add_effort_entry(
                            EffortMonthlyEntry(
                                project_id=project.id,
                                task_id=payload.task_id,
                                performer_id=payload.performer_id,
                                month_start=payload.month_start,
                                planned_person_days=payload.planned_person_days,
                                actual_person_days=payload.actual_person_days,
                            )
                        )
                    else:
                        row.planned_person_days = payload.planned_person_days
                        row.actual_person_days = payload.actual_person_days

                snapshots = self.refresh_project_snapshots(project.id)

            self.db.commit()
        except HTTPException:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bulk matrix save violated entry uniqueness constraints.",
            ) from exc

        return MatrixUpsertResult(updated_entries=len(normalized), snapshots=snapshots)

    # ---------- Snapshot refresh ----------
    def refresh_project_snapshots(self, project_id: UUID) -> list[ProjectMonthlySnapshot]:
        project = self.repo.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        months = month_sequence(project.start_month, project.end_month)
        effort_entries = self.repo.list_effort_entries(
            project.id,
            from_month=project.start_month,
            to_month=project.end_month,
        )
        rates = self.repo.list_rates_for_business_unit(project.business_unit_id, project_id=project.id)
        invoice_by_month = self.repo.aggregate_invoices_by_month(project.id)
        revenue_by_month = self.repo.aggregate_revenues_by_month(project.id)

        rates_by_performer: dict[UUID, list[PerformerRate]] = {}
        for rate in rates:
            rates_by_performer.setdefault(rate.performer_id, []).append(rate)

        totals: dict[date, dict[str, Decimal]] = {
            month: {
                "planned_person_days": ZERO,
                "actual_person_days": ZERO,
                "planned_cost": ZERO,
                "actual_cost": ZERO,
            }
            for month in months
        }
        for entry in effort_entries:
            bucket = totals.setdefault(
                entry.month_start,
                {
                    "planned_person_days": ZERO,
                    "actual_person_days": ZERO,
                    "planned_cost": ZERO,
                    "actual_cost": ZERO,
                },
            )
            bucket["planned_person_days"] += entry.planned_person_days
            bucket["actual_person_days"] += entry.actual_person_days

            rate = self._resolve_effective_rate(
                rates_by_performer=rates_by_performer,
                performer_id=entry.performer_id,
                project_id=project.id,
                month_start=entry.month_start,
            )
            if rate is None:
                continue

            rate_per_day = self._rate_value_per_day(rate)
            bucket["planned_cost"] += _q2(entry.planned_person_days * rate_per_day)
            bucket["actual_cost"] += _q2(entry.actual_person_days * rate_per_day)

        cumulative_planned_cost = ZERO
        cumulative_actual_cost = ZERO
        cumulative_revenue = ZERO

        refreshed: list[ProjectMonthlySnapshot] = []
        for month in months:
            bucket = totals.get(month) or {
                "planned_person_days": ZERO,
                "actual_person_days": ZERO,
                "planned_cost": ZERO,
                "actual_cost": ZERO,
            }
            planned_total = _q2(bucket["planned_person_days"])
            actual_total = _q2(bucket["actual_person_days"])
            planned_cost = _q2(bucket["planned_cost"])
            actual_cost = _q2(bucket["actual_cost"])
            revenue_amount = _q2(revenue_by_month.get(month, ZERO))
            invoice_amount = _q2(invoice_by_month.get(month, ZERO))

            cumulative_planned_cost = _q2(cumulative_planned_cost + planned_cost)
            cumulative_actual_cost = _q2(cumulative_actual_cost + actual_cost)
            cumulative_revenue = _q2(cumulative_revenue + revenue_amount)

            snapshot = self.repo.get_snapshot(project_id=project.id, month_start=month)
            if snapshot is None:
                snapshot = ProjectMonthlySnapshot(
                    project_id=project.id,
                    month_start=month,
                    planned_person_days=planned_total,
                    actual_person_days=actual_total,
                    planned_cost=planned_cost,
                    actual_cost=actual_cost,
                    revenue_amount=revenue_amount,
                    invoice_amount=invoice_amount,
                    cumulative_planned_cost=cumulative_planned_cost,
                    cumulative_actual_cost=cumulative_actual_cost,
                    cumulative_revenue=cumulative_revenue,
                )
                self.repo.add_snapshot(snapshot)
            else:
                snapshot.planned_person_days = planned_total
                snapshot.actual_person_days = actual_total
                snapshot.planned_cost = planned_cost
                snapshot.actual_cost = actual_cost
                snapshot.revenue_amount = revenue_amount
                snapshot.invoice_amount = invoice_amount
                snapshot.cumulative_planned_cost = cumulative_planned_cost
                snapshot.cumulative_actual_cost = cumulative_actual_cost
                snapshot.cumulative_revenue = cumulative_revenue

            refreshed.append(snapshot)

        self.repo.delete_snapshots_outside_range(
            project.id,
            start_month=project.start_month,
            end_month=project.end_month,
        )
        self.db.flush()
        return refreshed
