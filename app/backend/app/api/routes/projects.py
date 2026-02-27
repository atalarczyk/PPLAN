"""Project setup and lifecycle endpoints for phase-2 backend scope."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import RequestUserContext, get_current_user_context
from app.db.dependencies import get_db_session
from app.models.entities import ProjectStatus
from app.services.planning_service import (
    AssignmentCreateData,
    PerformerCreateData,
    PerformerUpdateData,
    PlanningService,
    ProjectCreateData,
    ProjectUpdateData,
    StageCreateData,
    StageUpdateData,
    TaskCreateData,
    TaskUpdateData,
)

router = APIRouter(tags=["projects"])


class ProjectCreatePayload(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    start_month: date
    end_month: date
    status: ProjectStatus = ProjectStatus.DRAFT


class ProjectUpdatePayload(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    start_month: date | None = None
    end_month: date | None = None
    status: ProjectStatus | None = None


class StageCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_month: date
    end_month: date
    color_token: str = Field(min_length=1, max_length=32)
    sequence_no: int = Field(ge=0)


class StageUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_month: date | None = None
    end_month: date | None = None
    color_token: str | None = Field(default=None, min_length=1, max_length=32)
    sequence_no: int | None = Field(default=None, ge=0)


class TaskCreatePayload(BaseModel):
    stage_id: UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    sequence_no: int = Field(ge=0)
    active: bool = True


class TaskUpdatePayload(BaseModel):
    stage_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_no: int | None = Field(default=None, ge=0)
    active: bool | None = None


class PerformerCreatePayload(BaseModel):
    external_ref: str | None = Field(default=None, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    active: bool = True


class PerformerUpdatePayload(BaseModel):
    external_ref: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class AssignmentCreatePayload(BaseModel):
    task_id: UUID
    performer_id: UUID


def _planning_service(db: Session) -> PlanningService:
    return PlanningService(db)


@router.get("/business-units/{business_unit_id}/projects")
def list_business_unit_projects(
    business_unit_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    service = _planning_service(db)
    items = service.list_projects(context=context, business_unit_id=business_unit_id)
    return {"items": [service.serialize_project(project) for project in items]}


@router.post("/business-units/{business_unit_id}/projects", status_code=status.HTTP_201_CREATED)
def create_business_unit_project(
    business_unit_id: UUID,
    payload: ProjectCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    project = service.create_project(
        context=context,
        business_unit_id=business_unit_id,
        data=ProjectCreateData(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            start_month=payload.start_month,
            end_month=payload.end_month,
            status=payload.status,
        ),
    )
    return service.serialize_project(project)


@router.get("/projects/{project_id}")
def get_project(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    project = service.get_project(context=context, project_id=project_id)
    return service.serialize_project(project)


@router.patch("/projects/{project_id}")
def update_project(
    project_id: UUID,
    payload: ProjectUpdatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    project = service.update_project(
        context=context,
        project_id=project_id,
        data=ProjectUpdateData(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            start_month=payload.start_month,
            end_month=payload.end_month,
            status=payload.status,
        ),
    )
    return service.serialize_project(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _planning_service(db)
    service.delete_project(context=context, project_id=project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/stages")
def list_project_stages(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    service = _planning_service(db)
    rows = service.list_stages(context=context, project_id=project_id)
    return {"items": [service.serialize_stage(stage) for stage in rows]}


@router.post("/projects/{project_id}/stages", status_code=status.HTTP_201_CREATED)
def create_project_stage(
    project_id: UUID,
    payload: StageCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    stage = service.create_stage(
        context=context,
        project_id=project_id,
        data=StageCreateData(
            name=payload.name,
            start_month=payload.start_month,
            end_month=payload.end_month,
            color_token=payload.color_token,
            sequence_no=payload.sequence_no,
        ),
    )
    return service.serialize_stage(stage)


@router.patch("/projects/{project_id}/stages/{stage_id}")
def update_project_stage(
    project_id: UUID,
    stage_id: UUID,
    payload: StageUpdatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    stage = service.update_stage(
        context=context,
        project_id=project_id,
        stage_id=stage_id,
        data=StageUpdateData(
            name=payload.name,
            start_month=payload.start_month,
            end_month=payload.end_month,
            color_token=payload.color_token,
            sequence_no=payload.sequence_no,
        ),
    )
    return service.serialize_stage(stage)


@router.delete("/projects/{project_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_stage(
    project_id: UUID,
    stage_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _planning_service(db)
    service.delete_stage(context=context, project_id=project_id, stage_id=stage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/tasks")
def list_project_tasks(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    service = _planning_service(db)
    rows = service.list_tasks(context=context, project_id=project_id)
    return {"items": [service.serialize_task(task) for task in rows]}


@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def create_project_task(
    project_id: UUID,
    payload: TaskCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    task = service.create_task(
        context=context,
        project_id=project_id,
        data=TaskCreateData(
            stage_id=payload.stage_id,
            code=payload.code,
            name=payload.name,
            sequence_no=payload.sequence_no,
            active=payload.active,
        ),
    )
    return service.serialize_task(task)


@router.patch("/projects/{project_id}/tasks/{task_id}")
def update_project_task(
    project_id: UUID,
    task_id: UUID,
    payload: TaskUpdatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    task = service.update_task(
        context=context,
        project_id=project_id,
        task_id=task_id,
        data=TaskUpdateData(
            stage_id=payload.stage_id,
            code=payload.code,
            name=payload.name,
            sequence_no=payload.sequence_no,
            active=payload.active,
        ),
    )
    return service.serialize_task(task)


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_task(
    project_id: UUID,
    task_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _planning_service(db)
    service.delete_task(context=context, project_id=project_id, task_id=task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/performers")
def list_project_performers(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    service = _planning_service(db)
    rows = service.list_project_performers(context=context, project_id=project_id)
    return {"items": [service.serialize_performer(performer) for performer in rows]}


@router.post("/projects/{project_id}/performers", status_code=status.HTTP_201_CREATED)
def create_project_performer(
    project_id: UUID,
    payload: PerformerCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    performer = service.create_project_performer(
        context=context,
        project_id=project_id,
        data=PerformerCreateData(
            external_ref=payload.external_ref,
            display_name=payload.display_name,
            active=payload.active,
        ),
    )
    return service.serialize_performer(performer)


@router.patch("/projects/{project_id}/performers/{performer_id}")
def update_project_performer(
    project_id: UUID,
    performer_id: UUID,
    payload: PerformerUpdatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    performer = service.update_project_performer(
        context=context,
        project_id=project_id,
        performer_id=performer_id,
        data=PerformerUpdateData(
            external_ref=payload.external_ref,
            display_name=payload.display_name,
            active=payload.active,
        ),
    )
    return service.serialize_performer(performer)


@router.delete(
    "/projects/{project_id}/performers/{performer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_project_performer(
    project_id: UUID,
    performer_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _planning_service(db)
    service.delete_project_performer(
        context=context,
        project_id=project_id,
        performer_id=performer_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/task-performer-assignments")
def list_task_performer_assignments(
    project_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    service = _planning_service(db)
    rows = service.list_assignments(context=context, project_id=project_id)
    return {"items": [service.serialize_assignment(assignment) for assignment in rows]}


@router.post(
    "/projects/{project_id}/task-performer-assignments",
    status_code=status.HTTP_201_CREATED,
)
def create_task_performer_assignment(
    project_id: UUID,
    payload: AssignmentCreatePayload,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    service = _planning_service(db)
    assignment = service.create_assignment(
        context=context,
        project_id=project_id,
        data=AssignmentCreateData(
            task_id=payload.task_id,
            performer_id=payload.performer_id,
        ),
    )
    return service.serialize_assignment(assignment)


@router.delete(
    "/projects/{project_id}/task-performer-assignments/{task_id}/{performer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task_performer_assignment(
    project_id: UUID,
    task_id: UUID,
    performer_id: UUID,
    context: RequestUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db_session),
) -> Response:
    service = _planning_service(db)
    service.delete_assignment(
        context=context,
        project_id=project_id,
        task_id=task_id,
        performer_id=performer_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
