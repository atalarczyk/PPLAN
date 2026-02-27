from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import APP_ROLE_TO_DB_ROLE, AppRole, ensure_user_principal
from app.models.entities import BusinessUnit, RoleAssignment


def _headers(oid: str, email: str, display_name: str) -> dict[str, str]:
    return {
        "X-MS-OID": oid,
        "X-MS-EMAIL": email,
        "X-MS-DISPLAY-NAME": display_name,
    }


def _create_business_unit(db: Session, *, code: str, name: str) -> BusinessUnit:
    now = datetime.utcnow()
    row = BusinessUnit(code=code, name=name, active=True, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _assign_role(
    db: Session,
    *,
    oid: str,
    email: str,
    display_name: str,
    role: AppRole,
    business_unit_id: uuid.UUID | None,
) -> None:
    user = ensure_user_principal(db, microsoft_oid=oid, email=email, display_name=display_name)
    now = datetime.utcnow()
    assignment = RoleAssignment(
        user_id=user.id,
        business_unit_id=business_unit_id,
        role=APP_ROLE_TO_DB_ROLE[role],
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(assignment)
    db.commit()


def _create_project_with_stage_task_assignment(
    client: TestClient,
    headers: dict[str, str],
    business_unit_id: str,
) -> tuple[str, str, str, str]:
    create_project = client.post(
        f"/api/v1/business-units/{business_unit_id}/projects",
        headers=headers,
        json={
            "code": "PRJ-1",
            "name": "Project 1",
            "description": "phase2",
            "start_month": "2026-01-01",
            "end_month": "2026-03-01",
            "status": "active",
        },
    )
    assert create_project.status_code == 201
    project_id = create_project.json()["id"]

    create_stage = client.post(
        f"/api/v1/projects/{project_id}/stages",
        headers=headers,
        json={
            "name": "Stage A",
            "start_month": "2026-01-01",
            "end_month": "2026-02-01",
            "color_token": "blue",
            "sequence_no": 1,
        },
    )
    assert create_stage.status_code == 201
    stage_id = create_stage.json()["id"]

    create_task = client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={
            "stage_id": stage_id,
            "code": "T-1",
            "name": "Task 1",
            "sequence_no": 1,
            "active": True,
        },
    )
    assert create_task.status_code == 201
    task_id = create_task.json()["id"]

    create_performer = client.post(
        f"/api/v1/projects/{project_id}/performers",
        headers=headers,
        json={"display_name": "Alice", "external_ref": "EMP-1", "active": True},
    )
    assert create_performer.status_code == 201
    performer_id = create_performer.json()["id"]

    create_assignment = client.post(
        f"/api/v1/projects/{project_id}/task-performer-assignments",
        headers=headers,
        json={"task_id": task_id, "performer_id": performer_id},
    )
    assert create_assignment.status_code == 201

    return project_id, stage_id, task_id, performer_id


def test_project_crud_and_scoping(client: TestClient, db_session: Session) -> None:
    unit_owned = _create_business_unit(db_session, code="BU-P2-A", name="Owned")
    unit_other = _create_business_unit(db_session, code="BU-P2-B", name="Other")
    _assign_role(
        db_session,
        oid="oid-editor-owned",
        email="editor.owned@test.local",
        display_name="Editor Owned",
        role=AppRole.EDITOR,
        business_unit_id=unit_owned.id,
    )

    headers = _headers("oid-editor-owned", "editor.owned@test.local", "Editor Owned")

    denied = client.post(
        f"/api/v1/business-units/{unit_other.id}/projects",
        headers=headers,
        json={
            "code": "DENY",
            "name": "Denied",
            "start_month": "2026-01-01",
            "end_month": "2026-02-01",
            "status": "draft",
        },
    )
    assert denied.status_code == 403

    create = client.post(
        f"/api/v1/business-units/{unit_owned.id}/projects",
        headers=headers,
        json={
            "code": "P-OWN-1",
            "name": "Owned Project",
            "description": "desc",
            "start_month": "2026-01-01",
            "end_month": "2026-03-01",
            "status": "draft",
        },
    )
    assert create.status_code == 201
    project = create.json()
    assert project["business_unit_id"] == str(unit_owned.id)

    listing = client.get(f"/api/v1/business-units/{unit_owned.id}/projects", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1

    patch = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"name": "Owned Project Updated", "status": "active"},
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "Owned Project Updated"
    assert patch.json()["status"] == "active"


def test_stage_task_performer_assignment_crud(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P2-CRUD", name="CRUD")
    _assign_role(
        db_session,
        oid="oid-editor-crud",
        email="editor.crud@test.local",
        display_name="Editor CRUD",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    headers = _headers("oid-editor-crud", "editor.crud@test.local", "Editor CRUD")

    project_id, stage_id, task_id, performer_id = _create_project_with_stage_task_assignment(
        client,
        headers,
        str(unit.id),
    )

    stages = client.get(f"/api/v1/projects/{project_id}/stages", headers=headers)
    assert stages.status_code == 200
    assert len(stages.json()["items"]) == 1

    tasks = client.get(f"/api/v1/projects/{project_id}/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()["items"]) == 1

    performers = client.get(f"/api/v1/projects/{project_id}/performers", headers=headers)
    assert performers.status_code == 200
    assert len(performers.json()["items"]) == 1

    assignments = client.get(f"/api/v1/projects/{project_id}/task-performer-assignments", headers=headers)
    assert assignments.status_code == 200
    assert len(assignments.json()["items"]) == 1

    deactivate_task = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers=headers,
        json={"active": False},
    )
    assert deactivate_task.status_code == 200
    assert deactivate_task.json()["active"] is False

    activate_task = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task_id}",
        headers=headers,
        json={"active": True},
    )
    assert activate_task.status_code == 200
    assert activate_task.json()["active"] is True

    # Cannot delete assignment/task/stage/performer in wrong order while dependencies exist.
    del_stage_conflict = client.delete(f"/api/v1/projects/{project_id}/stages/{stage_id}", headers=headers)
    assert del_stage_conflict.status_code == 409

    del_task_conflict = client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=headers)
    assert del_task_conflict.status_code == 409

    del_performer_conflict = client.delete(
        f"/api/v1/projects/{project_id}/performers/{performer_id}",
        headers=headers,
    )
    assert del_performer_conflict.status_code == 409

    del_assignment = client.delete(
        f"/api/v1/projects/{project_id}/task-performer-assignments/{task_id}/{performer_id}",
        headers=headers,
    )
    assert del_assignment.status_code == 204

    del_task = client.delete(f"/api/v1/projects/{project_id}/tasks/{task_id}", headers=headers)
    assert del_task.status_code == 204

    del_stage = client.delete(f"/api/v1/projects/{project_id}/stages/{stage_id}", headers=headers)
    assert del_stage.status_code == 204

    del_performer = client.delete(
        f"/api/v1/projects/{project_id}/performers/{performer_id}",
        headers=headers,
    )
    assert del_performer.status_code == 204


def test_matrix_read_and_bulk_write_success(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P2-M", name="Matrix")
    _assign_role(
        db_session,
        oid="oid-editor-matrix",
        email="editor.matrix@test.local",
        display_name="Editor Matrix",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    headers = _headers("oid-editor-matrix", "editor.matrix@test.local", "Editor Matrix")

    project_id, _stage_id, task_id, performer_id = _create_project_with_stage_task_assignment(
        client,
        headers,
        str(unit.id),
    )

    upsert = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "2.50",
                    "actual_person_days": "1.00",
                },
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-02-01",
                    "planned_person_days": "3.00",
                    "actual_person_days": "1.50",
                },
            ]
        },
    )
    assert upsert.status_code == 200
    upsert_payload = upsert.json()
    assert upsert_payload["updated_entries"] == 2
    assert len(upsert_payload["project_monthly_snapshots"]) == 3

    read_matrix = client.get(f"/api/v1/projects/{project_id}/matrix", headers=headers)
    assert read_matrix.status_code == 200
    matrix = read_matrix.json()

    assert matrix["months"] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert len(matrix["entries"]) == 3

    january_entry = next(
        row for row in matrix["entries"] if row["month_start"] == "2026-01-01"
    )
    assert Decimal(january_entry["planned_person_days"]) == Decimal("2.50")
    assert Decimal(january_entry["actual_person_days"]) == Decimal("1.00")

    snapshots = {row["month_start"]: row for row in matrix["project_monthly_snapshots"]}
    assert Decimal(snapshots["2026-01-01"]["planned_person_days"]) == Decimal("2.50")
    assert Decimal(snapshots["2026-02-01"]["planned_person_days"]) == Decimal("3.00")
    assert Decimal(snapshots["2026-03-01"]["planned_person_days"]) == Decimal("0.00")


def test_matrix_validation_failures_and_rbac(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P2-V", name="Validation")
    _assign_role(
        db_session,
        oid="oid-editor-val",
        email="editor.val@test.local",
        display_name="Editor Validation",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    _assign_role(
        db_session,
        oid="oid-viewer-val",
        email="viewer.val@test.local",
        display_name="Viewer Validation",
        role=AppRole.VIEWER,
        business_unit_id=unit.id,
    )

    editor_headers = _headers("oid-editor-val", "editor.val@test.local", "Editor Validation")
    viewer_headers = _headers("oid-viewer-val", "viewer.val@test.local", "Viewer Validation")

    project_id, _stage_id, task_id, performer_id = _create_project_with_stage_task_assignment(
        client,
        editor_headers,
        str(unit.id),
    )

    invalid_month = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=editor_headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-02",
                    "planned_person_days": "1.00",
                    "actual_person_days": "0.50",
                }
            ]
        },
    )
    assert invalid_month.status_code == 422

    invalid_negative = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=editor_headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "-1.00",
                    "actual_person_days": "0.50",
                }
            ]
        },
    )
    assert invalid_negative.status_code == 422

    invalid_range = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=editor_headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-04-01",
                    "planned_person_days": "1.00",
                    "actual_person_days": "0.50",
                }
            ]
        },
    )
    assert invalid_range.status_code == 422

    viewer_forbidden = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=viewer_headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "1.00",
                    "actual_person_days": "0.50",
                }
            ]
        },
    )
    assert viewer_forbidden.status_code == 403


def test_bulk_upsert_is_transactional_on_invalid_payload(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P2-TX", name="Transactional")
    _assign_role(
        db_session,
        oid="oid-editor-tx",
        email="editor.tx@test.local",
        display_name="Editor TX",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    headers = _headers("oid-editor-tx", "editor.tx@test.local", "Editor TX")

    project_id, _stage_id, task_id, performer_id = _create_project_with_stage_task_assignment(
        client,
        headers,
        str(unit.id),
    )

    initial = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "1.00",
                    "actual_person_days": "0.25",
                }
            ]
        },
    )
    assert initial.status_code == 200

    invalid_batch = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "9.00",
                    "actual_person_days": "2.00",
                },
                {
                    "task_id": task_id,
                    "performer_id": performer_id,
                    "month_start": "2026-01-01",
                    "planned_person_days": "10.00",
                    "actual_person_days": "3.00",
                },
            ]
        },
    )
    assert invalid_batch.status_code == 422

    matrix = client.get(f"/api/v1/projects/{project_id}/matrix", headers=headers)
    assert matrix.status_code == 200
    jan_entry = next(row for row in matrix.json()["entries"] if row["month_start"] == "2026-01-01")
    assert Decimal(jan_entry["planned_person_days"]) == Decimal("1.00")
    assert Decimal(jan_entry["actual_person_days"]) == Decimal("0.25")


def test_viewer_can_read_but_cannot_edit_project_setup(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P2-VIEW", name="Viewer Scope")
    _assign_role(
        db_session,
        oid="oid-editor-view-scope",
        email="editor.view.scope@test.local",
        display_name="Editor View Scope",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    _assign_role(
        db_session,
        oid="oid-viewer-scope",
        email="viewer.scope@test.local",
        display_name="Viewer Scope",
        role=AppRole.VIEWER,
        business_unit_id=unit.id,
    )

    editor_headers = _headers(
        "oid-editor-view-scope",
        "editor.view.scope@test.local",
        "Editor View Scope",
    )
    viewer_headers = _headers("oid-viewer-scope", "viewer.scope@test.local", "Viewer Scope")

    create = client.post(
        f"/api/v1/business-units/{unit.id}/projects",
        headers=editor_headers,
        json={
            "code": "P-VIEW",
            "name": "Project Viewer",
            "start_month": "2026-01-01",
            "end_month": "2026-02-01",
            "status": "draft",
        },
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    read_allowed = client.get(f"/api/v1/projects/{project_id}", headers=viewer_headers)
    assert read_allowed.status_code == 200

    mutate_denied = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=viewer_headers,
        json={"name": "Should Fail"},
    )
    assert mutate_denied.status_code == 403
