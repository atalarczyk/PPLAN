"""Administration endpoints for business units and role assignments."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    APP_ROLE_TO_DB_ROLE,
    AppRole,
    ROLE_TYPE_TO_APP_ROLE,
    RequestUserContext,
    ensure_business_unit_exists,
    has_business_unit_access,
    require_roles,
)
from app.db.dependencies import get_db_session
from app.models.entities import BusinessUnit, RoleAssignment, User

router = APIRouter(tags=["admin"])
legacy_router = APIRouter(prefix="/admin", tags=["admin"])


class BusinessUnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    active: bool = True


class BusinessUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class RoleAssignmentCreate(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    user_display_name: str | None = Field(default=None, min_length=1, max_length=255)
    user_microsoft_oid: str = Field(min_length=1, max_length=128)
    role: AppRole
    business_unit_id: UUID | None = None
    active: bool = True


class RoleAssignmentUpdate(BaseModel):
    role: AppRole | None = None
    business_unit_id: UUID | None = None
    active: bool | None = None


def _serialize_business_unit(unit: BusinessUnit) -> dict[str, object]:
    return {
        "id": str(unit.id),
        "code": unit.code,
        "name": unit.name,
        "active": unit.active,
        "created_at": unit.created_at.isoformat(),
        "updated_at": unit.updated_at.isoformat(),
    }


def _serialize_user(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "microsoft_oid": user.microsoft_oid,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _serialize_role_assignment(assignment: RoleAssignment) -> dict[str, object]:
    return {
        "id": str(assignment.id),
        "user_id": str(assignment.user_id),
        "business_unit_id": str(assignment.business_unit_id) if assignment.business_unit_id else None,
        "role": ROLE_TYPE_TO_APP_ROLE[assignment.role].value,
        "active": assignment.active,
        "created_at": assignment.created_at.isoformat(),
        "updated_at": assignment.updated_at.isoformat(),
    }


def _ensure_assignment_scope_valid(role: AppRole, business_unit_id: UUID | None) -> None:
    if role is AppRole.SUPER_ADMIN and business_unit_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="super_admin role must not include business_unit_id.",
        )
    if role is not AppRole.SUPER_ADMIN and business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Scoped roles require business_unit_id.",
        )


def _ensure_actor_can_assign(
    actor: RequestUserContext,
    *,
    role: AppRole,
    business_unit_id: UUID | None,
) -> None:
    if role is AppRole.SUPER_ADMIN and not actor.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can assign super_admin role.",
        )

    if actor.is_super_admin:
        return

    if role is AppRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can assign super_admin role.",
        )

    if business_unit_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope permissions for this role assignment.",
        )

    allowed_roles = {AppRole.BUSINESS_UNIT_ADMIN}
    if not has_business_unit_access(
        actor,
        business_unit_id=business_unit_id,
        allowed_roles=allowed_roles,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope permissions for this role assignment.",
        )


def _resolve_or_create_user(
    db: Session,
    *,
    email: str,
    microsoft_oid: str,
    display_name: str,
) -> User:
    normalized_email = email.strip().lower()
    normalized_oid = microsoft_oid.strip()
    now = datetime.utcnow()

    user = db.scalar(
        select(User).where(
            and_(User.email == normalized_email, User.microsoft_oid == normalized_oid)
        )
    )
    if user is not None:
        if user.display_name != display_name:
            user.display_name = display_name
            user.updated_at = now
            db.flush()
        return user

    user_by_email = db.scalar(select(User).where(User.email == normalized_email))
    if user_by_email is not None and user_by_email.microsoft_oid != normalized_oid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists with different microsoft_oid.",
        )

    user_by_oid = db.scalar(select(User).where(User.microsoft_oid == normalized_oid))
    if user_by_oid is not None and user_by_oid.email != normalized_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this microsoft_oid already exists with different email.",
        )

    if user_by_email is not None:
        user_by_email.display_name = display_name
        user_by_email.updated_at = now
        db.flush()
        return user_by_email

    if user_by_oid is not None:
        user_by_oid.email = normalized_email
        user_by_oid.display_name = display_name
        user_by_oid.updated_at = now
        db.flush()
        return user_by_oid

    user = User(
        email=normalized_email,
        microsoft_oid=normalized_oid,
        display_name=display_name,
        status="active",
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    return user


def _validate_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_email must be a valid email address.",
        )
    return normalized


@router.get("/business-units")
def list_business_units(
    context: RequestUserContext = Depends(
        require_roles(AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN)
    ),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    """List business units for authorized admin roles."""

    units = db.scalars(select(BusinessUnit).order_by(BusinessUnit.code.asc())).all()
    if context.is_super_admin:
        return {"items": [_serialize_business_unit(unit) for unit in units]}

    scoped = [unit for unit in units if unit.id in context.business_unit_ids]
    return {"items": [_serialize_business_unit(unit) for unit in scoped]}


@router.post("/business-units", status_code=status.HTTP_201_CREATED)
def create_business_unit(
    payload: BusinessUnitCreate,
    _: RequestUserContext = Depends(require_roles(AppRole.SUPER_ADMIN)),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Create a business unit (super admin only)."""

    now = datetime.utcnow()
    unit = BusinessUnit(
        code=payload.code.strip(),
        name=payload.name.strip(),
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(unit)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Business unit code already exists.",
        ) from exc

    db.refresh(unit)
    return _serialize_business_unit(unit)


@router.patch("/business-units/{business_unit_id}")
def update_business_unit(
    business_unit_id: UUID,
    payload: BusinessUnitUpdate,
    _: RequestUserContext = Depends(require_roles(AppRole.SUPER_ADMIN)),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Update business unit mutable fields (super admin only)."""

    unit = ensure_business_unit_exists(db, business_unit_id)
    if payload.name is not None:
        unit.name = payload.name.strip()
    if payload.active is not None:
        unit.active = payload.active
    unit.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(unit)
    return _serialize_business_unit(unit)


@router.get("/users")
def list_users(
    business_unit_id: UUID | None = None,
    context: RequestUserContext = Depends(
        require_roles(AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN)
    ),
    db: Session = Depends(get_db_session),
) -> dict[str, list[object]]:
    """List users with role assignments (global for super admin, scoped for BU admin)."""

    if business_unit_id is not None and not context.is_super_admin:
        if not has_business_unit_access(
            context,
            business_unit_id=business_unit_id,
            allowed_roles={AppRole.BUSINESS_UNIT_ADMIN},
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope permissions to list users for this business unit.",
            )

    assignments = db.scalars(
        select(RoleAssignment).where(RoleAssignment.active.is_(True)).order_by(RoleAssignment.created_at.asc())
    ).all()

    visible_assignments: list[RoleAssignment] = []
    for assignment in assignments:
        assignment_role = ROLE_TYPE_TO_APP_ROLE[assignment.role]
        if context.is_super_admin:
            if business_unit_id is None or assignment.business_unit_id == business_unit_id:
                visible_assignments.append(assignment)
            continue

        if assignment_role is AppRole.SUPER_ADMIN:
            continue

        if assignment.business_unit_id is None:
            continue

        if assignment.business_unit_id in context.business_unit_ids:
            if business_unit_id is None or assignment.business_unit_id == business_unit_id:
                visible_assignments.append(assignment)

    if not visible_assignments:
        return {"items": []}

    user_ids = sorted({assignment.user_id for assignment in visible_assignments}, key=str)
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    users_by_id = {user.id: user for user in users}

    items = []
    assignments_by_user: dict[UUID, list[dict[str, object]]] = {}
    for assignment in visible_assignments:
        assignments_by_user.setdefault(assignment.user_id, []).append(_serialize_role_assignment(assignment))

    for user_id in user_ids:
        user = users_by_id.get(user_id)
        if user is None:
            continue
        user_payload = _serialize_user(user)
        user_payload["role_assignments"] = assignments_by_user.get(user_id, [])
        items.append(user_payload)

    return {"items": items}


@router.post("/users/role-assignments", status_code=status.HTTP_201_CREATED)
def create_role_assignment(
    payload: RoleAssignmentCreate,
    context: RequestUserContext = Depends(
        require_roles(AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN)
    ),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Create role assignment and upsert user account for first-time assignment."""

    user_email = _validate_email(payload.user_email)
    _ensure_assignment_scope_valid(payload.role, payload.business_unit_id)
    _ensure_actor_can_assign(
        context,
        role=payload.role,
        business_unit_id=payload.business_unit_id,
    )

    if payload.business_unit_id is not None:
        ensure_business_unit_exists(db, payload.business_unit_id)

    user_display_name = payload.user_display_name.strip() if payload.user_display_name else payload.user_email
    user = _resolve_or_create_user(
        db,
        email=user_email,
        microsoft_oid=payload.user_microsoft_oid,
        display_name=user_display_name,
    )

    now = datetime.utcnow()
    assignment = RoleAssignment(
        user_id=user.id,
        business_unit_id=payload.business_unit_id,
        role=APP_ROLE_TO_DB_ROLE[payload.role],
        active=payload.active,
        created_at=now,
        updated_at=now,
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role assignment already exists or violates assignment constraints.",
        ) from exc

    db.refresh(assignment)
    return _serialize_role_assignment(assignment)


@router.patch("/users/role-assignments/{assignment_id}")
def update_role_assignment(
    assignment_id: UUID,
    payload: RoleAssignmentUpdate,
    context: RequestUserContext = Depends(
        require_roles(AppRole.SUPER_ADMIN, AppRole.BUSINESS_UNIT_ADMIN)
    ),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Update role assignment scope/role/activity with RBAC checks."""

    assignment = db.scalar(select(RoleAssignment).where(RoleAssignment.id == assignment_id))
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found.")

    if not context.is_super_admin:
        if assignment.business_unit_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope permissions for this role assignment.",
            )
        if not has_business_unit_access(
            context,
            business_unit_id=assignment.business_unit_id,
            allowed_roles={AppRole.BUSINESS_UNIT_ADMIN},
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope permissions for this role assignment.",
            )

    current_role = ROLE_TYPE_TO_APP_ROLE[assignment.role]
    target_role = payload.role or current_role
    target_business_unit_id = payload.business_unit_id
    if "business_unit_id" not in payload.model_fields_set:
        target_business_unit_id = assignment.business_unit_id

    _ensure_assignment_scope_valid(target_role, target_business_unit_id)

    # Actor must be allowed to manage assignment in current and target scopes.
    _ensure_actor_can_assign(
        context,
        role=current_role,
        business_unit_id=assignment.business_unit_id,
    )
    _ensure_actor_can_assign(
        context,
        role=target_role,
        business_unit_id=target_business_unit_id,
    )

    if target_business_unit_id is not None:
        ensure_business_unit_exists(db, target_business_unit_id)

    assignment.role = APP_ROLE_TO_DB_ROLE[target_role]
    assignment.business_unit_id = target_business_unit_id
    if payload.active is not None:
        assignment.active = payload.active
    assignment.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role assignment already exists or violates assignment constraints.",
        ) from exc

    db.refresh(assignment)
    return _serialize_role_assignment(assignment)


legacy_router.include_router(router)

