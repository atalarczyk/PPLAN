from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import APP_ROLE_TO_DB_ROLE, AppRole, ensure_user_principal
from app.models.entities import BusinessUnit, RoleAssignment


def _create_business_unit(db: Session, *, code: str, name: str) -> BusinessUnit:
    now = datetime.utcnow()
    unit = BusinessUnit(code=code, name=name, active=True, created_at=now, updated_at=now)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def _assign_role(
    db: Session,
    *,
    oid: str,
    email: str,
    display_name: str,
    role: AppRole,
    business_unit_id: uuid.UUID | None,
    active: bool = True,
) -> RoleAssignment:
    user = ensure_user_principal(db, microsoft_oid=oid, email=email, display_name=display_name)
    now = datetime.utcnow()
    assignment = RoleAssignment(
        user_id=user.id,
        business_unit_id=business_unit_id,
        role=APP_ROLE_TO_DB_ROLE[role],
        active=active,
        created_at=now,
        updated_at=now,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _headers(oid: str, email: str, display_name: str) -> dict[str, str]:
    return {
        "X-MS-OID": oid,
        "X-MS-EMAIL": email,
        "X-MS-DISPLAY-NAME": display_name,
    }


def test_me_and_access_context_for_unassigned_user(client: TestClient) -> None:
    headers = _headers("oid-new-user", "new.user@test.local", "New User")

    me_response = client.get("/api/v1/me", headers=headers)
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["email"] == "new.user@test.local"
    assert me_payload["roles"] == []

    access_response = client.get("/api/v1/access/context", headers=headers)
    assert access_response.status_code == 200
    access_payload = access_response.json()
    assert access_payload["has_access"] is False
    assert access_payload["roles"] == []
    assert access_payload["business_units"] == []


def test_access_context_exposes_scoped_roles(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-A", name="Business Unit A")
    _assign_role(
        db_session,
        oid="oid-editor",
        email="editor@test.local",
        display_name="Editor",
        role=AppRole.EDITOR,
        business_unit_id=unit.id,
    )

    response = client.get(
        "/api/v1/access/context",
        headers=_headers("oid-editor", "editor@test.local", "Editor"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_access"] is True
    assert payload["roles"] == ["editor"]
    assert payload["business_units"] == [str(unit.id)]


def test_me_endpoint_exposes_business_unit_admin_role_name(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-ME", name="Me Scope")
    _assign_role(
        db_session,
        oid="oid-bu-me",
        email="bu.me@test.local",
        display_name="BU Me",
        role=AppRole.BUSINESS_UNIT_ADMIN,
        business_unit_id=unit.id,
    )

    response = client.get(
        "/api/v1/me",
        headers=_headers("oid-bu-me", "bu.me@test.local", "BU Me"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == [
        {
            "role": "business_unit_admin",
            "business_unit_id": str(unit.id),
        }
    ]


def test_business_unit_admin_cannot_create_business_unit(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-ADM", name="Admin Scope")
    _assign_role(
        db_session,
        oid="oid-bu-admin",
        email="bu.admin@test.local",
        display_name="BU Admin",
        role=AppRole.BUSINESS_UNIT_ADMIN,
        business_unit_id=unit.id,
    )

    response = client.post(
        "/api/v1/business-units",
        headers=_headers("oid-bu-admin", "bu.admin@test.local", "BU Admin"),
        json={"code": "BU-NO", "name": "Not Allowed", "active": True},
    )
    assert response.status_code == 403


def test_super_admin_can_create_and_update_business_unit(client: TestClient, db_session: Session) -> None:
    _assign_role(
        db_session,
        oid="oid-super",
        email="super@test.local",
        display_name="Super",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    create_response = client.post(
        "/api/v1/business-units",
        headers=_headers("oid-super", "super@test.local", "Super"),
        json={"code": "BU-NEW", "name": "New BU", "active": True},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["code"] == "BU-NEW"

    patch_response = client.patch(
        f"/api/v1/business-units/{created['id']}",
        headers=_headers("oid-super", "super@test.local", "Super"),
        json={"name": "Renamed BU", "active": False},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Renamed BU"
    assert patched["active"] is False


def test_super_admin_can_create_role_assignment_and_duplicate_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    unit = _create_business_unit(db_session, code="BU-R", name="Role Scope")
    _assign_role(
        db_session,
        oid="oid-super2",
        email="super2@test.local",
        display_name="Super 2",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    payload = {
        "user_email": "editor2@test.local",
        "user_display_name": "Editor 2",
        "user_microsoft_oid": "oid-editor2",
        "role": "editor",
        "business_unit_id": str(unit.id),
        "active": True,
    }
    create_response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super2", "super2@test.local", "Super 2"),
        json=payload,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["role"] == "editor"
    assert created["business_unit_id"] == str(unit.id)

    duplicate_response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super2", "super2@test.local", "Super 2"),
        json=payload,
    )
    assert duplicate_response.status_code == 409


def test_business_unit_admin_can_assign_only_within_owned_scope(
    client: TestClient,
    db_session: Session,
) -> None:
    owned = _create_business_unit(db_session, code="BU-OWN", name="Owned")
    foreign = _create_business_unit(db_session, code="BU-FOR", name="Foreign")

    _assign_role(
        db_session,
        oid="oid-bu-owner",
        email="owner@test.local",
        display_name="Owner Admin",
        role=AppRole.BUSINESS_UNIT_ADMIN,
        business_unit_id=owned.id,
    )

    in_scope_response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-bu-owner", "owner@test.local", "Owner Admin"),
        json={
            "user_email": "viewer.in.scope@test.local",
            "user_display_name": "Viewer In Scope",
            "user_microsoft_oid": "oid-viewer-owned",
            "role": "viewer",
            "business_unit_id": str(owned.id),
            "active": True,
        },
    )
    assert in_scope_response.status_code == 201

    out_scope_response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-bu-owner", "owner@test.local", "Owner Admin"),
        json={
            "user_email": "viewer.out.scope@test.local",
            "user_display_name": "Viewer Out Scope",
            "user_microsoft_oid": "oid-viewer-foreign",
            "role": "viewer",
            "business_unit_id": str(foreign.id),
            "active": True,
        },
    )
    assert out_scope_response.status_code == 403


def test_business_unit_admin_cannot_assign_super_admin(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-SA", name="Scope")
    _assign_role(
        db_session,
        oid="oid-bu-nosa",
        email="nosa@test.local",
        display_name="No SA",
        role=AppRole.BUSINESS_UNIT_ADMIN,
        business_unit_id=unit.id,
    )

    response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-bu-nosa", "nosa@test.local", "No SA"),
        json={
            "user_email": "target@test.local",
            "user_display_name": "Target",
            "user_microsoft_oid": "oid-target",
            "role": "super_admin",
            "business_unit_id": None,
            "active": True,
        },
    )
    assert response.status_code == 403


def test_update_role_assignment_scope_and_activity(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-UP", name="Update Scope")
    _assign_role(
        db_session,
        oid="oid-super-up",
        email="super.up@test.local",
        display_name="Super Up",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    create_response = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super-up", "super.up@test.local", "Super Up"),
        json={
            "user_email": "editor.up@test.local",
            "user_display_name": "Editor Up",
            "user_microsoft_oid": "oid-editor-up",
            "role": "editor",
            "business_unit_id": str(unit.id),
            "active": True,
        },
    )
    assignment_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/api/v1/users/role-assignments/{assignment_id}",
        headers=_headers("oid-super-up", "super.up@test.local", "Super Up"),
        json={"role": "viewer", "active": False},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["role"] == "viewer"
    assert patched["active"] is False


def test_super_admin_scope_validation_for_assignment_payload(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-SV", name="Validation Scope")
    _assign_role(
        db_session,
        oid="oid-super-sv",
        email="super.sv@test.local",
        display_name="Super Scope Validation",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    invalid_super_admin = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super-sv", "super.sv@test.local", "Super Scope Validation"),
        json={
            "user_email": "bad.super@test.local",
            "user_display_name": "Bad Super",
            "user_microsoft_oid": "oid-bad-super",
            "role": "super_admin",
            "business_unit_id": str(unit.id),
            "active": True,
        },
    )
    assert invalid_super_admin.status_code == 422

    invalid_scoped_role = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super-sv", "super.sv@test.local", "Super Scope Validation"),
        json={
            "user_email": "bad.editor@test.local",
            "user_display_name": "Bad Editor",
            "user_microsoft_oid": "oid-bad-editor",
            "role": "editor",
            "business_unit_id": None,
            "active": True,
        },
    )
    assert invalid_scoped_role.status_code == 422


def test_update_rejects_duplicate_role_assignments(client: TestClient, db_session: Session) -> None:
    unit = _create_business_unit(db_session, code="BU-DUP", name="Duplicate Scope")
    _assign_role(
        db_session,
        oid="oid-super-dup",
        email="super.dup@test.local",
        display_name="Super Duplicate",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    first = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super-dup", "super.dup@test.local", "Super Duplicate"),
        json={
            "user_email": "dup.target@test.local",
            "user_display_name": "Dup Target",
            "user_microsoft_oid": "oid-dup-target",
            "role": "editor",
            "business_unit_id": str(unit.id),
            "active": True,
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/users/role-assignments",
        headers=_headers("oid-super-dup", "super.dup@test.local", "Super Duplicate"),
        json={
            "user_email": "dup.target@test.local",
            "user_display_name": "Dup Target",
            "user_microsoft_oid": "oid-dup-target",
            "role": "viewer",
            "business_unit_id": str(unit.id),
            "active": True,
        },
    )
    assert second.status_code == 201

    second_id = second.json()["id"]
    collision = client.patch(
        f"/api/v1/users/role-assignments/{second_id}",
        headers=_headers("oid-super-dup", "super.dup@test.local", "Super Duplicate"),
        json={"role": "editor"},
    )
    assert collision.status_code == 409


def test_list_users_filtered_by_business_unit_query(client: TestClient, db_session: Session) -> None:
    unit_a = _create_business_unit(db_session, code="BU-QA", name="Query A")
    unit_b = _create_business_unit(db_session, code="BU-QB", name="Query B")
    _assign_role(
        db_session,
        oid="oid-super-query",
        email="super.query@test.local",
        display_name="Super Query",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )
    _assign_role(
        db_session,
        oid="oid-user-a",
        email="user.a@test.local",
        display_name="User A",
        role=AppRole.VIEWER,
        business_unit_id=unit_a.id,
    )
    _assign_role(
        db_session,
        oid="oid-user-b",
        email="user.b@test.local",
        display_name="User B",
        role=AppRole.VIEWER,
        business_unit_id=unit_b.id,
    )

    response = client.get(
        f"/api/v1/users?business_unit_id={unit_a.id}",
        headers=_headers("oid-super-query", "super.query@test.local", "Super Query"),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    emails = {item["email"] for item in items}
    assert "user.a@test.local" in emails
    assert "user.b@test.local" not in emails


def test_users_list_is_scoped_for_business_unit_admin(client: TestClient, db_session: Session) -> None:
    unit_a = _create_business_unit(db_session, code="BU-LA", name="List A")
    unit_b = _create_business_unit(db_session, code="BU-LB", name="List B")

    _assign_role(
        db_session,
        oid="oid-bu-list",
        email="bu.list@test.local",
        display_name="BU List",
        role=AppRole.BUSINESS_UNIT_ADMIN,
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
    _assign_role(
        db_session,
        oid="oid-viewer-b",
        email="viewer.b@test.local",
        display_name="Viewer B",
        role=AppRole.VIEWER,
        business_unit_id=unit_b.id,
    )

    response = client.get(
        "/api/v1/users",
        headers=_headers("oid-bu-list", "bu.list@test.local", "BU List"),
    )
    assert response.status_code == 200
    payload = response.json()
    emails = {item["email"] for item in payload["items"]}
    assert "viewer.a@test.local" in emails
    assert "viewer.b@test.local" not in emails


def test_legacy_admin_routes_still_work(client: TestClient, db_session: Session) -> None:
    _assign_role(
        db_session,
        oid="oid-super-legacy",
        email="legacy@test.local",
        display_name="Legacy",
        role=AppRole.SUPER_ADMIN,
        business_unit_id=None,
    )

    response = client.post(
        "/api/v1/admin/business-units",
        headers=_headers("oid-super-legacy", "legacy@test.local", "Legacy"),
        json={"code": "BU-LGC", "name": "Legacy Path", "active": True},
    )
    assert response.status_code == 201
    assert response.json()["code"] == "BU-LGC"
