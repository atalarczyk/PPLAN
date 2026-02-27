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


def _create_project_with_two_performers(
    client: TestClient,
    headers: dict[str, str],
    business_unit_id: str,
) -> tuple[str, str, str, str, str]:
    create_project = client.post(
        f"/api/v1/business-units/{business_unit_id}/projects",
        headers=headers,
        json={
            "code": "PH3-P1",
            "name": "Phase 3 Project",
            "description": "phase3",
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
            "end_month": "2026-03-01",
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
            "code": "TASK-1",
            "name": "Task One",
            "sequence_no": 1,
            "active": True,
        },
    )
    assert create_task.status_code == 201
    task_id = create_task.json()["id"]

    perf_a = client.post(
        f"/api/v1/projects/{project_id}/performers",
        headers=headers,
        json={"display_name": "Alice", "external_ref": "EMP-A", "active": True},
    )
    assert perf_a.status_code == 201
    performer_a = perf_a.json()["id"]

    perf_b = client.post(
        f"/api/v1/projects/{project_id}/performers",
        headers=headers,
        json={"display_name": "Bob", "external_ref": "EMP-B", "active": True},
    )
    assert perf_b.status_code == 201
    performer_b = perf_b.json()["id"]

    assign_a = client.post(
        f"/api/v1/projects/{project_id}/task-performer-assignments",
        headers=headers,
        json={"task_id": task_id, "performer_id": performer_a},
    )
    assert assign_a.status_code == 201

    assign_b = client.post(
        f"/api/v1/projects/{project_id}/task-performer-assignments",
        headers=headers,
        json={"task_id": task_id, "performer_id": performer_b},
    )
    assert assign_b.status_code == 201

    return project_id, task_id, performer_a, performer_b, stage_id


def _seed_effort(client: TestClient, headers: dict[str, str], project_id: str, task_id: str, performer_a: str, performer_b: str) -> None:
    upsert = client.put(
        f"/api/v1/projects/{project_id}/matrix/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "task_id": task_id,
                    "performer_id": performer_a,
                    "month_start": "2026-01-01",
                    "planned_person_days": "2.00",
                    "actual_person_days": "1.00",
                },
                {
                    "task_id": task_id,
                    "performer_id": performer_a,
                    "month_start": "2026-02-01",
                    "planned_person_days": "3.00",
                    "actual_person_days": "2.00",
                },
                {
                    "task_id": task_id,
                    "performer_id": performer_b,
                    "month_start": "2026-01-01",
                    "planned_person_days": "1.00",
                    "actual_person_days": "0.50",
                },
            ]
        },
    )
    assert upsert.status_code == 200


def test_rates_finance_summary_and_registers(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P3-FIN", name="Finance")
    _assign_role(
        db_session,
        oid="oid-editor-fin",
        email="editor.fin@test.local",
        display_name="Editor Finance",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    headers = _headers("oid-editor-fin", "editor.fin@test.local", "Editor Finance")

    project_id, task_id, performer_a, performer_b, _ = _create_project_with_two_performers(
        client,
        headers,
        str(unit.id),
    )
    _seed_effort(client, headers, project_id, task_id, performer_a, performer_b)

    rates_bulk = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "100.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": "2026-01-01",
                },
                {
                    "performer_id": performer_a,
                    "project_id": project_id,
                    "rate_unit": "day",
                    "rate_value": "200.00",
                    "effective_from_month": "2026-02-01",
                    "effective_to_month": None,
                },
                {
                    "performer_id": performer_b,
                    "project_id": None,
                    "rate_unit": "fte_month",
                    "rate_value": "2000.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": None,
                },
            ]
        },
    )
    assert rates_bulk.status_code == 200
    assert rates_bulk.json()["updated_entries"] == 3

    add_request = client.post(
        f"/api/v1/projects/{project_id}/financial-requests",
        headers=headers,
        json={
            "request_no": "REQ-1",
            "request_date": "2026-01-15",
            "month_start": "2026-01-01",
            "amount": "1000.00",
            "currency": "PLN",
            "status": "approved",
        },
    )
    assert add_request.status_code == 201

    add_invoice = client.post(
        f"/api/v1/projects/{project_id}/invoices",
        headers=headers,
        json={
            "invoice_no": "INV-1",
            "invoice_date": "2026-01-20",
            "month_start": "2026-01-01",
            "amount": "800.00",
            "currency": "PLN",
            "payment_status": "paid",
            "payment_date": "2026-01-25",
        },
    )
    assert add_invoice.status_code == 201

    add_revenue = client.post(
        f"/api/v1/projects/{project_id}/revenues",
        headers=headers,
        json={
            "revenue_no": "REV-1",
            "recognition_date": "2026-01-28",
            "month_start": "2026-01-01",
            "amount": "1500.00",
            "currency": "PLN",
        },
    )
    assert add_revenue.status_code == 201

    summary = client.get(f"/api/v1/projects/{project_id}/finance-summary", headers=headers)
    assert summary.status_code == 200
    months = {row["month_start"]: row for row in summary.json()["months"]}

    # Jan planned: Alice 2*100 + Bob 1*(2000/20=100) = 300
    # Jan actual : Alice 1*100 + Bob 0.5*100 = 150
    assert Decimal(months["2026-01-01"]["planned_cost"]) == Decimal("300.00")
    assert Decimal(months["2026-01-01"]["actual_cost"]) == Decimal("150.00")

    # Feb planned/actual for Alice should use project-specific 200/day
    assert Decimal(months["2026-02-01"]["planned_cost"]) == Decimal("600.00")
    assert Decimal(months["2026-02-01"]["actual_cost"]) == Decimal("400.00")

    assert Decimal(months["2026-01-01"]["invoice_amount"]) == Decimal("800.00")
    assert Decimal(months["2026-01-01"]["revenue_amount"]) == Decimal("1500.00")


def test_rate_overlap_and_scope_rbac_failures(client: TestClient, db_session: Session) -> None:
    unit_a = _create_business_unit(db_session, code="BU-P3-A", name="A")
    unit_b = _create_business_unit(db_session, code="BU-P3-B", name="B")

    _assign_role(
        db_session,
        oid="oid-editor-a",
        email="editor.a@test.local",
        display_name="Editor A",
        role=AppRole.EDITOR,
        business_unit_id=unit_a.id,
    )
    _assign_role(
        db_session,
        oid="oid-viewer-a",
        email="viewer.a@test.local",
        display_name="Viewer A",
        role=AppRole.VIEWER,
        business_unit_id=unit_a.id,
    )

    headers_editor = _headers("oid-editor-a", "editor.a@test.local", "Editor A")
    headers_viewer = _headers("oid-viewer-a", "viewer.a@test.local", "Viewer A")

    project_id, task_id, performer_a, performer_b, _ = _create_project_with_two_performers(
        client,
        headers_editor,
        str(unit_a.id),
    )
    _seed_effort(client, headers_editor, project_id, task_id, performer_a, performer_b)

    first_rate = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers_editor,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "100.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": "2026-02-01",
                }
            ]
        },
    )
    assert first_rate.status_code == 200

    overlap_rate = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers_editor,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "120.00",
                    "effective_from_month": "2026-02-01",
                    "effective_to_month": "2026-03-01",
                }
            ]
        },
    )
    assert overlap_rate.status_code == 422

    viewer_mutate_denied = client.post(
        f"/api/v1/projects/{project_id}/invoices",
        headers=headers_viewer,
        json={
            "invoice_no": "INV-V",
            "invoice_date": "2026-01-10",
            "month_start": "2026-01-01",
            "amount": "100.00",
            "currency": "PLN",
            "payment_status": "unpaid",
            "payment_date": None,
        },
    )
    assert viewer_mutate_denied.status_code == 403

    # Viewer can still read scoped report endpoint.
    viewer_read_ok = client.get(f"/api/v1/reports/projects/{project_id}/effort-by-task", headers=headers_viewer)
    assert viewer_read_ok.status_code == 200

    # Access to other BU should fail.
    project_b_create = client.post(
        f"/api/v1/business-units/{unit_b.id}/projects",
        headers=headers_editor,
        json={
            "code": "NOPE",
            "name": "Denied",
            "start_month": "2026-01-01",
            "end_month": "2026-01-01",
            "status": "draft",
        },
    )
    assert project_b_create.status_code == 403


def test_reports_dashboards_and_exports(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-P3-R", name="Reports")
    _assign_role(
        db_session,
        oid="oid-editor-r",
        email="editor.r@test.local",
        display_name="Editor Reports",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    _assign_role(
        db_session,
        oid="oid-viewer-r",
        email="viewer.r@test.local",
        display_name="Viewer Reports",
        role=AppRole.VIEWER,
        business_unit_id=unit.id,
    )

    headers_editor = _headers("oid-editor-r", "editor.r@test.local", "Editor Reports")
    headers_viewer = _headers("oid-viewer-r", "viewer.r@test.local", "Viewer Reports")

    project_id, task_id, performer_a, performer_b, _ = _create_project_with_two_performers(
        client,
        headers_editor,
        str(unit.id),
    )
    _seed_effort(client, headers_editor, project_id, task_id, performer_a, performer_b)

    rates_bulk = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers_editor,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "100.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": None,
                },
                {
                    "performer_id": performer_b,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "80.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": None,
                },
            ]
        },
    )
    assert rates_bulk.status_code == 200

    invoice = client.post(
        f"/api/v1/projects/{project_id}/invoices",
        headers=headers_editor,
        json={
            "invoice_no": "INV-2",
            "invoice_date": "2026-02-01",
            "month_start": "2026-02-01",
            "amount": "900.00",
            "currency": "PLN",
            "payment_status": "paid",
            "payment_date": "2026-02-05",
        },
    )
    assert invoice.status_code == 201

    revenue = client.post(
        f"/api/v1/projects/{project_id}/revenues",
        headers=headers_editor,
        json={
            "revenue_no": "REV-2",
            "recognition_date": "2026-02-06",
            "month_start": "2026-02-01",
            "amount": "1500.00",
            "currency": "PLN",
        },
    )
    assert revenue.status_code == 201

    effort_by_performer = client.get(
        f"/api/v1/reports/projects/{project_id}/effort-by-performer",
        headers=headers_viewer,
    )
    assert effort_by_performer.status_code == 200
    effort_rows = effort_by_performer.json()["rows"]
    assert len(effort_rows) == 2

    cost_by_task = client.get(
        f"/api/v1/reports/projects/{project_id}/cost-by-task",
        headers=headers_viewer,
    )
    assert cost_by_task.status_code == 200
    assert len(cost_by_task.json()["rows"]) == 1

    filtered = client.get(
        f"/api/v1/reports/projects/{project_id}/effort-by-performer",
        params={"performer_id": performer_a},
        headers=headers_viewer,
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["rows"]) == 1

    project_dashboard = client.get(f"/api/v1/dashboards/projects/{project_id}", headers=headers_viewer)
    assert project_dashboard.status_code == 200
    project_payload = project_dashboard.json()
    assert len(project_payload["cumulative_cost_trend"]) == 3
    assert len(project_payload["workload_trend"]) == 2
    assert len(project_payload["realization_trend"]) == 3

    bu_dashboard = client.get(f"/api/v1/dashboards/business-units/{unit.id}", headers=headers_viewer)
    assert bu_dashboard.status_code == 200
    bu_payload = bu_dashboard.json()
    assert bu_payload["scope"] == "business_unit"
    assert len(bu_payload["aggregated_cumulative_cost_trend"]) >= 1
    assert len(bu_payload["realization_trend"]) >= 1

    export_csv = client.get(
        "/api/v1/exports/effort-by-performer",
        params={"project_id": project_id, "format": "csv"},
        headers=headers_viewer,
    )
    assert export_csv.status_code == 200
    assert export_csv.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in export_csv.headers["content-disposition"]
    assert b"month_start" in export_csv.content

    export_xlsx = client.get(
        "/api/v1/exports/cost-by-task",
        params={"project_id": project_id, "format": "xlsx"},
        headers=headers_viewer,
    )
    assert export_xlsx.status_code == 200
    assert (
        export_xlsx.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment; filename=" in export_xlsx.headers["content-disposition"]
    assert len(export_xlsx.content) > 0


def test_finance_edge_validations_for_ranges_and_rate_payload(
    client: TestClient,
    db_session: Session,
) -> None:
    unit = _create_business_unit(db_session, code="BU-P3-EDGE", name="Finance Edge")
    _assign_role(
        db_session,
        oid="oid-editor-edge",
        email="editor.edge@test.local",
        display_name="Editor Edge",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )
    headers = _headers("oid-editor-edge", "editor.edge@test.local", "Editor Edge")

    project_id, _task_id, performer_a, _performer_b, _stage_id = _create_project_with_two_performers(
        client,
        headers,
        str(unit.id),
    )

    summary_outside_range = client.get(
        f"/api/v1/projects/{project_id}/finance-summary",
        params={"from_month": "2025-12-01", "to_month": "2026-01-01"},
        headers=headers,
    )
    assert summary_outside_range.status_code == 422
    assert "within project month range" in summary_outside_range.json()["detail"]

    summary_invalid_order = client.get(
        f"/api/v1/projects/{project_id}/finance-summary",
        params={"from_month": "2026-03-01", "to_month": "2026-02-01"},
        headers=headers,
    )
    assert summary_invalid_order.status_code == 422
    assert "greater than or equal" in summary_invalid_order.json()["detail"]

    request_outside_project_range = client.post(
        f"/api/v1/projects/{project_id}/financial-requests",
        headers=headers,
        json={
            "request_no": "REQ-EDGE-1",
            "request_date": "2026-02-15",
            "month_start": "2026-04-01",
            "amount": "10.00",
            "currency": "PLN",
            "status": "draft",
        },
    )
    assert request_outside_project_range.status_code == 422
    assert "within project month range" in request_outside_project_range.json()["detail"]

    wrong_project_scope_rate = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": str(uuid.uuid4()),
                    "rate_unit": "day",
                    "rate_value": "100.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": None,
                }
            ]
        },
    )
    assert wrong_project_scope_rate.status_code == 422
    assert "current project id" in wrong_project_scope_rate.json()["detail"]

    duplicate_rate_key_payload = client.put(
        f"/api/v1/projects/{project_id}/rates/entries/bulk",
        headers=headers,
        json={
            "entries": [
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "100.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": "2026-01-01",
                },
                {
                    "performer_id": performer_a,
                    "project_id": None,
                    "rate_unit": "day",
                    "rate_value": "120.00",
                    "effective_from_month": "2026-01-01",
                    "effective_to_month": "2026-02-01",
                },
            ]
        },
    )
    assert duplicate_rate_key_payload.status_code == 422
    assert "Duplicate rate key" in duplicate_rate_key_payload.json()["detail"]
